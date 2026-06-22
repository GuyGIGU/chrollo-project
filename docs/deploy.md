# Chrollo Always-On Local Dashboard

This guide turns Chrollo into a local app you open in the browser with no terminals. The app does not need IBKR for normal screener, archive, watchlist, chart, or scheduled-scan use. Click **Reconnect** in the dashboard only when you want a fresh IBKR portfolio snapshot.

## 1. One-Time Setup

Open PowerShell in the repo folder:

```powershell
cd "C:\Users\User\Documents\Projects\Chrollo Project"
.\setup.bat
```

This installs Python packages, installs frontend packages, and builds the browser UI into `webapp\frontend\dist`.

## 2. Register The Windows Service

Install NSSM first, then run these commands from an Administrator PowerShell. Adjust `python.exe` if your Python lives somewhere else.

```powershell
cd "C:\Users\User\Documents\Projects\Chrollo Project"

nssm install ChrolloDashboard "python.exe" "-m uvicorn main:app --host 127.0.0.1 --port 8000"
nssm set ChrolloDashboard AppDirectory "C:\Users\User\Documents\Projects\Chrollo Project\webapp\backend"
nssm set ChrolloDashboard DisplayName "Chrollo Dashboard"
nssm set ChrolloDashboard Description "Local Chrollo dashboard and scheduled stock scans"
nssm set ChrolloDashboard Start SERVICE_AUTO_START
nssm set ChrolloDashboard AppExit Default Restart
nssm set ChrolloDashboard AppStdout "C:\Users\User\Documents\Projects\Chrollo Project\output\chrollo-service.log"
nssm set ChrolloDashboard AppStderr "C:\Users\User\Documents\Projects\Chrollo Project\output\chrollo-service-error.log"
nssm set ChrolloDashboard AppEnvironmentExtra IBKR_AUTO_CONNECT=false
nssm start ChrolloDashboard
```

Do **not** set `IBKR_LIVE_CONFIRMED` on this service — it must stay broker-free at boot so a reboot or crash-restart never auto-grabs your single IBKR session (which would fight TradingView).

You still get live snapshots on demand: open the dashboard and click **Connect IBKR**. In live mode this pops a confirmation ("connect to your real-money account?") and, only on your OK, hands the IBKR API session to Chrollo for the duration. Click **Disconnect** to release the session before you trade in TWS / TradingView. This is a per-click human action — it is *not* persisted, so the next boot is broker-free again. (The connection is read-only; keeping IB Gateway's **Read-Only API** enabled is recommended as a broker-level guarantee.)

Alternative: Windows Task Scheduler can start `python -m uvicorn main:app --host 127.0.0.1 --port 8000` at logon, with the working folder set to `webapp\backend`, but NSSM is recommended because it auto-starts on boot and restarts after crashes.

## 3. Create The Browser Shortcut

```powershell
$shortcut = "$env:USERPROFILE\Desktop\Chrollo Dashboard.url"
"[InternetShortcut]`nURL=http://127.0.0.1:8000" | Set-Content -Path $shortcut -Encoding ASCII
```

From now on, opening Chrollo should mean double-clicking that shortcut.

## 4. Schedule Backups

The valuable local data is:

- `webapp\backend\trading_journal.db`
- `webapp\backend\trading_journal.db-wal`
- `webapp\backend\trading_journal.db-shm`
- `market_data_cache_5y.parquet`
- `cache_meta.json`
- `market_context.json`

Create a small backup script:

```powershell
@'
$repo = "C:\Users\User\Documents\Projects\Chrollo Project"
$root = Join-Path $env:USERPROFILE "ChrolloBackups"
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$dest = Join-Path $root $stamp
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item "$repo\webapp\backend\trading_journal.db*" $dest -ErrorAction SilentlyContinue
Copy-Item "$repo\market_data_cache_5y.parquet" $dest -ErrorAction SilentlyContinue
Copy-Item "$repo\cache_meta.json" $dest -ErrorAction SilentlyContinue
Copy-Item "$repo\market_context.json" $dest -ErrorAction SilentlyContinue
# Retention: keep the 14 most recent snapshots (the 108 MB parquet adds up fast).
Get-ChildItem -Path $root -Directory | Sort-Object Name -Descending | Select-Object -Skip 14 | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
'@ | Set-Content "$env:USERPROFILE\ChrolloBackup.ps1" -Encoding UTF8
```

Schedule it daily:

```powershell
schtasks /Create /TN "Chrollo Daily Backup" /SC DAILY /ST 20:30 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"%USERPROFILE%\ChrolloBackup.ps1`"" /F
```

## 5. Verify It Is Live

1. Reboot the PC.
2. Double-click the **Chrollo Dashboard** shortcut.
3. Confirm the grid loads at `http://127.0.0.1:8000`.
4. Wait for the scheduled scan time, or temporarily set `SCAN_SCHEDULE_HOUR_ET` and `SCAN_SCHEDULE_MINUTE_ET` in `config\settings.py` a few minutes ahead and restart the service.
5. Confirm the header shows the latest scan time, setup count, and `ok`.

Keep the scheduled scan supervised for 1-2 weeks before fully trusting it unattended.

## Applying Code Changes (one click)

After any code change (frontend or backend), you do **not** need to run `npm run build` and an
elevated `nssm restart` by hand. Double-click **`update_dashboard.bat`** in the repo root (or run
`update_dashboard.ps1`). It:

1. Self-elevates once via UAC (restarting a Windows service needs admin rights).
2. Rebuilds the frontend into `webapp\frontend\dist`.
3. Restarts the `ChrolloDashboard` service.
4. Polls `http://127.0.0.1:8000/health` and prints the result.

It never sets `IBKR_LIVE_CONFIRMED` and never changes the service's broker-free configuration — the
dashboard stays broker-free at boot exactly as before.

## Service Commands

```powershell
nssm status ChrolloDashboard
nssm restart ChrolloDashboard
nssm stop ChrolloDashboard
nssm remove ChrolloDashboard confirm
```
