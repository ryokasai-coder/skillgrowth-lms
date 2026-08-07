# Registers the LMS backup as a Windows Scheduled Task.
# Run in an ELEVATED (Administrator) PowerShell:
#   powershell -ExecutionPolicy Bypass -File register_backup_task.ps1
#
# Creates a task that runs run_backup.bat every day at 02:00.
# NOTE: ASCII-only on purpose. Windows PowerShell 5.1 reads a BOM-less .ps1 as
# ANSI, so non-ASCII characters can corrupt parsing.

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$batPath   = Join-Path $scriptDir 'run_backup.bat'
$taskName  = 'LMS_Backup'

if (-not (Test-Path $batPath)) {
    Write-Error "run_backup.bat not found: $batPath"
    exit 1
}

$action    = New-ScheduledTaskAction -Execute $batPath
$trigger   = New-ScheduledTaskTrigger -Daily -At 2:00AM
$settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited

# Replace an existing task if present.
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Removed existing task '$taskName'."
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'LMS training system: daily backup of learner data (5-year retention).'

Write-Host "Task '$taskName' registered (runs daily at 02:00)."
Write-Host "Manual test run: Start-ScheduledTask -TaskName $taskName"
