# The nightly-scan / shutdown collision — measured, 2026-09-05

This distils the machine-local evidence behind the scan-failure diagnostics feature. The
Windows event log and the NSSM service log are not in the repository and roll away, so the
numbers a `decisions.md` row cites live here.

## The collision is structural, not a one-off

The scheduled scan slot is **18:00 America/New_York**, which is **01:00 the operator's local
time** (Israel). A full scan takes about 17 minutes. He powers the PC off from the Start menu
most nights between roughly 01:00 and 02:00 — Windows System log `User32` event **1074**
(a shutdown was initiated), three consecutive nights:

| Local time of the 1074 | Relative to the 01:00 local slot |
|---|---|
| 2026-09-05 01:00:25 | 24 s AFTER the scan started — killed it mid-run |
| 2026-09-06 00:59:30 | 30 s BEFORE the slot — the scan never started at all |
| 2026-09-07 01:42:27 | after that night's scan had finished |

So there are **two distinct failure shapes**, and only the first writes a `scan_runs` row.

## The incident row

`scan_runs` id **277**, read read-only from `webapp/backend/trading_journal.db`:

```
started_at   2026-09-04T22:00:01.532328+00:00
finished_at  2026-09-04T22:00:30.462683+00:00
status       failed
n_setups     NULL
trigger      scheduled
kind         scan
error        process died before completion (reconciled at boot)
```

`finished_at` here is **not** a completion time — it is the moment the orphaned row was
DETECTED. `n_setups` is NULL, which is why the topbar rendered "0 setups" (`Number(null)`
is zero, and zero is finite) and read to the operator as "the scan ran and found nothing".

## Why the obvious fix does not work

The intuitive rule — at boot-reconcile time, compare the run's `started_at` against the
machine's last boot — is **falsified by this incident**. The reconcile did not run at the
next boot. `output/chrollo-service-error.log` line 19694:

```
2026-09-05 01:00:30,464 WARNING [chrollo.migrate] reconciled 1 orphaned 'running'
                                scan_runs row(s) at boot
```

and the lines around it show `Finished server process [5976]` immediately before and
`Started server process [20680]` immediately after. Windows stopped the service during
shutdown, NSSM restarted uvicorn (`AppExit Default Restart`), and that fresh process ran
`initialize_database()` at import scope — **five seconds after the operator pressed Shut Down
and about one second before the OS went down**. The machine's last boot at that instant was
2026-09-04 09:49 local, i.e. EARLIER than `started_at` 2026-09-05 01:00:01. `boot_time >
started_at` is **False** for the exact night the feature exists to explain. The real next boot
was eleven hours later, 12:19 local.

Worse, the same window shows `EventLog` event **6006** ("the Event log service was stopped")
at 01:00:29 — one second before the reconcile. So the evidence is not merely unhelpful at that
moment, it is **unreadable**.

The rule also fails in the other direction: a scan that crashes on its own at 01:00 on a
machine that stays up all night, followed by a normal reboot at 09:00, satisfies
`boot_time > started_at` and would be reported as "your computer was turned off" — a lie on a
trust surface.

## What does work

`User32` 1074 falling inside the run's own live window. For row 277 the record sits at
**2026-09-04T22:00:25.5079768Z**, squarely inside `[22:00:01.53Z, 22:00:30.46Z]`. Read
dependency-free:

```powershell
wevtutil qe System /q:"*[System[(EventID=1074 or EventID=6008 or EventID=41) and TimeCreated[@SystemTime>='2026-09-04T21:00:00.000Z' and @SystemTime<='2026-09-05T02:00:00.000Z']]]" /f:xml /c:5
```

Measured 0.06 s. The service runs as LocalSystem, so the System log needs no elevation.

Three traps in that command, all measured:

* **`/f:xml`, never `/f:text`.** The text format prints its `Date:` header in LOCAL time and
  suffixes it with `Z` — it rendered `2026-09-05T01:00:25.5070000Z` for an event whose true
  UTC is `22:00:25.507Z`. Windowing on that mis-places every event by the UTC offset.
* **Anchor on 1074, not on Kernel-General 13** ("the operating system is shutting down"). On
  this incident 13 landed at 22:00:31.496Z — 1.03 s AFTER `finished_at`. A window clamped hard
  at the detection stamp misses the case it was built for.
* **Bound the window.** Across the ten live reconciled rows the gap between `started_at` and
  the reconcile ranges from 29 seconds (id 277) to **six days** (ids 47/48, started 2026-06-25
  and stamped 2026-07-01T16:41:44). An uncapped window would borrow an unrelated evening's
  shutdown.

## The bound was not enough — measured again in review, 2026-09-07

A window running from `started_at` to `min(detected_at, started_at + 2h) + 90s` still blames
this machine's *habit*. Every recent power-off lands inside the 18:00 scan's own two-hour cap:

| `User32` 1074 (UTC) | 2026-08-30 22:57 · 08-31 23:58 · 09-01 22:26 · 09-02 23:03 · 09-03 22:51 · 09-04 22:00 · 09-05 21:59 · 09-06 22:42 |
|---|---|
| Inside the scan's window | **8 of 8** |

So a scan that dies alone at 22:05 for an unrelated reason, on a night the dashboard survives
(the orphan is then detected at next morning's boot, and the cap collapses to `start + 2h`),
was stamped *"the computer was shut down while the scan was still running"* — a confident
wrong cause, with a remedy ("leave the computer on past the scan") that would not have helped.

**The claim is now anchored on `detected_at`**, the one instant we can *prove* the run was
still alive, because the reconcile found the row still marked `running`. A 1074 must sit
within `DETECTION_GRACE_SECONDS` of it (the existing cap still applies). Row 277 still
classifies — its 1074 is 4.95 s before the reconcile — and the late-detection case falls to
`interrupted_unrecorded`, which claims nothing.

**6008 / Kernel-Power 41 were dropped rather than re-windowed.** Windows writes both at the
NEXT boot, so their `TimeCreated` is the reboot moment, not the crash: an overnight power cut
stamps them the following morning, hours outside any window anchored on the run. The arm could
only fire when the machine came back within minutes. `interrupted_unrecorded` now says
"Windows has no record of the computer going down while it was running", which is exactly what
was searched for.

## Why the answer is stamped rather than re-derived

The System log is **circular**, capped at 20 MB, currently full and holding ~38,600 records
back to 2026-04-06. A read-time classifier would say "the computer was shut down" today and
"reason not recorded" once that date rolls out — two different answers to one historical
question, from the same code. So the resolved cause is written once into
`scan_runs.failure_kind` and never re-examined.

## The other numbers this change relies on

* The reconcile message is written for **every** kind, not just scans: the ten live rows
  carrying it split scan 4 / maturation 5 / download 1.
* Two live rows (41, 42) carry `scan status expired before completion`, a string with **no
  writer anywhere in today's code** — so any reason table needs a default arm.
* 13 of the 18 `stale_data` rows carry a real `n_setups`, so "not-ok means unknown" would be
  wrong; only the reconciled/aborted/exception rows are NULL.
* `psutil` is **not** installed and is not in `requirements.txt`. `time.time() -
  time.monotonic()` derives this machine's boot instant exactly (matched `Kernel-General`
  event 12 and `Win32_OperatingSystem.LastBootUpTime` to under a second), so no dependency was
  added. Windows Fast Startup IS enabled here (`HiberbootEnabled=1`), and every observed boot
  is still a cold one — but the guarantee is one-directional, which is why that clock is only
  ever used to REFUSE a claim.
