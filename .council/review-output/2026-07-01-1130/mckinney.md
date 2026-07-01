# McKinney (Numerical / Quant Correctness) — E3 faithfulness fix

Reviewed against current source (`metrics.py`, `scoring.py`, `narrative.py`, `bricks.py`,
`lps.py`, `evaluation.py`), not just the diff. Ran the 4 new/changed tests (all pass) and
confirmed the shipped ramp-anchor configs.

## Verification summary (the five focus areas)

1. **Inner-LPS bar translation — CORRECT.** `structure.lps` on an inner-LPS fire is
   `find_lps(df, inner, atr)`, and `find_lps` slices `work_df.iloc[box.start_bar:]` but returns
   `start/end/low` from `detect_lps` computed as `end = n - offset` over the FULL `work_df`
   (`lps.py:177,211`), i.e. **absolute df indices** regardless of inner-vs-parent. The injected
   path translates by `- box.start_bar` (parent). `find_inner_box` sets `inner.start_bar` from
   `select_inner_box` over the parent frame and `find_lps` requires `eval_idx > swing_complete_idx
   = max(r_anchor, s_anchor) >= inner.start_bar >= parent.start_bar`, so
   `lp.start_bar >= box.start_bar` always holds — the `- start` translation needs no rebasing.
   The assertion `int(lp.start_bar) >= start` is sound and, being gated on `lps is not _DETECT`,
   **cannot fire on the DETECT path**. All translated bars are `int(...)`-cast; no NaN/dtype/float
   path (bricks are int dataclass fields).

2. **`lps_pre_v_dropped` observable — CORRECT.** `injected_lps = lps` (line 1196) captures the
   PARAM before `spring = lps = None` (line 1214) shadows the local, so it holds the kwarg
   (`_DETECT` / `None` / brick), not the filtered event. The condition
   (`injected_lps is not _DETECT and injected_lps is not None and lps is None and has_valley`) fires
   only when a real brick was injected yet no `lps` event survived the Phase-D gate
   (`lstart >= 0 and lstart > v_bar`, line 1118) — the sole drop path. No false positive/negative.

3. **F3 `upthrust_terminal` range term — CORRECT and bit-for-bit for markup/in_progress.** The
   refactor factors `int(e["anchor_bar"]) >= last_up` out and ORs the type conditions:
   markup/in_progress reduce to the exact original predicate (identical), and the new `range`
   disjunct is guarded by `int(e["anchor_bar"]) > v_bar`. This **exactly mirrors the engine's own**
   Phase-B/D discriminator `in_phase_d = top_bar > v_bar` (`metrics.py:892`), where a `range` event's
   `anchor_bar == peak_bar == top_bar` and the SAME resolved `_deepest_valley_bar` `v_bar` is
   single-sourced. A Phase-D range clears; a Phase-B range (shares the label, `top_bar <= v_bar`)
   does not. markup/in_progress behavior is unchanged.

4. **`_ramp` guard — CORRECT polarity, no live change.** `full_at <= zero_at → 0.0`, placed before
   `value <= zero_at`. For every shipped anchor `full_at > zero_at` (verified:
   CANDLE_SPREAD_BOX 0.35<0.6, CANDLE_SPREAD_ATR 0.9<1.4, CANDLE_TIGHTBAR 0.3<0.65), so the first
   `if` is `False` and control flows identically — dead code for live anchors. The two inverting
   callers `1.0 - _ramp(...)` read `1.0` (full clean credit) on a collapsed band; additive callers
   read `0.0` (no bonus). Both are the polarity-safe neutral. Config floats are never NaN.

5. **Determinism / byte-parity — CLEAN.** The flag-on injected path REUSES the elected brick (no
   `find_spring`/`find_lps` call), and adds only int subtraction (`- start`) + `_clip` int min/max +
   an int-comparison `assert`. **No new float op.** Default `_DETECT` re-detects → measure-only path
   byte-identical. No dict/set-order or RNG dependence introduced.

## Findings

No P1/P2 numerical findings.

FINDING:
- Title: Elected-LPS geometry invariant is enforced only by a bare `assert` (silently stripped under `python -O`)
- File: core/structure/metrics.py:1113
- Principle: Off-by-one in windows and slicing — bound the first and last bar (Principle 4)
- Severity: P3
- What's wrong: The `inner ⊆ parent` guarantee (`lp.start_bar >= box.start_bar`) is pinned by a bare `assert`; under `-O` the assert is removed and a hypothetical left-of-box injected LPS would translate to a negative `lstart`. The immediately-following `lstart >= 0` gate (line 1118) catches it, so no negative index ever leaks — but the loud invariant becomes silent.
- Consequence: Under `-O` a future upstream regression that elects an LPS left of the parent box would be silently gate-dropped (surfaced only via `lps_pre_v_dropped`) instead of failing loudly, delaying detection of the real upstream bug.
- Fix: Acceptable as-is given the `lstart >= 0` safety net; optionally note in the comment that the assert is the loud path and the `lstart >= 0` gate is the `-O` fallback, or confirm the pipeline never runs under `-O`.

No numerical findings above P3. The bar translation, the name-capture, the F3 `v_bar` phase guard, the `_ramp` polarity, and the byte-parity of the injected path are all correct against the real code.
