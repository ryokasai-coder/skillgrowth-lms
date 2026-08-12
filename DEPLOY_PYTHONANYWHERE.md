# PythonAnywhere へのデプロイ手順（無料プランでインターネット公開）

Flask製の本LMSを、無料で・データを永続保持したままインターネット公開する手順。
公開URLは `https://<ユーザー名>.pythonanywhere.com` になる（HTTPS込み）。

> ⚠️ 注意: 無料プランはサーバが海外・3か月ごとに延長操作が必要・低トラフィック向け。
> 助成金の「本番の証憑保管」として長期運用する場合は、国内VPS等への移行を推奨
> （その際はSQLiteファイルをコピーするだけで移行できる）。

---

## 事前準備（あなたの操作）
1. https://www.pythonanywhere.com/ で **無料アカウント（Beginner）** を作成。
2. 固定の秘密鍵を手元で1つ生成しておく（後でWSGIに貼る）:
   ```
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

---

## 手順

### 1. コードを配置（Bashコンソール）
PythonAnywhere の **「Consoles」→「Bash」** を開いて：
```bash
cd ~
git clone https://github.com/ryokasai-coder/skillgrowth-lms.git lms-project
cd lms-project
```

### 2. 仮想環境を作成して依存をインストール
```bash
python3.10 -m venv ~/.virtualenvs/lms-venv
source ~/.virtualenvs/lms-venv/bin/activate
pip install -r requirements.txt
# 日本語PDF用フォント（IPAexゴシック。証明書PDFの文字化け防止）
pip install japanize-matplotlib
```
> フォントの絶対パスを確認（WSGIに貼る）:
> ```bash
> python -c "import japanize_matplotlib, os; print(os.path.join(os.path.dirname(japanize_matplotlib.__file__),'data','ipaexg.ttf'))"
> ```

### 3. データベースを初期化
```bash
mkdir -p ~/lms-project/instance
export LMS_DATABASE_URI="sqlite:////home/$USER/lms-project/instance/lms.db"
python migrate.py          # テーブル作成＆列追加（冪等）
python -c "from app import create_initial_data; create_initial_data()"   # 管理者admin作成
```

### 4. Webアプリを設定（Webタブ）
1. 上部メニュー **「Web」→「Add a new web app」**。
2. フレームワークは **「Manual configuration」**、Pythonは **3.10** を選択。
3. **Virtualenv** 欄に `/home/<ユーザー名>/.virtualenvs/lms-venv` を設定。
4. **WSGI configuration file** のリンクを開き、中身を全削除して
   `deploy/pythonanywhere_wsgi.py`（本リポジトリ内）の内容を貼り付け、
   ファイル冒頭の **USERNAME・秘密鍵・フォントパス** を自分の値に書き換えて保存。
5. 「Web」タブ上部の緑の **「Reload」** ボタンを押す。

### 5. 動作確認
`https://<ユーザー名>.pythonanywhere.com` を開く。
- ログイン画面が出る（初期パスワードのヒントは本番では非表示）。
- `admin` / `admin123` でログイン → **初回パスワード変更を必ず実施**。
- 証明書PDFを1つ出力し、日本語が正しく表示されるか確認（フォント設定の検証）。

### 6. 自動バックアップ（Tasksタブ）
1. **「Tasks」** タブで日次タスクを1つ作成（例: 02:00 UTC）。
2. コマンドに以下を設定：
   ```
   source /home/<ユーザー名>/.virtualenvs/lms-venv/bin/activate && cd /home/<ユーザー名>/lms-project && LMS_DATABASE_URI="sqlite:////home/<ユーザー名>/lms-project/instance/lms.db" python backup.py
   ```
   → `backups/` にDBスナップショットとCSVが日次生成される。
   > 無料枠ではサーバ上に保存されるため、**定期的にWebのFilesタブから
   > `backups/` をダウンロード**してオフサイト保管することを推奨。

---

## 更新のデプロイ（コード変更を反映する）
```bash
cd ~/lms-project && git pull
source ~/.virtualenvs/lms-venv/bin/activate && pip install -r requirements.txt
python migrate.py          # 列追加があった場合のみ効く（冪等）
```
→ そのあと「Web」タブで **Reload**。

## 補足
- **無料枠の延長**: 「Web」タブに3か月ごとに「Run until 3 months from today」ボタンが出るので押す。
- **独自ドメイン**: 無料プランでは不可（有料プランで対応）。
- **国内VPSへ移す場合**: `instance/lms.db` をコピーして移すだけ。DB接続は
  `LMS_DATABASE_URI` で切替できるため、PostgreSQL移行も同様に容易。
