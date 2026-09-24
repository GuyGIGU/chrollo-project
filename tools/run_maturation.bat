@echo off
REM ============================================================================
REM Forwarding launcher -- the real script is tools\ops\run_maturation.bat.
REM
REM The "Chrollo Forward Returns" task in Windows Task Scheduler was registered
REM with THIS file's absolute path (docs/deploy.md, "Schedule Forward-Return
REM Maturation"). The script moved to tools\ops\ on 2026-09-24; this stub keeps
REM that registration working without touching the task. It is the only launcher
REM left at an old path. Remove it once the task points at tools\ops\ directly.
REM ============================================================================
call "%~dp0ops\run_maturation.bat"
exit /b %ERRORLEVEL%
