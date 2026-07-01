@echo off
REM ============================================================================
REM Chrollo - backend-INDEPENDENT nightly forward-return maturation tick.
REM
REM Runs the standalone updater (core.archive.forward_returns) so archived setups
REM mature their forward returns EVEN WHEN the ChrolloDashboard service is down, or
REM the PC was off at the in-process scheduler's 18:00 ET slot. The updater records
REM its OWN scan_runs row (kind='maturation'), so a stalled/failed maturation is
REM visible to the health watchdog instead of vanishing silently.
REM
REM Register via Windows Task Scheduler with -StartWhenAvailable (see
REM docs/deploy.md, "Schedule Forward-Return Maturation") so a missed run catches
REM up at the next boot/logon rather than being lost.
REM ============================================================================
cd /d "C:\Users\User\Documents\Projects\Chrollo Project"
python -m core.archive.forward_returns >> "output\maturation.log" 2>&1
