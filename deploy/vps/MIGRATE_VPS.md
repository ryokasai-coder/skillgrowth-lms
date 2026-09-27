# PythonAnywhere → Xserver VPS 移行手順

対象: https://skillgrowth.pythonanywhere.com → VPS (162.43.25.95, 既存本番システム同居)

方針
- 既存システムに触らない: 専用ユーザー `lms`、`/opt/skillgrowth-lms`、`127.0.0.1:3080` のみで待受。
- nginx は新規サイトファイルを1つ追加するだけ。必ず `nginx -t` 後に reload。ufw は触らない。
- PythonAnywhere は切替後もしばらく残す（切り戻し用）。

## 1. リハーサル（公開なし・受講者影響なし）
```bash
scp -i ~/.ssh/funlink_vps deploy/vps/setup.sh deploy/vps/import_db.sh root@162.43.25.95:/root/
ssh -i ~/.ssh/funlink_vps root@162.43.25.95 'bash /root/setup.sh 3080'
```
PythonAnywhere の Files から `lms-project/instance/lms.db` をダウンロードし:
```bash
scp -i ~/.ssh/funlink_vps lms.db root@162.43.25.95:/root/lms_from_pa.db
ssh -i ~/.ssh/funlink_vps root@162.43.25.95 'bash /root/import_db.sh /root/lms_from_pa.db'
```
確認: `ssh -i ~/.ssh/funlink_vps -N -L 3080:127.0.0.1:3080 root@162.43.25.95` → http://127.0.0.1:3080 で
ログイン・受講画面・修了証PDF(日本語)を確認。件数が PythonAnywhere と一致すること。

## 2. 公開
1. DNS: Xserver DNS に `<サブドメイン>` A → 162.43.25.95
2. nginx: `nginx-skillgrowth-lms.conf` の LMS_DOMAIN を置換し sites-available に配置 → sites-enabled に symlink → `nginx -t && systemctl reload nginx`
3. SSL: `certbot --nginx -d <ドメイン>`

## 3. 本番切替（受講のない時間帯）
1. 受講者への告知前、または利用の無い時間帯に実施
2. PythonAnywhere の最新 `lms.db` を再ダウンロード → `import_db.sh` で再投入（リハーサル分は .bak に退避される）
3. 件数突合・ログイン確認
4. 受講者/企業担当者へ新URLを案内（送信前に文面確認）
5. PythonAnywhere は延命をやめ自然停止に任せる（すぐには削除しない）

## 運用
- 更新: `sudo -u lms git -C /opt/skillgrowth-lms pull --ff-only && systemctl restart skillgrowth-lms`（DB変更時は migrate.py）
- バックアップ: systemd timer `skillgrowth-lms-backup.timer` が毎日 03:30 に `backups/` へ（5年保持）
- ログ: `journalctl -u skillgrowth-lms -n 100`
- CLI スクリプト実行: `cd /opt/skillgrowth-lms && sudo -u lms env $(cat /etc/skillgrowth-lms.env | xargs) .venv/bin/python xxx.py`
