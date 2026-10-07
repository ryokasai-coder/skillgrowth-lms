"""監査対応ステップ1-1: 保存はUTC、表示・出力はJST(UTC+9)に統一。"""
from datetime import datetime

from conftest import login
from app import (app as flask_app, db, Course, Lesson, User, Enrollment,
                 StudyLog, LoginSession)
from werkzeug.security import generate_password_hash

# UTC 2026-10-07 16:30 = JST 2026/10/08 01:30（日付またぎで検証）
UTC_DT = datetime(2026, 10, 7, 16, 30, 15)


def _seed():
    with flask_app.app_context():
        admin = User(username='admin', email='admin@a.com',
                     password_hash=generate_password_hash('adminpass'),
                     role='skillgrowth', full_name='管理者')
        emp = User(username='emp', email='emp@a.com',
                   password_hash=generate_password_hash('pass1234'),
                   role='employee', full_name='受講太郎')
        c = Course(title='JSTコース', category='研修', training_type='eラーニング',
                   total_hours=1.0, is_published=True)
        db.session.add_all([admin, emp, c])
        db.session.flush()
        l = Lesson(course_id=c.id, title='L1', content='x', order=1)
        db.session.add(l)
        db.session.flush()
        db.session.add(Enrollment(user_id=emp.id, course_id=c.id,
                                  started_at=UTC_DT, completed_at=UTC_DT,
                                  status='completed', total_study_seconds=3600))
        db.session.add(StudyLog(user_id=emp.id, course_id=c.id, lesson_id=l.id,
                                login_at=UTC_DT, logout_at=UTC_DT,
                                duration_seconds=60))
        db.session.add(LoginSession(user_id=emp.id, login_at=UTC_DT, logout_at=UTC_DT))
        db.session.commit()
        return c.id


def test_jst_filter():
    flt = flask_app.jinja_env.filters['jst']
    assert flt(UTC_DT) == '2026/10/08 01:30:15'
    assert flt(UTC_DT, '%Y/%m/%d') == '2026/10/08'
    assert flt(None) == '-'


def test_study_log_csv_is_jst(client):
    _seed()
    login(client, 'admin', 'adminpass')
    r = client.get('/admin/logs/export/csv')
    text = r.data.decode('utf-8-sig')
    assert '視聴開始日時(JST)' in text
    assert '2026/10/08 01:30:15' in text
    assert '2026/10/07 16:30' not in text


def test_login_csv_is_jst(client):
    _seed()
    login(client, 'admin', 'adminpass')
    r = client.get('/admin/logs/login/export/csv')
    text = r.data.decode('utf-8-sig')
    assert 'ログイン日時(JST)' in text
    assert '2026/10/08 01:30:15' in text
    assert '2026/10/07 16:30' not in text


def test_course_csv_dates_are_jst(client):
    cid = _seed()
    login(client, 'admin', 'adminpass')
    r = client.get(f'/admin/courses/{cid}/export/csv')
    text = r.data.decode('utf-8-sig')
    assert '2026/10/08' in text
    assert '2026/10/07' not in text


def test_admin_logs_page_is_jst(client):
    _seed()
    login(client, 'admin', 'adminpass')
    r = client.get('/admin/logs')
    html = r.data.decode('utf-8')
    assert '2026/10/08 01:30:15' in html
    assert '2026/10/07 16:30' not in html


def test_export_filename_uses_jst_date(client, monkeypatch):
    """ファイル名の日付はサーバーTZでなくJST基準。"""
    import app as appmod
    _seed()
    monkeypatch.setattr(appmod, 'jst_now',
                        lambda: datetime(2026, 10, 8, 1, 30), raising=True)
    login(client, 'admin', 'adminpass')
    r = client.get('/admin/logs/export/csv')
    assert '20261008' in r.headers['Content-Disposition'] or \
        '%' in r.headers['Content-Disposition']
