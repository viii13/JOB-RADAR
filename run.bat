@echo off
echo ========================================================
echo Starting JobRadar Platform (Backend + Frontend)
echo ========================================================

set ROOT=%~dp0
start "JobRadar Backend (FastAPI)" cmd /k "cd /d "%ROOT%JobRadar\JobRadar\DDS-Job-Market-Project" && set PYTHONPATH=src && .venv\Scripts\python.exe -m uvicorn job_market.api:app --host 127.0.0.1 --port 8000 --reload"
start "JobRadar Frontend (Vite)" cmd /k "cd /d "%ROOT%JobRadar\JobRadar\Frontend" && npm run dev"

echo.
echo Both servers are starting in separate windows:
echo - Backend API:  http://127.0.0.1:8000
echo - Frontend UI:  http://localhost:5173
echo ========================================================
