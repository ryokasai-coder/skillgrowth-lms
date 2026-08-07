# バックアップの自動化手順（Windows）

受講データを法定保存期間（5年）にわたり保全するため、毎日自動でバックアップを取得する。

## 仕組み

- `backup.py` … DBの一貫スナップショット（SQLite backup API）＋受講ログCSV＋ログイン証跡CSVを
  `backups/` に出力し、5年より古いバックアップを自動削除する。
- `run_backup.bat` … タスクスケジューラから呼ばれるラッパー。venvがあれば有効化して `backup.py` を実行し、
  `backups/backup.log` にログを追記する。
- `register_backup_task.ps1` … 上記を毎日 AM2:00 に実行するタスクを登録する。

## 登録手順

1. **管理者権限のPowerShell** を開く。
2. プロジェクトフォルダへ移動:
   ```powershell
   cd "C:\Users\ryo19\開発プロジェクト\LMS研修システム\lms-project"
   ```
3. 登録スクリプトを実行:
   ```powershell
   powershell -ExecutionPolicy Bypass -File register_backup_task.ps1
   ```
4. 登録確認:
   ```powershell
   Get-ScheduledTask -TaskName LMS_Backup
   ```

## 動作テスト

手動で即時実行して `backups/` にファイルが生成されるか確認する:

```powershell
Start-ScheduledTask -TaskName LMS_Backup
# 数秒後
Get-ChildItem .\backups
Get-Content .\backups\backup.log -Tail 20
```

## 実行時刻・保持期間の変更

- 実行時刻: `register_backup_task.ps1` の `-At 2:00AM` を変更して再実行。
- 保持期間: `backup.py` の `RETAIN_DAYS`（既定 `365 * 5`）を変更。

## 復旧（リストア）

バックアップからの復元は、稼働を停止したうえで対象の `lms_YYYYMMDD_HHMMSS.db` を
`instance/lms.db` に上書きコピーするだけでよい。

```powershell
Copy-Item .\backups\lms_20260807_020000.db .\instance\lms.db -Force
```
