# The edge tile's denominator, 2026-09-08

Read-only measurement against the live archive (`mode=ro`), main at `84d09dd`. It started
as the follow-up to the 2026-09-08 tail read — verify the claims that analysis left
unverified — and turned up a defect in the statistic itself.

**What it settles:** the win rate on the Home *Engine Edge* tile is computed on a
denominator that varies from 62% to 16% across tiers, which is why it ranked tier C
best. Fixed here by shipping the resolution rate beside it and putting an
outcome-threshold rate in the column instead. **What it does NOT settle:** whether a
corrected denominator restores the standalone edge the signal-edge backtest ruled absent
on 2026-09-03 — see *The limit* below. That question is now an ask
([asks.md](asks.md)).

## The finding

`core/backtest/edge_report.barrier_distribution` derives win / loss / timeout shares
from the stored `barrier_label`. A row whose label is `None` is excluded from the
shares. That exclusion is documented and deliberate. What was never measured is **how
many rows it removes, and whether it removes them evenly.**

It removes **2,843 of 6,979** matured screener rows — 41% — and it removes them in a
tier-ordered way:

| tier | matured rows | unlabelled | share unlabelled |
|---|---|---|---|
| S | 2,926 | 764 | 26.1% |
| A | 2,585 | 1,182 | 45.7% |
| B | 1,368 | 817 | 59.7% |
| C | 100 | 80 | 80.0% |

**Cause, attributed:** 2,811 of the 2,843 (98.9%) come from one line —
`core/archive/forward_returns.py:232`, which nulls a `timeout` label when fewer than 60
forward bars exist, on the sound reasoning that you cannot call a timeout before the
horizon is over. Only 32 come from a degenerate entry (`risk <= 0`, the scan close at or
under its own stop). So the unlabelled rows are overwhelmingly **"nothing has happened
yet"** — and a stronger setup resolves sooner, which is exactly why the share is
tier-ordered.

**It is not recency.** Bucketing by the scan's calendar age, the S → A → B → C ordering
holds inside every bucket:

| scan age | S | A | B | C |
|---|---|---|---|---|
| < 40d | 52.7% | 53.2% | 64.1% | 91.7% |
| 40–60d | 37.8% | 51.2% | 61.2% | 73.3% |
| 60–90d | 33.0% | 41.6% | 55.4% | 73.7% |
| 90–120d | 0.5% | 0.0% | 0.0% | — |

## What the tile was showing

On the deduped episode basis the tile actually reads (4,169 unbiased episodes):

| tier | episodes | resolved | **win rate shown** | P(MFE≥25%) | P(MFE≥40%) |
|---|---|---|---|---|---|
| S | 1,579 | 62.1% | 40.3% | **7.63%** | **2.16%** |
| A | 1,718 | 43.5% | 38.2% | 5.87% | 1.47% |
| B | 796 | 34.4% | **41.6%** | 3.41% | 0.60% |
| C | 76 | 15.8% | **50.0%** | 7.32% † | 0.00% † |

† 41 matured rows — below the display floor, suppressed on the tile.

The win-rate column is non-monotonic and puts the worst tier first, on twelve resolved
rows out of seventy-six. Conditioning on resolution removes almost all the difference
between tiers, because *whether a setup resolves at all* is most of what separates them.
The threshold-exceedance rates on the same rows are monotonic S → B and separate S from B
by 2.2x at 25% and 3.6x at 40%.

## The limit — stated, not buried

The clean test of "does a corrected denominator restore the edge" is the cohort old
enough that every row carries a label. That cohort exists (scan age ≥ 90 days, 0.5%
unlabelled) but it is **1,072 rows over six scan days and 85% tier S** — one market
episode, with the tier mix of nothing. Its own within-day score deciles are
non-monotonic and, if anything, point the *other* way (P(MFE≥25%) 5.4% in the top decile
against 16.4% in the bottom). That is far too thin and too concentrated to rule on, in
either direction, and it is not quoted here as evidence for anything except its own
insufficiency. **The corrected denominator makes the tile honest; it does not by itself
overturn the 2026-09-03 verdict.**

## What shipped

Reporting only — no engine change, no scoring change, no threshold moved.

- `core/backtest/edge_report.py` — `tail_rates()` (P(MFE ≥ 25%) and ≥ 40%, measured on
  the fixed 20-bar window because an exceedance rate only compares across rows when the
  window is the same), carried on every `edge_block` and on the bias-safe headline;
  `resolution_rate` added to `barrier_distribution`.
- `webapp/backend/routers/engine_edge.py` — both declared on the response model. They
  would otherwise have been silently dropped by the Pydantic projection.
- `webapp/frontend/src/components/home/EdgePulse.jsx` — the tail pair leads the tile;
  the per-tier column is the ≥25% rate at a floor of 100 matured rows; the win rate moves
  into the tooltip **with its resolution rate**, never alone.
- `tests/test_backtest_engine.py` — six new guards, each mutation-proven (inclusive
  boundary, fixed-vs-elapsed window, None-not-zero on no data, the median/tail separation,
  and both wiring points). Suite 1934 → 1940.

The threshold travels over the wire beside the rate it was measured against, so the
frontend labels what the backend measured instead of re-declaring it (EC-28).
