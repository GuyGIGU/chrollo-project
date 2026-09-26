@echo off
REM Double-click to rebuild the Chrollo frontend and restart the service.
REM The PowerShell script self-elevates (UAC) because restarting the Windows
REM service needs administrator rights.
REM It refuses to run while a scan is in progress; pass -Force to override.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_dashboard.ps1" %*
