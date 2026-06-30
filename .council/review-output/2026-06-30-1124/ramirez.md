# Ramírez — Backend Quality Review (multi-universe screener seam)

## Domain Verdict

From the backend lane the `universe_type` architecture is **sound and the seam-closing is normal hardening, not a rebuild signal** — but the equities-default scope has crossed the line into a genuine cross-cutting concern that should be *named once and depended on*, not re-derived per call site. The async/error/streaming discipline is good: every DB-touching route is plain `def` (correctly threadpooled, never blocking the loop), the SSE scan/eval/download routes are plain `def` driving subprocesses with `invalidate_screener_cache()` in `finally`, the engine-edge tile is deliberately `def` + TTL-cached + NaN-scrubbed before JSON, and the migration rebuild is transactional with a row-count drift guard. The descriptor (`default_universe().universe_type`) is the *intended* single source for the `us_stocks`-key↔`us_equities`-type duality, and `engine_edge` consumes it correctly. The problem is that the OTHER scope pins do **not** route through that source: `_apply_setup_filters` hardcodes the string default `"us_equities"`, `_grouped_episodes` re-hardcodes it in a `setdefault`, `archive_health` hardcodes it in a raw `.filter(...)`, `_latest_episode_first_seen` hardcodes it again, and `_resolve_universe_type` in the router hardcodes it a fourth time. Five independent string literals encode one policy. That's not leaky-by-design — the identity key is clean and the writers are universe-aware — it's a missing *named constant / scope helper*. The risk is the next universe (or a renamed type) leaving one literal behind, exactly the class of "scope-mix" bug the last two rounds chased. So: keep fixing surgically, but the surgical fix worth doing now is **centralize the equities-scope policy into one symbol** (the descriptor's `universe_type` + a single `default_scope()` the read surfaces call), retiring the scattered literals. Below are the concrete backend findings.

---

FINDING:
- Title: Equities-default scope is a cross-cutting policy re-pinned as a bare string literal in 5 places
- File: webapp/backend/services/archive_queries.py:26, webapp/backend/services/archive_queries.py:117, webapp/backend/services/archive_queries.py:161, webapp/backend/routers/archive_browse.py:29-34, webapp/backend/routers/archive_calibration.py:88-90
- Principle: Principle 4 — keep `core/` pure, keep routes thin (service-layer single-source); reinforced by Principle 5 (config accessed N different ways)
- Severity: P2
- What's wrong: The string `"us_equities"` is the load-bearing scope default in `_apply_setup_filters`, re-asserted in `_grouped_episodes.setdefault`, re-asserted in `_latest_episode_first_seen.filter`, re-asserted in the router's `_resolve_universe_type`, and re-asserted again in `archive_health`'s raw query — five independent literals for one policy, none deriving from `default_universe().universe_type` the way `engine_edge` correctly does.
- Consequence: A renamed universe_type or an added 4th universe leaves one site behind, silently re-introducing the exact "ETF rows pooled into the equities population" scope-mix this round closed.
- Fix: Introduce one scope symbol (e.g. a `DEFAULT_ARCHIVE_SCOPE` sourced from `default_universe().universe_type`, plus a single helper the read surfaces call) and replace every literal with it, so the policy has one definition.

FINDING:
- Title: `missed-winners` relies on an implicit default for scope while siblings pin it explicitly — silent inconsistency
- File: webapp/backend/routers/archive_reviews.py:128 (via services/archive_queries.py:117 `_grouped_episodes.setdefault`)
- Principle: Principle 3 — empty/implicit as a silent contract; Principle 4 — logic that can drift between sibling call sites
- Severity: P3
- What's wrong: `missed_winners_report` calls `_episode_context(db, source=source)` with no `universe_type`, depending entirely on the `setdefault("us_equities")` deep inside `_grouped_episodes`, whereas `archive_health` and `_latest_episode_first_seen` pin the same scope explicitly at the call site — so two surfaces that must agree express the same invariant in two different ways.
- Consequence: A future refactor that "cleans up" the `setdefault` (it reads like a cache-key detail, not a domain default) would silently widen missed-winners to all universes while the explicitly-pinned surfaces stay scoped, re-creating cross-surface disagreement.
- Fix: Make the equities scope explicit at the `missed-winners` call site (pass the scope symbol), so no read surface's scope is implied by a helper's internal default.

FINDING:
- Title: `sort_by` query param reaches `getattr(SetupArchive, sort_by, ...)` with no whitelist
- File: webapp/backend/routers/archive_browse.py:64-65, webapp/backend/routers/archive_browse.py:118-120
- Principle: Principle 3 — validate at the boundary with Pydantic (the model is the tripwire)
- Severity: P3
- What's wrong: `sort_by`/`sort_dir` are accepted as free `str` and fed to `getattr(SetupArchive, sort_by, SetupArchive.scan_date)` (rows) and `getattr(e, sort_by, None)` (episodes); the fallback prevents an outright crash, but an arbitrary attribute name (e.g. a relationship/hybrid/dunder) can resolve to a non-orderable attribute and raise inside the ORM `order_by` rather than 422 at the edge.
- Consequence: A malformed `sort_by` produces a 500 with a SQLAlchemy/internal traceback instead of a clean 422, and the contract of "sortable columns" lives nowhere explicit.
- Fix: Constrain `sort_by`/`sort_dir` to an enum/`Literal` of the actual sortable columns (Pydantic `Query(..., pattern=...)` or a `Literal[...]`), failing unknown values at the boundary.

FINDING:
- Title: PATCH `/setups/{id}/label` commits without rollback on failure
- File: webapp/backend/routers/archive_browse.py:285-299
- Principle: Principle 6 — resource cleanup on the error path (DB session left dirty); Principle 1 — operational-vs-programmer error discipline
- Severity: P3
- What's wrong: `update_label` mutates the ORM row and calls `db.commit()`/`db.refresh()` with no `try/except` to `db.rollback()`; if the commit raises (constraint, locked DB), the request-scoped session is left in a failed-transaction state and the exception propagates raw.
- Consequence: A failed write leaks an inconsistent session for that request and surfaces a raw DB error to the client instead of a curated response; under SQLite "database is locked" this is the most likely real failure.
- Fix: Wrap the mutation+commit in `try/except` that rolls back and raises a curated `HTTPException`, or centralize rollback in the `get_db` dependency's `finally`/`except`.

FINDING:
- Title: `_resolve_universe_type` default duplicates the route's `Query` default — two defaults, one of which is dead but misleading
- File: webapp/backend/routers/archive_browse.py:22-34, webapp/backend/routers/archive_browse.py:48-50, webapp/backend/routers/archive_browse.py:80-82
- Principle: Principle 5 — configuration/default accessed more than one way
- Severity: P3
- What's wrong: The `/setups` and `/episodes` routes declare `universe_type: Optional[str] = Query("us_equities", ...)`, so the param is never `None` from a normal request; yet `_resolve_universe_type` *also* defaults `None → "us_equities"`. The `None` branch is effectively dead via these routes, so the real default is encoded twice (Query string + helper branch) and could diverge.
- Consequence: A maintainer changing the default in one place (e.g. the Query to `None` to mean "all") would get behavior governed by the *other* default, producing a surprising scope.
- Fix: Pick one home for the default — either default the `Query` to `None` and let `_resolve_universe_type` own the equities default, or keep the Query default and drop the helper's `None→equities` mapping — so the default has a single definition.

---

### Notes on things checked and found sound (not findings)

- **Async correctness (Principle 2):** All archive/screener/calibration/engine-edge routes are plain `def` → Starlette threadpools them; no CPU-bound pandas or blocking SQLAlchemy runs on the event loop. `engine_edge.py:40` even documents the deliberate `def` choice. The heavy `import pandas`/`daily_candle_frame` in the chart route are lazy and threadpooled. Clean.
- **Streaming cleanup (Principle 6):** `run-scan-stream` / `run-evaluation-stream` wrap the generator in `try/finally: invalidate_screener_cache()`; the scan lock + subprocess reaping live in `scan_runner` (out of scope here) but the router half is correct.
- **Config-vs-cwd trap (Principle 5):** `scan_job.py`'s module-level `from config import settings` is safe — `scan_job` runs only in the scan **subprocess** (cwd = repo root), never imported at backend boot (the backend launches `run_screener.py` as a subprocess via `scan_runner`, confirmed). `archive_calibration.py:324-330` correctly loads root `config/settings.py` by explicit file path via `importlib` to dodge the shadow. No boot-crash exposure.
- **Pydantic boundary:** `EarningsBatchIn`, `LabelUpdate`, `ReviewToggleIn/MarkIn`, `ManualSetupIn` are real models; `SetupOut`/`EpisodeOut`/`EngineEdgeResponse` are explicit response projections with `from_attributes`, so the ORM row is never returned raw and NaN can't leak (engine_edge `_finite` scrubs before JSON). Good.
- **scan_metrics per-universe lock:** `persist_scan_metrics` re-takes the per-universe `cache_lock` around the meta read-modify-write and writes the same file it locks, correctly closing the post-fetch clobber window; the history append goes to a separate append-only file. Runs in the engine path, not an async route. Sound.
- **Migration:** transactional rebuild (isolation_level=None + explicit BEGIN), pre-backup, row-count drift guard, idempotency keyed on column AND 3-col-unique presence — solid; depth is Brandur's/Leach's lane.
