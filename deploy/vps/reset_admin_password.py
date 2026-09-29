"""管理者(skillgrowth ロール)のパスワードを対話入力で再設定する。

    cd /opt/skillgrowth-lms && sudo -u lms .venv/bin/python deploy/vps/reset_admin_password.py [ユーザー名]

入力はエコーされず、ログにも残らない。ログイン失敗回数・ロックも解除する。
"""
import getpass
import os
import sqlite3
import sys

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'instance', 'lms.db')


def main():
    username = sys.argv[1] if len(sys.argv) > 1 else 'admin'
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT id, role FROM user WHERE username=?", (username,)).fetchone()
    if not row or row[1] != 'skillgrowth':
        print(f'管理者ユーザー {username} が見つかりません')
        return 1
    pw1 = getpass.getpass('新しいパスワード(8文字以上): ')
    pw2 = getpass.getpass('もう一度: ')
    if pw1 != pw2:
        print('一致しません。やり直してください')
        return 1
    if len(pw1) < 8:
        print('8文字以上にしてください')
        return 1
    conn.execute(
        "UPDATE user SET password_hash=?, force_password_change=0, "
        "failed_login_count=0, lockout_until=NULL WHERE id=?",
        (generate_password_hash(pw1), row[0]))
    conn.commit()
    print(f'{username} のパスワードを更新しました')
    return 0


if __name__ == '__main__':
    sys.exit(main())
