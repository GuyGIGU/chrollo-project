# Wyckoff-Minervini Stock Screener — Strategy & Implementation Reference

This document is the **single source of truth** for what the screener actually does. It mirrors the implementation in `core/` and the parameter values in `config/settings.py` exactly. Every rule below cites the function and the module it lives in. (For the high-level map of how `core/` is organized, see [core/MAP.md](../core/MAP.md).)

The strategy combines Mark Minervini's Volatility Contraction Pattern (VCP) bias with Richard Wyckoff's Phase A / Phase B structural model. Goal: isolate **tight horizontal equilibrium bases** that have just printed an active **Last Point of Support (LPS)**, with no widening downward continuation, sitting after both R/S have been carved out by an actual swing.

---

## Pipeline Overview

```
Phase 0  Universe & data acquisition          core.pipeline.data public API
Phase 1  Baseline universe filter              core.pipeline.evaluation (apply_baseline_filters)
Phase 2  Consolidation detection               core.structure           (detect_boxes -> parent find_outer_box + best-of-both inner range)
Phase 2b Crash / extension filters             core.pipeline.evaluation (_evaluate_ticker)
Phase 3  LPS detection                         core.structure           (detect_lps)
Phase 3b Read-only phase scoping               core.structure           (scope_consolidation)
Phase 4  Scoring & tier assignment             core.scoring             (score_setup, calculate_tier)
Archive  Persist + forward-return backfill     core.archive             (writer / forward_returns / seed)
```

The code is organized as two engines plus a conductor (see [core/MAP.md](../core/MAP.md)):
**`core/structure/`** = the Visual Structure Engine (pure geometry/measurement),
**`core/scoring/`** = the Scoring Engine (the tunable opinion layer),
**`core/pipeline/`** = the conductor that wires them together, with **`core/archive/`** as the
measuring-stick tooling. Orchestrated by `run_screener()` in
[core/pipeline/screener.py](../core/pipeline/screener.py), running per-ticker evaluation from
[core/pipeline/evaluation.py](../core/pipeline/evaluation.py) in a `ProcessPoolExecutor`.

---

## Phase 0 — Universe & Data

### Ticker universe — `get_tickers()` ([core/pipeline/data.py](../core/pipeline/data.py), implemented in [core/pipeline/tickers.py](../core/pipeline/tickers.py))

1. Read from cached `config/tickers.csv` if it exists and is younger than `TICKER_CACHE_MAX_AGE_DAYS` (1 day).
2. Otherwise download `ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqtraded.txt`, filter rows where `Test Issue == 'N'` and `ETF == 'N'`.
3. Keep symbols that are **alpha-only and ≤ 5 chars** — drops dotted/class-share tickers (e.g. `BRK.B`) because yfinance handles them inconsistently.
4. Dedupe (preserving order) and write back to the CSV cache.
5. Hard fallback to a 15-stock sample if FTP fails.

### Market data — `fetch_data()` ([core/pipeline/data.py](../core/pipeline/data.py), implemented in [core/pipeline/downloads.py](../core/pipeline/downloads.py))

- Reads from `market_data_cache_2y.parquet` and applies an **incremental refresh** policy via `cache_meta.json`:
  - `TTL_FRESH_HOURS_MARKET = 1` (RTH) / `TTL_FRESH_HOURS_OFFHOURS = 12` — under TTL the cache is reused as-is.
  - `FULL_REFRESH_INTERVAL_DAYS = 7` — at least once a week, force a cold 2y refetch regardless of TTL.
  - Between those, `_incremental_fetch()` re-downloads only the last few business days (`INCREMENTAL_OVERLAP_BDAYS = 5`), with a `SPLIT_PROBE_*` guard that detects yfinance's auto-adjust silently rescaling history and falls back to a cold refetch when > 2% of probed tickers drift.
- Cold path: downloads from `yfinance` in batches of **500 tickers** with `period = "2y"` (`DOWNLOAD_PERIOD`), 1.5s sleep between batches, exponential-backoff retry (3 attempts: 2s/4s/8s).
- `_recover_missing_data()` re-downloads tickers that came back missing or with < 200 bars (skipped if more than half the universe is missing — likely rate-limit). Recovered batches replace the bad columns and the merged frame is written back to Parquet.
- SPY rides in the same parquet as the screened universe but is excluded from screening — it exists only to feed `get_market_context()` (SPY 6m return + breadth).

---

## Phase 1 — Baseline Universe Filter

`apply_baseline_filters()` ([core/pipeline/evaluation.py](../core/pipeline/evaluation.py)).

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

`_evaluate_ticker()` then attaches `ATR_10` and `ATR_50` ([core/structure/indicators.py](../core/structure/indicators.py): Wilder's smoothing via SciPy `lfilter`). `ADX` is implemented in `indicators.py` but **not used** by the live screener — only `backtest_watchlist.py` references it.

### Market-context broadcast — `get_market_context()` ([core/pipeline/data.py](../core/pipeline/data.py), implemented in [core/pipeline/market_context.py](../core/pipeline/market_context.py))

Before per-ticker workers fan out, the orchestrator computes two scalars once and pickles them into every worker:

- **`spy_6m_return`** — SPY close-to-close return over `RS_LOOKBACK_BARS` (126 bars). Feeds the Soft RS bonus in scoring (`excess_return_6m = stock_6m − spy_6m`).
- **`breadth_pct`** — share of the screened universe with `Close > SMA_50`. Persisted to the archive (`_breadth_pct`) and used by the market-breadth bonus in scoring; never used as a hard gate.

Cached in `market_context.json` next to the parquet with TTL 1h during market hours, 12h otherwise; invalidated when SPY's last-bar date changes.

---

## Phase 2 — Consolidation Detection

`detect_boxes()` ([core/structure/consolidation.py](../core/structure/consolidation.py)) is the live entry point. It calls `find_outer_box()` for the parent Wyckoff range, then probes for a best-of-both inner Phase D range (mechanical midpoint and detected inner climax; see "Parent + Inner" below). The parent remains the base of record. The inner, when present, is drawn alongside and used for LPS detection/scoring only when the LPS forms inside it.

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

### Swing Segmentation — Phase-A Display Reconnect

`segment_swings()` ([core/structure/segmentation.py](../core/structure/segmentation.py)) measures the swing path with ATR-normalized displacement and identifies a root counter-swing from trend into range. The live pipeline uses this only after the box/LPS have already passed: if the detector's BC anchor drifted to an ancient climax, `_evaluate_ticker()` may reconnect `bc_anchor_bar` to the largest recent counter-trend swing whose end lands near `phase_b_start_bar`. This affects Phase-A scoping diagnostics (`_bars_since_BC`, `_descent_length`, and chart-region labels), but it does **not** feed R/S selection, LPS detection, scoring, tiering, or filtering.

### Phase B — Zigzag S/R Anchoring

`_phase_b_zigzag()` ([core/structure/box_candidates.py](../core/structure/box_candidates.py)).

1. **Pivots** — `_find_pivots()` (vectorized; asymmetric `>=` left, `>` right so flat tops/bottoms still pivot at the rightmost — the structurally meaningful "last touch"):
   - `ORDER = PIVOT_ORDER_LONG (2)` if window ≥ `PIVOT_ORDER_THRESHOLD (40)` bars, else `PIVOT_ORDER_SHORT (1)`.
2. **Zigzag construction** — `_build_zigzag()`: merge peaks + valleys chronologically, enforce strict alternation; on consecutive same-type pivots, keep the more extreme (higher peak or lower valley).
3. **ATR reference** — use the engine-aligned snapshot from `find_outer_box` if supplied; otherwise the median `ATR_10` over the last `PHASE_B_ATR_WINDOW` (30) bars; final fallback = median(High-Low).
4. **Candidate generation** — only **strictly consecutive** zigzag pairs (peak→valley or valley→peak) are tested. The peak's High = R, the valley's Low = S.
5. **Per-candidate validation — the "worked equilibrium" test.** A candidate (a
   Resistance-anchor / Support-anchor pair) is a REAL trading range only if price
   *respects, touches, and zigzags through both rails constantly, with no dead
   space*:
   - **Box width:** `(R - S) / S <= MAX_BOX_WIDTH` (0.18 — a range wider than this
     is the BC→AR extremes, not a tradeable equilibrium).
   - **Boundary respect** — `_is_boundary_respected()`:
     - Buffered band `[S - 0.5·ATR, R + 0.5·ATR]`; wicks count as breaches.
     - ≥ `MIN_BOUNDARY_RESPECT_PCT` (80%) of bars inside the band, no consecutive
       outside run longer than `MAX_CONSECUTIVE_OUTSIDE_DAYS` (10).
   - **Worked-equilibrium occupancy** — `_validate_base_quality()`:
     - In-base crash filter: `min(Low) >= S × CRASH_FILTER_MULT` (0.70).
     - **Constant two-sided touch:** ≥ `EQ_MIN_TOUCHES_PER_RAIL` (3) on each rail,
       each touched in ≥ `EQ_MIN_TOUCH_THIRDS` (2) of 3 time-thirds (not clustered).
     - **No dead space:** ≥ `EQ_MIN_HALF_DWELL` (0.15) of closes in BOTH the lower
       and upper box third, and box-height `coverage` ≥ `EQ_MIN_COVERAGE` (0.80).
     - **Not mid-churn:** middle-third dwell ≤ `EQ_MAX_MID_DWELL` (0.45).
     - Public `metrics.measure_equilibrium()` additionally reports High/Low
       range occupancy for analysis, but the box-of-record selector keeps close
       residence as the calibrated dead-space gate so Phase-B rails do not drift.
   - The old "≥2 touches + N midline crosses" gate is retired — a wide box
     mechanically racked up crosses while a one-time AR low left dead space
     beneath the real range, so the widest framing always won.
6. **Structural-quality score:** every *valid* candidate gets
   `combined = 0.4 × box_tightness + 0.4 × touch_density(/10) + 0.2 × coverage`.
7. **Candidate selection (`select="earliest"` live default):** choose the
   **earliest** `cand_start` among the valid candidates (longest cause),
   tie-broken toward higher quality — "the earliest *of the ones that qualify*."
   There is no reach-quality floor anymore: a sparse / dead-space framing can no
   longer be valid, so the support anchor naturally climbs off one-time lows
   until the band is genuinely worked. **If no candidate is valid → no box → the
   stock is rejected.**

`select="best"` remains a diagnostic mode (highest combined regardless of start);
`select="debug"` returns the valid-candidate landscape. The inner Phase-D
mini-consolidation runs the same worked-equilibrium validity one scale down
(mini Resistance/Support anchors) but still selects for tightness.

#### `cand_start` trim — measure on the actual chop window

Phase B begins at the AR *low* (or the bounce *high* for SC anchors), but the structural box rarely starts there — it starts at the next zigzag pivot, which is the inner "mini BC" / "mini AR" that opens the working consolidation. Bars between the outer AR and this inner pivot are the early-chop drift, not part of the box, and including them in boundary respect / base quality measurement inflates breach counts and forgives wicks that aren't really chop. To correct this, every candidate inside `_phase_b_zigzag()` is measured on its own bar window: starting at `cand_start = min(r_anchor_bar, s_anchor_bar)` (the earlier of the two zigzag anchors that define R and S). Both `_is_boundary_respected()` and `_validate_base_quality()` run over `eq_df.iloc[cand_start:]`, so the boundary-respect % and the touch / midline-cross counts reflect the actual chop range, not the BC→AR span. The returned `base_length` is also the trimmed length (`base_length - cand_start`), and the r/s anchor bars are rebased to it. The outer BC anchor (`bc_anchor_bar`) remains df-positional — only the box window itself is trimmed.

`_phase_b_zigzag` returns: `(base_length, R, S, box_width, r_touches, s_touches, total_outside, r_anchor_bar, s_anchor_bar)`.

`find_outer_box` returns a **12-tuple** for the parent: `(base_length, R, S, box_width, r_touches, s_touches, breach_days, r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar, is_inner_box)`. `bc_anchor_bar` / `phase_b_start_bar` are df-positional and feed the `_bars_since_BC` / `_descent_length` archive fields. `detect_boxes` wraps that as `{"parent": <12-tuple>, "inner": <dict|None>}`; the inner dict carries its own `R`, `S`, `box_width`, `base_len`, `start_bar`, touches, and anchor bars.

`r_anchor_bar` / `s_anchor_bar` are returned in **eq_df-relative** (base-relative) coordinates — the dashboard and SQLite archive consume them that way. The LPS detector translates them into df-positional indices locally.

### Phase 2b — Crash & Extension Filters

After consolidation passes, `_evaluate_ticker()` re-checks at the latest bar:

- **Crash filter:** `Close >= S × CRASH_FILTER_MULT` (0.70).
- **Extension filter:** `Close < R × EXTENSION_FILTER_MULT` (1.15) — too far above R means the move has already gone, no entry left.

---

## The Phase D Model — Reading the Right-Most Region

Phases A and B establish *where the base is* and *what its R/S are*. But everything a trade actually depends on happens in **Phase D — the right-most region of the consolidation**, where the LPS is evaluated before markup. This is the part a human reads *first* when scanning, and it is the north star the engine exists to honor: read Phase D faithfully and the rest is context.

**Phase D is defined by its Last Point of Support (LPS).** The LPS is the foundation of every setup worth considering — no LPS in the right-most region means no Phase D and no setup. This is not aspirational: `detect_lps()` is mandatory in the pipeline, and a ticker with no qualifying LPS is dropped (`_evaluate_ticker` returns `None`).

**What an LPS is (and isn't).** An LPS is **support forming and holding around the support zone, in general** — price returns to the floor and holds. It is **not** *defined* by being a higher low. A higher-low / ascending / "tennis-ball" shape is **rewarded, not required**: plenty of valid LPSs simply form around the support zone without stair-stepping up. The implementation already reflects this general definition:

- the pullback-shape gate is **graded, not binary** — `descent_frac` *multiplies* LPS quality rather than rejecting non-higher-lows (Phase 3, gate 5);
- the zone gate accepts the LPS **anywhere around the zone** — `INSIDE`, `OVERSHOOT_R` (breakout retest), or `UNDERCUT_S` (spring) — not only a clean higher low (Phase 3, gate 6);
- the ascending-support footprint is a **bonus-only** score, never a filter (see "Ascending Support / Higher-Lows Footprint").

**The optional tenant: a mini-consolidation.** Phase D *may* contain a second, tighter mini-consolidation — a natural development when live equilibrium shifts during accumulation and the range re-settles inside the larger process. It is **not** always present. The engine handles the "sometimes" via the parent+inner detector (`detect_boxes` → `_inner_zigzag`; see "Parent + Inner"). The inner box is a *structural fact to recognize*, not a requirement to impose.

**The "V" — a positioning guide, not a detected object.** The right-most action often traces a V: a final dip / shakeout / spring down into support, then a turn back up. The V is a guide for *where the trader wants to stand*:

- **before the tip** (still descending into the dip) = wrong place, wrong time — the low isn't in;
- **after the tip** (turned up off the low, demand returning) = the shakeout is done and we are walking toward launch.

The LPS *is* that turn — the last support after the reaction. The engine leans this way structurally: the trigger must sit **above** current price (room to run; Phase 3, gate 13), so a qualifying setup is biased toward the up-leg rather than a knife still falling.

**The comprehension this encodes.** Read top-to-bottom, Phase D is the bridge from *"a consolidation exists"* to *"I understand I'm in the right-most region, past the shakeout — now localize the LPS zone."* That region is now surfaced explicitly by `scope_consolidation()` ([core/structure/scope.py](../core/structure/scope.py)), an adaptive scoping pass over the detector + LPS output. It is strictly a **read-only hint**, never a gate: it cannot drop a ticker, change R/S, or alter score/tier.

The scoping layer emits best-effort chart anchors:

- **Phase A:** compact root climax / automatic-reaction lead-in, from the BC/SC anchor to the reaction bar. The live pipeline may reconnect a drifted ancient BC to a recent swing-segmentation bridge for this display/scoping purpose only.
- **Phase B:** the whole working base / cause-building region from `phase_b_start_bar` through the setup end. In the chart validation view, Phase D is an overlapping right-side read, not a cutoff that truncates Phase B.
- **Phase D:** the right-most launch region. A true Phase-C spring recovery floors the Phase-D search; it is not itself the boundary source. Phase D starts at the earliest credible right-side evidence at/after that floor: support-test cluster, inner mini-consolidation, or recovered V-tip. If none is present, the LPS window is the mandatory fallback.
- **Phase C:** optional measured spring event in Bin B. A `SPRING` is a late Low undercut below S that stays near the box, then recovers by Close back above S within the configured recovery window. Ordinary held support tests remain part of the LPS/support-test layer, not a forced Phase C. Most bases have no Phase C and that is normal.
- **LPS zone:** a tight price-and-time box around the exact LPS candidate bars (`lps_zone_low/high` plus `lps_zone_start/end_date`), not a level stretched across all of Phase D.

All boundaries are nullable. If the engine cannot place a region confidently, it emits `None` and the frontend skips that label/box. Young bases may yield only a base body and a right edge; the model must never force four tidy quadrants.

---

## Phase 3 — LPS Detection

`detect_lps()` ([core/structure/lps.py](../core/structure/lps.py)). For each `(offset, length)` window in the recent tape, every hard gate below must pass; failing any hard gate disqualifies the window. Candidate geometry is terminal-bar based: the LPS peak is the first bar's High, the LPS low is the last bar's Low, and the trigger is the last bar's High. Surviving candidates are filtered for actionability (`current_price < trigger`) and the latest valid setup LPS wins.

`offset` = bars between the LPS evaluation bar and "today" (`offset = 0` means the LPS ends today). `length` = number of bars in the LPS sequence.

| # | Gate | Rule | Setting / source |
|---|------|------|------------------|
| 1 | **Recency** | `offset` in the last 7 active LPS bars | `LPS_SCAN_OFFSET_MAX = 7` |
| 2 | **Length** | `LPS_LENGTH_MIN ≤ length ≤ LPS_LENGTH_MAX` | 2 to 7 bars |
| 3 | **Window bound** | `offset + length ≤ base_len + AR_MAX_BARS` | redundant outer guard; never lets the LPS pre-date the box |
| 4 | **Swing-complete** | `eval_idx > swing_complete_idx` where `swing_complete_idx = (len(df) - base_len) + max(r_anchor, s_anchor)` | LPS must sit *after* the swing pivots that defined R and S |
| 5 | **Pullback shape (graded)** | `descent_frac >= LPS_MIN_DESCENT_FRAC` and `high_descent_frac >= LPS_MIN_HIGH_DESCENT_FRAC`; both are pair-wise non-rising fractions over lows/highs | shape gates + quality multipliers |
| 6 | **Zone gate** | terminal LPS low (= last-bar `Low`) lands in one of three buffered zones | `LPS_ZONE_ATR_MULT = 0.5` |
|   | • INSIDE | `S ≤ low ≤ R` → setup `LPS` | |
|   | • OVERSHOOT_R | `R < low ≤ R + 0.5·ATR` → setup `LPS` (backtest of breakout) | |
|   | • UNDERCUT_S | `S - 0.5·ATR ≤ low < S` → setup `REBOUND` (spring) | |
| 7 | **Pullback depth (profile-normalized)** | `pullback_profile = (first_high - last_low) / profile_unit`, where `profile_unit = max(base_range_threshold, 0.15 × box_height)`. INSIDE/UNDERCUT_S need `>= 0.65`; OVERSHOOT_R needs `>= 1.25`; all zones cap at `<= 4.50` | `LPS_PROFILE_BOX_FRACTION_FLOOR`, `LPS_PULLBACK_PROFILE_*` |
| 8 | **Terminal-low guard** | last-bar `Low` must be within `0.10 × profile_unit` of the lowest Low in the candidate window | `LPS_TERMINAL_LOW_TOL_PROFILE = 0.10` |
| 9 | **Spread (core)** | every LPS bar's `Spread (High - Low)` must be `<= profile_unit × 1.25`; the final bar may widen over the prior bar by at most `0.35 × profile_unit` | `LPS_SPREAD_MAX_PROFILE_MULT`, `LPS_SPREAD_EXPANSION_MAX_PROFILE` |
| 10 | **Declining spread quality** | last bar spread narrower than the prior bar earns full quality; widening inside the allowed expansion cap is discounted against `profile_unit` but does not reject by itself | `LPS_SPREAD_MUST_DECLINE = True` |
| 11 | **Volume floor** | `mean(Volume[LPS]) < Vol_50[eval_idx] × 0.85` | `LPS_VOL_CONTRACTION_MAX = 0.85` |
| 12 | **Hold tolerance** | `latest['Close'] >= last_low × 0.97` | `LPS_HOLD_TOLERANCE = 0.97` |
| 13 | **Post-LPS continuation** (only when `offset > 0`) | every bar between LPS end and current bar must hold `Low >= last_low × 0.97` and stay profile-tight | catches support-test failures that widen after the LPS |
| 14 | **Trigger room** | candidate is actionable only when `current_price < trigger_price`; `_evaluate_ticker` keeps the same final room check | trigger = last LPS bar High |

**Setup label:** `REBOUND` if zone is `UNDERCUT_S`; otherwise `LPS`.

**Quality ranking:** candidates still carry `vol_contraction × (1 - tightness_ratio) × descent_frac × high_descent_frac × spread_decline_quality`, but setup election is actionability-first and recency-first: latest valid `end_index`, then latest `low_index`, then longer length, then quality. If several clean slices share the same final low, the detector reports the longest clean pullback.

> **Note on breakouts.** Despite the historical name "VCP/breakout screener," the live `_detect_lps` is the only signal generator. A genuine breakout setup type isn't emitted from the engine right now — `BREAKOUT_VOLUME_MULT`, `BREAKOUT_DEFAULT_VOL_CONTRACTION`, and `BREAKOUT_DEFAULT_TIGHTNESS` exist in settings but are unused.

---

## Phase 4 — Scoring & Tier Assignment

`score_setup()` ([core/scoring/scoring.py](../core/scoring/scoring.py)). Total score is the sum of **14 components**, each clamped into `[0, cap]`. Maximum possible total ≈ **202**.

| Component | Formula | Cap (setting) |
|-----------|---------|---------------|
| **Box tightness** | `((MAX_BOX_WIDTH - box_width) / MAX_BOX_WIDTH) × 22` | `SCORE_BOX_TIGHTNESS = 22` |
| **Touch density** | `min(touches × 2, 15)` plus `+10` if `r_touches ≥ 3 AND s_touches ≥ 3` OR `total ≥ 6` | `SCORE_TOUCH_DENSITY = 25` (15 base + 10 bonus); `TOUCH_BONUS_INDIVIDUAL = 3`, `TOUCH_BONUS_TOTAL = 6`, `TOUCH_BONUS_POINTS = 10` |
| **Oscillation** | `(mean(|Close - midline|) / box_height) / 0.33 × 5`, rewarding closes that work the rails rather than clustering at mid-box | `SCORE_OSCILLATION = 5` |
| **ATR squeeze** | `(1 - ATR_10/ATR_50 at bar -6) × 8` | `SCORE_ATR_SQUEEZE = 8` |
| **LPS tightness** | `(1 - tightness_ratio) × (20 × 2)` | `SCORE_LPS_TIGHTNESS = 20` |
| **Volume contraction** | `vol_contraction × (20 × 2)` | `SCORE_VOL_CONTRACTION = 20` |
| **Base age** (only if `base_len > MIN_BASE_DAYS`) | `sqrt(base_len / BASE_AGE_CAP_DAYS) × 22`. Hits ~50% at 30d, ~71% at 60d, 100% at 120d | `SCORE_BASE_AGE = 22`, `BASE_AGE_CAP_DAYS = 120` |
| **Strong-uptrend bonus** | **Linear ramp**: `0` below 30% YoY return, full points at 60%+, linear between. Re-accumulation inside an established uptrend breaks out more reliably than the same structure on a flat YoY chart. The other three "uptrend conditions" (above SMA50, above SMA200, ≥ 50K volume) are already hard baseline gates in Phase 1, so YoY return is the only differentiating axis. | `SCORE_UPTREND_BONUS = 15`, `MIN_STRONG_YEARLY_RETURN = 0.30`, `MAX_STRONG_YEARLY_RETURN = 0.60` |
| **Soft RS bonus** | `min(1, excess_return_6m / 0.30) × 15` where `excess_return_6m = stock_6m_return − spy_6m_return`. Leadership reward, no filter — laggards just earn 0. | `SCORE_RS_BONUS = 15`, `RS_LOOKBACK_BARS = 126`, `RS_MAX_EXCESS_RETURN = 0.30` |
| **52w-high proximity** | Linear ramp from `0` at −20% below 52w high to full at −5% (or higher). Bases that consolidate near recent highs hold their breakouts more reliably than ones rebuilding from deep drawdowns. | `SCORE_52W_HIGH_PROXIMITY = 8`, `HIGH_PROXIMITY_FULL_PCT = -0.05`, `HIGH_PROXIMITY_ZERO_PCT = -0.20` |
| **Market-breadth bonus** | Linear ramp on % of universe with `Close > SMA_50`. Zero below 35%, full at 60%+. Same value for every setup in a run (it's a market-wide scalar), but a strong-tape setup is structurally a better trade than the same chart in a defensive regime where most stocks are under their SMA_50. | `SCORE_BREADTH_BONUS = 8`, `BREADTH_FULL_PCT = 0.60`, `BREADTH_ZERO_PCT = 0.35` |
| **VCP contraction** | `contraction_quality × 12`, where quality ∈ [0,1] from `measure_contractions()` (see below) = `0.40·count + 0.35·progressive_tightening + 0.25·final_tightness`. Captures the Minervini VCP *process* (each pullback tighter than the last), distinct from box-tightness/ATR-squeeze which only see *static* tightness. | `SCORE_CONTRACTION = 12`, `CONTRACTION_IDEAL_MIN/MAX = 2/6`, `CONTRACTION_FINAL_TIGHT_PCT = 0.03`, `CONTRACTION_FINAL_LOOSE_PCT = 0.12` |
| **Ascending support** | `support_quality × 8`, where quality ∈ [0,1] from `measure_support_slope()` (see below) = `0.6·slope_score + 0.4·higher_low_frac`. Rewards a base whose swing lows stair-step *up* (rising support / tennis-ball action). Bonus-only — a flat or sagging floor earns 0, never penalized. | `SCORE_ASCENDING_SUPPORT = 8`, `ASCENDING_SUPPORT_FULL_SLOPE = 0.10` |
| **ADR% absolute volatility** | `adr_quality × 8`, where `adr_quality = min(ADR% / 5.0, 1.0)`. Rewards Qullamaggie-style volatile movers: stocks that travel enough each day to be worth trading. Bonus-only — low-ADR names earn 0, never a penalty. | `SCORE_ADR = 8`, `ADR_WINDOW = 20`, `ADR_FULL_PCT = 5.0` |

**Tier mapping** — `_calculate_tier()`. Calibrated against the live archive distribution (mean ~95, max ~126 under the prior weights; with the new bonuses added, S now sits at roughly the top quartile rather than catching 75% of all setups):

| Tier | Threshold | Setting |
|------|-----------|---------|
| **S** | `score ≥ 110` | `TIER_S = 110` |
| **A** | `score ≥ 95` | `TIER_A = 95` |
| **B** | `score ≥ 75` | `TIER_B = 75` |
| **C** | `score ≥ 55` | `TIER_C = 55` |
| **D** | else | — |

---

## VCP Progressive-Contraction Footprint

`measure_contractions()` ([core/structure/metrics.py](../core/structure/metrics.py)) measures the **defining Minervini VCP signature** — a sequence of 2–6 pullbacks each tighter than the last (e.g. 18%→12%→6%) ending in a tight final coil. This is the *process* of tightening, which `box_width` / `atr_squeeze` (static tightness) cannot see.

It reuses the Phase B zigzag machinery over the base window: each peak→valley downswing is one contraction, `depth = (peak − valley) / peak`. The initial BC→AR descent into the base is excluded by design (it's the entry into the base, the early-chop the `cand_start` trim already removes).

`quality ∈ [0,1] = 0.40·count_score + 0.35·progressive + 0.25·final_tight`:
- **count_score** — full credit for 2–6 contractions (Minervini's range, 3–4 typical); partial for 1 or for an over-count (choppy, not a clean coil).
- **progressive** — fraction of consecutive contractions that don't widen (5% tolerance); 1.0 = textbook monotonic tightening.
- **final_tight** — ramp on the rightmost contraction depth: full ≤ 3%, zero ≥ 12%.

**Volume across the contractions (`vol_trend`).** In the same pass, the mean volume of each contraction's bars is captured and scored into `vol_trend ∈ [0,1] = 0.5·progressive_decline + 0.5·final_is_lightest` (`None` with < 2 contractions) — the Minervini nuance that volume should dry up step by step, lightest at the final coil. This is **measured only**: it is deliberately NOT folded into `quality`, so the contraction sub-score, the tiers, and the VCP-Coil tag are byte-for-byte unchanged (verified against the shadow-output guard). Archived raw as `contraction_vol_trend` to validate against forward returns before it is allowed to matter (or to surface on the tag).

Persisted to the archive as `contraction_count`, `contraction_quality`, `final_contraction_depth`, `contraction_vol_trend`, and the `score_contraction` sub-score. Fires the 🌀 **VCP Coil** tag chip when `quality ≥ CONTRACTION_QUALITY_TAG` (0.70). Scored, not gated — measure-first, like the touch-volume signature.

---

## Base Bar Compression Footprint

`measure_bar_compression()` ([core/structure/metrics.py](../core/structure/metrics.py)) measures the **texture inside the detected box**: whether the bars themselves are quiet / low-spread, not just whether R/S are close together. This is distinct from `box_width` (range tightness) and `atr_ratio` (ATR squeeze) because a narrow box can still contain sloppy wide bars.

It reports four raw diagnostics, all persisted to the archive and not scored:

| Field | Meaning |
|-------|---------|
| `base_median_spread_atr` | median base bar spread divided by the ATR snapshot used by the LPS detector |
| `base_p80_spread_atr` | 80th percentile base bar spread divided by that ATR snapshot |
| `base_median_spread_pct_box` | median base bar spread divided by box height (`R - S`) |
| `base_tight_bar_pct` | share of base bars whose spread is no wider than the ATR snapshot |

This is **measure-first / never-gated / never-penalizing**. It gives the archive a direct way to test whether visually quiet bases outperform choppier bases with similar box width.

---

## Ascending Support / Higher-Lows Footprint

`measure_support_slope()` ([core/structure/metrics.py](../core/structure/metrics.py)) measures whether the base's swing lows are **stair-stepping up** — the Minervini "tennis-ball action" / Qullamaggie "higher lows surfing the rising EMA" footprint. A flat box with a *rising floor* is a stronger coil than a flat box with a flat/sagging floor: demand is getting more aggressive into each pullback.

It reuses the same Phase B zigzag as the contraction metric, but reads the **valley** sequence. It fits a least-squares line through the `(bar_index, valley_low)` points and ATR-normalizes the slope so it's comparable across price levels and tickers.

`quality ∈ [0,1] = 0.6·slope_score + 0.4·higher_low_frac`:
- **slope_score** — linear ramp of the ATR-normalized slope from 0 (flat/descending → 0) to `ASCENDING_SUPPORT_FULL_SLOPE` (0.10 ATR/bar → 1.0).
- **higher_low_frac** — fraction of consecutive valley pairs that actually step up (consistency of the higher-lows).

Needs ≥ 2 zigzag valleys; otherwise returns neutral (quality 0). Persisted as `support_slope_atr`, `ascending_support_quality`, and the `score_ascending_support` sub-score. Fires the 📈 **Ascending Support** tag chip when `quality ≥ ASCENDING_SUPPORT_TAG` (0.70). **Bonus-only / measure-first** — a flat or descending floor earns 0 points and is never penalized.

---

## ADR% Absolute Volatility

`adr_pct()` ([core/structure/indicators.py](../core/structure/indicators.py)) measures Qullamaggie-style Average Daily Range % over the latest full tape, not just the consolidation window:

```
ADR%(20) = 100 × (mean(High / Low over the last 20 bars) - 1)
```

This captures the stock's **absolute volatility character**: a high-ADR stock resting in a tight base is a stronger momentum-continuation candidate than a low-range stock with the same visual structure. The metric is guarded at source: insufficient history, zero lows, NaN/Inf, or malformed ranges return `0.0`, so the dashboard payload never receives non-finite values from ADR.

Scoring uses `adr_quality = min(ADR% / ADR_FULL_PCT, 1.0)`, with full credit at `ADR_FULL_PCT = 5.0`. Persisted as `adr_pct` and the `score_adr` sub-score. Fires the ⚡ **High ADR** tag chip when `score_adr ≥ ADR_TAG × SCORE_ADR` (`0.80 × 8 = 6.4`). **Bonus-only / measure-first** — quiet names earn 0 points and are never filtered or penalized.

---

## Volume Signature Around Touches

After the consolidation passes, `_evaluate_ticker` computes two diagnostic z-scores using the base's own volume distribution as baseline:

```
touch_band = TOUCH_TOLERANCE_ATR × ATR_10
r_touch_vol_z = (mean_vol_at_R_touches − mean_base_vol) / std_base_vol
s_touch_vol_z = (mean_vol_at_S_touches − mean_base_vol) / std_base_vol
```

These don't gate anything — they're persisted to the archive (`r_touch_vol_z`, `s_touch_vol_z`) and surface as Wyckoff-classic interpretation tags on the frontend card:

| z-score signature | Tag chip | Meaning |
|---|---|---|
| `r_touch_vol_z < TOUCH_VOL_Z_NO_SUPPLY` (-0.30) | 🤫 No Supply | Resistance tested on below-average volume — buyers absorbed silently, textbook precursor to a clean breakout |
| `s_touch_vol_z > TOUCH_VOL_Z_SPRING` (+0.30) | 💪 Demand at S | Support tested on above-average volume — buyers stepping in at S, selling absorbed. **Not a spring** — a spring is the measured Phase C undercut-and-recover event (`bin_c_type = SPRING`), and an active undercut LPS still shows as `REBOUND`. |
| `r_touch_vol_z > TOUCH_VOL_Z_HEAVY_R` (+0.50) | ⚠️ Heavy Resistance | Resistance tested on ABOVE-average volume — supply hitting the bid every time, distribution-flavored, breakout risk |

The "Heavy Resistance" tag is the only *warning* tag in the system — designed to surface even when other positive tags would otherwise crowd it out (it carries higher `weight` in the tag-ordering than even Phase D).

These are bookkeeping (not score gates) intentionally: the volume signature at touches is a real Wyckoff axis but its predictive power needs to be measured in the archive before we make it a hard gate or a score component. Phase 2 archive analysis will tell us which thresholds actually matter and at what magnitude.

---

## Region (Bin) Features & Trend Template (Stage 2A)

Two measure-only layers. Both are **descriptive, never scored and never gated** —
every value is an underscore-prefixed result field persisted to the archive
(nullable, backward-compatible) so a later calibration pass can test whether any
of it predicts forward returns. Scoring (14 components, max ~202) and the tier
thresholds are **unchanged**.

### Bin features — "where am I in the base?"

`measure_bins()` ([core/structure/bin_features.py](../core/structure/bin_features.py))
slices an already-detected base into its named regions and reports raw size,
price-range, and volume character per region. It detects nothing new — it
consumes anchors the detector + LPS finder already produced.

| Region | Span | What it is |
|--------|------|------------|
| **A — climax event** | `bc_anchor_bar → phase_a_end_bar` | the BC/SC → AR trend-exhaustion lead-in |
| **B — working base** | the validated box (`base_df`) | the cause-building equilibrium |
| **D — Phase D** | the right-most region | earliest credible right-side evidence after the spring/search floor: support-test cluster, inner mini-consolidation, or recovered V-tip; else the LPS fallback |
| **LPS** | the exact LPS candidate bars | the Last Point of Support itself |

Per region: `_bin_{a,b,d}_bars`, `_bin_{a,b,d}_range_pct` ((maxHigh−minLow)/minLow),
`_bin_{a,b,d}_volume_ratio` (region mean volume ÷ trailing-50 mean). Plus:

- `_bin_lps_bars`, `_lps_position_in_box` ((lps_low − S)/(R − S): 0 = floor, 1 = ceiling);
- `_bin_d_vs_b_range_ratio` / `_bin_d_vs_b_volume_ratio` — is Phase D
  tighter / quieter than the base it sits in? (the VCP "coil into launch" read);
- `_bin_d_support_slope_atr`, `_bin_d_higher_low_frac`,
  `_bin_d_ascending_support_quality`, and
  `_bin_d_vs_b_support_quality_delta` — is the right side stair-stepping higher
  more clearly than the base as a whole?
- `_bin_d_boundary_source` — `support_tests` (a right-side support-test cluster),
  `inner_box` (a real detected mini-consolidation), `v_tip` (the final recovered
  late-base low), or `lps` (the mandatory gate / fallback). Spring recovery only
  floors the search; it is not itself a boundary source.

**Phase-D boundary is single-sourced.** The Phase-D start uses the *same* rule
the scoping overlay draws — both call `scope._resolve_phase_d_start()` — so the
measured Phase-D bin and the drawn Phase-D band can never drift apart. Any
region the engine can't place confidently (e.g. no LPS window) is emitted as
`None`; young bases legitimately have fewer regions.

### Last Supper stretch

The over-extension axis from the structure legend: how far the LPS foot sits
*above the box that birthed it* (its energy source).

- `_lps_stretch_atr` = `(lps_low − R) / ATR` — distance above the ceiling, in ATR;
- `_lps_stretch_box` = `(lps_low − R) / (R − S)` — same, in box-heights.

≤ 0 means the LPS formed in or below the box (no stretch); a large positive
value flags a stretched, Last-Supper-risk LPS far from its energy source. Raw
archived measure first — validated against the durable-win vs cash-grab outcome
before it is ever allowed to influence ranking.

### Inner-origin measurements

The selected inner Phase-D range also records how it was born:

- `_inner_source` = `midpoint` or `inner_climax`, describing which best-of-both
  search origin produced the selected inner box;
- `_inner_search_start_bar` = the df bar where that winning inner search began;
- `_inner_climax_bar` / `_inner_reaction_bar` = the detected mini-BC -> mini-AR
  swing when `_inner_source = inner_climax`;
- `_inner_reaction_pct` / `_inner_reaction_bars` = depth and duration of that
  reaction.

These are descriptive archive fields only. They let the calibration report learn
whether inner boxes born from a real mini-climax behave differently from midpoint
heuristic boxes before any later scoring or anchoring change is considered.

### Minervini Stage-2 trend template

`trend_template()` ([core/structure/indicators.py](../core/structure/indicators.py))
records the classic price/MA leadership template as raw context, computed
self-contained from the daily frame:

1. price > SMA_150 and > SMA_200; 2. SMA_150 > SMA_200; 3. SMA_200 rising over
~1 month (21 bars); 4. SMA_50 > SMA_150 > SMA_200; 5. price > SMA_50; 6. price
≥ 30% above the 52-week low; 7. price within 25% of the 52-week high.

Fields: `_stage2_ma_stack_pass`, `_stage2_ma200_slope_1m_pct`,
`_stage2_52w_low_pct`, `_stage2_trend_pass_count` (0–7), `_stage2_trend_pass`
(all 7). Minervini's 8th criterion (RS rating ≥ 70, a *universe percentile*) is
**deliberately omitted** — Chrollo measures relative strength SPY-relatively via
`excess_return_6m` and does not compute a universe rank — so the count is out of
7. Context only; no gate, no score.

All Stage-2A fields persist to `setup_archive` (writer + seed parity) and are
surfaced by `core/archive/analyze.py` in the fingerprint + correlation sections.

---

## Outputs

`_evaluate_ticker()` returns one dict per qualifying ticker. Public fields surfaced to terminal/dashboard: `Ticker`, `Tier`, `Setup`, `Score`, `Current Price`, `Base Len`, `Box Width`, `Touches`, `ATR Ratio`, `LPS Length`, `Breach Days`. Underscore-prefixed fields (`_R`, `_S`, `_lps_offset`, `_r_anchor_bar`, `_s_anchor_bar`, `_sub_scores`, `_r_touch_vol_z`, `_s_touch_vol_z`, `_lps_descent_frac`, `_lps_zone_type`, etc.) feed the chart renderer and the archive but are not displayed in the terminal.

The read-only scoping payload is also underscore-prefixed: `_phase_a_start_date`, `_phase_b_start_date`, `_phase_d_start_date`, optional `_phase_c_event_date`, `_lps_zone_low`, `_lps_zone_high`, `_lps_zone_start_date`, `_lps_zone_end_date`, `_has_mini_consolidation`, and `_scope_confidence`. These fields are visualization/diagnostic facts only; no downstream filtering or scoring consumes them.

Pipeline returns `(results_df, market_data, tickers)` — `results_df` is sorted by `Score` descending.

---

## Archive System

The screener writes every output to a SQLite-backed setup archive (`webapp/backend/trading_journal.db`, `setup_archive` table) so we can build a regression dataset of structural fingerprints + forward outcomes.

### `archive.writer.archive_scan_results()` ([core/archive/writer.py](../core/archive/writer.py))
- Called automatically after each screener run.
- Upserts on `(ticker, scan_date)` — re-running the same day updates rather than duplicates.
- `autoflush=False` on the session: avoids the "database is locked" path where a per-row existence query would auto-flush pending UPDATEs while the webapp holds a read lock.
- Attaches **market context** to every row: `spy_trend`, `vix_level`, `sector_etf`, `sector_trend` (sector ETF mapped per ticker, 50d trend pulled at scan_date). Sector lookups are cached per ticker within a run.

### `seed_archive()` ([core/archive/seed.py](../core/archive/seed.py))
- Bootstrap mechanism for known-winner setups defined in `SEED_SETUPS = [(ticker, trigger_date), ...]`.
- For each pair, scans `[trigger_date - 10d, trigger_date + 3d]` to find which day the screener actually fired (LPS is identified *before* the breakout), keeps the highest-scoring hit.
- Re-runs the full Phase 1–4 pipeline at that historical date via `_evaluate_at_date()` (a ported copy of `_evaluate_ticker` that works on a pre-sliced DataFrame).
- Computes forward returns immediately (we have the future data already).
- Tags rows with `source="seed"`, `quality_label="perfect"` to distinguish from live scans.
- CLI: `python -m core.archive.seed [--force]`.

### `update_forward_returns()` ([core/archive/forward_returns.py](../core/archive/forward_returns.py))
- Backfills outcome data for archive rows older than `--min-age` calendar days (default 5).
- For each setup, downloads OHLC after `scan_date` and computes via `_compute_returns()`:
  - **Forward returns:** `fwd_return_1d`, `5d`, `10d`, `20d`, `60d` (close-to-close from `scan_close`).
  - **MFE/MAE:** maximum favorable / adverse excursion at 20d and 60d windows.
  - **Trigger status:** `triggered = 1` if any forward `High >= trigger_price`, plus `trigger_date`.
- By default skips rows that already have `fwd_return_1d` populated; `--force` re-computes everything.
- CLI: `python -m core.archive.forward_returns [--min-age N] [--force]`.

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
MAX_BOX_WIDTH = 0.18
CRASH_FILTER_MULT = 0.70
EXTENSION_FILTER_MULT = 1.15
PIVOT_ORDER_SHORT = 1; PIVOT_ORDER_LONG = 2; PIVOT_ORDER_THRESHOLD = 40
BOUNDARY_ATR_BUFFER = 0.5
MAX_CONSECUTIVE_OUTSIDE_DAYS = 10
MIN_BOUNDARY_RESPECT_PCT = 0.80
TOUCH_TOLERANCE_ATR = 0.5
EQ_MIN_TOUCHES_PER_RAIL = 3
EQ_MIN_TOUCH_THIRDS = 2
EQ_MIN_HALF_DWELL = 0.15
EQ_MAX_MID_DWELL = 0.45
EQ_MIN_COVERAGE = 0.80
TRAVERSAL_GATE_ENABLED = True
TRAVERSAL_MIN = 2
TRAVERSAL_MIN_DENSITY = 0.08
SOS_TRIM_ENABLED = True
SOS_TRIM_MIN_RUN = 3
SOS_TRIM_MIN_PREFIX_FRAC = 0.30
TREND_MIN_GAIN_PCT = 0.15
TREND_MIN_MOVE_BARS = 20
TREND_PRIOR_LOOKBACK = 100
LOCAL_PEAK_BARS = 30
PHASE_B_ATR_WINDOW = 30
AR_MIN_DROP_PCT = 0.05
AR_MAX_BARS = 15

# Phase 3 — LPS detection
LPS_DROP_MIN = 0.02              # deprecated/back-compat only; live depth is profile-normalized
LPS_DROP_MIN_OVERSHOOT_R = 0.04  # deprecated/back-compat only
LPS_DROP_MAX = 0.10              # deprecated/back-compat only
LPS_MIN_DESCENT_FRAC = 0.50     # Graded shape gate (pair-wise low descent fraction)
LPS_MIN_HIGH_DESCENT_FRAC = 0.45
LPS_MAX_WINDOW_BOX_RANGE = 0.85
LPS_INSIDE_HIGH_EXTENSION_BOX_MAX = 0.35
LPS_INSIDE_HIGH_EXTENSION_ATR_MAX = 0.75
LPS_SCAN_OFFSET_MAX = 7         # today + up to 6 days back
LPS_LENGTH_MIN = 2; LPS_LENGTH_MAX = 7
LPS_HOLD_TOLERANCE = 0.97
LPS_PROFILE_BOX_FRACTION_FLOOR = 0.15
LPS_PULLBACK_PROFILE_MIN = 0.65
LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R = 1.25
LPS_PULLBACK_PROFILE_MAX = 4.50
LPS_TERMINAL_LOW_TOL_PROFILE = 0.10
LPS_SPREAD_MAX_PROFILE_MULT = 1.25
LPS_SPREAD_EXPANSION_MAX_PROFILE = 0.35
LPS_ZONE_ATR_MULT = 0.5
LPS_RANGE_PERCENTILE = 0.5
LPS_SPREAD_MUST_DECLINE = True  # quality discount, not a hard rejection
LPS_VOL_CONTRACTION_MAX = 0.85
BIN_C_UNDERCUT_ATR_MIN = 0.30; BIN_C_UNDERCUT_ATR_MAX = 3.00
BIN_C_UNDERCUT_BOX_MAX = 0.65; BIN_C_RECOVERY_BARS_MAX = 8
BIN_C_LINGER_BARS_MAX = 12; BIN_C_HOLD_BARS = 3
BIN_C_HOLD_TOL_ATR = 0.50
PHASE_D_VTIP_LATE_FRACTION = 0.35
PHASE_D_VTIP_RECOVERY_BARS = 6
TOUCH_VOL_Z_NO_SUPPLY = -0.30   # Tag: r_touch_vol_z below this → "No Supply"
TOUCH_VOL_Z_SPRING = 0.30       # Tag: s_touch_vol_z above this → "Spring Strength"
TOUCH_VOL_Z_HEAVY_R = 0.50      # Tag: r_touch_vol_z above this → "Heavy Resistance" (warning)

# Phase 4 — Scoring
TIER_S = 110; TIER_A = 95; TIER_B = 75; TIER_C = 55
SCORE_BASE_AGE = 22; BASE_AGE_CAP_DAYS = 120
SCORE_TOUCH_DENSITY = 25
SCORE_VOL_CONTRACTION = 20
SCORE_LPS_TIGHTNESS = 20
SCORE_BOX_TIGHTNESS = 22
SCORE_ATR_SQUEEZE = 8
SCORE_OSCILLATION = 5
TOUCH_BONUS_INDIVIDUAL = 3; TOUCH_BONUS_TOTAL = 6; TOUCH_BONUS_POINTS = 10
MIN_STRONG_YEARLY_RETURN = 0.30; MAX_STRONG_YEARLY_RETURN = 0.60; SCORE_UPTREND_BONUS = 15
SCORE_RS_BONUS = 15; RS_LOOKBACK_BARS = 126; RS_MAX_EXCESS_RETURN = 0.30
SCORE_52W_HIGH_PROXIMITY = 8; HIGH_PROXIMITY_FULL_PCT = -0.05; HIGH_PROXIMITY_ZERO_PCT = -0.20
SCORE_BREADTH_BONUS = 8; BREADTH_FULL_PCT = 0.60; BREADTH_ZERO_PCT = 0.35
SCORE_CONTRACTION = 12; CONTRACTION_IDEAL_MIN = 2; CONTRACTION_IDEAL_MAX = 6
CONTRACTION_FINAL_TIGHT_PCT = 0.03; CONTRACTION_FINAL_LOOSE_PCT = 0.12; CONTRACTION_QUALITY_TAG = 0.70
SCORE_ASCENDING_SUPPORT = 8; ASCENDING_SUPPORT_FULL_SLOPE = 0.10; ASCENDING_SUPPORT_TAG = 0.70
ADR_WINDOW = 20; SCORE_ADR = 8; ADR_FULL_PCT = 5.0; ADR_TAG = 0.80

# Data & cache (incremental fetch)
CACHE_FILENAME = "market_data_cache_2y.parquet"
TTL_FRESH_HOURS_MARKET = 1        # Re-fetch latest bars hourly during RTH
TTL_FRESH_HOURS_OFFHOURS = 12
FULL_REFRESH_INTERVAL_DAYS = 7    # Forced cold 2y refetch weekly
INCREMENTAL_OVERLAP_BDAYS = 5     # Overlap re-download for split-probe
INCREMENTAL_MAX_GAP_BDAYS = 10    # Above this gap → fall back to full refetch
DOWNLOAD_PERIOD = "2y"
TICKER_CACHE_MAX_AGE_DAYS = 1
SPY_SYMBOL = "SPY"                # Stored in parquet for market context, not screened
MARKET_CONTEXT_TTL_HOURS_MARKET = 1
MARKET_CONTEXT_TTL_HOURS_OFFHOURS = 12
```

---

## Acceptable Misses

Per the user's standing guidance: setups on **young bases that break out fast** (KEYS, BRZU, NE, CGON-style) will not be caught by this engine and that is **by design** — the base-age requirement (`MIN_BASE_DAYS = 20`, plus the sqrt-scaled scoring up to 120 days) explicitly trades early-stage breakouts for higher-cause Wyckoff setups. These should not be treated as bugs to fix.

---

## Parent + Inner — Nested Phase D Range (live)

`detect_boxes()` ([core/structure/consolidation.py](../core/structure/consolidation.py)) wraps `find_outer_box()` with a Phase D / VCP mini-consolidation probe. After the parent box is found, it runs the inner search from both the mechanical midpoint (`INNER_SEARCH_FRACTION = 0.5`) and the detected inner climax (`_detect_inner_root_swing`), then keeps the tighter valid inner box. The inner must be meaningfully tighter (`bw_inner < INNER_TIGHTNESS_RATIO * bw_outer`, i.e. at least 25% tighter at the default 0.75) and span `INNER_MIN_DAYS = 15`+ bars. If no qualifying inner exists, `inner` is `None`; the parent still remains the base of record either way.

Inner ⊂ outer is enforced **temporally**, not in price space — the inner can sit inside, above, or below the outer's R/S; the outer's boundary-respect gate already filters out wild outliers, so an inner found in the outer's recent half is structurally adjacent regardless.

The key difference between `_inner_zigzag` and `_phase_b_zigzag`: the inner version scores each candidate over **its own** bar range (from the earlier of the two anchors onward) rather than the full inner window. Bars before the inner's first anchor were forming a different structure and would unfairly fail boundary-respect.

Historical backtest snapshots are calibration inputs, not permanent truth. When a missed visual winner clusters around a hard LPS gate, the next step is to measure that gate against forward outcomes before moving it into quality/selector evidence.

### LPS scaling adaptations for tight inner boxes

When the hierarchical detector returns a tight inner box, the standard LPS gates are too strict. Two scalings address this — both self-gated so they cannot over-loosen wider boxes:

1. **Zone tolerance floor** — `if bw < 0.10: zone_tol = max(0.5*ATR, 0.5*box_height)` (in `_detect_lps`). Tight Phase D boxes often have the LPS forming as a breakout-retest just above R (resistance flipped to support post-breach) or a sellers-failing test just below S. Half-ATR alone is too narrow when `box_height` is small. The `bw < 0.10` gate prevents wide-outer-box over-loosening.
2. **Base range threshold floor** — `base_range_threshold = max(spread_quantile, 1.2*ATR)` (in `_evaluate_ticker`). Inside a tight inner box the 50%ile spread can be smaller than a normally-volatile bar, killing detection on any ATR-typical day. The floor is now applied **unconditionally** (no `bw` self-gate); chronically-wide bases simply have a percentile that already exceeds 1.2·ATR, so the `max(...)` resolves to the percentile and the rule is unchanged for them.

### Current calibration frontier

The reader should stay visually strict, but the LPS gates should be audited as
separate ideas: hard geometry, quality evidence, and active-setup selection.
Spread decline is already quality-only. Volume contraction, descent cleanliness,
and zone/range tolerances are the next places to test against the archive before
loosening or hardening anything.
