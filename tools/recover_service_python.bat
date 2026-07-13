@echo off
REM One-click recovery: point the ChrolloDashboard service at its dedicated venv,
REM verify /health, and optionally de-collide the Python registry tag.
REM The .ps1 self-elevates via UAC, so double-clicking this is enough.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0recover_service_python.ps1"
