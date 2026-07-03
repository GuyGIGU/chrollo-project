# Chrollo Always-On Local Dashboard

This guide turns Chrollo into a local app you open in the browser with no terminals. The app does not need IBKR for normal screener, archive, watchlist, chart, or scheduled-scan use. Click **Reconnect** in the dashboard only when you want a fresh IBKR portfolio snapshot.

## 1. One-Time Setup

Open PowerShell in the repo folder:

```powershell
cd "C:\Users\User\Documents\Projects\Chrollo Project"
.\setup.bat
```

This installs Python packages, installs frontend packages, and builds the browser UI into `webapp\frontend\dist`.

To reproduce the exact known-good dependency set (e.g. on a fresh machine or after a bad
upgrade), install with the committed constraints file — `requirements.txt` stays loose on
purpose so upgrades are deliberate; `constraints.txt` pins what the service was verified
against:

```powershell
pip install -r requirements.txt -c constraints.txt
```

After a deliberate upgrade, regenerate it: `pip freeze` → replace the pin lines in
`constraints.txt` (keep the header comment).

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

### 2a. Log rotation (do this once)

Without rotation the two service logs grow without bound (and the request log is chatty).
From an Administrator PowerShell:

```powershell
nssm set ChrolloDashboard AppRotateFiles 1
nssm set ChrolloDashboard AppRotateOnline 1
nssm set ChrolloDashboard AppRotateBytes 10485760   # rotate when a log reaches 10 MB
nssm restart ChrolloDashboard
```

NSSM renames the rotated file with a timestamp next to the live one; prune old rotations
occasionally (or add `Get-ChildItem output\chrollo-service*.log* | Sort-Object LastWriteTime
-Descending | Select-Object -Skip 10 | Remove-Item` to the backup script).

### 2b. Alert webhook (make the watchdog audible)

Every scan-failure / watchdog / degraded-fetch alert posts JSON (`{"text": ...}`) to the URL
in `ALERT_WEBHOOK_URL` — a Slack/Discord/ntfy-style webhook. **If it is unset, the entire
alert net terminates in a log file nobody watches.** Set it on the service:

```powershell
# ⚠ AppEnvironmentExtra REPLACES the whole extra-environment block. Always restate
# IBKR_AUTO_CONNECT=false in the same command, or the broker-free-boot guarantee is lost.
nssm set ChrolloDashboard AppEnvironmentExtra IBKR_AUTO_CONNECT=false ALERT_WEBHOOK_URL=https://your-webhook-url
nssm restart ChrolloDashboard
```

Then test-fire one alert end-to-end (temporarily set the webhook to a test channel and stop
the service before a scheduled scan slot, or POST to the webhook manually) so the first real
failure is not also the first delivery test.

You still get live snapshots on demand: open the dashboard and click **Connect IBKR**. In live mode this pops a confirmation ("connect to your real-money account?") and, only on your OK, hands the IBKR API session to Chrollo for the duration. Click **Disconnect** to release the session before you trade in TWS / TradingView. This is a per-click human action — it is *not* persisted, so the next boot is broker-free again. (The connection is read-only; keeping IB Gateway's **Read-Only API** enabled is recommended as a broker-level guarantee.)

Alternative: Windows Task Scheduler can start `python -m uvicorn main:app --host 127.0.0.1 --port 8000` at logon, with the working folder set to `webapp\backend`, but NSSM is recommended because it auto-starts on boot and restarts after crashes.

## 3. Create The Browser Shortcut

```powershell
$shortcut = "$env:USERPROFILE\Desktop\Chrollo Dashboard.url"
"[InternetShortcut]`nURL=http://127.0.0.1:8000" | Set-Content -Path $shortcut -Encoding ASCII
```

From now on, opening Chrollo should mean double-clicking that shortcut.

## 4. Schedule Backups

The nightly backup snapshots the **irreplaceable** local data:

- `webapp\backend\trading_journal.db` — journal, executions, watchlist, and the matured
  setup archive. Snapshotted with SQLite `VACUUM INTO` + `PRAGMA integrity_check`, which
  gives a consistent point-in-time copy even while the service holds the database open.
  Never rely on a plain file copy of a live `.db`/`-wal`/`-shm` set — it is not
  guaranteed restorable.
- `webapp\backend\uploads\` — journal chart attachments (the directory appears with the
  first attachment).
- `cache_meta*.json` and `market_context*.json` — small state files, all universes.

Deliberately **not** backed up: the `market_data_cache_5y*.parquet` price caches. They
are re-downloadable — deleting one triggers a clean cold rebuild — and at ~120 MB they
would bloat every snapshot.

The script is versioned in the repo at `tools\ChrolloBackup.ps1` and **deployed** as a
copy at `%USERPROFILE%\ChrolloBackup.ps1` — the scheduled task runs the deployed copy.
To change it (including setting the mirror destination), edit the repo copy, then
redeploy:

```powershell
Copy-Item "C:\Users\User\Documents\Projects\Chrollo Project\tools\ChrolloBackup.ps1" `
  "$env:USERPROFILE\ChrolloBackup.ps1" -Force
```

Behavior:

- Snapshots go to `%USERPROFILE%\ChrolloBackups\<yyyy-MM-dd_HHmm>\`; the 14 most recent
  are kept (locally and on the mirror).
- Every run appends to `%USERPROFILE%\ChrolloBackups\backup.log`. Any failure removes the
  partial snapshot, logs `FAILED`, and exits 1 — visible as the task's Last Run Result.
  Glance at the log weekly; there is no `-ErrorAction SilentlyContinue` on any data path.
- **Off-disk mirror:** set `$Mirror` at the top of the script to a second physical disk
  or a locally-synced cloud folder (e.g. `"$env:OneDrive\ChrolloBackups"`). Until it is
  set, every run logs a `WARN`, because snapshots on the same disk as the originals do
  not survive a disk failure. Mirrored database copies are hash-verified.

Register (or re-register) the task from an **Administrator** PowerShell. `-LogonType S4U`
makes it run whether or not you are logged on, with no stored password;
`-StartWhenAvailable` catches up a missed 20:30 run at the next boot instead of losing
the night:

```powershell
$action    = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$env:USERPROFILE\ChrolloBackup.ps1`""
$trigger   = New-ScheduledTaskTrigger -Daily -At 8:30PM
$settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
Register-ScheduledTask -TaskName "Chrollo Daily Backup" -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal `
  -Description "Nightly snapshot of Chrollo's irreplaceable data (VACUUM INTO + integrity check)." -Force
```

If **Chrollo Forward Returns** (section 4b) still runs with an `Interactive` principal —
meaning it silently skips whenever you are not logged on — upgrade it the same way:

```powershell
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
Set-ScheduledTask -TaskName "Chrollo Forward Returns" -Principal $principal
```

One S4U caveat: such tasks cannot reach network drives, so keep the backup mirror on a
local folder (a cloud-synced one like OneDrive is fine — the sync client uploads it).

## 4b. Schedule Forward-Return Maturation (backend-independent tick)

The scheduled scan runs *inside* the ChrolloDashboard service (in-process APScheduler,
weekdays 18:00 ET) and backfills forward returns in the same job. That is fine while the
service is up — but if the service is down or the PC is off at 18:00 ET, that day's
maturation never ticks, and archived setups stall one bar short of maturing. Because the
maturation record is what proves the engine's edge, add a **second, backend-independent**
nightly tick via Windows Task Scheduler. It runs the standalone updater directly, records
its own `scan_runs` row (`kind='maturation'`) so the health watchdog can see it, and — with
`-StartWhenAvailable` — **catches up a missed run** at the next boot/logon instead of losing
the day.

The repo ships `tools\run_maturation.bat` (it `cd`s to the repo and runs
`python -m core.archive.forward_returns`, logging to `output\maturation.log`). Register it
from an Administrator PowerShell:

```powershell
$action  = New-ScheduledTaskAction -Execute "C:\Users\User\Documents\Projects\Chrollo Project\tools\run_maturation.bat"
# Evening LOCAL time, after the US EOD data has settled. Adjust if your PC is not on US time.
$trigger = New-ScheduledTaskTrigger -Daily -At 7:00PM
# StartWhenAvailable = "run as soon as possible after a scheduled start is missed" (the catch-up).
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "Chrollo Forward Returns" -Action $action -Trigger $trigger `
  -Settings $settings -RunLevel Limited `
  -Description "Backend-independent nightly forward-return maturation; catches up a missed run." -Force
```

The updater re-downloads fresh per-ticker data itself, so exact timing is not critical — any
evening slot after the US close works; the important part is that it runs (and catches up)
daily. Verify after the first run:

```powershell
# A kind='maturation' row should appear, status 'ok'.
python -c "import sqlite3; c=sqlite3.connect(r'C:\Users\User\Documents\Projects\Chrollo Project\webapp\backend\trading_journal.db'); print(c.execute(\"select started_at,status,n_setups from scan_runs where kind='maturation' order by id desc limit 3\").fetchall())"
```

If maturation ever fails or stalls, the morning watchdog (Tue–Sat 08:00 ET, while the service
is up) now alerts on it through the same webhook as scan failures.

## 4c. Restore (and the monthly restore drill)

A backup that has never been restored is a hope, not a backup. The drill proves the
newest snapshot actually restores — run it monthly, and after any change to the backup
script:

```powershell
python "C:\Users\User\Documents\Projects\Chrollo Project\tools\restore_drill.py"
```

It copies the latest snapshot's database to a temp dir, opens it **read-only**, runs
`PRAGMA integrity_check`, and compares `setup_archive` / `trade_logs` / `executions` row
counts against the live database, printing `PASS` or `FAIL` (exit 0/1). It also fails if
the newest snapshot is older than 48 h — i.e. the nightly task has silently stopped. It
never writes to the live database or to the snapshots.

Real restore, after data loss:

1. Stop the service: `nssm stop ChrolloDashboard`.
2. In `webapp\backend`, move the damaged set aside (don't delete it yet): rename
   `trading_journal.db`, `trading_journal.db-wal`, and `trading_journal.db-shm` with a
   `.broken` suffix.
3. Copy `trading_journal.db` from the chosen snapshot into `webapp\backend\`. Snapshots
   are `VACUUM`ed, self-contained databases — there is no `-wal`/`-shm` to restore.
4. If the snapshot contains `uploads\`, copy it to `webapp\backend\uploads\`.
5. Optionally copy the snapshot's `cache_meta*.json` / `market_context*.json` to the repo
   root — they regenerate on the next scan either way. The price caches were never backed
   up, so the first scan after a full-machine restore does a cold re-download.
6. Start the service (`nssm start ChrolloDashboard`) and verify with the drill or the
   `scan_runs` query in section 4b.

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
2. Preflights the backend: `compileall` plus an import-`main` smoke from the service's own
   working directory (import does **not** run the lifespan — nothing starts, nothing touches
   the broker). A backend that would die on boot is caught **before** the running service is killed.
3. Snapshots the current bundle to `webapp\frontend\dist_previous`, then rebuilds the frontend.
4. Restarts the `ChrolloDashboard` service and polls `http://127.0.0.1:8000/health`.

If a deploy looks wrong in the browser, roll the frontend back in one command (backend code
comes from git, so rollback only swaps the frontend bundle):

```powershell
powershell -File update_dashboard.ps1 -Rollback
```

It never sets `IBKR_LIVE_CONFIRMED` and never changes the service's broker-free configuration — the
dashboard stays broker-free at boot exactly as before.

## Service Commands

```powershell
nssm status ChrolloDashboard
nssm restart ChrolloDashboard
nssm stop ChrolloDashboard
nssm remove ChrolloDashboard confirm
```
