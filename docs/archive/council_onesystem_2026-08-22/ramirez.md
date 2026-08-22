# Ramírez (backend) — One-System consolidation review, webapp/backend/

Run: 2026-08-22-2250 · main @ dd4c0ab (clean) · lane: routers/, services/, main.py, database.py, broker_config.py, ibkr/.
Method: full read of every router and every service on the request path; the two SSE suspicions were
verified empirically with the repo venv (asyncio semantics test, SQLAlchemy deleted-instance test) —
no repo file touched, no backend booted.

---

## Part 1 — The verdict wire map: does the wire serve BOTH legacy and TA_SCORE_V2?

Yes — deliberately, on every surface, and with no EC-28 violation found server-side. The backend
never re-declares a rule; every judgment crosses the wire already resolved. The one place the ban is
actively ENFORCED at the type layer is the health-board contract (`routers/screener.py:32-66`,
`extra='forbid'` — a member carrying a score/tier/trigger field is rejected at serve time). That is
the strongest EC-28 posture in the repo and worth naming as the pattern.

Field census, route by route:

| Wire surface | Legacy-path fields | V2 fields | Retirement ruling |
|---|---|---|---|
| `/screener-data/`, `/screener-summary/`, `/screener-data/drilldown/` (`routers/screener.py:115-218`) | `tier`, `score`, `sub_scores` dict (per-ticker, artifact passthrough) | `ta_grade`, `ta_grade_raw`, `ta_grade_chapters(+fractions)`, `ta_grade_warnings`, `score_spring`, `score_story_*`, `fired_tags` (key-absent flag-off) | KEEP the routes as-is — they are pure passthrough; the server-side retirement lever for this wire lives in the artifact builder (`output/dashboard.py:222-223` vs `:356-382`, engine lane). The backend has nothing to remove here. |
| `/setups`, `/episodes`, `/setups/{id}` — `SetupOut` (`routers/archive_schemas.py:13-293`) | `score`, `tier`, twelve legacy `score_*` sub-score columns (`:37-46,128-136,145,204`) | full `ta_grade` family (`:246-262`), `latest_ta_grade` on episodes | KEEP — books of record; pre-flip rows are NULL-graded forever (no backfill), so the serializer must speak both vocabularies for the life of the archive. |
| Dual list filters `min_score` / `min_ta_grade` (`services/archive_queries.py:52-59`) | `min_score` (raw-sum semantics) | `min_ta_grade` (NULL rows excluded by design) | KEEP-WITH-REASON — already operator-ruled ("min_score keeps raw-sum semantics FOREVER; the two scales are incommensurable"). Not a twin: two filters over two populations. |
| `/setups/{id}/chart` (`routers/archive_browse.py:258-273`) | `tier`, `score` only | **none** | Finding 6 below — the one asymmetric surface. |
| Watchlist review/replay (`routers/watchlist.py:78-85`, `services/watchlist_ledger.py:241-262`) | `tier`, `score` quoted from the stored snapshot | `ta_grade` quoted from the same bytes | KEEP — EC-28-exemplary (row and replay quote the same stored snapshot); snapshots are frozen history, so the reader must parse both vocabularies indefinitely. |
| Concordance (`services/concordance.py:58-60`) | `score`, `tier` | `ta_grade` | KEEP — carrying both is the point (task-14 ruling: split "read wrong" from "graded wrong"). |
| `/archive/calibration`, `/archive/calibration/equity-curve`, `/archive/stats` (`routers/archive_calibration.py`) | tier_performance with `avg_score` (legacy sum), correlations over the six legacy core sub-scores (`:301-317`), suggested re-weighting of the legacy `SCORE_*` knobs read live from `config/settings.py` (`:329-364`) | **none** | Finding 5 below — the server-side counterpart of `setupScoreMath.js`. |
| `/missed-winners` (`routers/archive_reviews.py:298-309`) | episode `tier` + legacy `score` in outcomes | none | KEEP — tier is the live ranking; the legacy score cell is inert context. |
| `/engine-edge/` (`routers/engine_edge.py`) | `by_tier` keyed on tier | none | KEEP — tier is not a legacy-only concept; edge report is tier-keyed by design. |

**What a server-side staged retirement actually removes:** almost nothing in routers/ — the archive
serializers and snapshot readers must keep both vocabularies forever. The genuine retire-with-legacy
sites in this lane are (a) the legacy-analytics block of `/archive/calibration` (finding 5) and
(b) the legacy-only verdict quote on the chart envelope (finding 6). Everything else either
passes through the artifact (retirement happens engine-side) or is ruled dual-vocabulary.

**Where my domain holds two things answering the same question** (the census question): findings
5, 6, 7, 8 below. That is the complete backend list — the rest of the dual-verdict carriage is
ruled-deliberate.

---

## Part 2 — Findings

FINDING 1:
- Title: `/stream/executions` self-terminates after its first idle 15 seconds — the keep-alive timeout kills the subscription
- File: webapp/backend/routers/portfolio_streams.py:77-97
- Principle: quality-backend P5 (resource lifecycle) / Collina — never cancel an async generator's `__anext__` you intend to keep
- Severity: P2
- What's wrong: The handler waits on the subscriber generator with a 15-second `wait_for`. On timeout, the cancellation is thrown into the generator at its queue await, which finalizes it (its cleanup runs, the queue is unsubscribed); the very next resume then reports the generator exhausted and the loop breaks. Verified empirically in the repo venv: after one timeout the second pull raises StopAsyncIteration and the generator's finally has already run.
- Consequence: The push-only fills stream sends exactly one keep-alive and then closes on every idle 15s window. The browser's EventSource silently reconnects in a ~15s loop all session, and any fill landing during a dead/reconnect gap never reaches the push channel (the journal is safe — auto_import persists fills independently — but the live UI channel is unreliable by construction).
- Fix: Use the sibling's pattern (`_subscribed_snapshots` waits on a task with `asyncio.wait`, which does NOT cancel on timeout): hold the pending `__anext__` task across timeouts and only await it again, exactly as the portfolio stream already does.
- Ruling-recommendation: FOLD — one wait-with-keep-alive helper shared by both streams; the correct implementation already exists 40 lines above the broken one.

FINDING 2:
- Title: Portfolio SSE loop swallows every exception silently in an infinite 1-second retry
- File: webapp/backend/routers/portfolio_streams.py:32-40 (and the inner silent `return` at :59-64)
- Principle: quality-backend P1 (never swallow what you can't explain) — reference severity for non-DB swallows
- Severity: P2
- What's wrong: The outer loop wraps the whole subscription machinery in a bare exception catch with a 1s sleep and NO log line; the inner loop likewise converts any task failure into a silent return. A persistent programmer error (broadcaster API drift, snapshot serialization bug) becomes an invisible 1 Hz loop that re-subscribes and recomputes the full portfolio snapshot payload forever, per connected client.
- Consequence: The exact failure class EC-20/EC-6 exists to make loud is muted: the stream "works" (snapshots flow) while its push path is broken, and nothing in the log ever says so.
- Fix: Log the exception (once per distinct failure or rate-limited) in both catch sites; keep the degrade behavior. This is a two-line change, not a redesign.
- Ruling-recommendation: KEEP the degrade-and-retry shape, add the loud line (EC-20's "degrade, but never blind" — the exact wording already used in watchlist_candles).

FINDING 3:
- Title: Broadcaster binds to the IBKR thread's loop and clears live subscribers — the push channel is orphaned or cross-loop exactly when the broker connects
- File: webapp/backend/ibkr/broadcaster.py:27-32, 41-72; webapp/backend/ibkr/service.py:321-325
- Principle: quality-backend P2 (never hide what the event loop is doing) / P5; asyncio.Queue is not thread-safe
- Severity: P2
- What's wrong: `bind_loop` is called from the IBKR service thread's own loop at start and (a) wipes every existing subscriber queue — but the SSE generators holding those queues keep awaiting them forever, so any stream open at the moment the operator clicks Connect IBKR (the normal sequence: dashboard open, then connect) silently stops receiving pushes; and (b) all subsequent publishes run on the IBKR loop while subscriber queues and their waiter futures live on uvicorn's loop — an unsynchronized cross-thread wakeup that works only by GIL accident, delivers with wakeup latency, and has a narrow race (a waiter concurrently cancelled by the portfolio stream's own task-cancel path makes the wakeup raise inside the publish callback, dropping the event and logging an asyncio callback error on the IB loop).
- Consequence: With IBKR connected, the portfolio pane updates mostly via the 15-second keep-alive re-snapshot rather than push, and the executions channel (already killed by finding 1) additionally starves; intermittent "exception in callback" noise can appear on the IB loop under load.
- Fix: Bind the broadcaster to the SERVER's loop (captured once in lifespan), never the IBKR loop; `publish_threadsafe` should `call_soon_threadsafe` onto the subscribers' loop; stop clearing `_subs` on bind (queues from a dead loop should instead be dropped when their put fails).
- Ruling-recommendation: FOLD to one loop-ownership rule ("queues live where the consumers live"); no second broadcast mechanism.

FINDING 4:
- Title: Unguarded simple-request routes spawn subprocesses and hold SCAN_LOCK — a drive-by page can starve the nightly scan
- File: webapp/backend/routers/archive_actions.py:252-298 (GET /analysis), :301-337 (POST /update-returns); posture rule stated at routers/calibration.py:41-53
- Principle: quality-backend P4 (make the wrong thing impossible); security overlap — Hunt's lane, noted briefly
- Severity: P2
- What's wrong: Both routes lack the same-app header the newer surfaces carry, and both are reachable by CORS "simple requests" (a GET, and a body-less POST) — no preflight stops a cross-origin page from firing them blind at localhost. TrustedHost closes DNS-rebinding but not this: Host is legitimate on a direct no-cors fetch. `/analysis` spawns a 120s pandas subprocess per request with no lock and no concurrency bound; `/update-returns` takes SCAN_LOCK for up to 300s — and the scheduled scan does a non-blocking acquire and SKIPS the night's run when the lock is held (services/scan_runner.py:340-342), so repeated fire across 18:00 ET loses the nightly scan without a trace beyond one warning line.
- Consequence: Resource-spend and scan-starvation from any web page open in the operator's browser; also, one operator click on Update Returns at the wrong moment silently costs the scheduled scan.
- Fix: Add the `require_same_app` dependency to both (the calibration posture rule explicitly anticipates deliberate retrofit); optionally have the scheduled scan retry once after a bounded wait instead of skipping outright.
- Ruling-recommendation: MERGE these two routes into the guarded posture — the rule text ("default to guarded; retrofit is deliberate, not drift") already names this decision as pending.

FINDING 5:
- Title: `/archive/calibration`'s legacy-analytics block is the server-side setupScoreMath.js — un-flagged as such
- File: webapp/backend/routers/archive_calibration.py:295-364 (six-legacy-sub-score correlations + suggested re-weighting of `SCORE_*` knobs)
- Principle: brief §1 (version census); conventions EC-3 lineage
- Severity: P3
- What's wrong: The endpooint's correlation table and suggested-weights advisory exist solely to tune the legacy raw-sum path (they read the live `SCORE_*` weights from config/settings.py and advise reallocating the 128-point cap). Nothing marks it as retiring with that path, unlike its frontend twin which carries an explicit test-pin and a "retires with the legacy path" ruling. tier_performance/`avg_score` also averages the legacy sum with no ta_grade dimension anywhere on the surface.
- Consequence: After the staged retirement this endpoint would keep advising weight moves on knobs the paying read no longer consults — a falsified advisory surface (EC-15's class), reached from the UI.
- Fix: No code change this run. Rule it: the correlations + suggested-weights block retires WITH the legacy score path (same seal as setupScoreMath.js); tier_performance stays (tier is live) but its `avg_score` cell goes with the sum.
- Ruling-recommendation: FOLD into the legacy-retirement program as its named server-side site; until then KEEP frozen (do not extend it with new sub-scores).

FINDING 6:
- Title: The archive chart envelope quotes only the legacy verdicts — no grade on the one surface that frames the chart
- File: webapp/backend/routers/archive_browse.py:258-273
- Principle: brief §1 (wire duplication / retirement mapping); EC-28 (a needed number is a backend serialization addition)
- Severity: P3
- What's wrong: `/setups/{id}/chart` serves `tier` and legacy `score` in its envelope but not `ta_grade`, so the chart payload's only verdict vocabulary is the retiring one. Post-retirement this envelope would speak exclusively in dead vocabulary.
- Consequence: Any consumer rendering verdicts from the chart envelope (rather than the row it already fetched) shows the legacy number with no V2 alternative; the asymmetry also makes the retirement diff touch a chart route that should have been verdict-neutral.
- Fix: Either add `ta_grade` beside the existing pair (one line, EC-28-clean — it is a resolved verdict) or drop both verdict cells from the envelope and let the row be the verdict source. Prefer the drop at retirement time.
- Ruling-recommendation: MERGE with the retirement diff — decide "envelope carries no verdicts" (preferred) or "carries both", but not the current legacy-only middle state.

FINDING 7:
- Title: scan_runs "kind" column back-compat branch is dead code re-checked on every status call
- File: webapp/backend/services/scan_status.py:15-17 (per-call PRAGMA), :20-44, :70-142 (no-kind branches); guaranteed-live by services/startup.py:14-26 (CREATE with kind + idempotent ALTER at every boot)
- Principle: brief census question ("two things answering the same question"); refactoring P5
- Severity: P3
- What's wrong: Every start_run/latest_run/recent_runs issues a PRAGMA table sniff and carries a duplicate no-kind SQL branch, but the boot migrations make the column existence unconditional on any DB this backend has ever booted against. Two writers and two readers for one schema, one of them unreachable in production.
- Consequence: Wasted work on the hottest poll path (the 60s scan-status tick) and a maintenance twin — a future column change must be made in four SQL strings instead of two.
- Fix: Delete the fallback branches and the per-call sniff; if paranoia is wanted, assert the column once at startup.
- Ruling-recommendation: DELETE the no-kind branch (the boot migration is the single source of schema truth).

FINDING 8:
- Title: `_parse_n_setups` is production-dead — a back-compat wrapper kept alive only by its own test
- File: webapp/backend/services/scan_runner.py:117-119; sole caller tests/test_fetch_repair.py:35,801-809
- Principle: brief census question; refactoring P5
- Severity: P3
- What's wrong: The wrapper exists purely so an old test import keeps resolving; every production caller uses `_parse_scan_result` directly.
- Consequence: A phantom second entry point into the scan-result parse — exactly the "two versions of one answer" shape this run is hunting, in miniature.
- Fix: Repoint the test at `_parse_scan_result` and delete the wrapper.
- Ruling-recommendation: DELETE.

FINDING 9:
- Title: Two unbounded process-lifetime caches in the calibration router on an always-on service
- File: webapp/backend/routers/calibration.py:206 (`_ENGINE_READS`), :305 (`_FRAME_PREVIEWS`)
- Principle: quality-backend P5 (resource lifecycle); every sibling cache in this backend is bounded (episode cache 32, frame cache 96, candle cache 64)
- Severity: P3
- What's wrong: Both dicts grow monotonically for the life of the NSSM service; `_ENGINE_READS` keys include the engine manifest hash, so entries from rotated manifests are never evicted, and each engine-read entry carries the full projection payload.
- Consequence: Slow memory growth across long calibration sittings and engine iterations between service restarts; invisible because nothing surfaces cache size.
- Fix: Give both the same small-bound treatment their siblings have (the existing VersionedCache is a drop-in shape for the previews; the engine-read memo can evict non-current-manifest keys on manifest change).
- Ruling-recommendation: FOLD onto the existing bounded-cache primitives — no new mechanism.

FINDING 10:
- Title: The calibration session candle cache can never cover a recent as-of — day-scrubbing recent marks refetches ~900 bars per step
- File: webapp/backend/services/candle_cache.py:47-52 (coverage test) with :137-140 (entry stores the frame's own index range)
- Principle: quality-backend P2 (the runtime cost is hidden); the module's own stated invariant ("one raw fetch per ticker per session") breaks
- Severity: P3
- What's wrong: The cache entry records the ACTUAL data range (last traded bar), but the chart route requests as_of+45 days; whenever that end lies beyond the last session — i.e., any mark within ~45 days of today — coverage fails, so every scrub step is a fresh vendor pull that overwrites the cache and never satisfies the next request either.
- Consequence: For the most common marking flow (recent charts), the cache is inert: repeated ~900-bar Yahoo pulls per scrub step, which is both the latency and the rate-limit pressure the cache exists to remove — the throttle path then kicks in and the operator sees "rate_limited" refusals mid-sitting.
- Fix: Store the requested window clamped to the fetch day (end = max(actual end, min(requested end, today))) as the coverage bound, not the frame's own last index.
- Ruling-recommendation: KEEP the cache design; fix the coverage bound.

FINDING 11:
- Title: Archive health/stats/calibration endpoints hydrate the full ORM row set — deep JSON columns included — to compute counts
- File: webapp/backend/routers/archive_calibration.py:89-99 (`/archive/health` loads every equities row twice-over), :48, :253 (`/stats`, `/calibration` via `_canonical_setups`)
- Principle: quality-backend P2 (event-loop/threadpool cost hidden); Performance seat overlap — flagged here for the pattern, quantification is theirs
- Severity: P3
- What's wrong: `db.query(SetupArchive).all()` materializes all ~9,438 rows with every column, including the unbounded TEXT cells (election_trace, event_map_episodes, story_admission_profile), to derive scalar counts and a max date. The episode path at least prunes to five columns for grouping, but the health endpoint's raw-row pass does not.
- Consequence: A health poll costs a full-archive hydration that grows ~140 rows/trading-day; the threadpool worker holding it stalls other requests as the archive scales.
- Fix: Select only the aggregated columns (source, scan_date, the two fwd_return cells) for the health/stat passes — the queries already exist in column-pruned form elsewhere in the same file family.
- Ruling-recommendation: FOLD onto the column-pruned read pattern `_build_grouping` already demonstrates.

FINDING 12:
- Title: Concordance reader is an N+1 join on its growth surface
- File: webapp/backend/services/concordance.py:28-40
- Principle: quality-backend P2; the docstring names this "the grade's future ground-truth harvest" — i.e., it is designed to grow
- Severity: P3
- What's wrong: One archive SELECT per verdict row. Harmless at today's verdict count; linear vendor of small queries on a surface whose whole purpose is to accumulate operator verdicts over months.
- Consequence: The concordance view slows in proportion to exactly the success of the harvesting program it serves.
- Fix: Batch the archive lookups on the identity triples (one IN-query chunked like `_rows_by_ids`), keyed back per verdict.
- Ruling-recommendation: KEEP semantics (orphans surfaced, mismatches flagged) — batch the read only.

FINDING 13:
- Title: The one async route does synchronous disk writes on the event loop
- File: webapp/backend/routers/journal.py:180-237 (upload_attachment)
- Principle: quality-backend P2 (event-loop blocking; sync I/O in async context)
- Severity: P3
- What's wrong: This is the backend's single `async def` handler (everything else is deliberately sync-in-threadpool), and it opens/writes the upload file synchronously between awaited reads. Up to 10MB of 64KB sync writes run on the same loop that serves the SSE streams.
- Consequence: Brief SSE/latency stalls during uploads on a slow disk; more importantly it is the lone exception to the codebase's own "sync handlers, threadpool" rule, in the wrong direction.
- Fix: Make it a sync `def` handler using the non-async file API (UploadFile's underlying SpooledTemporaryFile reads work sync), returning it to the threadpool like every sibling route.
- Ruling-recommendation: FOLD to the house pattern (sync handler); do not introduce aiofiles.

FINDING 14:
- Title: Two idioms for the naive-UTC stamp, one of them deprecated
- File: webapp/backend/routers/journal.py:98,137,246; services/auto_import.py:104; ibkr/mapping.py:95-97 (all `datetime.utcnow()`), vs the house helper shape at services/watchlist_ledger.py:48-50
- Principle: refactoring P4 (inconsistent vocabulary); `utcnow` is deprecated on the venv's Python and slated for removal
- Severity: P3
- What's wrong: The codebase's ruled stamp is "naive UTC via now(timezone.utc)" (watchlist_ledger documents why); six call sites still use the deprecated spelling, which will warn today and break on a future interpreter bump.
- Consequence: DeprecationWarnings now; a mechanical breakage risk later; and two spellings of one fact invite a future timezone drift.
- Fix: Point all six at one shared `_utc_now`-style helper.
- Ruling-recommendation: FOLD to the one helper.

---

## Clean checks (looked for, not found)

- EC-28 server-side: no scoring cap, threshold, fire-rule, or chapter membership re-declared anywhere in webapp/backend/ — every verdict is quoted from the artifact, the archive row, or a stored snapshot. The health-board type contract actively enforces the ban.
- Scan subprocess: UTF-8 forcing intact on all three subprocess sites (scan_runner, /analysis, /update-returns) — keep. Child-termination on client disconnect (GeneratorExit) is handled correctly, with the run-record relabel guard.
- SQLite discipline: every direct `SessionLocal()` use closes in finally; scan_status uses engine-level transactions; WAL + busy_timeout pragmas correct; the deleted-ORM-instance access in delete_mark was tested and is safe on this SQLAlchemy (deleted instances keep loaded attributes).
- Scheduler: America/New_York, misfire grace, boot catch-up, and the watchdog's hung/stale/absent legs are all coherent; maturation is its own recorded run per EC-21.
- IBKR: read-only structurally (order APIs replaced with hard failures per instance), live gate is per-click and unpersisted, boot is broker-free. Not flagged: all known-intentional items per the brief.
- Known-intentional respected: sync handlers, scheduler TZ, threadpool routers — not flagged.
