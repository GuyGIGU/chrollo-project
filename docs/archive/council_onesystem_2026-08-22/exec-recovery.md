# Exec — worktree-council-p2-followups recovery (3 stranded pieces re-landed)

Run 2026-08-23 · working tree on main @ 03d984f · NOT committed (chair commits)
Source: branch `worktree-council-p2-followups` @ 20fe178 (2026-06-30), read via `git show` only — never checked out.

## What landed

### 1. Close-coverage vectorization — `core/pipeline/data_freshness.py`
Replaced the per-symbol scalar `_has_symbol_close` loop with the branch's vectorized
`_close_presence_on` (one `xs` + single-row slice), and rewired its two call sites
(`close_coverage_on`, `symbols_missing_closes_on`). The helper region of main's file was
byte-identical to the branch's base, so the branch hunk re-derived onto current main with no
adaptation needed — main's later additions (`deep_history_ratio`, `history_too_shallow`) are
untouched. Semantics preserved exactly, including both torn-merge edges: a duplicate
`(ticker,'Close')` column ORs via `groupby(level=0).any()`, a duplicated session row ORs via
`any(axis=0)`; missing-Close-level KeyError → all-False; absent symbols reindex to False.
`_has_symbol_close` had no other references repo-wide.

### 2. Its test file — `tests/test_data_freshness.py` (NEW, 71 lines)
Branch file brought over verbatim — the module API (`close_coverage_on`,
`symbols_missing_closes_on`) is unchanged on current main, so zero adaptation. Pins: basic
present/NaN/absent, duplicate-Close-column any-non-NaN, duplicate-row-label any-non-NaN,
empty/flat-panel, and no-rows-for-day. 5 tests.

### 3. Universe-scoped `_archive_version` — `webapp/backend/services/archive_queries.py`
`_archive_version(db)` → `_archive_version(db, universe_type=None)`: the (max id, row count)
signature filters on `SetupArchive.universe_type` when given; `_grouped_episodes` now passes
`filters.get("universe_type")` (which it already defaults to `DEFAULT_UNIVERSE_TYPE` for the
cache key). An ETF/commodity archive insert no longer busts the cached us_equities episode
grouping. `None` keeps the whole-table signature (the all-universes grouping — correct).
Only call site repo-wide is `_grouped_episodes`; main's evolved `_grouped_episodes` docstring
(same-day-upsert note) kept as-is.

Tests for piece 3:
- **`tests/test_scan_metrics.py`** — the branch's stranded `test_persist_scan_metrics_routes_to
  _the_scanned_universe` (Council #11) added, verbatim-compatible with current main's
  `persist_scan_metrics(metrics, universe=)` API (only new patch needed: `cache_lock` →
  `nullcontext`, exactly as the branch already had it).
- **`tests/test_archive_version_scope.py`** (NEW, 2 tests) — the branch had no test for the
  cache-scoping fix itself, so a minimal one was written per spec: (a) the equities-scoped
  signature ignores a sectors insert while the unscoped one moves, and (b) end-to-end through
  `_grouped_episodes` with a `_build_grouping` spy + fresh `VersionedCache`: warm cache survives
  an ETF insert (build count stays 1 — fails on the whole-table signature), an equities insert
  still invalidates, and the ETF row stays excluded from the grouping. Real throwaway
  `make_sqlite_engine(":memory:")` DB, never the live DB.

## Verification

- `py_compile` clean on all five touched files.
- **Isolation run** (clean `git worktree` at HEAD 03d984f + only these five files copied in):
  142 passed — test_data_freshness, test_archive_version_scope, test_scan_metrics,
  test_episode_cache, test_episodes, test_missed_winners, test_manual_add_universe_stamp,
  test_universe_scope_invariant, test_fetch_health, test_fetch_repair, test_market_data_health,
  test_market_data_service. Worktree removed after.
- **Working-tree run**, same net: 142 passed.
- **Remaining archive_queries-touching suites** (test_backend_services, test_archive_column_parity,
  test_archive_row_assembly, test_dashboard_wire, test_power_play_lane, test_ta_grade_cascade):
  110 passed.
- Total: 252 passed, 0 failed. 8 of those are the new/recovered tests.

## Findings the chair should know

1. **The working tree is NOT clean and it is not this recovery.** A large uncommitted change-set
   from a concurrent session is in flight (legacy-path retirement sweep + rank-by-`_ta_grade` in
   `core/pipeline/screener.py`, `setupScoreMath.js`/`ta_grade_ab` deletions, conventions.md
   additions, ~70 files). This recovery's whole diff is exactly: `core/pipeline/data_freshness.py`,
   `webapp/backend/services/archive_queries.py`, `tests/test_scan_metrics.py` (+1 test, +1 import),
   plus new `tests/test_data_freshness.py` and `tests/test_archive_version_scope.py`.
2. Mid-run, the two pre-existing `test_run_screener_*` failures (KeyError `_ta_grade` — the
   concurrent session's screener re-rank vs its stale test fakes; verified pre-existing via a
   pristine-HEAD worktree run that passed 3/3) were fixed BY that session on disk (it added
   `_ta_grade` to the fakes). Both sessions' edits to test_scan_metrics.py coexist cleanly; the
   final working-tree state passes all 4 tests in the file.
3. Nothing was committed, no branch was checked out, no branch/tag was deleted — the hunt's
   follow-up (`retired/council-p2-followups-2026-06` tag + branch deletion) remains for the chair.
