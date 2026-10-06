"""LMS_TRUST_PROXY=1 のとき X-Forwarded-For の実クライアントIPが記録されること。"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SNIPPET = r'''
from flask import request
import app as m
@m.app.route('/__ip')
def __ip():
    return request.remote_addr or ''
c = m.app.test_client()
print(c.get('/__ip', headers={'X-Forwarded-For': '203.0.113.7'},
            environ_base={'REMOTE_ADDR': '127.0.0.1'}).get_data(as_text=True))
'''


def _remote_addr(trust_proxy, tmp_path):
    env = dict(os.environ)
    env['LMS_DATABASE_URI'] = 'sqlite:///' + (tmp_path / 'ip.db').as_posix()
    env.pop('LMS_TRUST_PROXY', None)
    if trust_proxy:
        env['LMS_TRUST_PROXY'] = '1'
    out = subprocess.run([sys.executable, '-c', SNIPPET], cwd=ROOT, env=env,
                         capture_output=True, text=True, check=True)
    return out.stdout.strip().splitlines()[-1]


def test_forwarded_ip_used_when_trusted(tmp_path):
    assert _remote_addr(True, tmp_path) == '203.0.113.7'


def test_forwarded_ip_ignored_by_default(tmp_path):
    assert _remote_addr(False, tmp_path) == '127.0.0.1'


WAITRESS_SNIPPET = r'''
import threading, time, urllib.request, socket
from flask import request
import app as m
import serve
@m.app.route('/__ip2')
def __ip2():
    return request.remote_addr or ''
from waitress import create_server
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
kw = serve.serve_kwargs(); kw.update(host='127.0.0.1', port=port)
srv = create_server(m.app, **kw)
threading.Thread(target=srv.run, daemon=True).start()
time.sleep(0.5)
req = urllib.request.Request(f'http://127.0.0.1:{port}/__ip2', headers={'X-Forwarded-For': '203.0.113.9'})
print(urllib.request.urlopen(req).read().decode())
srv.close()
'''


def test_forwarded_ip_survives_waitress(tmp_path):
    """waitress 経由でも X-Forwarded-For が捨てられず実IPが記録されること（本番VPS構成）。"""
    env = dict(os.environ)
    env['LMS_DATABASE_URI'] = 'sqlite:///' + (tmp_path / 'ip2.db').as_posix()
    env['LMS_TRUST_PROXY'] = '1'
    out = subprocess.run([sys.executable, '-c', WAITRESS_SNIPPET], cwd=ROOT, env=env,
                         capture_output=True, text=True, check=True, timeout=60)
    assert out.stdout.strip().splitlines()[-1] == '203.0.113.9'
