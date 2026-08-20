# Spec: Archive pipeline reliability fixes

**Branch:** `fix/archive-pipeline` · **Origin:** 2026-07-01 adversarial audit `wf_d46463de-e96` (memory `project_archive_silent_stall`).

## Problem
The archive/forward-return pipeline keeps *appearing* fixed then stalling again ("matured setups never accumulate"). Root cause = ONE class: **no reliable, backend-independent daily maturation tick + zero observability on whether it ran/threw.** Downstream leaves (lost cohorts, stale days, aged-out 60d) are consequences of that trunk. Confirmed by direct DB + code forensics; the return math itself is sound (idempotent, correct) — this is a reliability/observability class, not data corruption.

## Scope (5 fixes; the audit served as the multi-seat plan review)
All changes are **archive-path only** — they do NOT touch the scoring/structure engine, so `shadow_diff` (engine byte-parity) and `seed_recall` (firing invariant) must stay green.

### Fix #1 — maturation tick: reliable + visible  (BLOCKER, the trunk)
- **Visibility:** `scan_runner.run_scheduled_scan_and_forward_returns` — wrap the forward-return backfill in `scan_status.start_run('scheduled', kind='maturation')` / `finish_run(status=..., n_setups=updated)`; on failure record `status='failed'` + `alert_if_needed`, not a bare swallowed log. Same for the standalone `forward_returns.__main__` (the OS-task entrypoint) so an OS-scheduled run is equally visible.
- **Watchdog:** `scan_watchdog.run_scan_health_watchdog` — also check `latest_run(kind='maturation')` for failed / stale (>26h). `scan_status` already supports arbitrary `kind`.
- **Reliable tick (ops):** register a Windows Task Scheduler task running `python -m core.archive.forward_returns` nightly, "run if missed" → maturation ticks even when the FastAPI backend is down. Documented in `docs/deploy.md`.

### Fix #2 — partial per-ticker archive on degraded coverage  (BLOCKER)
`scan_job.run_scan_and_export` (non-empty branch): when the universe-wide latest-session coverage misses the 95% bar **but the session is current** (not a whole-panel-behind `stale_session`), archive the subset of fired setups whose OWN ticker carries a close on the expected session (`symbols_missing_closes_on`), instead of discarding the entire cohort. Keep the universe-wide health for the alert/status; keep the genuine whole-panel-stale abort; leave the empty-results branch unchanged.

### Fix #3 — non-trading-day earliest cohort  (MAJOR)
`forward_returns.update_forward_returns` — pad the batch download `start` back ~5 calendar days so the trading close on/before a weekend/holiday earliest `scan_date` is in-frame (yfinance `start` is inclusive → otherwise the earliest row's `scan_close` can't resolve and it's skipped forever).

### Fix #4 — 60d aged-out re-touch window  (MAJOR)
`forward_returns` — decouple `FORWARD_RETURN_MAX_SCAN_AGE_DAYS` from the download buffer and widen 120→200 so a maturation gap can't abandon a row's fixed-window columns before the 60-bar (~87 cal day) fill point (slack 33d→113d). The re-touch predicate already only re-selects rows with a null window, so fully-matured rows are unaffected; the cap only bounds dead-ticker re-download.

### Fix #5 — orphaned `running` row  (MAJOR)
`startup.initialize_database` — boot-time reconcile: mark any `scan_runs` row left `status='running'` (process killed between start/finish) as `failed`. `scan_watchdog` — alert on a run stuck `running` beyond ~2h (hung) instead of the 26h stale mislabel. Unsticks the live-price fallback gate (`_scan_is_running`) on restart.

## Gates
`pytest -q` (incl. new tests per fix) · `compileall` · `shadow_diff --check` (expect NO drift) · `seed_recall --check` (expect baseline). Then council-review the diff; commit to `fix/archive-pipeline` (not merged).

## Verify (post-merge, real DB)
Run `python -m core.archive.forward_returns` → confirm a `kind='maturation'` `scan_runs` row appears; force a maturation failure → confirm a watchdog alert. The recurring symptom dissolves at Fix #1.
