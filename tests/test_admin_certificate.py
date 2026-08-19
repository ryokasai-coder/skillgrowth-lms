"""管理画面からの修了証ダウンロード（admin_download_certificate）の回帰テスト。

- skillgrowth 管理者は、修了した受講者の修了証PDFを取得できる。
- 未修了の受講者では発行されない（レポートへリダイレクト）。
- 一般受講者(employee)は管理者ルートにアクセスできない。
"""
from datetime import datetime

from conftest import login
from app import (app as flask_app, db, Course, Lesson, User, Enrollment)
from werkzeug.security import generate_password_hash


def _seed_admin_and_completed():
    with flask_app.app_context():
        admin = User(username='admin', email='admin@a.com',
                     password_hash=generate_password_hash('adminpass'),
                     role='skillgrowth', full_name='管理者')
        emp = User(username='emp', email='emp@a.com',
                   password_hash=generate_password_hash('pass1234'),
                   role='employee', full_name='修了太郎',
                   employee_id='E1', department='営業部')
        c = Course(title='修了テストコース', category='研修',
                   training_type='eラーニング', total_hours=1.0, is_published=True)
        db.session.add_all([admin, emp, c])
        db.session.flush()
        db.session.add(Lesson(course_id=c.id, title='L1', content='x', order=1))
        enr = Enrollment(user_id=emp.id, course_id=c.id,
                         started_at=datetime(2026, 8, 1),
                         completed_at=datetime(2026, 8, 18),
                         status='completed', total_study_seconds=3600)
        db.session.add(enr)
        db.session.commit()
        return c.id, emp.id


def test_admin_can_download_completed_certificate(client):
    cid, uid = _seed_admin_and_completed()
    login(client, 'admin', 'adminpass')
    r = client.get(f'/admin/courses/{cid}/certificate/{uid}')
    assert r.status_code == 200, r.data
    assert r.data[:4] == b'%PDF'
    # 日本語フォント埋め込みでサイズが跳ねる（豆腐化＝約2KB を検知）
    assert len(r.data) > 20000


def test_admin_certificate_blocked_for_incomplete(client):
    cid, uid = _seed_admin_and_completed()
    with flask_app.app_context():
        enr = Enrollment.query.filter_by(course_id=cid, user_id=uid).first()
        enr.status = 'in_progress'
        enr.completed_at = None
        db.session.commit()
    login(client, 'admin', 'adminpass')
    r = client.get(f'/admin/courses/{cid}/certificate/{uid}')
    # PDFではなくレポートへのリダイレクト
    assert r.status_code == 302
    assert '%PDF' not in r.data.decode('latin-1')


def test_employee_cannot_use_admin_certificate_route(client):
    cid, uid = _seed_admin_and_completed()
    login(client, 'emp', 'pass1234')
    r = client.get(f'/admin/courses/{cid}/certificate/{uid}')
    assert r.status_code == 302  # dashboard へリダイレクト（管理者専用）
    assert r.data[:4] != b'%PDF'
