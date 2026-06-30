# Performance Review — Multi-Universe Screener (Pipeline)

## Domain Verdict

The per-universe cache/scan design **pays off structurally** — it is surgical, not a perf liability. Three properties make it sound: (1) the universes run **sequentially** (`run_all_universe_scans`), so the bounded download pool and the global rate-limit token bucket are never contended across universes — no 3× burst into Yahoo; (2) each universe reads/writes **only its own parquet** (`_cache_paths(universe)`), so an ETF scan can land an incremental hit on its own small cache while the 5.5k-ticker US-Stocks cache is untouched — the per-universe caches *do* achieve real incremental hits, and the prior-review SPY/QQQ re-pull is genuinely gone (commodities carries no index symbols, so it doesn't re-pull SPY/QQQ; us_sectors carries SPY/QQQ but borrows regime rather than recomputing breadth); (3) the ETF universes **borrow** the broad regime from a JSON read instead of recomputing it, so the marginal cost of two extra universes is ~30–40 tickers each, negligible against the primary scan. The new `deep_history_ratio` depth scan is correctly vectorized (one `xs("Close").notna().sum()` over the panel), and the episode-grouping cache is keyed on a cheap `(max_id, count)` signature. The only structural cost worth naming is **cache-version granularity**: the episode cache's version is the *whole-table* `(max_id, count)`, so an unrelated commodities/ETF scan inserting rows busts the cached **equities** grouping (P2 below) — a seam where "one table, many universes" leaks into the cache layer. That is a one-line fix, not a rebuild signal. No findings rise to P1.

---

FINDING:
- Title: `close_coverage_on` does a Python-loop scalar `.loc` per symbol over the full ~5.5k panel, several times per fetch
- File: core/pipeline/data_freshness.py:51-63, 40-48 (callers: core/pipeline/downloads.py:676,750,953,1101,1153)
- Principle: Vectorization over per-row loops
- Severity: P2
- What's wrong: `close_coverage_on` resolves coverage with `present = sum(1 for symbol in symbols if _has_symbol_close(...))`, and `_has_symbol_close` does a `data.loc[row_label, (symbol, 'Close')]` MultiIndex scalar indexer per symbol — i.e. ~5.5k individual indexed lookups per call, and `fetch_data` calls it on the fresh/current fast path plus again after repair/cold/incremental.
- Consequence: Even the daily "cache is fresh, return as-is" fast path spends tens of thousands of per-symbol MultiIndex `.loc` lookups (the slowest pandas access pattern) before returning, when the answer is one row.
- Fix: Slice the target row once (`data.xs('Close', axis=1, level=1).reindex(columns=symbols).loc[row_label]`) and compute `.notna().sum()` vectorized, the same shape `deep_history_ratio` already uses; the per-symbol `.loc` loop should disappear.

FINDING:
- Title: `_history_too_shallow` recomputes the full-panel deep-history scan up to 3× in one `fetch_data` call
- File: core/pipeline/downloads.py:670,768,1043 (via 695-710 → data_freshness.py:84-113)
- Principle: Redundant recompute on the hot path
- Severity: P3
- What's wrong: `fetch_data` calls `_history_too_shallow(cached, tickers_with_indexes)` independently in the fresh-cache check, the current-cache check, and the `do_incremental` guard; each rebuilds the `xs("Close")` cross-section and a full `notna().sum()` over the ~5.5k-column panel on the same unchanged DataFrame.
- Consequence: Two-to-three redundant full-panel scans per daily run when the first result already settled the question, paid on every healthy fast-path return.
- Fix: Compute the depth verdict (and the per-row coverage) once per `fetch_data` after `_read_cached_panel` and thread the boolean/coverage through `_try_current_cache` / the `do_incremental` predicate instead of re-deriving from the panel at each branch.

FINDING:
- Title: Episode cache version is whole-table, so any ETF/commodities insert invalidates the equities grouping
- File: webapp/backend/services/archive_queries.py:59-64,99-123
- Principle: Cache-key granularity / cross-universe invalidation
- Severity: P2
- What's wrong: `_archive_version` returns `(max(id), count(id))` over the **entire** `setup_archive` table, but the cache stores per-`universe_type` groupings; an insert from any universe (a commodities or sector scan) moves `max(id)`/`count`, busting the cached `us_equities` episode grouping even though no equities row changed.
- Consequence: After the daily multi-universe scan, the first equities `/archive/episodes` and `/missed-winners` request re-runs `build_episodes` over the full equities archive (now ~thousands of rows) despite nothing equities-relevant having changed — defeating the cache exactly when it's most wanted.
- Fix: Make the version `universe_type`-scoped — `MAX(id)/COUNT(id)` filtered by the same `universe_type` as the cache key (a cheap indexed aggregate) — so a grouping only invalidates when its own universe's rows change.

FINDING:
- Title: `_episode_context` re-queries every `passed` SetupReview row on each episodes request
- File: webapp/backend/services/archive_queries.py:175-191
- Principle: Unfiltered full-table read on a served endpoint
- Severity: P3
- What's wrong: `_episode_context` builds `passed_notes` from `db.query(SetupReview).filter(verdict == "passed").all()` — the full passed-review set — on every `/episodes` and `/missed-winners` call, independent of the date/tier filters narrowing the episodes actually returned (and the page is then sliced to `limit`).
- Consequence: A linearly-growing unfiltered table scan + dict build runs on every paginated episode request, even when only 200 episodes are returned; the cost is uncached and grows with review history.
- Fix: This is small today; if review volume grows, restrict the `SetupReview` query to the `(ticker, scan_date)` keys of the canonical rows being returned (or cache it under the same version signature), rather than materializing the whole passed set per request.

---

## Notes (assessed, no finding)

- **Frontend card-wall render** (`ScreenerGrid.jsx`, `ScreenerCard.jsx`): renders only `filters.paginatedTickers` (24/page, `ITEMS_PER_PAGE`), `ScreenerCard` is `React.memo`'d, and `useScreenerFilters` memoizes the tag map / filtered list. Render cost is bounded to a page regardless of universe size — no finding. (`buildTagMap` rebuilds over the *whole* `chart_data` on any `screenerData` change, but that's one pass over a few hundred setups, memoized, not per-card.)
- **`market_context.py` ETF borrow**: a single JSON `_read_meta` of the broad context plus a same-session guard — O(1), no recompute of breadth/regime for ETF universes. Correct and cheap.
- **`_batched_download` / `_recover_missing_data` / `_repair_latest_session`**: concatenation is batched (`pd.concat(frames, axis=1)` once), tz-localization is per-frame but linear, and duplicate-column dedupe via `~columns.duplicated()` is vectorized. Repair is correctly batched (`LATEST_REPAIR_BATCH_SIZE`) with inter-batch sleeps. No redundant per-ticker concat in a loop.
- **`screener.py` evaluation**: market context computed once and broadcast to the `ProcessPoolExecutor`; per-ticker frames extracted once. No per-ticker recompute of context/regime.
- **`deep_history_ratio`**: properly vectorized and duplicate-column-safe — the depth guard itself is cheap; only its *repeated invocation* per fetch is flagged (P3 above).
