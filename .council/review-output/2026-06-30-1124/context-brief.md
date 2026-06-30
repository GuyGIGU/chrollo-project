## Context Brief for Council Review

**Review question (from the user):** This is an ARCHITECTURE-VERDICT review, not a line hunt. The
multi-universe screener feature is mature (all 10 build tasks shipped) but has now absorbed THREE
rounds of fixes at its seams. The Chair needs each expert to answer, in their domain: **is the
`universe_type` architecture sound (→ keep fixing surgically) or is it accumulating the kind of
cross-cutting inconsistency that signals a deeper refactor/rebuild?** Flag the structural verdict
explicitly where your domain bears on it.

### What this code does
The deterministic Wyckoff/VCP screener engine (`core/`) now runs over THREE universes — US Stocks,
US Sectors+Market (SPDR ETFs), Commodities+ETFs — plus a top-down ETF→equities drill-down. Each
universe is one immutable `Universe` descriptor (`core/pipeline/universe.py`) that owns its ticker
source, market-data parquet cache, cache-meta json, market-context json, dashboard artifact, regime
index set, and an archive tag `universe_type` ("us_equities" / "us_sectors" / "commodities_etf").
`universe_type` is part of the archive identity key (3-col unique: ticker, scan_date, universe_type),
so the same ticker can be both an ETF and a stock setup on one date without colliding.

### Architecture
- **Descriptor** `core/pipeline/universe.py`: registry built per-call (settings read at call time to
  dodge the config-vs-cwd shadowing trap); paths anchored to project root, never cwd; `resolve_universe`
  is a closed-set allowlist (unknown key → ValueError). NOTE the deliberate vocabulary split: the
  default universe's `key` is `us_stocks` but its `universe_type` is `us_equities` (the other two match).
- **Cache lifecycle** `core/pipeline/downloads.py` (`fetch_data`: fresh→current→incremental→cold paths,
  split-drift probe, latest-session repair, deep-history depth guard), `scan_job.py` (orchestration +
  archive freshness gate), `market_data_health.py` (health classifier), `data_freshness.py` (shared
  coverage/depth predicates), `cache.py` (`_cache_paths(universe)`, atomic parquet write), `file_lock.py`
  (cross-process re-entrant lock), `scan_metrics.py`, `market_context.py` (ETF universes BORROW broad
  regime from the US-Stocks run).
- **Archive identity/scoping** `webapp/backend/archive_models.py` (SetupArchive + 3-col unique),
  `core/archive/writer.py` (universe-aware writer), `core/archive/episodes.py` (gap-and-islands episode
  grouping — now keyed on universe_type), `core/backtest/loader.py` (read-only archive→episodes),
  `webapp/backend/services/archive_queries.py` (the `_apply_setup_filters` default-equities scope +
  per-(filter,version) episode cache), `routers/archive_browse.py` / `archive_calibration.py` (serving),
  `services/engine_edge.py` (us_equities-pinned edge metric), `tools/backtest_engine.py` (offline twin),
  `services/startup.py` (the one-time universe_type migration).
- **Serving / frontend** `routers/screener.py`, `hooks/useScreenerData.js`, `components/ScreenerGrid.jsx`,
  `UniverseSwitcher.jsx`, `ScreenerToolbar.jsx`.

### Stack in use
Python 3.11 engine + FastAPI/Pydantic backend; SQLite via SQLAlchemy (archive) + parquet market cache;
pandas/numpy; React 19 + Vite SPA; yfinance (pinned). No web auth (local single-user lab). No LLM in
product — engine is deterministic, byte-parity across refactors is a HARD requirement.

### Key observations
- **This is the THIRD pass over the same seam.** (1) Council review `2026-06-30-0041` found 15 issues
  (1 P1: download-path universe-blindness corrupting the US-Stocks cache; + migration-guard, edge-twin,
  fetch races, filter persistence). Those are RESOLVED in commits `e8da04f` + `39766b6` — **do NOT
  re-flag the 15 prior findings.** (2) A follow-up adversarial pass produced 13 more surgical fixes,
  applied UNCOMMITTED in the current working tree (loader cross-universe merge, duplicate-column cache
  crash, universe-inconsistent archive queries, browse scoping, archive_health scope-mix, scan_job
  helper extraction, cold-fetch depth chokepoint, scan_metrics per-universe lock, shared depth predicate,
  ScreenerToolbar label). (3) An independent adversarial verification of THOSE fixes just caught a real
  NaN-coercion bug (pandas reads SQL NULL as `np.nan`, which is truthy → leaked the literal "nan" into an
  episode key) — now fixed with `_clean_cell` + regression tests.
- **REVIEW THE CURRENT WORKING TREE**, not git HEAD — the latest fixes are uncommitted.
- **The recurring theme** the user is worried about: every round, the `universe_type` seam leaks at a
  different boundary (cache write, archive scoping, episode identity, health scope, metadata lock). The
  question is whether that's an inherently leaky design (rebuild signal) or just edges being closed one
  by one (normal hardening of a sound design). Fowler and Leach and McKinney are the load-bearing seats.
- **Specific structural smells worth a verdict:** (a) the `us_stocks` key vs `us_equities` universe_type
  split (prior P3 #13, still present — does it keep causing scoping bugs?); (b) the equities-default
  scope is enforced in MANY independent places (`_apply_setup_filters` default, `_latest_episode_first_seen`,
  `archive_health`, `engine_edge`, `backtest_engine`, `loader`) — is "equities-only" a cross-cutting
  concern that should be centralized rather than re-pinned per call site? (c) the depth/coverage/scope
  predicates were just de-duplicated into shared helpers — are there MORE such twins still duplicated?

### Automated check results
- **pytest: 604 passed** (full suite incl. seed-recall + shadow baselines — engine output unchanged).
- **compileall** (core / webapp/backend / tools): clean.
- Frontend eslint not run this round (frontend changes are 1-line label + prior-review items already merged).
- No pre-existing failures.

### Domain File Assignments

**Hunt (Security):** `core/pipeline/universe.py` (closed-set key allowlist, project-root path anchoring,
`drilldown_map` JSON load), `core/pipeline/cache.py` (cache path handling, atomic write), `core/pipeline/downloads.py`
(parquet read/write, yfinance ingestion), `core/pipeline/providers.py`, `webapp/backend/services/startup.py`
(migration SQL — RENAME/CREATE/INSERT…SELECT), `webapp/backend/archive_models.py`.

**Dodds (Frontend):** `webapp/frontend/src/hooks/useScreenerData.js`, `webapp/frontend/src/components/ScreenerGrid.jsx`,
`webapp/frontend/src/components/UniverseSwitcher.jsx`, `webapp/frontend/src/components/ScreenerToolbar.jsx`.

**Ramírez (Backend):** `webapp/backend/routers/screener.py`, `webapp/backend/routers/archive_browse.py`,
`webapp/backend/routers/archive_calibration.py`, `webapp/backend/services/archive_queries.py`,
`webapp/backend/services/engine_edge.py`, `webapp/backend/services/startup.py`, `core/pipeline/scan_job.py`,
`core/pipeline/scan_metrics.py`.

**Leach (Data Integrity):** `webapp/backend/archive_models.py` (3-col unique, type affinity, nullability),
`core/archive/writer.py`, `core/archive/episodes.py`, `core/backtest/loader.py`, `webapp/backend/services/startup.py`
(migration safety on a live SQLite archive), `core/pipeline/cache.py` (parquet atomicity/schema drift),
`core/pipeline/downloads.py` (parquet write integrity, duplicate-column shape), `core/pipeline/market_data_health.py`.

**Performance (Pipeline):** `core/pipeline/downloads.py` (cold/incremental fetch, repair batching, depth scan),
`core/pipeline/scan_job.py` (sequential per-universe scans), `core/pipeline/screener.py`, `core/pipeline/market_context.py`
(ETF regime borrow), `webapp/backend/services/archive_queries.py` (episode grouping over the whole table),
`webapp/frontend/src/components/ScreenerGrid.jsx` (card-wall render).

**Saarinen (UI Quality):** `webapp/frontend/src/components/UniverseSwitcher.jsx`, `webapp/frontend/src/components/ScreenerGrid.jsx`,
`webapp/frontend/src/components/ScreenerToolbar.jsx`.

**Friedman (UX Quality):** `webapp/frontend/src/components/ScreenerGrid.jsx`, `webapp/frontend/src/components/UniverseSwitcher.jsx`,
`webapp/frontend/src/components/ScreenerToolbar.jsx`, `webapp/frontend/src/hooks/useScreenerData.js`.

**Fowler (Refactoring) — LEAD SEAT for the verdict:** `core/pipeline/universe.py`, `core/pipeline/cache.py`,
`core/archive/episodes.py`, `core/backtest/loader.py`, `webapp/backend/services/archive_queries.py`,
`core/pipeline/scan_job.py`, `core/pipeline/downloads.py`, `core/pipeline/market_data_health.py`,
`core/pipeline/data_freshness.py`, `core/pipeline/scan_metrics.py`, `core/pipeline/market_context.py`,
`core/pipeline/screener.py`, `webapp/backend/services/engine_edge.py`, `tools/backtest_engine.py`,
`webapp/backend/routers/archive_browse.py`, `webapp/backend/routers/archive_calibration.py`.

**McKinney (Numerical):** `core/archive/episodes.py` (gap-and-islands, busday_count), `core/backtest/loader.py`
(NaN/dtype coercion of archive cells), `core/pipeline/market_context.py` (ETF borrow as-of / lookahead guard),
`core/pipeline/data_freshness.py` (deep_history_ratio, coverage, history_too_shallow), `core/pipeline/downloads.py`
(split-drift probe, latest-session merge), `core/pipeline/market_data_health.py` (classify thresholds).

**Beck (Test Quality):** `tests/test_loader_universe_filter.py`, `tests/test_episodes.py`,
`tests/test_universe_migration.py`, `tests/test_universe_descriptor.py`, `tests/test_market_context_universe.py`,
`tests/test_providers.py`, `tests/test_scan_metrics.py`, `tests/test_backend_services.py`,
`tests/test_market_data_health.py`, `tests/test_backtest_engine.py`, plus the source files they cover.
