# Council Review: Multi-Universe Screener

**Scope:** commits `0a4f43b..7c6111e` on `feat/cockpit-and-chart-fidelity` — the 3-universe screener (descriptor, ETF universes + context sourcing, serving endpoint, switcher, orchestration, drill-down, archive migration + universe-aware writer). WIP files and the parked ActionCenter were out of scope.
**Context:** The existing deterministic engine now runs over US Stocks / Sectors+Market / Commodities+ETFs. Prime directive held: US-Stocks engine OUTPUT stayed byte-identical (shadow + seed_recall green). The review's sharpest finding is that the live US-Stocks cache STATE — separate from engine output — is being corrupted by the ETF scans.
**Council dispatched:** Hunt (no findings — surfaces closed), Dodds (4), Ramírez (2), Leach (2), Performance (3), Saarinen (2), Friedman (2), Beck (3), Fowler (2), McKinney (1). 21 raw → 15 after dedup/Carmack-filter.
**Automated gates:** pytest 588 passed; compileall clean; build green; shadow + seed_recall green.

---

## P1 — Fix Now

### 1. Download-mode ETF scans read/write the US-Stocks market-data cache (confirmed on disk)

| | |
|---|---|
| **File** | `core/pipeline/screener.py:163-164` (download path) → `core/pipeline/downloads.py` `fetch_data` / `_cache_paths()` |
| **Council** | Pipeline Performance × Carmack — Resource lifecycle / config-vs-cwd trap (Principle 5) |
| **Ref** | `references/quality-backend.md` → P5 |

**Finding:** `run_screener` threads the universe into the cache-READ path (`_read_cached_market_data(tickers, uni)`) but the download path is `get_provider().fetch(tickers)` → `fetch_data` → `_cache_paths()` with **no universe**, so it always resolves to the US-Stocks parquet + `cache_meta.json`. The scheduled scan runs `--all-universes` in download mode, so every ETF universe fetch reads/rewrites the US-Stocks cache. **Verified:** `market_data_cache_5y.parquet` now contains `GLD` (a commodities-universe ETF, which is filtered OUT of the stock universe), no `market_data_cache_5y_us_sectors/commodities_etf.parquet` exist, and `cache_meta.json`'s `last_full_refresh` is stamped from the ETF test runs.

**Consequence:** The US-Stocks cache's freshness / fetch-health / scan_metrics metadata is overwritten by 13–29-ticker ETF fetches, so the next US-Stocks incremental/repair/observability decision runs off polluted state; ETF tickers leak into the stock parquet; the per-universe ETF caches never materialize (a later `--cached` ETF scan raises `CachedMarketDataError`). The scheduled `--all-universes` run repeats this daily. Engine byte-parity output is unaffected (it runs on a frozen fixture), but trusted live state is corrupted.

**Fix:** Thread `universe` through the download write path — give `fetch_data` (and `_prepare_fetch_scope`/`_symbols_with_indexes`) a universe argument, pass `uni.cache_paths()`, and forward `uni` from `run_screener`/the provider so each universe reads+writes only its own `cache_filename`/`cache_meta_filename`. This one fix also resolves findings 9 and 10 (redundant SPY/QQQ re-pull; borrow-session desync). After fixing, re-pull the US-Stocks cache to evict the leaked ETF tickers.

---

## P2 — Fix Soon

### 2. Scheduled `--all-universes` scan silently masks a stale/failed primary US-Stocks run

| | |
|---|---|
| **File** | `core/pipeline/scan_job.py` `run_all_universe_scans` + `run_screener.py` + `webapp/backend/services/scan_runner.py:262` |
| **Council** | Sebastián Ramírez × Carmack — Operational vs programmer errors; alert on degraded (P1+P7) |
| **Ref** | `references/quality-backend.md` → P1, P7 |

**Finding:** `run_all_universe_scans` catches `StaleMarketDataError`/`Exception` per universe and returns `None` without re-raising, so the `--all-universes` subprocess always exits 0; the scheduled run records `status='ok'`, `n_setups=0` even when the **primary** US-Stocks scan was stale or crashed. The prior single-universe path re-raised → non-zero exit → `stale_data` → alert fired.

**Fix:** In `run_all_universe_scans`, track the primary (us_stocks) outcome and propagate it to the process exit / `SCAN_RESULT_JSON` (re-raise on a stale/failed primary, or emit a status the runner maps to `stale_data`/`failed`) so the scheduled status + alert reflect the primary run as before.

---

### 3. Manual scan/refresh is hardwired to US-Stocks — ETF universes are scheduler-only and always read "ready"

| | |
|---|---|
| **File** | `webapp/backend/services/scan_runner.py:226-238`; `webapp/frontend/src/hooks/useScanRunner.js:55,67`; `webapp/backend/routers/screener.py` (status) |
| **Council** | Vitaly Friedman + Sebastián Ramírez + Kent C. Dodds × Carmack — Trust compounds / None-as-silent-success / server-state |
| **Ref** | `references/quality-ux.md` → P9 · `references/quality-backend.md` → P3 |

**Finding:** The manual SSE jobs spawn `run_screener` with no `--universe`/`--all-universes`, so they only regenerate the US-Stocks artifact; and `useScanRunner` refetches `fetchScreener()` (defaults to us_stocks) regardless of the on-screen universe. So an ETF universe can't be scanned OR refreshed from the UI, and `get_screener_data` reports `status='ready'` for any universe whose artifact merely exists, with no age signal. (Friedman rated this P1 as a trust dead-end; downgraded to P2 because the scheduler is the intended refresh path.)

**Fix:** Thread the active universe through `useScanRunner`'s `fetchScreener` calls so a post-scan refresh repopulates the visible universe; either add a manual per-universe scan path or hide Evaluate/Download on ETF universes; and carry the artifact mtime/age in `get_screener_data` so the UI can distinguish a fresh "ready" from a stale one.

---

### 4. Migration idempotency guard checks the column, not the constraint — an out-of-band ADD COLUMN defeats the rebuild forever

| | |
|---|---|
| **File** | `webapp/backend/services/startup.py:255-259` (with `core/archive/writer.py` `_ensure_new_columns`, `core/archive/forward_returns.py`) |
| **Council** | Brandur Leach × Carmack — Migrations are production operations (P3) |
| **Ref** | `references/quality-postgres.md` → P3 |

**Finding:** `migrate_universe_type` returns early if the `universe_type` column merely exists. But two non-backend entry points (the scan writer's `_ensure_new_columns` and the forward-returns model-derived ADD pass) add `universe_type` as a plain nullable column WITHOUT the 3-col UNIQUE or CHECK. If a scan/forward-return job touches a pre-migration DB before the backend boots, the rebuild is then skipped permanently.

**Fix:** Make the guard verify the actual identity (presence of `uq_ticker_scan_date_universe` / the 3-col unique), not just the column name — so a column added out-of-band still triggers the rebuild. (Not a risk on the already-migrated live DB, but a landmine for a fresh-from-old-backup or a dev DB.)

---

### 5. Standalone-edge backtest harness still ingests ETF setups (the offline twin of the edge filter)

| | |
|---|---|
| **File** | `tools/backtest_engine.py:459` (consumes `core/backtest/loader.py`) |
| **Council** | Brandur Leach × Carmack — Queries explicit about what they fetch (P4) |
| **Ref** | `references/quality-postgres.md` → P4 |

**Finding:** ETF universes now archive under `source='screener'`. `engine_edge.py` was correctly pinned to `universe_type='us_equities'`, but the offline backtest harness calls `load_episodes(source=source)` without the universe filter, so its population absorbs ETF setups.

**Fix:** Pass `universe_type='us_equities'` to `load_episodes` in `tools/backtest_engine.py` (or add a `--universe-type` flag defaulting to us_equities), mirroring the `engine_edge.py` pin. Keeps the calibration ground-truth population stock-only.

---

### 6. Universe-switch fetch race can stamp the wrong status onto the new universe

| | |
|---|---|
| **File** | `webapp/frontend/src/hooks/useScreenerData.js:48-52` |
| **Council** | Kent C. Dodds × Carmack — Make impossible states unrepresentable (P3) |
| **Ref** | `references/quality-frontend.md` → P3 |

**Finding:** On resolve, `fetchScreener` writes the payload into a per-universe cache key (data is safe) but then calls `setStatus(deriveStatus(data))` unconditionally, with no check that the resolved request's universe still matches the selected one. A slow fetch for A resolving after a switch to B forces B's status from A's data.

**Fix:** Capture the request's target universe and only apply `setStatus` when it still equals the latest requested universe (a ref or per-request token), mirroring how the data write is already keyed.

---

### 7. Drill-down fetch has no staleness guard and duplicates the screener's fetch/status model

| | |
|---|---|
| **File** | `webapp/frontend/src/components/ScreenerGrid.jsx:30-45` |
| **Council** | Kent C. Dodds + Martin Fowler × Carmack — Structural async error handling / twin code paths (P6, P5) |
| **Ref** | `references/quality-frontend.md` → P6 · `references/refactoring.md` → P5 |

**Finding:** `openDrilldown` fires a bare fetch with hand-rolled loading/error/basis sentinels inline in the grid, unconditionally `setDrilldown` on resolve — no abort, no check the drilldown is still active. Clicking Back then having the stale fetch land re-opens the view; clicking ETF A then B can paint A under B's header. It's also a second fetch-status-render path separate from `useScreenerData`'s status machine, so the two will drift.

**Fix:** Extract a small `useDrilldown` hook mirroring `useScreenerData`'s status model; tag each request (etf/id) and only apply state when the resolved request is still current (optionally an AbortController).

---

### 8. Screener filters silently persist across a universe switch, faking a "no matches" empty state

| | |
|---|---|
| **File** | `webapp/frontend/src/components/ScreenerGrid.jsx:29-32` (with `hooks/useScreenerFilters.js`) |
| **Council** | Vitaly Friedman × Carmack — Design all five screen states (P2) |
| **Ref** | `references/quality-ux.md` → P2 |

**Finding:** `handleUniverseChange` resets only the page; tier/setup/tag/search/sort carry over with no universe binding. A tag/setup that exists in US Stocks need not exist in Commodities+ETFs, and a stale WATCHLIST tier filter applies to the new universe → a populated universe renders "No setups match the current filters," reading as broken.

**Fix:** Reset filter state (at least tier/setup/tag → ALL/empty) alongside the page when the universe key changes, or surface a visible "filters active" affordance so the empty result is attributable.

---

### 9. Each ETF universe download redundantly re-pulls SPY/QQQ and triggers a near-full refetch

| | |
|---|---|
| **File** | `core/pipeline/downloads.py` `_symbols_with_indexes` + cold-fetch path |
| **Council** | Pipeline Performance × Carmack — Understand the cost (P2) |
| **Ref** | `references/quality-backend.md` → P2 |

**Finding:** Because `fetch_data` is universe-blind (finding 1), `_symbols_with_indexes` appends the global `INDEX_SYMBOLS` (SPY, QQQ) for every universe regardless of `uni.index_symbols`, and the shared cache never holds ETF tickers, so each ETF download fails its coverage check and falls through to a near-full Yahoo pull, re-downloading SPY/QQQ the US-Stocks run already fetched.

**Fix:** Resolved by finding 1 — once `fetch_data` is universe-aware, drive appended indices from `uni.index_symbols` (commodities_etf is empty → no SPY/QQQ pull) and let each universe hit its own parquet so prior bars satisfy coverage.

---

### 10. Migration rebuild + backfill have no behavioral pytest coverage; the `'us_equities'` literal is asserted nowhere

| | |
|---|---|
| **File** | `tests/test_universe_migration.py` (covers `startup.py` rebuild) |
| **Council** | Kent Beck × Carmack — Test what might break; assertions are the test (P4, P6) |
| **Ref** | `references/quality-testing.md` → P4, P6 |

**Finding:** Both tests assert the no-op early returns; the rebuild body (RENAME, stale-index drop, CREATE-from-model, INSERT…SELECT backfill, row-count guard, DROP) is never executed by any test, and the backfill literal `'us_equities'` — which `engine_edge`/`load_archive` filter on — is pinned nowhere. The live rebuild was verified by a one-time manual rehearsal, not a repeatable check. (Beck rated P1; downgraded to P2 since the live DB is migrated + verified — this is regression protection, not a live bug.)

**Fix:** Add a test that seeds a legacy-schema temp SQLite table (no universe_type, a few rows), runs `migrate_universe_type`, and asserts it returned True, row count preserved, the column exists, the 3-col unique exists, and the distinct universe_type set is exactly `{'us_equities'}`.

---

## P3 — Consider

### 11. Endpoint status test asserts an OR over both outcomes, so it cannot fail

`tests/test_backend_services.py:563-573` — Kent Beck × Carmack (`references/quality-testing.md` → P6). `test_screener_data_endpoint_tags_universe_and_status` asserts `status in ('ready','never_scanned')` — every possible value — so it passes even if the sentinel wiring breaks. Make the artifact state deterministic (tmp_path with/without an artifact) and assert each status exactly.

### 12. Switching universe while a drill-down is open masks the switch

`webapp/frontend/src/components/ScreenerGrid.jsx:29-32,135` — Kent C. Dodds × Carmack. `handleUniverseChange` doesn't clear `drilldown`, and the drilldown render takes precedence, so the URL/switcher change one universe while the screen shows another's members. Clear `drilldown` on universe change.

### 13. `'us_stocks'` key vs `'us_equities'` universe_type — inconsistent vocabulary for one universe

`core/pipeline/universe.py` — Martin Fowler × Carmack. The default splits key (`us_stocks`) from universe_type (`us_equities`) while the other two match; a developer reaches for the wrong token on the most-used case and gets a silent empty result. Route key↔universe_type through one mapping helper on the descriptor (aligning the literals is a follow-up migration since the live DB is on `us_equities`).

### 14. New interactive controls miss the design-standard Signal-Blue focus ring

`UniverseSwitcher.jsx`, `ScreenerCard.jsx` (Members), `ScreenerGrid.jsx` (Back) — Karri Saarinen × Carmack. These inline-styled buttons have no `:focus-visible` treatment while the rest of the app applies the standardized ring. Add a shared focus-visible rule and apply it.

### 15. ETF borrow as-of guard compares two different "latest session" derivations

`core/pipeline/market_context.py:59-68` — Wes McKinney × Carmack. The lookahead/borrow gate equates the ETF panel's any-column last-bar against the broad context's SPY-only last-bar — two definitions that agree today but could drift (an all-NaN trailing ETF row, a SPY gap), silently flipping a same-session scan to the neutral fallback. Single-source the session stamp.

---

## Summary

| # | Finding | Severity | Council | Fix effort |
|---|---------|----------|---------|------------|
| 1 | Download-mode ETF scans corrupt the US-Stocks cache | P1 | Performance | ~30–50 lines (thread universe through fetch_data) |
| 2 | Scheduled all-universes masks stale/failed primary | P2 | Ramírez | ~15 lines |
| 3 | Manual scan/refresh hardwired to US-Stocks; ETF always "ready" | P2 | Friedman/Ramírez/Dodds | ~20–40 lines |
| 4 | Migration guard checks column, not constraint | P2 | Leach | ~5 lines |
| 5 | Backtest harness ingests ETF setups | P2 | Leach | ~1 line |
| 6 | Universe-switch status race | P2 | Dodds | ~5 lines |
| 7 | Drill-down fetch no staleness guard + twin path | P2 | Dodds/Fowler | ~30 lines (extract hook) |
| 8 | Filters persist across universe switch | P2 | Friedman | ~5 lines |
| 9 | ETF download re-pulls SPY/QQQ (root = #1) | P2 | Performance | folded into #1 |
| 10 | Migration rebuild/backfill no test coverage | P2 | Beck | ~20 lines (1 test) |
| 11 | Endpoint status test can't fail | P3 | Beck | ~10 lines |
| 12 | Switch-while-drilldown masks switch | P3 | Dodds | ~1 line |
| 13 | key vs universe_type vocabulary | P3 | Fowler | helper or follow-up migration |
| 14 | Focus ring missing on new controls | P3 | Saarinen | ~5 lines CSS |
| 15 | as-of guard two date methods | P3 | McKinney | ~5 lines |

## Verdict

Solid, well-structured feature: the security surface is genuinely closed (Hunt — nothing), the engine output stayed byte-identical, and the irreversible archive migration was rehearsed-then-applied with backup + verification — exactly the discipline this codebase demands. **The one thing to fix before the scheduled `--all-universes` run is trusted is finding 1**: the download path is universe-blind, so ETF scans corrupt the US-Stocks market-data cache and its freshness/health metadata (confirmed: GLD is in the stock parquet, no per-universe caches exist). It's the same root behind findings 9 and partly 15. The most critical domain here is the **data-pipeline cache lifecycle** (Performance/Leach) — the engine math is clean, but the *state around it* (caches, the migration idempotency guard, the offline edge-population twin) is where the multi-universe seam leaks. After finding 1, the backend-honesty pair (2 + 3) matters most for an unattended deployment. Everything else is P2/P3 polish on a shippable feature.

---

## Findings Breakdown by Expert

| Expert | P1 | P2 | P3 | Total | Key Areas |
|--------|----|----|----|----|-----------|
| Hunt (Security) | 0 | 0 | 0 | 0 | (surfaces closed) |
| Dodds (Frontend) | 0 | 3 | 1 | 4 | fetch races, drilldown lifecycle, post-scan refresh |
| Ramírez (Backend) | 0 | 2 | 0 | 2 | scheduled-status masking, manual-scan gap |
| Leach (Data Integrity) | 0 | 2 | 0 | 2 | migration guard, edge-population twin |
| Performance | 1 | 1 | 0 | 2(+1 folded) | cache corruption, redundant fetch |
| Saarinen (UI) | 0 | 0 | 2 | 2 | focus ring, ink-ramp/type |
| Friedman (UX) | 0 | 2 | 0 | 2 | ETF refresh dead-end, filter persistence |
| Beck (Test) | 0 | 1 | 1 | 2(+1 merged) | migration coverage, tautological assert |
| Fowler (Refactoring) | 0 | 1 | 1 | 2 | drilldown twin path, key/type vocabulary |
| McKinney (Numerical) | 0 | 0 | 1 | 1 | as-of session stamp |
| **TOTAL** | **1** | **9** | **5** | **15** | |
