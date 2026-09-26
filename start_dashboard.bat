@echo off
echo Starting Chrollo Dashboard...
cd /d "%~dp0"

echo Clearing previous sessions on port 8000...
FOR /F "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo Starting Chrollo at http://127.0.0.1:8000 ...
cd webapp\backend
"%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
