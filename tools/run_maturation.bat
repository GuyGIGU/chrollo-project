@echo off
REM ============================================================================
REM Entry point of the "Chrollo Forward Returns" scheduled task -- PERMANENT.
REM
REM Windows Task Scheduler's "Chrollo Forward Returns" task runs THIS file by its
REM absolute path (docs/deploy.md, "Schedule Forward-Return Maturation"), and the
REM task is not being re-registered, so this path is its stable entry point: do
REM not move, rename or delete it. The implementation lives in
REM tools\ops\run_maturation.bat (it moved there 2026-09-24); change what the tick
REM does THERE. This file only forwards to it and passes back its exit code.
REM tests/tooling/test_maturation_launcher.py pins both halves.
REM ============================================================================
call "%~dp0ops\run_maturation.bat"
exit /b %ERRORLEVEL%
