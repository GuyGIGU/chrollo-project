@echo off
REM Double-click to rebuild the Chrollo frontend and restart the service.
REM The PowerShell script self-elevates (UAC) because restarting the Windows
REM service needs administrator rights.
REM It refuses to run while a scan is in progress; pass -Force to override.
REM It refuses a checkout that is not on the release branch (main) or that has
REM uncommitted tracked files; pass -AllowAnyCheckout to override.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_dashboard.ps1" %*
