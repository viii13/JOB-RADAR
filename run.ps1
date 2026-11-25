Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Starting JobRadar Platform (Backend + Frontend)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$rootDir = $PSScriptRoot

$backendCmd = "cd /d `"$rootDir\JobRadar\JobRadar\DDS-Job-Market-Project`" && set PYTHONPATH=src && .venv\Scripts\python.exe -m uvicorn job_market.api:app --host 127.0.0.1 --port 8000 --reload"
$frontendCmd = "cd /d `"$rootDir\JobRadar\JobRadar\Frontend`" && npm run dev"

Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "`"$backendCmd`""
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "`"$frontendCmd`""

Write-Host ""
Write-Host "Both servers launched in separate console windows:" -ForegroundColor Green
Write-Host " - Backend API:  http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host " - Frontend UI:  http://localhost:5173" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan
