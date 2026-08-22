# exec-backend — Ramírez findings 1, 2, 3, 4, 7, 8

Run: 2026-08-22-2250 · executed 2026-08-23 · interpreter `.\.venv\Scripts\python.exe` · backend never booted.

## Changes

### F1 (P2) — /stream/executions no longer dies on its first idle 15s
`webapp/backend/routers/portfolio_streams.py`
- Folded ONE shared wait-with-keep-alive helper, `_channel_events(request, channels)` (EC-3): holds the
  pending `__anext__` tasks across `asyncio.wait` timeouts (which do NOT cancel), yielding a `_KEEP_ALIVE`
  sentinel per idle window and each payload as it arrives. Both streams now ride it:
  - `_subscribed_snapshots` = `_channel_events` over `_PORTFOLIO_CHANNELS`, keep-alive → comment + snapshot,
    payload → snapshot (byte-identical wire behavior to before).
  - `stream_executions`' gen = `_channel_events` over `("executions",)`, keep-alive → comment,
    payload → `_sse_data(payload)`. The broken `asyncio.wait_for(sub.__anext__(), 15)` (cancel-into-generator
    → finalized → StopAsyncIteration on next resume) is gone.
- The idle window is the module constant `_IDLE_TIMEOUT_S = 15` (tests shrink it; production value unchanged).

### F2 (P2) — the degrade-and-retry catches now log loudly
`webapp/backend/routers/portfolio_streams.py`
- `_log_stream_failure_once(where, exc)` on `logging.getLogger("chrollo.portfolio_streams")`: full
  `exc_info` ONCE per distinct `(site, ExcType: message)`; repeats stay quiet (the 1 Hz retry can't flood);
  the seen-set is bounded (cleared past 32 distinct entries). Wired at BOTH catch sites: the outer
  subscription loop (`_stream_snapshot_events`) and the inner subscriber-pull failure (`_channel_events`).
  Degrade shape unchanged — `StopAsyncIteration` (normal generator end) does not log.

### F3 (P2) — broadcaster binds to the SERVER loop; Connect no longer orphans streams
`webapp/backend/ibkr/broadcaster.py`, `webapp/backend/ibkr/service.py` (bind_loop call site only)
- `bind_loop` DELETED (with its `_subs.clear()` — the wipe that orphaned every stream open at Connect click).
  `service._run_loop` no longer touches the broadcaster (a NOTE comment marks why).
- The publish loop is captured lazily under the lock from the first subscriber's `asyncio.get_running_loop()`
  (uvicorn's — queues live where their consumers live). `publish_threadsafe` still hops via
  `call_soon_threadsafe`, so `publish` executes ON the subscribers' loop — no cross-thread queue wakeups;
  a benign shutdown race (`RuntimeError` from a just-closed loop) is swallowed.
- A queue whose `put` fails (consumer's loop dead) is dropped individually; QueueFull keeps the existing
  drop-oldest behavior. Nothing ever wipes the subscriber set wholesale.

### F4 (P2) — same-app guard on the two open action routes
`webapp/backend/routers/archive_actions.py`
- `GET /archive/analysis` and `POST /archive/update-returns` now declare
  `dependencies=[Depends(require_same_app)]` (imported from `routers.calibration`, the stated posture rule —
  deliberate retrofit, comment at the site). Scheduled-scan behavior untouched.
- **HANDOFF (frontend lane):** the two frontend callers do NOT yet send the header and will 403 once this
  deploys — `webapp/frontend/src/hooks/useArchiveData.js:52` (POST update-returns) and
  `webapp/frontend/src/hooks/useArchiveMaintenance.js:33` (GET analysis) need
  `headers: { 'X-Chrollo-Client': 'chrollo-dashboard' }` like their guarded siblings. I touched no frontend
  file (out of my lane).

### F7 (P3) — scan_status runs on the boot-migrated schema only
`webapp/backend/services/scan_status.py`
- Deleted `_has_kind_column` (the per-call PRAGMA sniff) and all four no-kind SQL twins; one INSERT and one
  SELECT shape per helper. Kept `COALESCE(kind, 'scan')` (cheap belt for an explicit-NULL row). No assert-once
  added — a missing column now fails loudly as "no such column: kind", which is the honest failure.

### F8 (P3) — production-dead wrapper deleted
`webapp/backend/services/scan_runner.py` — `_parse_n_setups` deleted.
`tests/test_fetch_repair.py` — import + sole test repointed at `_parse_scan_result` (renamed to
`test_parse_scan_result_reads_json_before_stale_traceback`, asserts the full `(140, 0)` tuple).

## New tests
- `tests/test_portfolio_stream_lifecycle.py` (7 tests, plain asyncio loops, no boot): F1 — the executions
  channel survives two idle windows then still delivers a fill; the folded portfolio stream keeps its
  keep-alive+snapshot idle behavior. F2 — once-per-distinct-failure logging; a subscriber-pull failure logs
  loudly then degrades. F3 — cross-thread publish delivers onto the subscriber's captured loop with the
  subscriber set intact (the Connect-click sequence); publish_threadsafe pre-subscriber is a no-op; a
  dead-loop queue is dropped individually while a live sibling still receives; `bind_loop` is retired.
- `tests/test_archive_actions_guard.py` (2 tests): both routes declare `require_same_app`
  (watchlist/candles guard-pin mold).
- `tests/test_scan_status.py` (3 tests): round-trip + kind filtering + NULL-kind COALESCE, against a temp DB
  built from `services/startup.py`'s OWN scan_runs CREATE (pins "the boot migration is the schema truth").

## Verification
- `py_compile` on all 10 touched files: clean.
- pytest (relevant files only, per mandate): `test_portfolio_stream_lifecycle` + `test_archive_actions_guard`
  + `test_scan_status` + `test_fetch_repair` + `test_eval_error_counter` + `test_ibkr_hardening` +
  `test_scheduler_misfire` + `test_manual_add_universe_stamp` + `test_rate_limit` → **106 passed**;
  `test_backend_services` + `test_archive_reliability` → **93 passed**. Total **199 passed, 0 failed**.
- `import main` in a subprocess (cwd webapp/backend, no lifespan): all routes register —
  `/stream/portfolio`, `/stream/executions` present; `/analysis` and `/update-returns` both carry the guard
  (this FastAPI defers includes as `_IncludedRouter`; walked recursively). Prints `MAIN_IMPORT_OK`.
- Side observation for the chair: the import check's idempotent boot pass applied two migrations that were
  PENDING on the live backend DB from a sibling lane's `startup.py` edit
  (`ALTER TABLE near_miss_archive DROP COLUMN would_be_score` / `would_be_tier`) — exactly what the next
  real boot would have done, but noting it since it landed during my verification, not my diff.

## Files touched (10)
Modified: `webapp/backend/routers/portfolio_streams.py`, `webapp/backend/ibkr/broadcaster.py`,
`webapp/backend/ibkr/service.py`, `webapp/backend/routers/archive_actions.py`,
`webapp/backend/services/scan_status.py`, `webapp/backend/services/scan_runner.py`,
`tests/test_fetch_repair.py`.
New: `tests/test_portfolio_stream_lifecycle.py`, `tests/test_archive_actions_guard.py`,
`tests/test_scan_status.py`.
