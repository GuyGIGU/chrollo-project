# McKinney — Numerical & Quant-Engine Correctness Review

## Domain Verdict

In my domain the `universe_type` seam is **sound — keep fixing surgically**. The numerical/dtype handling here is not accumulating cross-cutting inconsistency; on the contrary, this round consolidated the two depth-predicate twins (`downloads._history_too_shallow` + the inlined health check) into one shared `data_freshness.history_too_shallow`, which is exactly the right move and is byte-parity-preserving (the empty/short-panel and empty-symbol-set fast paths both still resolve to `history_ok=True`). The ETF "borrow broad regime" as-of logic is the prime lookahead suspect, and it is **correct**: the borrow gate is strict session-equality between the broad context's `spy_last_bar_date` and the ETF panel's own SPY-derived `etf_asof`, computed the *same* way on both sides, so an ETF setup can never be scored against a regime that incorporates a bar it could not have seen. The recurring NaN/dtype bug class is real but **localized to one boundary** — the archive→episodes projection where pandas hands SQL NULL back as `np.nan`. The `_clean_cell` fix is correct and the right shape. I did **not** find another live instance of the same NaN-truthiness trap in these files (the other NaN handling — `_finite_float`, `dropna`, `pd.to_numeric(errors='coerce')`, `.notna().sum()` — is already defensive). What I'd recommend instead of a refactor: a single typed boundary coercion for *all* archive-row string fields would prevent the class from recurring if a fourth grouping/identity column is ever added, but that is hardening, not a rebuild signal. The duplicate-`(ticker,Close)`-column dedupe in `deep_history_ratio` is correct for crash-avoidance; its one soft edge (which duplicate is kept) is a P3, below.

---

FINDING:
- Title: Split-probe ratio is poisoned by inf when a cached/fresh Close is zero
- File: core/pipeline/downloads.py:404-411
- Principle: NaN and inf propagate silently — quarantine them at the boundary (Principle 2)
- Severity: P2
- What's wrong: `ratios = (f / c).dropna()` does not drop `inf` — a zero or near-zero Close on a halt/bad bar yields `inf`, which survives `.dropna()` and then makes `ratio_mean`/`ratio_std` `inf`. `rel_drift = abs(inf - 1.0)` is `inf` (> threshold) while `is_constant` (`ratio_std < max(0.001, 0.2*rel_drift)`) becomes `inf < inf` = False, so the ticker is silently *not* flagged.
- Consequence: A genuinely split-drifted ticker that also carries one zero/bad overlap bar escapes the split probe, so its history is never re-fetched and the screener reads pre-split (mis-scaled) prices on that name.
- Fix: Replace `[np.inf, -np.inf]` with NaN before `.dropna()` on the ratio series (the same `replace([inf,-inf], nan).dropna()` pattern the metrics code uses), so a degenerate overlap bar drops out instead of poisoning the constant-ratio fingerprint.

FINDING:
- Title: Constant-ratio split fingerprint uses an unstated `std` tolerance basis that breaks at very small drift
- File: core/pipeline/downloads.py:408-414
- Principle: Never compare prices or ratios with `==` — use tolerances / unstated tolerance basis (Principle 3)
- Severity: P3
- What's wrong: `is_constant = ratio_std < max(0.001, 0.2 * rel_drift)`. For a real but small split-equivalent drift just over the 0.5% threshold (`rel_drift≈0.005`), the bound is `max(0.001, 0.001) = 0.001`, an absolute std floor on a ratio that is dimensionless but whose noise scales with the names probed. The `0.001` floor is an absolute number with no stated basis, mixing an absolute std tolerance with a drift-relative one.
- Consequence: At the low end of the drift band the constant-ratio test can reject a true split (std just above 0.001) or admit noise, slightly mis-tuning when the universe-wide cold-refetch trips — a calibration wobble, not a wrong price.
- Fix: Document the `0.001` as the absolute-ratio noise floor it is, and state that the test is "std small relative to drift magnitude"; consider expressing the floor as a fraction of `ratio_mean` so it is scale-consistent with the ratio it bounds.

FINDING:
- Title: Duplicate-`(ticker,Close)` dedupe in `deep_history_ratio` keeps an arbitrary column, which can mask the very corruption it guards
- File: core/pipeline/data_freshness.py:109-112
- Principle: Dtype correctness / determinism — pandas index alignment is implicit (Principle 5/7)
- Severity: P3
- What's wrong: `closes.loc[:, ~closes.columns.duplicated(keep="last")]` keeps the *last* of two duplicate Close columns. A torn merge can leave one full column and one hollow (mostly-NaN) column; `keep="last"` picks by position, not by which carries the deeper history, so the count used for the depth ratio is whichever duplicate landed last.
- Consequence: If the surviving duplicate is the full one, a torn-merge cache can read as deep-history-OK and skip the cold refetch that should rebuild it (the latest-session coverage check would normally still catch it, so impact is bounded). The crash it prevents is correctly fixed; only the measurement edge is soft.
- Fix: When deduping for the depth count specifically, prefer the column with more non-NaN bars (e.g. keep the max-count duplicate) rather than positional `keep="last"`, so the depth verdict is conservative toward "refetch" on a torn cache.

FINDING:
- Title: NULL `setup_type` and NULL `universe_type` both collapse to the default, silently merging two genuinely different rows into one episode key
- File: core/backtest/loader.py:85-96, 119-123
- Principle: NaN/dtype coercion at the boundary (Principle 2/6)
- Severity: P3
- What's wrong: `_clean_cell` correctly maps `None`/`NaN`/blank to a default — but for `setup_type` the default is `""` and for `universe_type` it is `"us_equities"`. On a mixed/legacy archive where some rows have a real `universe_type` and a sibling row has NULL, the NULL row is grouped *as if* it were `us_equities`, so a NULL-universe ETF continuation row can merge into a us_equities episode (the inverse of the cross-universe split the fix is protecting). The fix is correct for the committed-schema case (NOT NULL after migration); the residual is only the transient mixed-NULL window.
- Consequence: On a partially-migrated archive, a NULL-`universe_type` row can be merged into the wrong universe's episode, mis-anchoring its first-seen entry date and double-counting one scan.
- Fix: This is acceptable as-is given the migration makes the column NOT NULL; if a mixed-NULL window is possible, treat a NULL `universe_type` as its own sentinel group (e.g. `"__unknown__"`) rather than silently defaulting it into `us_equities`, so it never merges across a real universe boundary.

FINDING:
- Title: Distribution-day count compares volume against the prior *present* bar, not the prior calendar session
- File: core/pipeline/market_context.py:175-180
- Principle: Missing bars and holidays — gaps are data, not zeros (Principle 9)
- Severity: P3
- What's wrong: `close` is `Close.dropna()` and `volume` is `reindex(close.index)`; `volume > volume.shift(1)` then compares each bar to the previous *non-NaN* bar. If a Close bar is missing (NaN-dropped), the "prior day" volume is actually two-plus calendar days back. Alignment is explicit and correct (no NaN-hole misalignment), so this is descriptive-context only, not a scoring input.
- Consequence: A distribution-day classification can use a stale prior-volume comparison across a gap; this only affects the descriptive regime label (UNDER_PRESSURE pressure-day count), not a fire/score, so the blast radius is the dashboard banner.
- Fix: None required for correctness; if the regime label is ever promoted to a scoring input, reindex volume onto the dense session calendar before the `shift(1)` so the comparison is always session-to-session.

---

## Notes on items checked and cleared (no finding)

- **ETF regime BORROW as-of guard (market_context.py:60-90)** — sound. `etf_asof` is derived from SPY's last Close the same way the broad context derives `spy_last_bar_date`, and the borrow only fires on strict session-equality, so no future-bar regime can leak into an ETF score. The neutral fallback + diagnostic print on session-drift is the correct safe default.
- **SPY 6m return off-by-one (market_context.py:339-341)** — correct. `len > RS_LOOKBACK_BARS` guards `iloc[-RS_LOOKBACK_BARS-1]`; with 126 it needs ≥127 bars and reads `iloc[-127]`, which exists. Matches the evaluation-side RS convention.
- **`history_too_shallow` shared-helper fold (data_freshness.py:116-143, downloads.py:695-710, market_data_health.py:152-154)** — byte-parity preserved. Empty/short panel → False, empty symbol set → `deep_history_ratio` returns 1.0 → not shallow; the old per-call guards resolve identically.
- **`np.busday_count` in episodes (episodes.py:64-78)** — safe. Rows are date-sorted ascending so the count is non-negative; malformed dates fall to a 1e6 gap (start-new-episode) rather than crashing the grouping. Unchanged vs HEAD.
- **`_patch_market_data` combine_first dedupe (downloads.py:466-483)** — correct; both sides deduped before the column-wise `combine_first`, regression-tested (`test_patch_market_data_tolerates_duplicate_base_columns`).
- **`_clean_cell` NaN-truthiness fix (loader.py:85-96)** — correct and is the right shape for the reported bug; I found no other live instance of the `bool(np.nan) is True` trap across these six files.
