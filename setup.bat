@echo off
setlocal

echo Setting up Chrollo...
cd /d "%~dp0"

echo Installing Python requirements...
python -m pip install -r requirements.txt

echo Installing frontend packages...
npm --prefix webapp\frontend install

echo Building frontend...
npm --prefix webapp\frontend run build

echo.
echo Setup complete. Use start_dashboard.bat to open the local app.
