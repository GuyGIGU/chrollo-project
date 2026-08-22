# Performance seat — parallel-version cost + pipeline hot-path pass

Council review 2026-08-22-2250 · main @ dd4c0ab (clean, read-only run)
Evidence basis: code trace of `core/pipeline/` + `engine_alpha/evaluation.py` + `engine_alpha/scoring/`,
plus REAL production instruments — `output/scan_metrics.jsonl` (the last two primary scans) and the live
payload's species-lane counters (`output/screener_data.json` → `market_context.power_play.counts`).
No scan was run.

## Measured ground truth (the two most recent primary scans)

| phase | 2026-08-20 | 2026-08-21 |
|---|---|---|
| total | 739.0 s | 1240.4 s |
| market_data_fetch | 538.0 s | 1005.5 s |
| evaluation (wall) | 181.8 s | 224.2 s |
| power_play_lane_worker_s (aggregate across workers) | 270.0 s | 313.2 s |
| frame_prep / market_context / result_assembly | 4.7 / 5.2 / 0.03 s | 5.8 / 4.9 / 0.04 s |
| counts | 5,498 evaluated → 254 setups | 5,498 evaluated → 253 setups |

The scan is **provider-IO-bound**: the throttled per-ticker fetch is 73–81% of wall time (that shape is
the deliberate Yahoo-hardening design — not re-litigated). Everything engine-side fits in ~180–225 s of
wall. Any consolidation win should be judged against that budget, not against the fetch.

---

## Lane question 1 — does the scan compute BOTH the legacy score and TA_SCORE_V2?

**Definitive answer: both VERDICTS are computed per fire, but there is only ONE measurement pipeline,
and the legacy-exclusive arithmetic is ~0% of per-ticker work.**

Trace (`engine_alpha/evaluation.py` `_score_eval_context`, lines 488–737):
`score_setup` (the legacy scorer, `engine_alpha/scoring/scoring.py:116-295`) runs unconditionally for
every fire candidate and produces the 15 v1 term points. With `TA_SCORE_V2 = True` (live),
`compose_ta_grade` (`scoring.py:403-470`) then **reuses those same term points** as its inputs — it adds
only the spring/story terms, the warning discounts, and the chapter sums (~100 float ops plus ~60 lazy
`getattr` cap lookups per fire). The tier ternary (`evaluation.py:728-729`) calls `calculate_tier` only
on the flag-OFF branch, so the legacy ladder does not execute live. `calculate_tier` and `score_setup`
each have exactly one live call site (verified by grep).

Legacy-EXCLUSIVE compute when V2 is live = the raw-sum line + round (`scoring.py:273-275`) and the
breadth term's inclusion in that sum — microseconds per fire, ~253 fires/night. **Fraction of per-ticker
work that is legacy-only: well under 0.01% of the evaluation phase.** Retiring the legacy path buys
essentially zero scan seconds; its cost is surface area (wire fields, archive columns, frontend math),
not CPU. Which leads to the one real dependency:

FINDING:
- Title: The ranking key is still the legacy raw sum — retirement is rank-repoint first, not a delete
- File: core/pipeline/screener.py:327 · engine_alpha/scoring/scoring.py:273-275 · webapp/frontend/src/hooks/useScreenerFilters.js:12,137
- Principle: EC-3 (twin verdict surfaces) / quality-performance P1 (measure before you claim a win)
- Severity: P2
- What's wrong: With TA_SCORE_V2 live, the serialized Tier comes from `ta_grade`, but the order of
  `results_df` (and therefore the payload's default order, which the frontend's default `sortBy:'score'`
  passes through untouched) is still `sort_values(by='Score')` — the legacy ~122-point raw sum, which
  INCLUDES the 8-cap breadth term the grade deliberately exiled to the regime layer and excludes the
  grade's warning discounts.
- Consequence: The operator's default leaderboard is ranked by one verdict while the letter beside each
  row comes from the other; and any "just delete the legacy path" consolidation plan silently breaks
  ranking. Cost-wise this is free; decision-wise it is the load-bearing blocker the retirement estimate
  must price in.
- Fix: The retirement's first task is repointing the ranking key (results_df sort + frontend default) to
  the grade, with the ordering change surfaced as its own A/B-visible seam — then the legacy total, the
  Score wire field, and setupScoreMath.js can retire together. (Judgment on which order is RIGHT belongs
  to Fowler/McKinney; I flag only the dependency and its cost shape.)

## Lane question 2 — species (Power Play) lane cost, and is the dark lane bounded?

**Per evaluated ticker when the preset is live** (`evaluate_ticker_with_power_play`,
`evaluation.py:1282-1333`): the base eval runs unchanged, then `species_watch` (lines 1150–1279) runs
for every ticker. Its ladder, with the LIVE counters from the current payload (5,498 evaluated):

- ALL 5,498 pay `ticker_episodes` (`structure/power_play.py:119-205`) — vectorized rolling/numpy over
  the full frame, O(n), ~1–2 ms each ≈ ~5–10 worker-s total.
- 1,135 are watched (pole ≥ 90% in 40 bars, AR within 90 bars); 286 pending + 26 refused_clock return
  before any heavy work.
- 823 pay a SECOND full `_prepare_eval_frame_with_reason` (see finding below); 701 of those stop at the
  re-run universe gate (`pp_prep_refused`).
- Only **122** pay the second `read_structure` walk under the species window override (3 admitted_dark +
  73 refused_occupancy + 8 refused_story + 32 shelf_unframed + 6 no_seed). That second walk is the
  DESIGN (a different clock preset must produce its own election), not waste.

**Bounded: yes, three ways** — at most ONE episode per ticker (`recent[-1]`), the 90-bar
`LIVE_EPISODE_MAX_AR_AGE_BARS` recency wall, and the universe prep gate before the walk. And the cost is
**self-instrumented in production** (EC-8's instrument): summed in-worker time lands in the metrics line
as `power_play_lane_worker_s` — 270–313 aggregate worker-seconds/scan. That is roughly 10–20% of total
evaluation compute (313 worker-s against 224 s wall × worker count), i.e. an estimated ~20–40 s of wall
≈ **2–3% of the whole scan**. Honest instrument, bounded lane, cost proportionate to a live preset.

FINDING:
- Title: Species lane re-runs the frame prep the base eval just computed for the same ticker
- File: engine_alpha/evaluation.py:1206 (species_watch prep) vs 993 (_run_eval_chain prep)
- Principle: quality-performance P6 (allocate and copy deliberately) / P3 (re-computation inside a run)
- Severity: P3
- What's wrong: `species_watch` calls `_prepare_eval_frame_with_reason(df)` on the exact raw frame the
  base evaluation prepped seconds earlier inside the same worker call — the full-frame copy, three
  200/50-bar rolling windows, the 2y trim + copy, and two ATR passes, all duplicated. Live counters show
  823 of 1,135 watched tickers per scan pay it (701 duplicate refusals + 122 on the walk path).
- Consequence: An estimated ~10–25% of the lane's 313 worker-s (~40–80 worker-s, a few seconds of wall
  per scan) is byte-duplicate work; the rest of the lane's cost is the by-design second walk.
- Fix: Thread the base eval's prep result (or its refusal reason) from `evaluate_ticker_with_power_play`
  into `species_watch` instead of re-deriving it — one parameter through the composed twin, no behavior
  change, and the lane's own cost instrument verifies the saving.

## Lane question 3 — weight-0 sub-scores (rs, uptrend): computed then multiplied by zero?

Yes, literally — and it costs nothing worth fixing. `SCORE_UPTREND_BONUS = 0` and `SCORE_RS_BONUS = 0`
(config/settings.py:877,884; demoted 2026-07-25). `score_setup` still evaluates both ramps
(scoring.py:233-238), and `_ramp` computes `progress × cap` with cap 0 — about ten float ops per fire,
~253 fires/night: nanoseconds. The MEASUREMENTS feeding them (`_yearly_return`, `_excess_return_6m`)
are archived raw by the measure-first law and must stay. The zero-cap terms also legitimately flow into
the v2 grade's fixed divisor (contributing 0 by arithmetic, per taxonomy's design) and keep the
demoted chips dead-by-design. **No finding: the redundant scoring arithmetic is below measurement
noise, and removing the terms would touch the ranking sum for zero gain.**

## Lane question 4 — hot-path pass over core/pipeline/

One finding; the rest of the surface is in good shape and is listed as checked-clean below.

FINDING:
- Title: Breadth-50 is computed twice per fresh market-context, in triplicate Python passes
- File: core/pipeline/market_context.py:344 (get_market_context) and 231-238 (_compute_regime)
- Principle: quality-performance P3 (right-size the work; don't recompute inside a run)
- Severity: P3
- What's wrong: On a cache miss, `get_market_context` computes `_compute_breadth(ticker_frames, 50)`,
  then `_compute_regime` recomputes the identical breadth-50 (plus breadth-200). Each pass is a Python
  loop over ~5,500 per-ticker frames doing a fresh `pd.to_numeric(...).dropna()` copy per frame per
  pass.
- Consequence: The market_context phase measures 4.9–5.2 s/scan; roughly a third of it (~1.5–1.7 s) is
  the redundant second breadth-50 pass. Small in absolute terms (the TTL cache means it runs about once
  per session), but it is a pure duplicate.
- Fix: Compute the breadth pair once in `get_market_context` and pass the results into
  `_compute_regime` as parameters — a two-line thread-through, no behavior change.

**Checked and clean (with numbers where available):**
- `_prepare_ticker_frames` per-ticker panel slicing: measured 4.7–5.8 s for 5,895 tickers (frame_prep
  phase) — proportionate, no action.
- `apply_baseline_filters_with_reason`'s three full-frame rolling windows are NOT gate-only waste: the
  enriched SMA/Vol_50/Spread columns are consumed downstream (detect_lps re-samples Vol_50 at eval_idx;
  trend_template reads the SMAs), and the price/bars floors short-circuit BEFORE the copy+rolling. Correctly shaped.
- `result_assembly`: 0.03–0.04 s. Nothing to do.
- The archive writer's iterrows runs over fires only (~254 rows) and its sector-ETF IO is already
  batched once-per-unique-ETF with a disk cache (writer.py:383-460) — the good pattern, keep.
- `ticker_admission.screen_directory_rows` iterrows over the ~11k-row NASDAQ directory costs an
  estimated 1–2 s inside a 9 s ticker_universe phase, once per download-mode scan — below the action
  threshold; noted, not a finding.
- `downloads.py` fetch: pooled single-ticker downloads under one shared rate ceiling — the deliberate
  Yahoo-hardening/AP-2 design; scan-dominating (538–1005 s) but by ruling, and its variance is
  provider-side. Not flagged.
- Flag-dark blocks (`ELECTION_STABILITY`, `STRATEGY_READ`, `ELECTION_TRACE_EXPORT`, `FUNDAMENTALS`)
  verified compute-free when off: import + compute strictly inside the flag, spreads `{}`. EC-8 honored.
- The near-miss lane rides the ONE walk via recorder (no second walk); its per-ticker deferred-rows fold
  is bounded. Folded into the evaluation phase, no separate concern.
- Weight-0/zero-cap arithmetic in `compose_ta_grade`: ~60 lazy getattr cap resolutions per fire —
  negligible at 253 fires.

## Lane question 5 — frontend double-work from dual grade sources (one paragraph, Dodds's lane)

The payload ships BOTH families per row (`score` + `sub_scores` and the `ta_grade` family), and
`setupScoreMath.js` still derives the legacy visual/market buckets client-side per render/sort
(`useScreenerFilters.js:149-150`). At ≤254 rows this is trivial arithmetic and a few KB against a
payload dominated by candle arrays (~20.7 MB `screener_data.json`) — **no material performance cost**;
the case for retiring the dual source is EC-28/consolidation, not CPU, and the ranking-key dependency in
finding 1 is the piece of it that lands in this lane. Defer the rest to Dodds.

## Summary for the chair

The parallel versions cost almost nothing at runtime: one measurement pipeline feeds both verdicts, the
legacy-exclusive arithmetic is microseconds, the weight-0 knobs are nanoseconds, and the species lane is
bounded, gated, and self-measured at ~2–3% of scan wall (its one avoidable slice is a duplicated frame
prep, P3). The scan's real budget is the provider fetch (73–81% of wall). The one thing consolidation
MUST price in from this lane: the operator's default ranking is still the legacy raw sum — including a
term the live grade excludes — so legacy-path retirement is a rank-repoint program, not a deletion.

Out-of-lane observation passed to Hunt: `output/chrollo-service-error.log` is 173 MB two days after the
2026-08-20 log cleanup — something is churning stderr at high volume.
