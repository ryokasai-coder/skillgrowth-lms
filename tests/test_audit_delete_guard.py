"""監査対応ステップ1-3: 受講記録のあるコース/レッスン/会社は削除不可（証憑保全）。"""
import subprocess
import sys
import os

from conftest import login, set_watched
from app import (app as flask_app, db, Course, Lesson, Company, User,
                 Enrollment, StudyLog, LessonProgress)
from werkzeug.security import generate_password_hash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCKED = '受講記録があるため削除できません'


def _admin():
    with flask_app.app_context():
        db.session.add(User(username='admin', email='admin@a.com',
                            password_hash=generate_password_hash('adminpass'),
                            role='skillgrowth', full_name='管理者'))
        db.session.commit()


def _company_with_user(uid, name):
    with flask_app.app_context():
        co = Company(name=name)
        db.session.add(co)
        db.session.flush()
        db.session.get(User, uid).company_id = co.id
        db.session.commit()
        return co.id


def test_course_with_records_not_deleted(client, seed_course):
    _admin()
    cid, l1 = seed_course['course_id'], seed_course['lesson_ids'][0]
    set_watched(cid, l1, 100)  # LessonProgress あり
    login(client, 'admin', 'adminpass')
    r = client.post(f'/admin/courses/{cid}/delete', follow_redirects=True)
    assert BLOCKED in r.data.decode('utf-8')
    with flask_app.app_context():
        assert db.session.get(Course, cid) is not None
        assert LessonProgress.query.count() == 1


def test_course_with_studylog_only_not_deleted(client, seed_course):
    _admin()
    cid, uid = seed_course['course_id'], seed_course['user_id']
    with flask_app.app_context():
        db.session.add(StudyLog(user_id=uid, course_id=cid, duration_seconds=5))
        db.session.commit()
    login(client, 'admin', 'adminpass')
    client.post(f'/admin/courses/{cid}/delete')
    with flask_app.app_context():
        assert db.session.get(Course, cid) is not None


def test_course_without_records_can_be_deleted(client, seed_course):
    _admin()
    cid = seed_course['course_id']
    login(client, 'admin', 'adminpass')
    client.post(f'/admin/courses/{cid}/delete')
    with flask_app.app_context():
        assert db.session.get(Course, cid) is None


def test_lesson_with_records_not_deleted(client, seed_course):
    _admin()
    cid = seed_course['course_id']
    l1, l2 = seed_course['lesson_ids'][:2]
    set_watched(cid, l1, 100)
    login(client, 'admin', 'adminpass')
    r = client.post(f'/admin/lessons/{l1}/delete', follow_redirects=True)
    assert BLOCKED in r.data.decode('utf-8')
    client.post(f'/admin/lessons/{l2}/delete')  # 記録なしは削除可
    with flask_app.app_context():
        assert db.session.get(Lesson, l1) is not None
        assert db.session.get(Lesson, l2) is None


def test_lesson_with_studylog_not_deleted(client, seed_course):
    _admin()
    cid, uid = seed_course['course_id'], seed_course['user_id']
    l1 = seed_course['lesson_ids'][0]
    with flask_app.app_context():
        db.session.add(StudyLog(user_id=uid, course_id=cid, lesson_id=l1, duration_seconds=5))
        db.session.commit()
    login(client, 'admin', 'adminpass')
    client.post(f'/admin/lessons/{l1}/delete')
    with flask_app.app_context():
        assert db.session.get(Lesson, l1) is not None
        assert StudyLog.query.first().lesson_id == l1


def test_company_with_member_records_not_deleted(client, seed_course):
    _admin()
    cid, uid = seed_course['course_id'], seed_course['user_id']
    l1 = seed_course['lesson_ids'][0]
    co_id = _company_with_user(uid, 'A社')
    set_watched(cid, l1, 100)
    login(client, 'admin', 'adminpass')
    r = client.post(f'/admin/companies/{co_id}/delete', follow_redirects=True)
    assert BLOCKED in r.data.decode('utf-8')
    with flask_app.app_context():
        assert db.session.get(Company, co_id) is not None
        assert db.session.get(User, uid).company_id == co_id


def test_company_without_records_can_be_deleted(client, seed_course):
    _admin()
    co_id = _company_with_user(seed_course['user_id'], 'B社')
    login(client, 'admin', 'adminpass')
    client.post(f'/admin/companies/{co_id}/delete')
    with flask_app.app_context():
        assert db.session.get(Company, co_id) is None


def _run_script(name, env_extra, stdin):
    env = dict(os.environ)
    env.pop('LMS_ALLOW_DESTRUCTIVE', None)
    env.update(env_extra)
    return subprocess.run([sys.executable, os.path.join(ROOT, name)], input=stdin,
                          capture_output=True, text=True, env=env, cwd=ROOT, timeout=60)


def test_destructive_scripts_guarded(tmp_path):
    db_uri = 'sqlite:///' + str(tmp_path / 't.db').replace('\\', '/')
    for name in ('reset_test_records.py', 'fix_watch_seconds.py'):
        # 環境変数なし → 何もせず終了
        r = _run_script(name, {'LMS_DATABASE_URI': db_uri}, 'DELETE\n')
        assert r.returncode != 0
        # 環境変数あり・確認入力が違う → 終了
        r = _run_script(name, {'LMS_DATABASE_URI': db_uri, 'LMS_ALLOW_DESTRUCTIVE': '1'}, 'no\n')
        assert r.returncode != 0
    # どちらもapp読込前に終了するのでDBは作られない
    assert not (tmp_path / 't.db').exists()
