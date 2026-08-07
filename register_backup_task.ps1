# LMS研修システム 自動バックアップをWindowsタスクスケジューラに登録する。
# 管理者権限のPowerShellで実行してください:
#   powershell -ExecutionPolicy Bypass -File register_backup_task.ps1
#
# 毎日 AM2:00 に run_backup.bat を実行するタスクを作成します。

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$batPath   = Join-Path $scriptDir 'run_backup.bat'
$taskName  = 'LMS_Backup'

if (-not (Test-Path $batPath)) {
    Write-Error "run_backup.bat が見つかりません: $batPath"
    exit 1
}

$action    = New-ScheduledTaskAction -Execute $batPath
$trigger   = New-ScheduledTaskTrigger -Daily -At 2:00AM
$settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable:$false
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited

# 既存タスクがあれば置き換える
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "既存タスク '$taskName' を削除しました。"
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description 'LMS研修システムの受講データを毎日バックアップ（5年保持）'

Write-Host "タスク '$taskName' を登録しました（毎日 AM2:00 実行）。"
Write-Host "手動テスト実行: Start-ScheduledTask -TaskName $taskName"
