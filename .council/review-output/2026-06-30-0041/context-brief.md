## Context Brief for Council Review

### What this code does
The **multi-universe screener**: runs the existing deterministic Wyckoff/VCP/LPS engine over THREE universes (US Stocks [existing], US Sectors+Market, Commodities+ETFs) instead of one, with a frontend universe switcher and a top-down "firing ETF → related US-stock setups" drill-down. Commits 0a4f43b..7c6111e on branch feat/cockpit-and-chart-fidelity.

### Architecture
- **Universe descriptor** (`core/pipeline/universe.py`, NEW): one immutable `Universe` dataclass (key, label, universe_type, ticker_source, ticker_csv, cache/meta/market_context/artifact filenames, index_symbols) + closed-set `resolve_universe()` (None→us_stocks default; unknown key raises = allowlist) + `all_universes()` (stocks-first) + `drilldown_map()` (reads config/commodity_equity_map.json). Paths anchor to project root; settings read at CALL time (config-vs-cwd shadow-safe). Registry rebuilt per call.
- **Scan path threaded with `universe`:** cache._cache_paths, screener.run_screener/_prepare_ticker_frames/_read_cached_market_data, scan_job.run_scan_and_export + run_all_universe_scans (sequential, stocks-first, failure-isolated), output/dashboard.generate_dashboard (artifact path). US-Stocks default resolves to EXACT prior literals → byte-identical.
- **ETF market context** (`core/pipeline/market_context.py`): `get_market_context(universe=)` early-branches for ETF universes → breadth NEUTRALIZED (breadth_pct=None → _ramp 0 bonus); SPY-6m + regime BORROWED from the broad US-Stocks context ONLY when the as-of session matches (lookahead guard), else neutral; per-universe context cache; `context_basis` tag. US-Stocks path verbatim.
- **Serving** (`webapp/backend/routers/screener.py`): `GET /screener-data/?universe=` validated via resolve_universe (422 on unknown, never builds a path from the value); default us_stocks; `never_scanned` sentinel ≠ empty; `GET /screener-data/drilldown/?etf=` resolves sector ETFs via each setup's sector_etf and commodity/thematic via the curated map, intersected with the latest us_stocks scan. `services/screener_data.py` cache re-keyed per artifact path.
- **Archive migration** (`webapp/backend/services/startup.py` + `archive_models.py`): SetupArchive gained `universe_type` (NOT NULL, server_default 'us_equities', CHECK closed-set), UNIQUE widened to (ticker,scan_date,universe_type) + index. `migrate_universe_type()` = one-off SQLite table rebuild (rename→create-from-model→INSERT…SELECT backfill→drop old), transactional (raw sqlite3, isolation_level=None + explicit BEGIN), checkpoint+file-backup first, row-count-verified, idempotent, wired BEFORE the ADD-only auto-migrator. ALREADY APPLIED LIVE to trading_journal.db (2775 rows preserved; backup at trading_journal.db.premigration.bak).
- **Writer** (`core/archive/writer.py`): archive_scan_results(universe=) stamps universe_type + includes it in the upsert filter_by; ETF archiving enabled in scan_job. **Edge population** (`core/backtest/loader.py` + `services/engine_edge.py`): load_archive/load_episodes gained a universe_type filter; engine_edge pins universe_type='us_equities' so ETF screener rows don't contaminate the stock edge metric.
- **Frontend:** useScreenerData(universe) (URL-driven via ?u=, per-universe payload cache, explicit status loading/ready/empty/never_scanned/error), UniverseSwitcher.jsx (segmented control, Signal-Blue active), ScreenerGrid.jsx (switcher + status-driven empty states + DrilldownView + modal threading), ScreenerCard.jsx (optional "Members →" drill affordance on ETF cards).

### Stack in use
Python 3.11 engine + FastAPI/Pydantic + SQLAlchemy/SQLite + parquet + pandas/numpy. React 19 + Vite SPA (no Next, no Tailwind; lightweight-charts + recharts; CSS vars). yfinance pinned. No web auth.

### Key observations
- PRIME DIRECTIVE held: US-Stocks engine output byte-identical (shadow_diff --check + seed_recall --check green throughout the session). The default-universe path is the prior code unchanged.
- The migration is irreversible-class and ALREADY LIVE; the review is post-hoc on that code (rehearsed on an online-backup copy first, which caught an index-name-collision bug before live).
- The serving + drilldown endpoints take user-supplied params (universe, etf) — the universe is allowlist-validated via resolve_universe; etf is a length-bounded dict key.
- ETF universes draw from curated CSVs (config/tickers_*.csv) with ticker_source="csv" (no FTP/admission). The commodity→equity map (config/commodity_equity_map.json) is a seeded starter.

### Automated check results
- compileall (core, webapp/backend, output, run_screener.py): PASS (exit 0).
- pytest -q: running fresh this phase; prior run minutes ago (no code change since): 590 passed. shadow_diff --check PASS (31 firing, no drift). seed_recall --check PASS (recall 54.5% = baseline). (Confirm fresh pytest green before trusting.)
- Frontend: `npm run build` green this session (812 modules).

### HARD CONSTRAINTS (do NOT review / out of scope)
- Owner WIP files — OFF LIMITS: core/structure/metrics.py, tests/test_market_structure.py, tools/l2_staircase_audit.py, tools/l2_staircase_render.py, tools/fidelity/l2/.
- Parked separate feature — OUT OF SCOPE: webapp/frontend/src/components/home/ActionCenter.jsx + the uncommitted HomeView.jsx / WatchlistZone.jsx / index.css edits.
