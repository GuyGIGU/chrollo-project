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

Install NSSM first, then run these commands from an Administrator PowerShell. **The service runs a
dedicated virtual environment** — not a bare `python.exe`, and not either machine-wide Python 3.14
directly. This box carries two Python 3.14 installs that share the same `PythonCore\3.14` registry
tag — a per-user PyManager "pythoncore" and an all-users Program Files install (added for the CI
runner, §6) — and that collision has broken the service twice: a bare `python.exe` resolves to the
dependency-less Program Files interpreter under the service account (no `fastapi` → boot-loop), and a
PyManager runtime reset once wiped the pythoncore interpreter out from under the running service. A
venv built from the Program Files interpreter is self-contained and depends on neither registry tag,
so it survives both. Build it once, install the pinned deps into it, then register the service
against it — and confirm what got stored with `nssm get ChrolloDashboard Application`.

```powershell
cd "C:\Users\User\Documents\Projects\Chrollo Project"

# One-time: build the service's dedicated venv from the all-users Program Files
# interpreter (a full, healthy CPython), then install this repo's pinned deps into it.
& "C:\Program Files\Python314\python.exe" -m venv "C:\Users\User\AppData\Local\ChrolloDashboard\venv"
& "C:\Users\User\AppData\Local\ChrolloDashboard\venv\Scripts\python.exe" -m pip install -r requirements.txt -c constraints.txt

nssm install ChrolloDashboard "C:\Users\User\AppData\Local\ChrolloDashboard\venv\Scripts\python.exe" "-m uvicorn main:app --host 127.0.0.1 --port 8000"
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

> **Recovering an existing service** (pointed at the wrong/broken interpreter, or after a PyManager
> reset): don't reinstall — run `tools\recover_service_python.bat` (double-click, or right-click → Run
> as administrator). It self-elevates, repoints the existing service at the venv, restarts it, polls
> `/health`, and then offers to remove the `HKLM\...\PythonCore\3.14\PythonPath` registry value that
> lets a half-broken interpreter borrow another's stdlib instead of failing loudly (backed up first,
> with automatic rollback if anything stops importing). It leaves `AppParameters`, `AppDirectory`, and
> the broker-free `AppEnvironmentExtra` untouched.

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
- `calibration_frames\` — the frozen bars each operator mark was drawn on, bound
  by `frame_digest`. **The least replaceable thing here:** a live re-fetch returns
  different bars, so a lost frame cannot be re-derived at any price. ~3 MB, rides every
  snapshot whole.
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

**Then verify — an un-redeployed change is inert and SILENT.** It raises nothing: the
deployed copy simply keeps doing what it always did, and the only trace is a log line
that never appears. Measured 2026-08-25 — the `calibration_frames` leg was added to the
repo copy on 2026-08-20 and recorded as done, but the redeploy never ran, so the 110
irreplaceable frames went five more nights unbacked-up while every run logged `OK`.
After redeploying, run it once by hand and read the log for the leg you just added:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\ChrolloBackup.ps1"
Get-Content "$env:USERPROFILE\ChrolloBackups\backup.log" -Tail 8
```

A healthy run names every leg — `db_snapshot`, `calibration frames: <n> copied`, `state
files`. **A leg missing from the log is a leg that is not running.**

Behavior:

- Snapshots go to `%USERPROFILE%\ChrolloBackups\<yyyy-MM-dd_HHmm>\`; the 14 most recent
  are kept (locally and on the mirror).
- Every run appends to `%USERPROFILE%\ChrolloBackups\backup.log`. Any failure removes the
  partial snapshot, logs `FAILED`, and exits 1 — visible as the task's Last Run Result.
  Glance at the log weekly; there is no `-ErrorAction SilentlyContinue` on any data path.
- **Off-disk mirror:** `$Mirror` now defaults to `%OneDrive%\ChrolloBackups` (this box has a
  single physical disk, so a cloud-synced local folder is what gives off-machine durability —
  the sync client uploads each snapshot). Every mirrored database copy is hash-verified. To
  point it at a second physical disk instead, edit `$Mirror` (e.g. `"D:\ChrolloBackups"`); set
  it to `""` to disable (every run then logs a `WARN` that all copies sit on the same disk as
  the originals).

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
maturation never ticks, and archived setups stall one bar short of maturing.

> **The 18:00 ET slot is 01:00 local time in Israel, and a full scan needs about 17 minutes.**
> Shutting the PC down between 01:00 and 01:20 kills that night's scan mid-run; shutting it
> down just before 01:00 means the scan never starts at all, and nothing re-runs a missed slot
> (`_missed_todays_slot` only ever recovers TODAY's slot, and a morning boot is always before
> the evening one). Both shapes are now explained in plain words by the topbar status pills —
> click either one for the scan-run registry, which names the reason and a proposed solution.
> To move the slot instead, edit `SCAN_SCHEDULE_HOUR_ET` / `SCAN_SCHEDULE_MINUTE_ET` in
> `config/settings.py` and restart with `update_dashboard.bat`. Keep it after the US close.
> Evidence for the collision: [scan_interruption_incident_2026-09.md](scan_interruption_incident_2026-09.md). Because the
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

## 6. Self-Hosted CI Runner (GitHub Actions)

The `verify-windows` job in `.github/workflows/quality.yml` runs on a **self-hosted runner
on this box** instead of GitHub's paid `windows-latest`. GitHub bills hosted Windows minutes
at **2×**, and that one job was roughly half the CI bill; a self-hosted runner makes it
**free and unlimited**, and — because this machine *is* the prod platform — gives true
prod-parity (same Windows, same Python 3.14). The Linux `verify` job stays on GitHub's hosted
runner (1× minutes, cheap).

> **Security — private repo only.** A self-hosted runner is safe while the repo is **private**.
> Do **not** leave it attached if the repo is ever made public: a pull request from a fork
> could execute arbitrary code on this machine. Detach it first (see *Managing the runner*).

> **Sequence matters.** Register the runner **before** pushing the workflow change — otherwise
> the `verify-windows` job has no `chrollo-win` runner to land on and sits queued (then fails
> after GitHub's ~24 h wait).

### Install (one-time)

1. On GitHub: **repo → Settings → Actions → Runners → New self-hosted runner → Windows / x64**.
   That page shows the current download URL and a short-lived **registration token** — copy
   both from there (they change between visits).
2. Download and extract (use the exact URL from step 1):

```powershell
mkdir C:\actions-runner; cd C:\actions-runner
Invoke-WebRequest -Uri <DOWNLOAD_URL_FROM_GITHUB> -OutFile actions-runner.zip
Expand-Archive .\actions-runner.zip -DestinationPath .
```

3. Register it **as a service** (installs *and* starts it; runs on boot). On Windows the
   service is installed by `config.cmd` itself via `--runasservice` — there is **no
   `svc.cmd`** (that is the Linux runner's helper). Installing a service needs elevation, so
   run this from an **Administrator** PowerShell:

```powershell
cd C:\actions-runner
.\config.cmd --url https://github.com/GuyGIGU/chrollo-project --token <REGISTRATION_TOKEN> --labels chrollo-win --runasservice --unattended
```

`--runasservice` installs and starts the Windows service (named
`actions.runner.GuyGIGU-chrollo-project.<MACHINE>`, running as `NT AUTHORITY\NETWORK SERVICE`,
delayed-auto-start); `--labels chrollo-win` is what the workflow targets. Confirm:

```powershell
Get-Service actions.runner.*        # -> Running
```

In **Settings → Actions → Runners** the runner should now show **Idle** with the `chrollo-win`
label. Open a PR and confirm the `verify-windows` job picks it up.

> **Reconfiguring later.** `config.cmd` refuses to run if the runner is already configured.
> Un-configure first — either `.\config.cmd remove --token <REMOVAL_TOKEN>` (removal token
> from the runner's **Remove** dialog), or clear local state with
> `Remove-Item .runner,.credentials,.credentials_rsaparams -Force` — then re-run `config.cmd`
> with `--replace` added.

### Managing the runner

The runner is an ordinary Windows service, so use the standard service cmdlets:

```powershell
Get-Service  actions.runner.*        # status
Stop-Service actions.runner.*        # pause (queued jobs wait; the workflow's concurrency cancels superseded ones)
Start-Service actions.runner.*       # resume
```

To **detach** it (before making the repo public, or to retire it): from an **Administrator**
PowerShell, `config.cmd remove` stops + deletes the service *and* unregisters from GitHub in
one step. Get a removal token from **Settings → Actions → Runners → (the runner) → Remove**:

```powershell
cd C:\actions-runner
.\config.cmd remove --token <REMOVAL_TOKEN>
```

### Notes for this machine

- CI jobs here are **pure compute and broker-free** — the tests never open an IBKR session,
  so the runner never contends with TWS / TradingView for the single login. It does use CPU
  while a job runs; the workflow's `concurrency: cancel-in-progress` stops rapid pushes from
  queuing a backlog on the box.
- The `verify-windows` job needs a **machine-wide** Python 3.14 on the runner's system PATH:
  `winget install --id Python.Python.3.14 --override "/quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1"`
  then `Restart-Service actions.runner.*`. The operator's day-to-day 3.14 is a *per-user*
  install under `%LOCALAPPDATA%` that the runner's `NETWORK SERVICE` account cannot read, and
  `actions/setup-python` can't self-install under that account either — so CI uses a
  system-wide interpreter (via a throwaway venv). Re-do this if the runner box is rebuilt.
- The runner **self-updates**; no routine maintenance.
- If a job can't find `git` or other tools, the runner runs as `NETWORK SERVICE`, which sees only
  the **system** PATH. Fix it by putting the missing tool on the **system** PATH (or calling it by
  full path) and restarting the runner — the same remedy this doc already uses for Python above.
  **Do not move the runner onto your own account.** Re-registering it with
  `--windowslogonaccount` / `--windowslogonpassword` is discouraged: it persists your Windows
  password on a service that executes arbitrary checked-out PR/CI code, and it gives that code
  read/write to your user profile — the live `trading_journal.db`, the backups, the OneDrive mirror.
  On this prod box (always-on dashboard + the single IBKR login), the `NETWORK SERVICE` account is
  the boundary that keeps CI code away from live trading data. Keep it.

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
