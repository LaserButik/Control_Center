<#
.SYNOPSIS
  Registers the Windows Scheduled Task "AI_Mentors_Daily_Run", which runs
  `python -m scheduler.run_daily` every day.

.DESCRIPTION
  - Trigger: daily at -DubaiTime (default 09:00 Dubai time), converted to
    this computer's time zone.
  - Action: <Control_Center>\venv\Scripts\python.exe -m scheduler.run_daily
    in <Control_Center>.
  - Runs as the current user, whether or not you are logged on (S4U: no
    password is stored; the task can reach the internet but not Windows
    network shares).
  - Starts a missed run as soon as possible; restarts up to 3 times, 15
    minutes apart, if the task fails to run; stops after 3 hours; never
    two at once.

  The task does NOT see variables set in a PowerShell window. Put SMTP_*,
  WHATSAPP_*, TELEGRAM_*, SERPER_API_KEY and IMAP_* in
  Control_Center\.env (run_daily loads it), or set them with setx.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scheduler\setup_windows_task.ps1
  powershell -ExecutionPolicy Bypass -File .\scheduler\setup_windows_task.ps1 -DubaiTime 08:30
  powershell -ExecutionPolicy Bypass -File .\scheduler\setup_windows_task.ps1 -WhatIf
#>
[CmdletBinding()]
param(
    [string]$DubaiTime = "09:00",
    [string]$TaskName = "AI_Mentors_Daily_Run",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "Python not found at $Python - create the venv first." -ForegroundColor Red
    exit 1
}

# 09:00 in Dubai (UTC+4, no daylight saving) -> this computer's local time
$dubaiTz = [TimeZoneInfo]::FindSystemTimeZoneById("Arabian Standard Time")
$parts = $DubaiTime.Split(":")
$todayDubai = [TimeZoneInfo]::ConvertTime([DateTime]::UtcNow, $dubaiTz).Date
$dubaiAt = $todayDubai.AddHours([int]$parts[0]).AddMinutes([int]$parts[1])
$localAt = [TimeZoneInfo]::ConvertTime($dubaiAt, $dubaiTz, [TimeZoneInfo]::Local)
$localTime = $localAt.ToString("HH:mm")

$action = New-ScheduledTaskAction -Execute $Python `
    -Argument "-m scheduler.run_daily" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Daily -At $localTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 15) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$user = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U `
    -RunLevel Limited

Write-Host ""
Write-Host "Task      : $TaskName"
Write-Host "Runs      : $Python -m scheduler.run_daily"
Write-Host "In        : $Root"
Write-Host "Daily at  : $DubaiTime Dubai = $localTime local ($([TimeZoneInfo]::Local.Id))"
Write-Host "As        : $user (whether logged on or not)"
Write-Host ""

if ($WhatIf) {
    Write-Host "-WhatIf: nothing registered." -ForegroundColor Yellow
} else {
    try {
        Register-ScheduledTask -TaskName $TaskName -Action $action `
            -Trigger $trigger -Settings $settings -Principal $principal `
            -Description "AI Mentors Agency - daily prospecting and outreach (Control Center)" `
            -Force | Out-Null
        Write-Host "Registered." -ForegroundColor Green
    } catch {
        Write-Host "Could not register: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "If this says 'Access is denied', run PowerShell as Administrator and try again."
        exit 1
    }
}

Write-Host ""
Write-Host "Equivalent schtasks command (interactive logon only, for reference):"
Write-Host "  schtasks /Create /TN $TaskName /SC DAILY /ST $localTime /TR `"'$Python' -m scheduler.run_daily`" /F"
Write-Host ""
Write-Host "Verify : schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "Run now: schtasks /Run /TN $TaskName"
Write-Host "Pause  : schtasks /Change /TN $TaskName /DISABLE"
Write-Host "Resume : schtasks /Change /TN $TaskName /ENABLE"
Write-Host "Time   : run this script again with -DubaiTime HH:MM"
Write-Host "Delete : schtasks /Delete /TN $TaskName /F"
Write-Host "Logs   : $Root\data\scheduler\run_log.jsonl and last_run.log"
