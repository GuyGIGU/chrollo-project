# engine-alpha — signal-edge backtest RESULTS (2026-07-07)

Companion to [`backtest_methodology.md`](backtest_methodology.md) (the spec). This is
the first full run of the point-in-time replay over the 5y cache. Read the methodology
doc for how the numbers are produced; this doc is what came out and what it means.

## What was measured

- **Engine:** frozen `engine-alpha` (tag `engine-alpha` = `51917ba` = main), byte-identical
  point-in-time replay (`_run_eval_chain`), the engine sees only `df[df.index <= T]`.
- **Universe / cadence:** full ~5,491-ticker cache, **weekly** scan dates.
- **Window:** **2022-04-29 → 2026-07-02** — *spans the 2022 bear*, so the single-bull-regime
  confound is (partly) broken with data on disk.
- **Sample:** **25,427 fires** (24,521 resolved to a triple-barrier label at run time; the
  rest are 2026 fires still inside their 60-bar window).
- **Storage:** scratch DB only (`backtest_weekly.db`), never the live archive.
- **Headline metric = the operator's bar:** triple-barrier **≥2.5R (or +15%) before the −1R
  stop**, in {win / loss / timeout}. Stop = `s_level × 0.97`; R = entry − stop.

## Headline — by the operator's metric (2.5R-before-−1R)

| Cohort | n | **WIN (≥2.5R)** | LOSS (−1R) | TIMEOUT |
|---|---:|---:|---:|---:|
| **Overall** | 24,521 | **30.1%** | 48.8% | 21.1% |
| Tier S | 7,789 | **33.0%** | 56.4% | 10.6% |
| Tier A | 9,196 | **31.0%** | 49.2% | 19.8% |
| Tier B | 6,776 | **26.0%** | 41.2% | 32.8% |
| Tier C | 760 | **24.6%** | 34.9% | 40.5% |
| Uptrend tape | 20,063 | **31.6%** | 47.3% | 21.1% |
| Neutral / chop | 1,988 | **19.7%** | 60.1% | 20.2% |
| Downtrend tape | 2,392 | **26.5%** | 51.5% | 22.0% |

**Tier × uptrend (how the operator actually trades):** S 34.4% · A 32.8% · B 27.5% · C 26.3%.

### What's genuinely good here
1. **The composite grade ranks the target-hit rate monotonically** — S > A > B > C, and it
   holds inside the uptrend cut too. Higher grade → more likely to reach 2.5R. The reading
   is *directionally correct*.
2. **Chop is quantifiably the worst tape** — neutral 19.7% win / 60.1% stop-out. "Don't
   trade the chop" is now a number, not a maxim. The operator already only trades longs in
   trends, so this is confirmation, not news.
3. **93.6% of fires actually break the LPS high within 60 bars** (S 94.5%, C 91.8%). The
   detected structures *resolve into a move* the vast majority of the time — they are not
   hallucinated dead zones. (Caveat: "broke out" = exceeded the LPS high, a low bar; it says
   the coil releases, not that the release runs.)

### The catch that matters for the grading rework
1. **Tier sorts WIN PROBABILITY, not R-EXPECTANCY.** S wins more (34%) *but also stops out
   more* (55%) — it is high-conviction / high-variance; C dithers (40% timeout). Crude
   barrier expectancy is **flat across tiers** (uptrend A ≈ +0.35R ≈ S ≈ +0.31R — and this
   is an *upper bound*; the realized scaled-exit sim was ≈ +0.11R). The grade answers "will
   it reach target," not "is it worth more R." That gap is a lever.
2. **What predicts reaching 2.5R is RANGE, not tightness** (trait-lift, 18.6k fires):
   `score_adr` **+19%** lift, `box_width` **+16%**; the whole tightness family is flat-to-
   negative (`box_tightness` ~0, `lps_tightness` ~0, `contraction` −4.5%, `traversal` −2%,
   `base_age` −4%); **`score_high_proximity` is INVERTED (−11%)** — setups pegged to the
   52-week high hit 2.5R *less*. The grade currently spends weight on tightness for the
   *reach* question; tightness most likely earns its keep on **risk** (fewer/smaller stops),
   which has **not** been isolated yet.

## What this run does NOT prove (the honesty bar)

1. **Base rate not computed.** The null model needs the eligible universe's forward outcomes
   per scan day (not stored). So I **cannot yet say 30% beats a random stock in the same
   tape** — and that comparison *is* the measure of reading skill. This is the one analytical
   gap worth closing.
2. **Survivorship inflates it.** The cache is a *current-survivor* list; 2022–23 delistings
   are absent, so the losers that went to zero are missing. **True win rate is lower than
   30%.**
3. **Regime-weighted toward the bull.** 82% of resolved fires (20,063 / 24,521) are uptrend;
   the bear slice is real but thin, so the headline is bull-weighted.
4. **Mechanical ≠ how the operator trades.** The barrier entered at the *fire close* with a
   fixed −1R stop and a 2.5R/+15% target. The operator waits for the *trigger* and exits
   discretionarily. These numbers describe the **engine's read graded mechanically**, not
   the operator's edge — measurement informs the grading rework, it does not define quality.
5. **Versus SPY it is beta, not alpha.** Trigger-gated CAR = −1.8% at 60 bars, calendar-time
   t = −6.5; the picks *lag* the index on a buy-and-hold basis, and DSR = 0.000 (not beyond
   the noise ceiling). The operator has explicitly ruled SPY-relative out as the bar (a
   defined-risk trader exits at target and does not care vs the index) — recorded here only
   so the file is complete, not as a verdict against the engine.

## Bottom line

By the operator's own metric, `engine-alpha` shows a **real but weak** reading skill signal:
grade-up → target-hit-up (monotonic), and the chop filter works — but the spread is narrow
(S 33% vs C 25%) and the **tightness half of the grade is not earning the reach**. The
mission is to **widen the S-vs-C gap**, which is exactly what the grading rework (driven by
the operator's quality rules + labelled examples, with these trait-lifts as evidence to
pressure-test, not as the definition) is for. The single measurement gap worth closing
alongside the examples is the **base-rate null** — "is 30% better than random in the same
tape?"

## Provenance
- Harness output: `tools/backtest_engine.py --db <scratch> --source screener --cache market_data_cache_5y.parquet`
  (full text + JSON in the session scratchpad: `report_full.txt` / `report_full.json`).
- Barrier-metric cuts: direct `setup_archive` GROUP BY (proportions self-check to 100%).
- Trait-lift: `scratchpad/trait_lift.py` (episode-collapsed, `source='screener'`).
