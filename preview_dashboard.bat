@echo off
REM Look at the checkout as it is right now -- committed or not, on any branch --
REM before anything is committed or deployed. Opens http://localhost:5173 in your
REM browser: the frontend straight from the source files, refreshing itself as they
REM change, talking to the live service on :8000 (real scans, real data).
REM Nothing is built, nothing restarts, no admin rights. Close this window to stop.
REM Backend changes do not show here: those go live only with update_dashboard.bat.
REM --strictPort: the service lets the dev page in from :5173 only, so a second
REM preview stops with "port in use" rather than opening an empty page on :5174.
cd /d "%~dp0"
echo Preview at http://localhost:5173  (close this window to stop it)
npm --prefix webapp\frontend run dev -- --open --strictPort
