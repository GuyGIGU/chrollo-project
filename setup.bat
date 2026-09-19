@echo off
setlocal

echo Setting up Chrollo...
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating the repo venv...
    python -m venv .venv
)

echo Installing Python requirements into the repo venv...
".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-dev.txt -c constraints.txt

echo Installing frontend packages...
npm --prefix webapp\frontend install

echo Building frontend...
npm --prefix webapp\frontend run build

echo.
echo Setup complete. Use start_dashboard.bat to open the local app.
