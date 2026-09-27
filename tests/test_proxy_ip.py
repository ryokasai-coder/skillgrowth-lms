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
