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

REM Resolve the interpreter from the service's own nssm config instead of a bare
REM `python`. Task Scheduler builds this process's PATH fresh from the registry
REM (System PATH + User PATH), where the machine-wide, dependency-less Python 3.14
REM installed for the CI runner sorts AHEAD of the per-user pythoncore that actually
REM has pandas/yfinance -- so a bare `python` would die at import and this tick (whose
REM whole point is proving the engine's edge) would stop near-silently. The service's
REM Application is the single source of truth for the right interpreter.
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "(nssm get ChrolloDashboard Application | Select-Object -First 1).Trim()"`) do set "PY=%%p"
if not defined PY (
    echo %DATE% %TIME%  run_maturation: could not resolve service Python from nssm; tick skipped>> "output\maturation.log"
    exit /b 1
)
"%PY%" -m core.archive.forward_returns >> "output\maturation.log" 2>&1
