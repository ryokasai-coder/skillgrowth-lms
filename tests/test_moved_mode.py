"""LMS_MOVED_TO 設定時は全リクエストが新URLへ転送されること（旧サーバーの移転モード）。"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SNIPPET = r'''
import app as m
c = m.app.test_client()
for p in ['/login', '/dashboard?x=1', '/']:
    r = c.get(p)
    print(r.status_code, r.headers.get('Location'))
r = c.post('/login', data={'username': 'a', 'password': 'b'})
print(r.status_code, r.headers.get('Location'))
'''


def _run(tmp_path, moved):
    env = dict(os.environ)
    env['LMS_DATABASE_URI'] = 'sqlite:///' + (tmp_path / 'mv.db').as_posix()
    env.pop('LMS_MOVED_TO', None)
    if moved:
        env['LMS_MOVED_TO'] = moved
    out = subprocess.run([sys.executable, '-c', SNIPPET], cwd=ROOT, env=env,
                         capture_output=True, text=True, check=True)
    return out.stdout.strip().splitlines()[-4:]


def test_moved_mode_redirects_everything(tmp_path):
    lines = _run(tmp_path, 'https://lms.example.jp/')
    assert lines == [
        '302 https://lms.example.jp/login',
        '302 https://lms.example.jp/dashboard?x=1',
        '302 https://lms.example.jp/',
        '302 https://lms.example.jp/login',
    ]


def test_no_redirect_by_default(tmp_path):
    lines = _run(tmp_path, None)
    assert not any(l.startswith('302 https://lms.example.jp') for l in lines)
