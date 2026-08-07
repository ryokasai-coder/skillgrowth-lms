"""機能強化（ログイン試行制限・進捗率%保存・MFA）の回帰テスト。"""
import pyotp

from conftest import login
from app import (app as flask_app, db, User, Enrollment)
from werkzeug.security import generate_password_hash


def _make_user(username='u1', password='pass1234', **kw):
    with flask_app.app_context():
        u = User(username=username, email=f'{username}@a.com',
                 password_hash=generate_password_hash(password),
                 role='employee', full_name='テスト', **kw)
        db.session.add(u)
        db.session.commit()
        return u.id


# ---------- ログイン試行回数制限 ----------

def test_account_locks_after_max_attempts(client):
    _make_user('locky', 'correct-pass')
    for _ in range(5):  # MAX_LOGIN_ATTEMPTS 回失敗
        client.post('/login', data={'username': 'locky', 'password': 'wrong'})
    with flask_app.app_context():
        u = User.query.filter_by(username='locky').first()
        assert u.lockout_until is not None  # ロックされた
    # 正しいパスワードでもロック中は拒否
    r = client.post('/login', data={'username': 'locky', 'password': 'correct-pass'},
                    follow_redirects=True)
    assert 'ログイン試行回数の上限' in r.get_data(as_text=True)


def test_successful_login_resets_failed_count(client):
    _make_user('resetme', 'correct-pass')
    for _ in range(3):
        client.post('/login', data={'username': 'resetme', 'password': 'wrong'})
    client.post('/login', data={'username': 'resetme', 'password': 'correct-pass'})
    with flask_app.app_context():
        u = User.query.filter_by(username='resetme').first()
        assert (u.failed_login_count or 0) == 0
        assert u.lockout_until is None


# ---------- 進捗率%のDB保存 ----------

def test_progress_percent_persisted(client, seed_course):
    cid = seed_course['course_id']
    l1, l2 = seed_course['lesson_ids'][0], seed_course['lesson_ids'][1]
    login(client)
    client.post(f'/courses/{cid}/lessons/{l1}/complete', json={'watch_seconds': 0})
    with flask_app.app_context():
        enr = Enrollment.query.filter_by(course_id=cid).first()
        assert enr.progress_percent == 33  # 1/3
    client.post(f'/courses/{cid}/lessons/{l2}/complete', json={'watch_seconds': 0})
    with flask_app.app_context():
        enr = Enrollment.query.filter_by(course_id=cid).first()
        assert enr.progress_percent == 66  # 2/3


# ---------- MFA（TOTP） ----------

def test_login_with_mfa_requires_second_factor(client):
    secret = pyotp.random_base32()
    _make_user('mfauser', 'pass1234', mfa_enabled=True, mfa_secret=secret)
    # パスワードだけでは本認証されず、MFA検証画面へ遷移
    r = client.post('/login', data={'username': 'mfauser', 'password': 'pass1234'})
    assert r.status_code == 302 and '/mfa/verify' in r.headers['Location']
    # 誤コードは拒否
    bad = client.post('/mfa/verify', data={'code': '000000'}, follow_redirects=True)
    assert '認証コードが正しくありません' in bad.get_data(as_text=True)
    # 正しいTOTPコードで本認証成立
    code = pyotp.TOTP(secret).now()
    ok = client.post('/mfa/verify', data={'code': code}, follow_redirects=True)
    body = ok.get_data(as_text=True)
    assert 'ダッシュボード' in body or 'ログアウト' in body


def test_mfa_setup_enable_and_disable(client):
    _make_user('setupper', 'pass1234')
    login(client, 'setupper', 'pass1234')
    # GETでシークレットがセッションに入る
    client.get('/mfa/setup')
    with client.session_transaction() as sess:
        secret = sess['mfa_setup_secret']
    # 正しいコードで有効化
    code = pyotp.TOTP(secret).now()
    client.post('/mfa/setup', data={'code': code})
    with flask_app.app_context():
        u = User.query.filter_by(username='setupper').first()
        assert u.mfa_enabled is True and u.mfa_secret == secret
    # 無効化
    client.post('/mfa/disable')
    with flask_app.app_context():
        u = User.query.filter_by(username='setupper').first()
        assert u.mfa_enabled is False and u.mfa_secret is None
