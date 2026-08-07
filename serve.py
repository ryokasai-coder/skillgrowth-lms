"""
本番用の起動スクリプト（waitress WSGIサーバ）。
開発時は `python app.py`、本番は `python serve.py` を使う。

環境変数:
  LMS_SECRET_KEY    セッション秘密鍵（本番では必須）
  LMS_ADMIN_PASSWORD 初期管理者パスワード（未設定時 admin123・初回変更強制）
  LMS_HTTPS=1       HTTPS配信時にCookieのSecure属性を有効化
  LMS_HOST          待受ホスト（既定 0.0.0.0）
  LMS_PORT          待受ポート（既定 8080）
"""
import os
from waitress import serve
from app import app, create_initial_data

if __name__ == '__main__':
    create_initial_data()
    host = os.environ.get('LMS_HOST', '0.0.0.0')
    port = int(os.environ.get('LMS_PORT', '8080'))
    print(f'本番サーバを起動します: http://{host}:{port}')
    serve(app, host=host, port=port)
