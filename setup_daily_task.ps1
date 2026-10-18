# Register daily task using bat file (avoids && quoting issues)
$TaskName = "AI_Mentors_Daily_Auto"
$CC = "C:\Users\butik\Documents\Control_Center"
$Bat = "$CC\run_daily.bat"

if (-not (Test-Path $Bat)) {
    Write-Host "❌ Missing $Bat" -ForegroundColor Red
    exit 1
}

# Delete if exists
schtasks /Query /TN $TaskName 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    schtasks /Delete /TN $TaskName /F | Out-Null
}

# Create task pointing to bat file
schtasks /Create `
    /TN $TaskName `
    /TR "`"$Bat`"" `
    /SC DAILY `
    /ST 09:00 `
    /RL HIGHEST `
    /F

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Task registered: $TaskName" -ForegroundColor Green
    Write-Host "   Runs daily at 09:00 (Dubai)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Manage from Control Center:"
    Write-Host "  http://localhost:8503/ATLAS_Scheduler"
} else {
    Write-Host "❌ Failed. Run PowerShell as Administrator." -ForegroundColor Red
}