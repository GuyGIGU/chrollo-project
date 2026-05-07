# Wyckoff-Minervini Stock Screener — Strategy & Implementation Reference

This document is the **single source of truth** for what the screener actually does. It mirrors the implementation in `core/` and the parameter values in `config/settings.py` exactly. Every rule below cites the function and (where useful) the line range in code.

The strategy combines Mark Minervini's Volatility Contraction Pattern (VCP) bias with Richard Wyckoff's Phase A / Phase B structural model. Goal: isolate **tight horizontal equilibrium bases** that have just printed an active **Last Point of Support (LPS)**, with no widening downward continuation, sitting after both R/S have been carved out by an actual swing.

---

## Pipeline Overview

```
Phase 0  Universe & data acquisition          (core/data.py)
Phase 1  Baseline universe filter              (_apply_baseline_filters)
Phase 2  Consolidation detection               (find_consolidation -> find_outer_box + _phase_b_zigzag, with optional _inner_zigzag refinement)
Phase 2b Crash / extension filters             (_evaluate_ticker)
Phase 3  LPS detection                         (_detect_lps)
Phase 4  Scoring & tier assignment             (_score_setup, _calculate_tier)
Archive  Persist + forward-return backfill     (archive_writer / update_forward_returns / seed_archive)
```

Orchestrated by `run_screener()` in [core/screener_v2.py](../core/screener_v2.py), running per-ticker evaluation in a `ProcessPoolExecutor`.

---

## Phase 0 — Universe & Data

### Ticker universe — `get_tickers()` ([core/data.py:15](../core/data.py#L15))

1. Read from cached `config/tickers.csv` if it exists and is younger than `TICKER_CACHE_MAX_AGE_DAYS` (1 day).
2. Otherwise download `ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqtraded.txt`, filter rows where `Test Issue == 'N'` and `ETF == 'N'`.
3. Keep symbols that are **alpha-only and ≤ 5 chars** — drops dotted/class-share tickers (e.g. `BRK.B`) because yfinance handles them inconsistently.
4. Dedupe (preserving order) and write back to the CSV cache.
5. Hard fallback to a 15-stock sample if FTP fails.

### Market data — `fetch_data()` ([core/data.py:182](../core/data.py#L182))

- Reads from `market_data_cache_2y.parquet` if newer than `CACHE_MAX_AGE_HOURS` (12h).
- Otherwise downloads from `yfinance` in batches of **500 tickers** with `period = "2y"` (`DOWNLOAD_PERIOD`), 1.5s sleep between batches, exponential-backoff retry (3 attempts: 2s/4s/8s).
- `_recover_missing_data()` re-downloads tickers that came back missing or with < 200 bars (skipped if more than half the universe is missing — likely rate-limit). Recovered batches replace the bad columns and the merged frame is written back to Parquet.

---

## Phase 1 — Baseline Universe Filter

`_apply_baseline_filters()` ([core/screener_v2.py:28](../core/screener_v2.py#L28)).

Reject the ticker entirely if any check fails. Run in this order:

| Gate | Rule | Setting |
|------|------|---------|
| History | `len(df) >= 200` bars | hard-coded |
| Price floor | `Close >= MIN_PRICE` | `MIN_PRICE = 3.0` |
| Liquidity | `Vol_50 >= MIN_VOLUME_50D` | `MIN_VOLUME_50D = 50_000` |
| Above 50d trend | `Close >= SMA_50` | hard-coded |
| Above 200d trend | `Close >= SMA_200` | hard-coded |
| 12-month return | `(Close - Close[-252]) / Close[-252] >= MIN_YEARLY_RETURN` | `MIN_YEARLY_RETURN = -0.20` (modest drawdowns OK) |

While computing baselines we attach `SMA_50`, `SMA_200`, `Vol_50`, and `Spread = High - Low` to the DataFrame for downstream use.

`_evaluate_ticker()` then attaches `ATR_10` and `ATR_50` ([core/indicators.py](../core/indicators.py): Wilder's smoothing via SciPy `lfilter`). `ADX` is implemented in `indicators.py` but **not used** by the live screener — only `backtest_watchlist.py` references it.

---

## Phase 2 — Consolidation Detection

`find_consolidation()` ([core/consolidation.py:653](../core/consolidation.py#L653)) is the live entry point. It calls `find_outer_box()` ([core/consolidation.py:488](../core/consolidation.py#L488)) for extreme-anchored Wyckoff base discovery, then optionally refines into a tighter inner sub-box (see "Hierarchical refinement" below). The seed-archive curator calls `find_outer_box()` directly when it wants the textbook outer box without inner refinement.

### Setup

- `eval_df = df.iloc[:-5]` — last 5 bars are excluded from structural analysis as "edge noise."
- Require `len(eval_df) >= MIN_BASE_DAYS + 15` = 35 bars.
- ATR snapshot: take `df.iloc[-1]['ATR_10']` from `eval_df` (which equals `df.iloc[-6]['ATR_10']`) to share one volatility frame with the LPS detector.
- **Macro gate (re-asserted):** at `eval_df.iloc[-1]`, `Close > SMA_200`. (Baseline already enforced this at the latest bar; this re-asserts at the evaluation bar so the function works standalone.)

### Phase A — Anchor Discovery

Walk bars from `scan_hi = end - MIN_BASE_DAYS` down to `scan_lo = TREND_MIN_MOVE_BARS + 5`. Each bar `i` is tested as both a possible **BC (Buying Climax)** and **SC (Selling Climax)**.

**BC qualification:**
1. `highs[i]` is the maximum over the last `LOCAL_PEAK_BARS` (30) bars.
2. Within the prior `TREND_PRIOR_LOOKBACK` (100) bars there exists a low such that `highs[i] / trough_low - 1 >= TREND_MIN_GAIN_PCT` (15%) AND the rise spans ≥ `TREND_MIN_MOVE_BARS` (20) bars.
3. **Automatic Reaction:** within `AR_MAX_BARS` (15) bars after `i`, some close drops `>= AR_MIN_DROP_PCT` (5%) below `highs[i]`. Phase B starts at the **AR low** (skips the descent so it doesn't pollute boundary respect).
4. The remaining window after the AR low must be `>= MIN_BASE_DAYS` (20).

**SC qualification:** mirror — `lows[i]` is local trough over 30 bars, fell ≥ 15% from a prior peak (≥ 20 bars), validated by ≥ 5% bounce within 15 bars; Phase B starts at the **bounce high**.

### Phase A — Anchor Selection

`anchors` is built most-recent-first; the loop iterates `reversed(anchors)` (oldest-first) and takes the **first anchor whose Phase B passes** all quality gates. Rationale (from the docstring): maximizes Wyckoff "cause" / base age, and resists the failure mode where a mid-base upthrust gets selected because its shorter window mechanically yields a tighter box.

### Phase B — Zigzag S/R Anchoring

`_phase_b_zigzag()` ([core/consolidation.py:249](../core/consolidation.py#L249)).

1. **Pivots** — `_find_pivots()` (vectorized; asymmetric `>=` left, `>` right so flat tops/bottoms still pivot at the rightmost — the structurally meaningful "last touch"):
   - `ORDER = PIVOT_ORDER_LONG (2)` if window ≥ `PIVOT_ORDER_THRESHOLD (40)` bars, else `PIVOT_ORDER_SHORT (1)`.
2. **Zigzag construction** — `_build_zigzag()`: merge peaks + valleys chronologically, enforce strict alternation; on consecutive same-type pivots, keep the more extreme (higher peak or lower valley).
3. **ATR reference** — use the engine-aligned snapshot from `find_outer_box` if supplied; otherwise the median `ATR_10` over the last `PHASE_B_ATR_WINDOW` (30) bars; final fallback = median(High-Low).
4. **Candidate generation** — only **strictly consecutive** zigzag pairs (peak→valley or valley→peak) are tested. The peak's High = R, the valley's Low = S.
5. **Per-candidate validation:**
   - **Box width:** `(R - S) / S <= MAX_BOX_WIDTH` (0.20).
   - **Boundary respect** — `_is_boundary_respected()`:
     - Buffered band: `[S - 0.5·ATR, R + 0.5·ATR]` (`BOUNDARY_ATR_BUFFER = 0.5`).
     - Each bar's High vs `R + buffer` and Low vs `S - buffer` — wicks count as breaches (bars not candles).
     - At least `MIN_BOUNDARY_RESPECT_PCT` (80%) of bars must keep their full range inside the band.
     - No consecutive run of outside-bars longer than `MAX_CONSECUTIVE_OUTSIDE_DAYS` (30).
   - **Quality** — `_validate_base_quality()`:
     - In-base crash filter: `min(Low) >= S × CRASH_FILTER_MULT` (0.70).
     - **Touch density** (ATR-normalized, `TOUCH_TOLERANCE_ATR = 0.5`): require ≥ 2 touches each on R and S.
     - **Midline crosses** ("tunnel-killer"): committed-cross count using `MIDLINE_ATR_BUFFER = 0.3·ATR` — a cross only counts after price first travels ≥ buffer away from the midline. Required: `max(MIN_MIDLINE_CROSSES=3, len(eq_df) // 15)`.
6. **Best-candidate weighting:** `0.4 × box_tightness + 0.4 × touch_density(/10) + 0.2 × midline_quality(/8)`.

#### `cand_start` trim — measure on the actual chop window

Phase B begins at the AR *low* (or the bounce *high* for SC anchors), but the structural box rarely starts there — it starts at the next zigzag pivot, which is the inner "mini BC" / "mini AR" that opens the working consolidation. Bars between the outer AR and this inner pivot are the early-chop drift, not part of the box, and including them in boundary respect / base quality measurement inflates breach counts and forgives wicks that aren't really chop. To correct this, every candidate inside `_phase_b_zigzag()` is measured on its own bar window: starting at `cand_start = min(r_anchor_bar, s_anchor_bar)` (the earlier of the two zigzag anchors that define R and S). Both `_is_boundary_respected()` and `_validate_base_quality()` run over `eq_df.iloc[cand_start:]`, so the boundary-respect % and the touch / midline-cross counts reflect the actual chop range, not the BC→AR span. The returned `base_length` is also the trimmed length (`base_length - cand_start`), and the r/s anchor bars are rebased to it. The outer BC anchor (`bc_anchor_bar`) remains df-positional — only the box window itself is trimmed.

Returns: `(base_length, R, S, box_width, r_touches, s_touches, total_outside, r_anchor_bar, s_anchor_bar)`.

`r_anchor_bar` / `s_anchor_bar` are returned in **eq_df-relative** (base-relative) coordinates — the dashboard and SQLite archive consume them that way. The LPS detector translates them into df-positional indices locally.

### Phase 2b — Crash & Extension Filters

After consolidation passes, `_evaluate_ticker()` re-checks at the latest bar:

- **Crash filter:** `Close >= S × CRASH_FILTER_MULT` (0.70).
- **Extension filter:** `Close < R × EXTENSION_FILTER_MULT` (1.15) — too far above R means the move has already gone, no entry left.

---

## Phase 3 — LPS Detection

`_detect_lps()` ([core/screener_v2.py:63](../core/screener_v2.py#L63)). For each `(offset, length)` window in the recent tape, every gate below must pass; failing any single gate disqualifies the window. The final candidate is the one with the highest `vol_contraction × (1 - tightness_ratio)` quality.

`offset` = bars between the LPS evaluation bar and "today" (`offset = 0` means the LPS ends today). `length` = number of bars in the LPS sequence.

| # | Gate | Rule | Setting / source |
|---|------|------|------------------|
| 1 | **Recency** | `offset ∈ {0,1,2,3}` | `LPS_SCAN_OFFSET_MAX = 4` |
| 2 | **Length** | `LPS_LENGTH_MIN ≤ length ≤ LPS_LENGTH_MAX` | 2 to 7 bars |
| 3 | **Window bound** | `offset + length ≤ base_len + AR_MAX_BARS` | redundant outer guard; never lets the LPS pre-date the box |
| 4 | **Swing-complete** | `eval_idx > swing_complete_idx` where `swing_complete_idx = (len(df) - base_len) + max(r_anchor, s_anchor)` | LPS must sit *after* the swing pivots that defined R and S |
| 5 | **Pullback shape** | `argmax(High) <= argmin(Low)` across the window — the highest high must occur at or before the lowest low | rejects up-march windows where lows and highs both rise; pure structural check, no retest semantics. Without this, an up-march trivially passes the drop-depth gate because the trough is the *highest* low |
| 6 | **Zone gate** | LPS low (= `min(Low)` across the window) lands in one of three buffered zones (tolerance = `0.5 × ATR_10` snapshot at bar -6) | `LPS_ZONE_ATR_MULT = 0.5` |
|   | • INSIDE | `S ≤ low ≤ R` → setup `LPS` | |
|   | • OVERSHOOT_R | `R < low ≤ R + 0.5·ATR` → setup `LPS` (backtest of breakout) | |
|   | • UNDERCUT_S | `S - 0.5·ATR ≤ low < S` → setup `REBOUND` (spring) | |
| 7 | **Pullback depth** | `LPS_DROP_MIN ≤ (max_high - min_low) / max_high ≤ LPS_DROP_MAX`, both extremes taken across the full window | 2% to 10% |
| 8 | **Spread (core)** | every bar's `Spread (High - Low)` < `base_range_threshold` = `base_df['Spread'].quantile(0.5)` | `LPS_RANGE_PERCENTILE = 0.5` (median) |
| 9 | **Declining spread** | last bar's spread ≤ prior bar's spread (when length ≥ 2) | `LPS_SPREAD_MUST_DECLINE = True` |
| 10 | **Volume floor** | `mean(Volume[LPS]) < Vol_50[eval_idx] × 0.85` | `LPS_VOL_CONTRACTION_MAX = 0.85` |
| 11 | **Hold tolerance** | `latest['Close'] >= min_low × 0.97` | `LPS_HOLD_TOLERANCE = 0.97` |
| 12 | **Post-LPS continuation** (only when `offset > 0`) | every bar between LPS end and current bar must hold `Low >= min_low × 0.97` AND `Spread < base_range_threshold` | catches MSGM-style failures where a tight 2-bar pullback is followed by widening down-bars |
| 13 | **Trigger room** (in `_evaluate_ticker`) | `(trigger_price - current_price) / current_price > 0` | trigger = `pullback_period['High'].max()` — must still be ahead of price |

**Setup label:** `REBOUND` if zone is `UNDERCUT_S`; otherwise `LPS`.

**Quality ranking:** among surviving candidates, pick the maximum of `vol_contraction × (1 - tightness_ratio)` where `tightness_ratio = end_lps_spread / base_range_threshold` and `vol_contraction = (Vol_50 - mean_pullback_vol) / Vol_50`.

> **Note on breakouts.** Despite the historical name "VCP/breakout screener," the live `_detect_lps` is the only signal generator. A genuine breakout setup type isn't emitted from the engine right now — `BREAKOUT_VOLUME_MULT`, `BREAKOUT_DEFAULT_VOL_CONTRACTION`, and `BREAKOUT_DEFAULT_TIGHTNESS` exist in settings but are unused.

---

## Phase 4 — Scoring & Tier Assignment

`_score_setup()` ([core/screener_v2.py:226](../core/screener_v2.py#L226)). Total score is the sum of 8 components, each clamped into `[0, cap]`. Maximum possible total ≈ 143.

| Component | Formula | Cap (setting) |
|-----------|---------|---------------|
| **Box tightness** | `((MAX_BOX_WIDTH - box_width) / MAX_BOX_WIDTH) × 15` | `SCORE_BOX_TIGHTNESS = 15` |
| **Touch density** | `min(touches × 2, 15)` plus `+10` if `r_touches ≥ 3 AND s_touches ≥ 3` OR `total ≥ 6` | `SCORE_TOUCH_DENSITY = 25` (15 base + 10 bonus); `TOUCH_BONUS_INDIVIDUAL = 3`, `TOUCH_BONUS_TOTAL = 6`, `TOUCH_BONUS_POINTS = 10` |
| **Oscillation** | `(0.3 - mean(|Close - midline|) / box_height) × (5 × 5)` | `SCORE_OSCILLATION = 5` |
| **ATR squeeze** | `(1 - ATR_10/ATR_50 at bar -6) × 8` | `SCORE_ATR_SQUEEZE = 8` |
| **LPS tightness** | `(1 - tightness_ratio) × (20 × 2)` | `SCORE_LPS_TIGHTNESS = 20` |
| **Volume contraction** | `vol_contraction × (20 × 2)` | `SCORE_VOL_CONTRACTION = 20` |
| **Base age** (only if `base_len > MIN_BASE_DAYS`) | `sqrt(base_len / BASE_AGE_CAP_DAYS) × 35`. Hits ~50% at 30d, ~71% at 60d, 100% at 120d | `SCORE_BASE_AGE = 35`, `BASE_AGE_CAP_DAYS = 120` |
| **Strong-uptrend bonus** | flat `+15` if `yearly_return ≥ 0.30`, else `0`. Re-accumulation inside an established uptrend breaks out more reliably than the same structure on a flat YoY chart, so qualifying setups are elevated. The other three "uptrend conditions" the user cares about (above SMA50, above SMA200, ≥ 50K volume) are already hard baseline gates in Phase 1, so the only differentiating condition is YoY return. | `SCORE_UPTREND_BONUS = 15`, `MIN_STRONG_YEARLY_RETURN = 0.30` |

**Tier mapping** — `_calculate_tier()`:

| Tier | Threshold | Setting |
|------|-----------|---------|
| **S** | `score ≥ 85` | `TIER_S = 85` |
| **A** | `score ≥ 70` | `TIER_A = 70` |
| **B** | `score ≥ 55` | `TIER_B = 55` |
| **C** | `score ≥ 40` | `TIER_C = 40` |
| **D** | else | — |

---

## Outputs

`_evaluate_ticker()` returns one dict per qualifying ticker. Public fields surfaced to terminal/dashboard: `Ticker`, `Tier`, `Setup`, `Score`, `Current Price`, `Base Len`, `Box Width`, `Touches`, `ATR Ratio`, `LPS Length`, `Breach Days`. Underscore-prefixed fields (`_R`, `_S`, `_lps_offset`, `_r_anchor_bar`, `_s_anchor_bar`, `_sub_scores`, etc.) feed the chart renderer and the archive but are not displayed.

Pipeline returns `(results_df, market_data, tickers)` — `results_df` is sorted by `Score` descending.

---

## Archive System

The screener writes every output to a SQLite-backed setup archive (`webapp/backend/trading_journal.db`, `setup_archive` table) so we can build a regression dataset of structural fingerprints + forward outcomes.

### `archive_writer.archive_scan_results()` ([core/archive_writer.py:29](../core/archive_writer.py#L29))
- Called automatically after each screener run.
- Upserts on `(ticker, scan_date)` — re-running the same day updates rather than duplicates.
- `autoflush=False` on the session: avoids the "database is locked" path where a per-row existence query would auto-flush pending UPDATEs while the webapp holds a read lock.
- Attaches **market context** to every row: `spy_trend`, `vix_level`, `sector_etf`, `sector_trend` (sector ETF mapped per ticker, 50d trend pulled at scan_date). Sector lookups are cached per ticker within a run.

### `seed_archive.seed_archive()` ([core/seed_archive.py:212](../core/seed_archive.py#L212))
- Bootstrap mechanism for known-winner setups defined in `SEED_SETUPS = [(ticker, trigger_date), ...]`.
- For each pair, scans `[trigger_date - 10d, trigger_date + 3d]` to find which day the screener actually fired (LPS is identified *before* the breakout), keeps the highest-scoring hit.
- Re-runs the full Phase 1–4 pipeline at that historical date via `_evaluate_at_date()` (a ported copy of `_evaluate_ticker` that works on a pre-sliced DataFrame).
- Computes forward returns immediately (we have the future data already).
- Tags rows with `source="seed"`, `quality_label="perfect"` to distinguish from live scans.
- CLI: `python -m core.seed_archive [--force]`.

### `update_forward_returns.update_forward_returns()` ([core/update_forward_returns.py:108](../core/update_forward_returns.py#L108))
- Backfills outcome data for archive rows older than `--min-age` calendar days (default 5).
- For each setup, downloads OHLC after `scan_date` and computes via `_compute_returns()`:
  - **Forward returns:** `fwd_return_1d`, `5d`, `10d`, `20d`, `60d` (close-to-close from `scan_close`).
  - **MFE/MAE:** maximum favorable / adverse excursion at 20d and 60d windows.
  - **Trigger status:** `triggered = 1` if any forward `High >= trigger_price`, plus `trigger_date`.
- By default skips rows that already have `fwd_return_1d` populated; `--force` re-computes everything.
- CLI: `python -m core.update_forward_returns [--min-age N] [--force]`.

---

## Settings Quick-Reference

All values from `config/settings.py` — change here to retune.

```text
# Phase 1 — Universe baseline
MIN_PRICE = 3.0
MIN_VOLUME_50D = 50_000
MIN_YEARLY_RETURN = -0.20

# Phase 2 — Consolidation
MIN_BASE_DAYS = 20
MAX_BOX_WIDTH = 0.20
CRASH_FILTER_MULT = 0.70
EXTENSION_FILTER_MULT = 1.15
PIVOT_ORDER_SHORT = 1; PIVOT_ORDER_LONG = 2; PIVOT_ORDER_THRESHOLD = 40
BOUNDARY_ATR_BUFFER = 0.5
MAX_CONSECUTIVE_OUTSIDE_DAYS = 30
MIN_BOUNDARY_RESPECT_PCT = 0.80
TOUCH_TOLERANCE_ATR = 0.5
MIN_MIDLINE_CROSSES = 3
MIDLINE_ATR_BUFFER = 0.3
TREND_MIN_GAIN_PCT = 0.15
TREND_MIN_MOVE_BARS = 20
TREND_PRIOR_LOOKBACK = 100
LOCAL_PEAK_BARS = 30
PHASE_B_ATR_WINDOW = 30
AR_MIN_DROP_PCT = 0.05
AR_MAX_BARS = 15

# Phase 3 — LPS detection
LPS_DROP_MIN = 0.02
LPS_DROP_MAX = 0.10
LPS_SCAN_OFFSET_MAX = 4         # today + up to 3 days back
LPS_LENGTH_MIN = 2; LPS_LENGTH_MAX = 7
LPS_HOLD_TOLERANCE = 0.97
LPS_ZONE_ATR_MULT = 0.5
LPS_RANGE_PERCENTILE = 0.5
LPS_SPREAD_MUST_DECLINE = True
LPS_VOL_CONTRACTION_MAX = 0.85

# Phase 4 — Scoring
TIER_S = 85; TIER_A = 70; TIER_B = 55; TIER_C = 40
SCORE_BASE_AGE = 35; BASE_AGE_CAP_DAYS = 120
SCORE_TOUCH_DENSITY = 25
SCORE_VOL_CONTRACTION = 20
SCORE_LPS_TIGHTNESS = 20
SCORE_BOX_TIGHTNESS = 15
SCORE_ATR_SQUEEZE = 8
SCORE_OSCILLATION = 5
TOUCH_BONUS_INDIVIDUAL = 3; TOUCH_BONUS_TOTAL = 6; TOUCH_BONUS_POINTS = 10
MIN_STRONG_YEARLY_RETURN = 0.30; SCORE_UPTREND_BONUS = 15

# Data & cache
CACHE_FILENAME = "market_data_cache_2y.parquet"
CACHE_MAX_AGE_HOURS = 12
DOWNLOAD_PERIOD = "2y"
TICKER_CACHE_MAX_AGE_DAYS = 1
```

---

## Acceptable Misses

Per the user's standing guidance: setups on **young bases that break out fast** (KEYS, BRZU, NE, CGON-style) will not be caught by this engine and that is **by design** — the base-age requirement (`MIN_BASE_DAYS = 20`, plus the sqrt-scaled scoring up to 120 days) explicitly trades early-stage breakouts for higher-cause Wyckoff setups. These should not be treated as bugs to fix.

---

## Hierarchical Refinement — Inner Sub-Box (live)

`find_consolidation()` ([core/consolidation.py:653](../core/consolidation.py#L653)) wraps `find_outer_box()` with a Phase D launchpad / VCP mini-consolidation probe. After an outer box is found, it probes the recent half of that box (`_INNER_SEARCH_FRACTION = 0.5`) via `_inner_zigzag()` ([core/consolidation.py:367](../core/consolidation.py#L367)) for a tighter inner sub-box. When the inner exists and is meaningfully tighter (`bw_inner < 0.75 * bw_outer`, i.e. ≥25% tighter) AND spans `_INNER_MIN_DAYS = 15`+ bars, the inner wins; otherwise the outer is returned unchanged.

Inner ⊂ outer is enforced **temporally**, not in price space — the inner can sit inside, above, or below the outer's R/S; the outer's boundary-respect gate already filters out wild outliers, so an inner found in the outer's recent half is structurally adjacent regardless.

The key difference between `_inner_zigzag` and `_phase_b_zigzag`: the inner version scores each candidate over **its own** bar range (from the earlier of the two anchors onward) rather than the full inner window. Bars before the inner's first anchor were forming a different structure and would unfairly fail boundary-respect.

Banked at **28/44 hits (63.6%)** on [backtest_watchlist.py](../backtest_watchlist.py). Of the 16 misses, 9 now fail at the LPS `shape_up_march` gate (the structural-pullback shape check added in the LPS rewrite — see "LPS Detection" above) and 5 fail at outer-box detection. None are tunable without weakening structural correctness, per the [Quality over hit-rate](../C:/Users/User/.claude/projects/c--Users-User-Screener-Project/memory/feedback_quality_over_hitrate.md) guidance.

### LPS scaling adaptations for tight inner boxes

When the hierarchical detector returns a tight inner box, the standard LPS gates are too strict. Two scalings address this — both self-gated so they cannot over-loosen wider boxes:

1. **Zone tolerance floor** — `if bw < 0.10: zone_tol = max(0.5*ATR, 0.5*box_height)` (in `_detect_lps`). Tight Phase D boxes often have the LPS forming as a breakout-retest just above R (resistance flipped to support post-breach) or a sellers-failing test just below S. Half-ATR alone is too narrow when `box_height` is small. The `bw < 0.10` gate prevents wide-outer-box over-loosening.
2. **Base range threshold floor** — `base_range_threshold = max(spread_quantile, 1.2*ATR)` (in `_evaluate_ticker`). Inside a tight inner box the 50%ile spread can be smaller than a normally-volatile bar, killing detection on any ATR-typical day. Self-gates: chronically-wide bases keep the percentile rule.

### Remaining misses

The 13 misses split into structural categories — none are tunable LPS-gate issues:

- **Anchor mis-detection** (NBR, GXO, VLO, SHEL): the outer-box detector picks the wrong window — an older quiet zone instead of the structurally relevant recent chop. The recent-first-anchor v5 hypothesis was tested and falsified (see [experiments/dead_ends/v5_recent_first_anchor/](../experiments/dead_ends/v5_recent_first_anchor/)): v5 picks different outer anchors but the LPS detector still rejects at the same gates. Re-test only if the LPS detector itself is rewritten — anchor preference alone won't help.
- **Marginal drop_pct edges** (TRS at 1.3% drop, SNDX at 10.6%): structurally real bounds; loosening sacrifices selectivity for two tickers.
- **Spread-decline strict** (ST, RRBI): pre-breakout bars not contracting; relaxing contradicts the LPS definition.
- **Acceptable misses** (KEYS, BRZU, NE) per the section above.
