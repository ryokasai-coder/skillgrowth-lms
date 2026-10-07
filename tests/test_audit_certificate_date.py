"""監査対応ステップ1-5: 修了証の発行日・修了日は「修了日時(JST)」に固定（再発行しても変わらない）。"""
from datetime import datetime

import app as appmod
from conftest import login
from app import (app as flask_app, db, Course, Lesson, User, Enrollment,
                 LessonProgress)
from werkzeug.security import generate_password_hash

# UTC 2026-10-07 16:30 = JST 2026-10-08 01:30
DONE_UTC = datetime(2026, 10, 7, 16, 30)
EXPECTED = '2026年10月08日'


def _seed():
    with flask_app.app_context():
        emp = User(username='emp', email='emp@a.com',
                   password_hash=generate_password_hash('pass1234'),
                   role='employee', full_name='修了太郎')
        c = Course(title='修了コース', category='研修', training_type='eラーニング',
                   total_hours=1.0, is_published=True)
        db.session.add_all([emp, c])
        db.session.flush()
        l = Lesson(course_id=c.id, title='L1', content='x', order=1)
        db.session.add(l)
        db.session.flush()
        enr = Enrollment(user_id=emp.id, course_id=c.id, started_at=DONE_UTC,
                         completed_at=DONE_UTC, status='completed',
                         total_study_seconds=3600)
        db.session.add(enr)
        db.session.flush()
        db.session.add(LessonProgress(enrollment_id=enr.id, lesson_id=l.id,
                                      is_completed=True, completed_at=DONE_UTC))
        db.session.commit()
        return c.id, l.id


def _capture(monkeypatch):
    got = []
    real = appmod._build_certificate_canvas

    def spy(*a, **kw):
        got.append(kw['completed_str'])
        return real(*a, **kw)
    monkeypatch.setattr(appmod, '_build_certificate_canvas', spy)
    return got


def _fake_now(monkeypatch, y, m, d):
    monkeypatch.setattr(appmod, 'jst_now', lambda: datetime(y, m, d, 9, 0, tzinfo=appmod.JST))


def test_course_certificate_date_fixed(client, monkeypatch):
    cid, _ = _seed()
    got = _capture(monkeypatch)
    login(client)
    _fake_now(monkeypatch, 2026, 11, 1)
    assert client.get(f'/courses/{cid}/course_certificate').status_code == 200
    _fake_now(monkeypatch, 2026, 12, 25)
    assert client.get(f'/courses/{cid}/course_certificate').status_code == 200
    assert got == [EXPECTED, EXPECTED]


def test_lesson_certificate_date_fixed(client, monkeypatch):
    cid, lid = _seed()
    got = _capture(monkeypatch)
    login(client)
    for day in (1, 20):
        _fake_now(monkeypatch, 2026, 11, day)
        r = client.get(f'/courses/{cid}/lessons/{lid}/certificate')
        assert r.status_code == 200, r.data
    assert got == [EXPECTED, EXPECTED]


def test_curriculum_certificate_date_fixed(client, monkeypatch):
    cid, _ = _seed()
    got = _capture(monkeypatch)
    login(client)
    for day in (1, 20):
        _fake_now(monkeypatch, 2026, 11, day)
        r = client.get(f'/courses/{cid}/curriculum_certificate')
        assert r.status_code == 200, r.data
    assert got == [EXPECTED, EXPECTED]


def test_full_certificate_issue_date_fixed(client, monkeypatch):
    """訓練修了証PDF（reportlab Platypus）の「発行日」「受講期間」も修了日時(JST)固定。"""
    cid, _ = _seed()
    texts = []
    real_p = appmod.Paragraph

    def spy_p(text, *a, **kw):
        texts.append(text)
        return real_p(text, *a, **kw)
    monkeypatch.setattr(appmod, 'Paragraph', spy_p)
    login(client)
    for day in (1, 20):
        _fake_now(monkeypatch, 2026, 11, day)
        assert client.get(f'/courses/{cid}/certificate').status_code == 200
    issued = [t for t in texts if t.startswith('発行日')]
    assert issued == [f'発行日: {EXPECTED}', f'発行日: {EXPECTED}']
    assert any('2026年10月08日 ～ 2026年10月08日' in t for t in texts)
