@echo off
echo Starting Chrollo Dashboard...

echo Installing Python Backend requirements...
python -m pip install fastapi uvicorn sqlalchemy pydantic ib_async python-multipart aiofiles -q

echo Clearing previous sessions on port 8000...
FOR /F "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo Starting FastAPI Backend...
set IBKR_LIVE_CONFIRMED=true
start cmd /k "set IBKR_LIVE_CONFIRMED=true&& cd webapp\backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000"

echo Starting React Frontend...
cd webapp\frontend
call npm run dev
