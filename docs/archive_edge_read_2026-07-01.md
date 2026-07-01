# Archive Edge Read — 2026-07-01 (first real live-data read)

**What this is:** the first honest edge measurement off the `setup_archive` after the
maturation pipeline was made reliable + visible (OS-scheduled tick, commit `ab77cde`).
This is the "what has the objective screener actually found?" read the
engine-validation north star is built around — not a cherry-picked recall test.

Reproduce:

```
python -m core.archive.analyze                     # all sources, deduped
python -m core.archive.analyze --source screener   # live-only (the honest cut)
```

Both run on **episodes** (continuation re-flags collapsed to the first-seen anchor).

---

## Sample (what we can and cannot say)

| | |
|---|---|
| Raw archive rows | 2,826 |
| **Episodes (deduped)** | **998** (1,828 continuation re-flags collapsed) |
| Source | screener **971**, seed 26, manual 1 → overwhelmingly **live** |
| Tiers present | S 670, A 263, B 65 (only fired setups are archived → no C/D) |
| Types | LPS 925, REBOUND 73 |
| Date range | 2026-01-16 → 2026-06-30 (5.5 months) |
| Matured @20d | ~236 episodes | 
| Matured @60d | ~20 episodes (too thin — treat 60d as noise) |

### The one caveat that gates every number below
**`spy_trend` == BULLISH for 100% of rows.** The entire archive is one uninterrupted
bull regime. Therefore:

- "Win rate" = P(20d return > 0) is **inflated by market beta** — an 86% hit rate is
  partly "the market went up," not pure setup edge.
- There is **no adverse-regime cohort** in the sample, so *standalone edge*
  (does it beat holding the index / survive a correction) is **not yet proven**.
- Everything here is **directional / hypothesis-generating** — strong enough to steer
  the scoring rework, not strong enough to declare a validated edge. The now-reliable
  tick will accumulate the corrective cohort that closes this gap.

All headline numbers below use the **live-screener-only** cut unless noted.

---

## Finding 1 — The composite ranking WORKS (monotonic, and B is net-negative)

| tier | n | avg 20d | avg R | win% |
|---|---|---|---|---|
| **S** | 649 | **+8.6%** | 1.71 | 85.9% |
| **A** | 257 | +5.5% | 1.67 | 71.4% |
| **B** | 65 | **−3.3%** | 0.77 | 25.0% |

The engine's overall score/tier ordering **cleanly rank-orders forward outcomes**, and
B-tier actually loses money. This is the single strongest validation: whatever we
rebrand the score to, **the ordering is doing real work.** (Removing the 26 seed winners
dropped S from +9.3% → +8.6% exactly as expected — no seed inflation hiding here.)

## Finding 2 — Prime directive, nuanced: tightness buys CONSISTENCY, not magnitude

The blunt §5 test (mean 20d return, tight-tertile vs loose-tertile) says tightness
*contradicts* the thesis: box_width −1.9%, atr_ratio −2.5%, tightness_ratio −1.6%,
contraction_quality −2.0% (looser tertile had the higher **mean**). But mean return is
tail-sensitive, and the §3 `box_width` tertile tells the truer story:

| box_width | win% | avg R | avg 20d |
|---|---|---|---|
| **low (tight)** | **90.4%** | **1.91** | +8.0% |
| mid | 79.7% | 1.88 | +8.6% |
| high (loose) | 74.1% | 1.64 | +9.1% |

**Tighter boxes win more often with better R-expectancy; looser boxes have a fatter
right tail that lifts the raw average.** So tightness is *not* useless — it is a
consistency/hit-rate lever, not an average-return maximizer. For a discretionary trader
who wants reliable setups, tight is better. The mean-based "contradiction" is a tail
artifact, not a refutation.

**Where tightness genuinely predicts return is the RIGHT side of the base, not the gross
box:** `bin_d_range_pct` −0.39 (tighter final contraction → higher return),
`bin_d_vs_b_range_ratio` +10.3% and `base_tight_bar_pct` +5.8% (tight-tertile edge, but
n=8 — directional).

## Finding 3 — Most sub-scores are INERT on durability (the actionable rework input)

Primary outcome `durable_win` (a win that *held*, not a cash-grab) passed the adequacy
gate (n=343, minority class=158). Rank-association of each sub-score:

| verdict | sub-scores |
|---|---|
| **BENEFICIAL** | `score_base_age` (+0.31), `score_traversal_quality` (+0.19, n=27) |
| **HARMFUL** (weak, top subtraction candidate) | `score_rs_bonus` (−0.17) |
| **INERT** (|r| < 0.15) | `score_box_tightness`, `score_uptrend_bonus`, `score_adr`, `score_contraction`, `score_touch_density`, `score_vol_contraction`, `score_atr_squeeze`, `score_lps_tightness`, `score_high_proximity`, `score_breadth_bonus`, `score_ascending_support` |

**The composite ranks well (Finding 1) while carrying a lot of inert freight.** 11 of 14
sub-scores do not measurably move whether a win holds; `score_rs_bonus` is a weak *net
negative* on live data (it was only inert with seeds included — the live cut exposes it).
Only base-age and traversal-quality clearly earn their points on durability.
NB: these are subtraction *candidates* — re-weighting is a separate, guarded step.

## Finding 4 — What actually correlates with forward return (build the new score around this)

Top |corr| vs `fwd_return_20d` (all-source):

- **Worked equilibrium / touch distribution:** `eq_s_touch_thirds` +0.39, `eq_lower_dwell` +0.34
- **Right-side improvement vs left half:** `bin_d_vs_b_support_quality_delta` +0.40, `bin_d_range_pct` −0.39, `bin_d_bars` −0.31
- **Swing containment:** `trav_max_swing_frac` −0.36
- **Trend / momentum maturity:** `stage2_52w_low_pct` +0.33 (and at 60d, on tiny n: `stage2_ma200_slope` +0.57, `excess_return_6m` +0.52, `adr_pct` +0.42)

Pattern: the edge lives in **worked-equilibrium quality, right-side-of-base improvement,
swing containment, and Stage-2 trend/momentum context** — *not* in gross box tightness.
This is the shortlist to promote when reworking the score.

## Finding 5 — Data-quality cleanup (small)

5 episodes with `base_length > 250` bars (~1yr+) — almost certainly anchor
mis-detection picking an over-long window: **CACC(325), MSCI(429), MSCI(433),
BMRN(296), CWT(274)**. Not distorting the aggregate; worth a targeted look before these
pollute a future fingerprint.

---

## Implications for the scoring rework ("Technical Analysis score")

1. **Keep the composite ordering** — it demonstrably ranks (Finding 1). Don't throw the
   baby out; the rework is a *reweighting*, not a rebuild.
2. **Promote the earners:** base-age, traversal/worked-equilibrium quality, right-side
   (bin_d vs bin_b) improvement, swing containment, Stage-2 trend/momentum context.
3. **Demote / trim the freight:** `score_rs_bonus` (weak-harmful on live data) is the #1
   subtraction candidate; the large inert block spends ranking influence for nothing and
   dilutes the real signal.
4. **Reframe tightness as a consistency lever,** not a return maximizer, and locate it on
   the right side of the base — that is where it pays.
5. **Do NOT declare edge yet.** Re-run this read once a corrective/bearish cohort has
   matured; that is the test that separates "found real setups" from "rode a bull market."

Full raw report archived alongside this doc; regenerate any time with the commands at top.
