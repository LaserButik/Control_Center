$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
.\venv\Scripts\Activate.ps1
.\venv\Scripts\python.exe -m streamlit run app.py `
    --server.port 8503 `
    --browser.gatherUsageStats false
