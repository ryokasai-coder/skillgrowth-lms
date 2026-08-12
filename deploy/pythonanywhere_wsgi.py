# =====================================================================
# PythonAnywhere 用 WSGI 設定テンプレート
# ---------------------------------------------------------------------
# これをそのまま PythonAnywhere の「Web」タブにある WSGI 設定ファイル
#   /var/www/<ユーザー名>_pythonanywhere_com_wsgi.py
# の中身として貼り付け、下記 3 か所を自分の値に書き換えてください。
#   1) USERNAME      … PythonAnywhere のユーザー名
#   2) SECRET_KEY    … 固定の秘密鍵（`python -c "import secrets;print(secrets.token_hex(32))"`）
#   3) JP_FONT_PATH  … 日本語フォントの絶対パス（DEPLOY手順で pip install したもの）
# =====================================================================
import os
import sys

USERNAME = 'USERNAME'  # ← 自分のPythonAnywhereユーザー名に変更
PROJECT_DIR = f'/home/{USERNAME}/lms-project'

# --- 環境変数（アプリ設定）---
os.environ['LMS_SECRET_KEY'] = 'ここに固定の秘密鍵を貼る'          # ← 変更必須
os.environ['LMS_HTTPS'] = '1'                                       # HTTPS配信のためCookie Secure有効化
os.environ['LMS_DATABASE_URI'] = f'sqlite:////home/{USERNAME}/lms-project/instance/lms.db'
# 日本語PDF用フォント（DEPLOY手順でpip installした ipaexg.ttf の絶対パス）
os.environ['LMS_JP_FONT_PATH'] = f'/home/{USERNAME}/.virtualenvs/lms-venv/lib/python3.10/site-packages/japanize_matplotlib/data/ipaexg.ttf'
# 本番なので FLASK_DEBUG は設定しない（初期パスワードのヒントも非表示になる）

# --- プロジェクトを import パスに追加 ---
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# --- Flask アプリを WSGI アプリとして公開 ---
from app import app as application  # noqa: E402
