# Numerical & Quant-Engine Correctness Reference — Carmack × McKinney

> **Repurposed doc.** This file was originally "LLM Pipeline Quality" (Willison). Chrollo has **no LLM** — the engine is fully deterministic. The filename is kept so manifests stay valid, but the seat is now **Wes McKinney** covering numerical and quant-engine correctness, where Chrollo's real bugs live.

Philosophy: John Carmack. Numerical-correctness expertise: Wes McKinney (creator of pandas, author of *Python for Data Analysis*, obsessed with data-alignment and dtype precision).
Stack context: Python 3.11 / pandas / numpy / scipy. The deterministic detector pipeline in `core/` reads OHLCV bars (yfinance + IBKR), detects boxes / springs / LPS / SOS, ranks setups, and archives them to SQLite. The **prime directive is accurate visual tight-structure detection**; the crown jewel is the detector math. Engine changes ship in small, evidence-driven steps validated against **seed-recall** and **shadow-harness** guards.

**PROJECT POLICY — CORRECTNESS BEFORE CLEVERNESS, NEVER BLIND REDESIGNS:** The engine is tuned incrementally (ship → user scans → dissect the weird case → tune), validated each step against recall/shadow guards and byte-parity. Do NOT recommend speculative vectorization rewrites, broad refactors, or "rewrite the detector" changes that can't be proven bit-identical. If a hot loop is slow, the fix is a measured, parity-checked change — not a blind redesign. A change that alters detector output without an explicit recall/shadow justification is a regression, not an optimization.

Every finding must describe the **concrete failure mode** — not just "this is bad practice." A wrong number that ranks a setup one slot higher is worse than a crash, because nobody sees it. Security/path/deserialization is Hunt's domain (security.md). Async/FastAPI is Ramírez (quality-backend.md). SQLite/parquet integrity is Leach (quality-postgres.md). This doc covers: lookahead/survivorship bias, NaN/inf propagation, float equality, off-by-one in windows/slicing, pandas index alignment, dtype correctness, determinism/reproducibility, resampling, missing-bar handling, and units/scale consistency.

---

## Principle 1: Never read a bar the trader couldn't have seen — lookahead is the worst bug

*Carmack: "If a mistake is possible, it will eventually happen."*
*McKinney: precise temporal alignment is the foundation of any time-series system — a value must be attributed to the index position at which it became knowable, not the position it describes.*

Lookahead (future leak) is the single most dangerous class of bug in Chrollo because it is **silent and flattering**: a detector that peeks one bar ahead "finds" winners the engine could never have fired on live, inflates recall, and produces a screener that looks brilliant in backtest and fails in production. There is no exception in the output that says "you cheated."

### What to check

**Centered or forward-looking windows**
- `rolling(...).max()` / `.min()` / `.mean()` must be **trailing** (right-aligned, the pandas default). A `center=True` window, or any `.shift(-n)`, reads future bars. A pivot-high confirmed by bars on *both* sides is fine *only* if the signal that uses it is delayed until the right-side confirmation bar has printed — the box/LPS must be knowable at the bar it is anchored to, not at the bar in the middle of the swing.
- Severity: **P1** for any forward shift or centered window feeding a fire/score decision.

**`_evaluate_at_date` vs `_evaluate_ticker` drift (the eval-twins)**
- The seed path (`_evaluate_at_date`) slices history at a historical date; the live path (`_evaluate_ticker`) uses the latest bar. If the seed path slices with an inclusive end that includes the decision day's *future*, seed-recall reports winners the live engine can't find. The eval-twins were folded into shared helpers precisely so both routes read the same bars — keep them folded.
- Severity: **P1** if the seed slice and live slice disagree on the as-of bar.

**Survivorship in the universe**
- The scan universe must be the universe as it was *then*, not today's survivors. Scanning only currently-listed tickers at a past date silently drops the delisted losers and inflates the hit rate. The dead-ticker quarantine is an integrity control, not just a fetch optimization — don't let it retroactively prune historical fires.
- Severity: **P2** for survivorship leaking into recall claims.

---

## Principle 2: NaN and inf propagate silently — quarantine them at the boundary

*Carmack: "The structure of the code should make the intended behavior obvious."*
*McKinney: NaN is contagious in floating-point arithmetic and propagates through aggregation unless explicitly handled — `mean()` skips it, but a raw comparison against it is always `False`.*

OHLCV from yfinance arrives with gaps: missing bars, zero-volume halts, `NaN` opens on the first listed day. A single `NaN` flowing into a ratio poisons every downstream metric, and the failure mode is a **dropped or mis-ranked setup**, not an exception.

### What to check

**Inf from division by a zero/near-zero denominator**
- `box_height`, `atr_val`, `box_width` can be zero or near-zero on a flat or single-bar slice. `spread / box_height` yields `inf`; `inf` then compares `False` against thresholds and the setup vanishes. The metrics code already guards `if atr_val is None or atr_val <= 0 or box_height <= 0: return empty` — that pattern is mandatory before any ratio. New ratios that skip the guard are the bug.
- Replace inf at the source: `spreads.replace([np.inf, -np.inf], np.nan).dropna()` before aggregating, exactly as `measure_bar_compression` does.
- Severity: **P1** for an unguarded divide feeding a gate or score.

**`NaN` in a comparison silently fails the gate**
- `value <= threshold` is `False` when `value` is `NaN`. A detector that should fire on a tight box can silently *not* fire because one input was `NaN`. Decide explicitly: does `NaN` mean "reject" or "treat as missing"? Don't let it default to a silent reject.
- `np.isfinite(...)` filtering (as in `_vol_trend_from_contractions`) is the right guard for "needs N valid points" logic.
- Severity: **P1** for `NaN` silently flipping a fire decision; **P2** for `NaN` skewing a measurement.

**`.mean()` / `.median()` over a partly-NaN series**
- pandas skips `NaN` by default, so a 20-bar mean over 18 valid bars is a mean of 18 — quietly a different window than intended. If the count matters (it does for windowed structure), assert the valid-count or use `min_periods`.
- Severity: **P2**.

---

## Principle 3: Never compare prices or ratios with `==` — use tolerances

*Carmack: "Don't build on assumptions you can't verify."*
*McKinney: floating-point equality is almost never the right test; adjusted-close prices are the product of split/dividend factors and rarely land on exact representable values.*

Adjusted OHLC is multiplied through float adjustment factors. Two prices that are "the same level" differ in the 12th decimal. A boundary-respect test, a "touched the rail" test, or a "same high" pivot test written with `==` will intermittently miss.

### What to check

**Exact equality on a price/level/ratio**
- "Did this bar touch resistance?" must be `abs(high - resistance) <= tol` or a band, never `high == resistance`. Express the tolerance in the right unit (ATR-relative or fraction-of-box), not raw price — see Principle 10.
- "Are these two pivots the same level?" — same rule. A zigzag that dedupes pivots by exact equality will keep micro-duplicates.
- Severity: **P1** for `==` on a price feeding a structure decision; **P2** elsewhere.

**`np.isclose` / `math.isclose` with the wrong tolerance basis**
- `np.isclose` defaults to a *relative* tolerance — fine for ratios, wrong for prices near zero or for "within 2% of box height." State `atol` in the metric's own units. Document the basis at the call site.
- Severity: **P2** for an unstated or mismatched tolerance basis.

**Accumulated float drift in iterative sums**
- Repeated `+=` over many bars accumulates error. For traversal-density / count-style accumulators, prefer a single vectorized sum over a Python loop; if a loop is required, it must reproduce bit-identically (Principle 7).
- Severity: **P3** unless it changes a ranking.

---

## Principle 4: Off-by-one in windows and slicing — bound the first and last bar

*Carmack: "Assertions catch assumption violations before they become exploitable."*
*McKinney: the first valid index of an N-bar rolling window is position N−1, and `iloc` slicing is half-open while `loc` label slicing is inclusive — confusing the two is the classic time-series bug.*

The base, the box, the LPS zone, the spring excursion are all defined by start/end indices. One bar of slop changes which swing anchors the box and can flip a fire.

### What to check

**Inclusive vs exclusive slice ends**
- `df.iloc[start:end]` excludes `end`; `df.loc[start_date:end_date]` includes `end_date`. A box defined `iloc[box_start:box_end]` that is supposed to *include* the final bar is silently one bar short. The "as-of bar" of the live scan must be the *last* row of the slice — verify it isn't dropped.
- Severity: **P1** when the off-by-one drops the decision bar; **P2** otherwise.

**`rolling(window=N)` leading-NaN region**
- The first N−1 outputs are `NaN`. Code that indexes `result[0]` for "the first ATR" reads a `NaN`. `min_periods` changes the semantics — set it deliberately, not to silence the warning.
- Severity: **P2**.

**Empty-slice and single-bar edge cases**
- A base slice of length 0 or 1 must return the explicit empty result (as the metrics functions do), not crash or compute a degenerate median. Boundary bars (first listed day, last bar of the fetched window) are where these hit.
- Severity: **P2** for missing empty/short-slice guards.

---

## Principle 5: pandas index alignment is implicit — make it explicit

*Carmack: "If it isn't tested, it's broken."*
*McKinney: pandas aligns on the index for every binary operation; two Series that "look parallel" but carry different indices produce `NaN` where they don't overlap, not an error.*

This is the McKinney signature bug. Subtracting two Series, joining a resampled frame back to daily, or `reset_index()` mid-pipeline can silently misalign signal to bar. The result is `NaN` holes or — worse — values attributed to the wrong date.

### What to check

**Arithmetic between misaligned Series**
- `highs - resistance_series` aligns on index; if one was re-indexed or `reset_index()`-ed, the overlap is partial and the difference is `NaN` off the overlap. Operate on `.values` (numpy, positional) only when you have *proven* the two are the same length and order; otherwise keep them index-aligned and let pandas align — but verify the index matches.
- Severity: **P1** for silent misalignment feeding structure math.

**`SettingWithCopyWarning` / copy-vs-view**
- Slicing a base out of the full frame and then assigning a derived column (`base_df["Spread"] = ...`) on a view mutates ambiguously. Take an explicit `.copy()` when you intend a new frame; the metrics code reads columns defensively rather than mutating the slice — follow that.
- Severity: **P2** — a real correctness hazard, not just a warning.

**`reset_index` / `merge` dropping the temporal index**
- When the HTF layer resamples daily→weekly and joins context back, the weekly index (`W-FRI`) must map back to the correct daily anchor. A `merge` on a stale or duplicated key attributes weekly context to the wrong daily bar. The HTF code keeps the resample local and prefixed (`htf_w_*`) for exactly this reason — don't flatten it into the daily frame without an explicit alignment.
- Severity: **P1** for cross-timeframe misalignment.

---

## Principle 6: Dtype correctness — int/float/object surprises

*Carmack: "Every input is a potential source of errors."*
*McKinney: an `object`-dtype column of stringified numbers compares and sorts lexically, not numerically, and silently defeats vectorized math.*

yfinance and the parquet cache can hand back columns as `object` or `float64` depending on the path and the presence of `NaN`. A `Volume` column that arrives as `object` ("1,234") breaks every aggregation downstream.

### What to check

**Implicit object dtype on a numeric column**
- Cast at the boundary: `base_df["High"].astype(float)`, as the metrics code does, rather than trusting the fetch. A column with one stray string poisons the whole Series to `object`.
- Sorting an `object` column of numbers orders `"10" < "9"`. Setup ranking that sorts on a not-quite-numeric score column will mis-rank.
- Severity: **P1** for object-dtype on a ranked/compared column; **P2** elsewhere.

**Integer division and int/float coercion**
- Bar-count windows are ints; ratios are floats. `n_full / n_swings` must be float division (Python 3 `/` is — but a numpy int over numpy int is fine, while truncation via `//` is a bug). The traversal-density floor (`≥0.08 n_full/n_swings`) depends on this.
- Severity: **P2**.

**Datetime index dtype / timezone**
- Mixing tz-aware and tz-naive timestamps raises or silently misaligns. yfinance daily bars should be tz-naive dates; IBKR intraday may carry tz. Normalize at ingest.
- Severity: **P2**.

---

## Principle 7: Determinism and reproducibility — byte-parity is the contract

*Carmack: "If you can't reproduce a bug, you can't fix it."*
*McKinney: stable, order-independent computation is what makes a result trustworthy; an aggregation whose answer depends on row order or dict iteration is not a measurement, it's a coincidence.*

Chrollo's refactors are validated by **byte-parity**: capture the engine's output before, refactor, prove the output is bit-identical (the eval-twins fold, the `_ramp()` DRY fold). This only works if the engine is deterministic in the first place.

### What to check

**Unstable sort changing tie-broken ranks**
- `sort_values` is not stable by default for all algorithms; ties between equal-score setups must break deterministically (e.g., a stable sort plus an explicit tiebreaker like ticker). A non-stable sort makes the same scan rank two setups differently across runs — and breaks shadow baselines for no real reason.
- Severity: **P1** for non-deterministic ranking; it poisons every parity check.

**Dict / set iteration order dependence**
- Computation that folds over a `set` or relies on dict insertion order for a *numeric* result is fragile. Enumeration order of candidate boxes must not change which "emergent" box wins — the box is supposed to be emergent and root-independent; verify enumeration order doesn't sneak in as a tiebreaker.
- Severity: **P2**.

**Unseeded randomness / floating reductions**
- Any RNG (sampling, jitter) must be seeded. `np.sum` over a large array can differ from a Python loop sum in the last bits — pick one and keep it for the parity baseline. Don't introduce a parallel reduction whose float order differs run-to-run.
- Severity: **P1** for unseeded RNG in the engine; **P2** for order-sensitive reductions.

**Refactors without a parity capture**
- A change to detector math with no before/after byte-parity capture is unverifiable. The method is non-negotiable: capture → fold → compare. If the output legitimately *must* change, the diff belongs in a seed-recall/shadow justification, not slipped in unannounced.
- Severity: **P1** for unverified detector-math changes.

---

## Principle 8: Resampling correctness — daily→weekly/monthly must not leak or misalign

*Carmack: "Find the simplest solution possible, and only increase complexity when needed."*
*McKinney: resampling is an aggregation over a time bin, and the bin's label, closed side, and aggregation function each independently change the answer.*

The HTF layer runs the *same* engine on weekly/monthly bars. Resampling is where temporal correctness quietly breaks: a partial final week, a wrong bin label, or a forward-leaking aggregation.

### What to check

**Aggregation function per column**
- OHLCV must resample with the correct reducer: `Open=first, High=max, Low=min, Close=last, Volume=sum`. A `Close` aggregated as `mean` is not a weekly close. The HTF `_AGG` map encodes this — any new resample must reuse it, not hand-roll.
- Severity: **P1** for a wrong per-column reducer.

**Partial final bin = lookahead**
- The current (incomplete) week's bar contains only the days seen so far. Treating it as a closed weekly bar, or — worse — letting a `W-FRI` label imply Friday's data before Friday, leaks future structure into the HTF read. The HTF read is measure-only and must reflect only completed information at the as-of date.
- Severity: **P1** for a partial bin treated as complete in a fire-influencing read.

**Bin label / closed side**
- `W-FRI` vs `W-SUN`, `closed='left'` vs `'right'`, `ME` (month-end) labeling — each shifts which daily bars fall in which HTF bar. Mismatched conventions between the resample and the join-back misalign HTF context to the daily setup.
- Severity: **P2** for an undocumented bin convention.

---

## Principle 9: Missing bars and holidays — gaps are data, not zeros

*Carmack: "Every input is a potential source of errors."*
*McKinney: a missing observation and a zero observation are different facts; reindexing a sparse series onto a dense calendar with a fill silently invents data.*

Markets close on weekends and holidays; tickers halt; yfinance occasionally drops a bar. A window that assumes "N rows = N trading days" or that forward-fills a gap into a fake flat bar will misread structure.

### What to check

**`reindex` + `fillna` inventing bars**
- Reindexing onto a full calendar and `ffill`-ing turns a holiday into a phantom flat bar — which a tightness/compression metric reads as a real quiet bar. Decide whether a gap should be skipped (operate on actual trading bars) or explicitly marked, never silently filled.
- Severity: **P1** for invented bars feeding structure detection.

**Row-count windows vs calendar windows**
- "20-bar base" means 20 *trading* bars, which is ~28 calendar days. Mixing a calendar-day span with a bar-count window mis-sizes the base across a holiday cluster. Bar-count windows are the daily-calibrated knobs — keep them in bars.
- Severity: **P2**.

**Zero-volume / halt bars**
- A halt prints zero volume; a volume-dry-up VCP metric must distinguish "quiet" from "halted/missing." `_vol_trend_from_contractions` already filters non-finite — extend that scrutiny to zeros where they mean "no data," not "no interest."
- Severity: **P2**.

---

## Principle 10: Units and scale consistency — relative vs absolute is a real bug

*Carmack: "The structure of the code should make the intended behavior obvious."*
*McKinney: a comparison only means something when both sides share units; an absolute price threshold applied across a universe of differently-priced, differently-volatile names is not one threshold, it's hundreds of different ones.*

This is the ADR-tightness lesson made general. `box_tightness` once rewarded raw flatness and correlated −0.73 with ADR — it was secretly a low-volatility filter, not a tightness filter, because the threshold was absolute. The fix was an **ATR/ADR-relative rebase**. Scale-invariance is what lets the same calibrated brick run on a $5 stock, a $500 stock, and on weekly bars.

### What to check

**Absolute price/dollar thresholds in detector math**
- A "moved less than $X" or "within $Y of the rail" test is wrong across a price-diverse universe. Express it ATR-relative or as a fraction of box height — the metrics already report `median_spread_atr` and `median_spread_pct_box` precisely so downstream logic compares in scale-invariant units.
- Severity: **P1** for an absolute threshold in a universe-wide gate; **P2** for a measurement.

**Mixing ratio bases**
- "% of box" and "multiple of ATR" are different scales; a gate that compares one against a threshold meant for the other is silently miscalibrated. The HTF split is explicit about this: RATIO thresholds are scale-invariant and reused; only BAR-COUNT windows are rescaled per timeframe. Don't rescale a ratio.
- Severity: **P1** for a cross-basis comparison.

**Percent vs fraction (0.21 vs 21)**
- Config knobs like the markup-gate `0.21` are fractions. A stray `*100` or a threshold entered as `21` is a 100× miscalibration that won't crash — it'll just gate nothing or everything.
- Severity: **P1** for a fraction/percent mismatch on a live knob.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | Wrong numbers, silent leaks, non-determinism that breaks parity | Lookahead/future shift, NaN flipping a fire gate, `==` on prices, cross-timeframe misalignment, non-stable ranking sort, absolute threshold in a universe-wide gate, fraction/percent mismatch |
| **P2 — Fix Soon** | Mis-measurement, fragile edges, mis-calibration | NaN skewing a metric, leading-NaN window indexing, copy-vs-view mutation, object dtype on a compared column, undocumented resample/tolerance convention, survivorship in recall claims |
| **P3 — Consider** | Hygiene, accumulated drift, design questions | Iterative-sum float drift, enumeration-order tiebreakers, parallel-reduction order, conscious-tradeoff documentation gaps |

### The Overriding Filter

**BEFORE ANYTHING ELSE:** Chrollo is tuned in small, evidence-driven, parity-validated steps. Do NOT recommend speculative rewrites, broad vectorization passes, or detector changes that can't be proven bit-identical or justified against seed-recall/shadow guards. The prime directive is *correct* tight-structure detection — a faster wrong answer is still wrong.

Before writing any finding, apply the McKinney–Carmack synthesis:

1. **Could this read a bar the trader couldn't see?** If a window is centered or a slice is forward-inclusive, flag it. (Lookahead is the worst bug — silent and flattering.)
2. **Can a NaN or inf reach a comparison?** If a divide is unguarded or a gate compares against a possibly-NaN value, flag it. (NaN compares False; the setup vanishes silently.)
3. **Is `==` used on a price or ratio?** If so, flag it — use a tolerance in the right unit.
4. **Are two Series assumed parallel without proven alignment?** If indices can differ, flag the implicit pandas alignment. (Misalignment yields NaN holes or wrong-date values.)
5. **Is the result deterministic and byte-parity-able?** If a sort is unstable, an RNG unseeded, or a refactor lacks a parity capture, flag it. (No determinism, no trustworthy baseline.)
6. **Is the threshold scale-invariant?** If an absolute price/dollar value or a cross-basis ratio drives a universe-wide gate, flag it. (The ADR-tightness lesson.)
