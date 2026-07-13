# Backtest methodology — validating the screener's signal edge

**Status:** spec (2026-07-07). Governs the `core/backtest/` harness and the
point-in-time backfill driver. Update this doc in the same change when the
methodology moves.

---

## 1. What we are measuring (and what we are NOT)

Chrollo is an **idea generator**, not an autonomous trader. So the question a
backtest must answer is **not** "what equity curve would trading these fires
produce" — that conflates the screener with the operator's discretionary entries
and exits. The question is narrower and more honest:

> **Does the screener's Score / Tier / sub-scores actually predict forward
> returns — and is that edge real, or a bull-market artifact?**

This is a **signal / factor-edge study**, not a strategy-simulation study. The
headline metric is **MFE (max favorable excursion)** — "what the setup made
available" — because realized R depends on the human exit. Realized R is
deliberately omitted from the edge headline.

**Entry-timing caveat (why we report two CAR reads).** The engine is a
*pre-breakout* screener: you enter on the breakout **trigger** (a breach of the
LPS high), not at the fire close. So a naive *buy-at-fire-close* CAR measures
something the strategy never does. The harness reports BOTH: (1) the strict
event-study CAR anchored at the fire close (§10, the academic "signal at t=0"
read), and (2) the **trigger-gated** read (§12) — the trigger *rate* plus a CAR
anchored at the breakout-day close, over only the fires that broke out. The
trigger-gated read + MFE + barrier/R are the operator-faithful metrics; the
fire-close CAR is the conservative lower bound.

### The honest-claim bar

A credible **"the edge is real"** claim (versus merely "hypothesis-generating")
must clear all four of these. Until it does, the report says *hypothesis-
generating*, out loud.

1. **N is disclosed and controlled.** Every sub-score / threshold / config we
   tried counts as a trial. A backtest that does not report how many things it
   tried is, per López de Prado, worthless regardless of performance.
2. **The observed edge exceeds the expected-maximum-Sharpe benchmark** for that
   N (False Strategy Theorem, §4). Beating zero is not enough; you must beat the
   best-of-N you'd expect from pure noise.
3. **Benchmark-relative.** The edge is measured as **abnormal return vs SPY over
   the same window** (alpha), not raw return. Raw win-rate in a bull tape is beta.
4. **Regime-conditioned.** The edge must survive *outside* an uptrend. This was
   the blocking constraint — and it is now solvable (§2).

---

## 2. The data spine — the single-regime confound is breakable

The live archive is 100% one uninterrupted bull regime, so its win rates are
inflated by market beta and prove nothing standalone. **But the 5-year price
cache (`market_data_cache_5y.parquet`) runs 2021-07 → 2026-07 across ~5,500
tickers — it contains the 2022 bear market (S&P −25%), the 2023 recovery, and the
2024–25 drawdowns.**

Because the replay chain (`_run_eval_chain`) is byte-identical to the live engine
and takes only `df[df.index <= T]`, we can **replay the frozen engine through
2022** with no look-ahead by construction. This produces a fire cohort that
spans adverse regimes — exactly the missing ingredient for condition (4). We do
not have to wait for a future correction.

**Consistency note:** the cache was rebuilt **as-traded** (`DATA_DIVIDEND_ADJUSTED
= False`) on 2026-07-02, so its entire 5-year history is one price regime — no
adjusted/as-traded seam inside the backfill. Forward returns for the backfill are
computed **offline from this same cache**, so entry and outcome share one price
basis.

---

## 3. Methodology stack (mapped to what exists)

The right methodology for a **sparse-event** signal is a hybrid: an event-study
layer for the CAR curves, the AFML stack for the predictive labels (already in
use), and a mandatory multiple-testing layer over everything.

| Method | Fit | Status |
|---|---|---|
| Triple-barrier labeling (AFML) | core | **built** (`core/archive/outcomes.py`) |
| Benchmark-relative alpha (ret − SPY, same window) | essential | **built** (`abnormal_ret_to_date`; per-row SPY col added by backfill) |
| Point-in-time replay (no look-ahead) | essential | **built** (`_run_eval_chain`) |
| MFE-headline edge, sliced by tier/type/horizon | core | **built** (`core/backtest/edge_report.py`) |
| Null / base-rate Monte-Carlo (darts on same universe) | core | **built** (`core/backtest/null_model.py`) |
| Multiple-testing haircut (BH-FDR / Bonferroni) | mandatory | **built** (`core/backtest/stats.py`) |
| IS/OOS split by frozen `engine_config_version` | good | **built** (`core/backtest/is_oos.py`) |
| **Event-study CAR curves w/ calendar-time (clustered) SEs** | **best fit for sparse events** | **built** (`core/backtest/event_study.py`) |
| **Deflated Sharpe / expected-max-Sharpe / PBO** | mandatory for N control | **built** (`core/backtest/deflated_sharpe.py`) |
| **Regime-segmented edge (bull/bear/correction)** | condition (4) | **built** (backfill tag + harness §9) |
| **Trigger-gated edge (enter on breakout, not fire close)** | operator-faithful | **built** (harness §12: trigger rate + breakout-anchored CAR) |
| Purged & embargoed / combinatorial-purged CV | only if we fit an ML model | deferred (engine is rule-based, not a classifier) |
| Meta-labeling ("which fires to trust") | optional 2nd stage | deferred |
| Alphalens IC / quantile-spread | **design mismatch** for sparse events | skip as primary (needs a dense daily panel) |

**Why not Alphalens:** it needs a dense `(date, asset)` panel bucketed into
per-date quantiles. A sparse event signal has too few names per date → broken
bins, ill-defined IC. It is maintained (Apache-2.0) but the wrong primary tool.

**Build vs adopt = reimplement the thin stats layer, don't import.** The AFML
reference implementation (`mlfinlab`) moved to a commercial model with OSS gaps —
uncertain license/maintenance. The math we need (DSR, expected-max-Sharpe, CAR
calendar-time variance, BH-FDR) is small and reimplementable from the primary
papers in a few hundred lines, keeping the harness dependency-light and
pandas-native. **Do not add a heavy backtest framework** (vectorbt/qlib/zipline)
— those simulate equity curves, which is not our question.

---

## 4. Pitfalls this harness must actively guard against

1. **Event clustering inflates significance.** A good screener fires *more* names
   on the same strong-tape days; same-day fires are positively cross-correlated,
   which biases naive cross-sectional standard errors **downward** and test-stats
   **upward**. **Fix:** compute CAR variance from a **calendar-time portfolio**
   (all names fired on date *t* → one portfolio return for *t*; t-stat on that
   time series), not the naive per-fire cross-section.
2. **Multiple testing across ~14 sub-scores.** `t > 2.0` is invalid here. Use a
   `t ≈ 3.0` hurdle (or BH-FDR, preferred for correlated signals). Empirically
   ~44–53% of *published* factors fail correction; an in-house scan has no
   publication filter, so the file-drawer risk is maximal. **Disclose N.**
3. **Structurally low power at 60 days.** Thin-at-60-bar, high-volatility names =
   a low-power regime. Short-horizon reads (5/10/20d) carry more statistical
   power than the 60-day; weight conclusions accordingly.
4. **Single-regime beta** (§2) — segment by regime, report alpha not raw return.
5. **Selection bias in the archive.** Seed/manual rows are a hand-picked winners
   gallery; the edge headline is computed on `source='screener'` only, by
   construction (already enforced in `edge_report.headline_edge`).

### Expected-maximum-Sharpe benchmark (False Strategy Theorem)

For N independent trials of a strategy with true SR 0, the expected maximum
sampled Sharpe is approximately

```
E[max SR_N] ≈ sqrt(2·ln N) · σ_SR      (σ_SR ≈ standard error of the SR estimate)
```

so the observed best-of-N must exceed this noise ceiling to mean anything. The
**Deflated Sharpe Ratio** turns this into a probability — `P(true SR > 0)`
corrected for selection (N), non-normal skew/kurtosis, and sample length.

---

## 5. Backtest design decisions (D1–D5)

Settled 2026-07-07. Scope: measure the frozen engine's standalone signal edge
across 2021-2026, regime-segmented, benchmark-relative, multiple-testing-corrected.

- **D1 — Cadence: WEEKLY** (each Friday close) point-in-time scan. Natural swing
  cadence; episode-dedup collapses consecutive re-flags; ~10× lighter than daily
  while still catching multi-week bases. The driver is every-bar-capable — weekly
  is the chosen run, not a hard limit.
- **D2 — Universe: FULL cache universe** (~5,500), gated by the SAME live
  pre-gate (`apply_baseline_filters`, inside `_evaluate_ticker`). A curated subset
  would reintroduce the selection bias we are trying to escape. The pre-gate is
  part of the engine, so applying it is faithful, not cheating.
- **D3 — Horizons: keep the frozen 60-bar cap** for the archived triple-barrier /
  MFE / R columns (that is the engine's frozen contract — not ours to move here).
  The **event-study CAR module computes its own longer window** (e.g. 120 bars)
  directly from the cache as an *additive measurement layer* — it answers the
  multi-month question without mutating the archive schema.
- **D4 — Regime framing:** tag every fire's `scan_date` with the prevailing SPY
  regime (200-DMA state / `spy_trend`) and report the edge **segmented by regime**;
  the headline is **abnormal-vs-SPY**, never raw return.
- **D5 — Scratch DB, never live.** The backfill writes to a dedicated scratch
  sqlite file; the live `webapp/backend/trading_journal.db` is never touched. The
  harness reads it via `--db PATH` (read-only, `mode=ro`). Enforced by
  construction — the driver takes an explicit `db_path` and defaults nowhere near
  the live archive.

---

## 6. How to run it

```powershell
# 1. Backfill: weekly point-in-time replay -> scratch DB (offline, from the cache)
python -m tools.backtest_backfill --cadence weekly --db <scratch.db>

# 2. Full standalone-edge harness on the scratch archive (read-only)
python -m tools.backtest_engine --db <scratch.db> --json out/backtest_report.json

# CAR curves + Deflated-Sharpe are additive sections of the harness (regime-segmented).
```

The backfill is offline (reads the cache, no network) and idempotent by
(ticker, scan_date, universe_type). Forward returns for a fire dated within ~60
bars of the cache end (≈ after 2026-04) are partially matured — the
elapsed-window metric (`mfe_to_date`) handles that by construction.

---

## 7. Primary sources

- Kothari & Warner — *Econometrics of Event Studies* (long-horizon
  misspecification; clustering).
- López de Prado — *Advances in Financial Machine Learning* (triple-barrier,
  meta-labeling, purged CV, PBO).
- Bailey & López de Prado — *The Deflated Sharpe Ratio* (selection bias, DSR;
  davidhbailey.com/dhbpapers/deflated-sharpe.pdf).
- Bailey & López de Prado — *The False Strategy Theorem / Probability of Backtest
  Overfitting* (SSRN 3177057, 2308659).
- Harvey & Liu — *Evaluating Trading Strategies* (SSRN 2474755) and Harvey, Liu &
  Zhu — *…and the Cross-Section of Expected Returns* (multiple-testing hurdles,
  BHY-FDR for correlated signals).
