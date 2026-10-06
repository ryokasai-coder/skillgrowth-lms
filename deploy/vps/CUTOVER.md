# 本番切替の段取り（PythonAnywhere → https://lms.skillgrowth.jp）

所要: 約15分。受講のない時間帯（夜間・休日）に実施する。

## 0. 事前（いつでも）
- [ ] `https://lms.skillgrowth.jp/login` が表示される（DNS反映＋certbot済）
- [ ] VPSの日次バックアップが動いている（`ls /opt/skillgrowth-lms/backups`）
- [ ] 受講者・企業担当者への案内文を確定（下の下書き）

## 1. 旧サイトの最終データを取得（Claude / Chrome）
1. PythonAnywhere(skillgrowth) にログイン（本人）
2. Files → `lms-project/instance/lms.db` をダウンロード
3. ローカルで `PRAGMA integrity_check` と主要テーブル件数を記録

## 2. 旧サイトを「移転モード」にする（以後、旧サイトに記録が残らない）
1. Bash コンソールで `cd ~/lms-project && git pull`
2. Web タブ → WSGI 設定に `os.environ['LMS_MOVED_TO'] = 'https://lms.skillgrowth.jp'` を追加
3. Reload → 旧URLを開くと新URLへ転送されることを確認
   ※ 手順1のDLと手順2の間に受講が入ると取りこぼすため、続けて行う

## 3. VPSへ取り込み（Claude）
```
scp lms.db root@162.43.25.95:/root/lms_from_pa.db
ssh root@162.43.25.95 'bash /opt/skillgrowth-lms/deploy/vps/import_db.sh /root/lms_from_pa.db && rm /root/lms_from_pa.db'
```
- [ ] 件数が手順1の記録と一致
- [ ] ローカルのDBコピーを削除

## 4. 管理者パスワードの再設定（本人・ターミナルに直接）
取り込みで旧DBのパスワードに戻るため、`reset_admin_password.py` を再実行する。

## 5. 動作確認
- [ ] admin でログイン → ログイン証跡のIPが 127.0.0.1 ではなく実IP
- [ ] 受講者1名分の画面・修了証PDF（日本語）を確認

## 6. 案内（送信は本人・送信前に文面確認）
## 7. PythonAnywhere は延命しない（自然停止。すぐには削除しない）

---

## 案内文の下書き（企業ご担当者さま向け）【差出人・送付手段は要確認】

件名: 研修サイトのアドレス変更のお知らせ

いつも研修にご参加いただき、ありがとうございます。
Skill Growth の研修サイトを、より安定して使える国内のサーバーへ引っ越しました。

新しいアドレスはこちらです。
https://lms.skillgrowth.jp

お手数ですが、受講者のみなさまにもお伝えいただけますでしょうか。

・ユーザー名、パスワードはこれまでと同じです
・これまでの受講記録はすべて引き継いでいます
・古いアドレスを開いた場合も、新しいサイトへ自動で移動します

ブックマークをされている方は、新しいアドレスへの登録し直しをお願いします。
ご不明な点があれば、このメールにそのままご返信ください。
