@echo off
REM ============================================================================
REM Forwarding launcher -- the real script is tools\ops\run_maturation.bat.
REM
REM Windows Task Scheduler's "Chrollo Forward Returns" task was registered with
REM THIS file's absolute path, and the script moved to tools\ops\ on 2026-09-24.
REM This file only calls it and passes back its exit code, so the task works at
REM either path; change what the tick does in tools\ops\. Pointing the task there
REM is one Administrator command (docs/deploy.md, "Schedule Forward-Return
REM Maturation"). Keep this file until the task shows the new path: deleting it
REM first stops the nightly tick. tests/tooling/test_maturation_launcher.py pins it.
REM ============================================================================
call "%~dp0ops\run_maturation.bat"
exit /b %ERRORLEVEL%
