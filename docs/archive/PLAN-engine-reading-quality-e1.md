# Council Plan: Engine Reading-Quality Pass E1 — L2 Event Reader + Candle-Spread Readability Grade

**Scope:** Finish the measure-only L2 "events off the staircase" reader (calibrate `measure_resistance_events`, add spring/test/LPS/upthrust as independent zones) and add a flag-gated candle-spread readability grade to `box_tightness`. One engine-lane task, two tracks, branch `engine/l2-event-reader`.
**Context:** Pure engine math (`core/structure`, `core/scoring`, `core/pipeline`) + measure-only diagnostic tools. The L2 reader is imported by nothing in `core/pipeline` (byte-parity by construction); the candle term enters only inside the existing flag-gated box-tightness block (containment).
**Boundaries:** No live wiring of L2 events (E2/E3); no re-weight; no event-gates-event; self-referential candle grade only (no global bar-width threshold); no merge/push; don't touch the E0 `analyze.py` work.
**Council dispatched:** McKinney (10), Fowler (5), Ramírez (4), Hunt (4), Saarinen (5), Friedman (4), Performance (3), Leach (1); Dodds — no recommendations (engine-only, no UI).

**Two hats (Fowler P8 / Hunt P9 — load-bearing framing):** Track A's `measure_resistance_events` calibration is *expected to move* that tool's output — it is validated by the operator chart-eyeball + the anchor-holds, never by a parity claim (it stays shadow/seed byte-identical only because it is measure-only). Track B's candle term is an *added behavior behind a flag* — with the flag OFF it must be byte-identical, proven by `shadow_diff --check`. Do not interleave the two in a way that muddies which change moved what.

---

## Task Sequence

### 1. Settings — add the flag + calibration constants (inert defaults)

| | |
|---|---|
| **Domain** | Sebastián Ramírez × Carmack — Configuration & dependency lifecycle (the config-vs-cwd trap) |
| **Ref** | `references/quality-backend.md` → Principle 5 |
| **Depends on** | — |

Define `CANDLE_SPREAD_AWARE = False` plus the readability ramp anchors and the new SOS calibration constants (the "near R" box-position ceiling and the mini-consolidation hold criterion) in `config/settings.py`, next to `TIGHTNESS_ADR_AWARE`. Defaults must make an older settings file degrade to off, never crash. The flag is read at call time via the already-imported `settings` object — never a module-level `CANDLE_SPREAD_AWARE = settings.X` read (that resolves against the backend-cwd config shadow and boot-crashes the service while repo-root pytest stays green).

---

### 2. Calibrate `measure_resistance_events` — real hold + near-R bound (measure-only)

| | |
|---|---|
| **Domain** | Wes McKinney × Carmack — No-lookahead (P1) · Units/scale consistency (P10) · Off-by-one windows (P4) |
| **Ref** | `references/quality-llm.md` → P1/P4/P10 |
| **Depends on** | Task 1 |

Two operator-identified fixes inside `metrics.py:843-867`. **(a) "Held" must be a genuine mini-consolidation/tightening**, not merely "no drop to the low-zone within `hold_min_bars`" — measure a *bounded, fully-printed* hold window; **preserve the existing `bars_after < hold_min_bars → in_progress` guard exactly** so a wave whose hold window runs past the last fetched bar stays `in_progress`, never a premature SOS (no right-edge lookahead). **(b) Bound SOS "near R"** against `peak_box_pos` (box-relative `(price−S)/box`, e.g. `<= 1 + k`) — NOT the ATR `breach_buf`, NOT an absolute gap — so AMRZ's `pkPos 2.0-2.4` markup reaches classify as a new `markup`/not-SOS type that scales across the universe. Keep the wave model, shakeout-tolerance, and the `v_bar` Phase-D split. All new boundary tests are tolerance-based `<=`/`>=` on box-relative zones, never `==` on prices. This is the SOS "hat": expected to move tool output; validated by eyeball + anchor-holds (AEF/BHF Jun-16 SOS survive, TITN run-up = one upthrust, AMRZ ~15 → sane), and by shadow/seed staying byte-identical (measure-only).

---

### 3. Add the `test` support-rail detector — new pure sibling brick (measure-only)

| | |
|---|---|
| **Domain** | Martin Fowler × Carmack — Feature Envy / put-things-that-change-together (P5); Cross-ref: McKinney P4 (symmetric S-side off-by-one) |
| **Ref** | `references/refactoring.md` → Principle 5 |
| **Depends on** | Task 2 |

Only the S-rail `test` (touch of S that holds) is genuinely new. Write it as its own small pure function reading the same box-relative staircase — a valley touching the low zone that does not break down, stage-agnostic, AREA-based (excursion + recovery). Do **not** copy-mirror the R-rail wave machinery into an S-rail twin (a second wave engine to keep calibrated in lockstep), and do **not** prematurely factor out a shared generic rail abstraction (the rails differ: SOS is Phase-D/v_bar-gated, test is stage-agnostic). Carry the identical first/last-bar bounds as the R-side so it never indexes `lows[-1]` (wraps) or `lows[n]` (raises).

---

### 4. Unified event assembler in `metrics.py` — index-aligned, deterministic, flat

| | |
|---|---|
| **Domain** | Martin Fowler × Carmack — Architecture earns its boundaries (P6); Cross-ref: McKinney P5 (index alignment) + P7 (determinism) |
| **Ref** | `references/refactoring.md` → Principle 6 |
| **Depends on** | Task 3 |

One pure assembler in `core/structure/metrics.py` (not in `tools/`, so E2 consumes it without re-homing) that returns flat independent zone dicts by reusing: `find_spring` (spring), `detect_lps`/`find_lps` (LPS — Phase-D-gated **purely on bar position right of `v_bar`, never on SOS presence**), `measure_resistance_events` (SOS/upthrust/range/rejection/markup), and the new `test` detector. **Critical: normalize every event's bar onto ONE index origin before merging** — `find_spring`/`find_lps` slice `df.iloc[box.start_bar:]` and return sub-frame-relative indices, while `measure_resistance_events` bars are `base_df`-relative; a positional merge of the two silently shifts every zone by `box.start_bar` bars. Order deterministically by `(bar, fixed type-priority)`; break `v_bar` ties by bar index. Keep field vocabulary consistent with `measure_resistance_events` (`type`/`zone_start`/`zone_end`/`peak_box_pos`). Measure-only — it must stay un-imported by `core/pipeline` (Performance: a single eval-chain import would run these multi-window scans across the whole universe every scan).

---

### 5. Candle readability grade helper + thread into `score_setup` (flag-gated, default-off)

| | |
|---|---|
| **Domain** | Wes McKinney × Carmack — NaN/inf quarantine (P2); Cross-ref: Ramírez P1 (single optional dict), Hunt P9 (no silent demote), Performance P2 (O(1)) |
| **Ref** | `references/quality-llm.md` → Principle 2 |
| **Depends on** | Task 1 |

A small pure helper `bar_compression dict → grade ∈ [floor, 1.0]`, built ONLY from the four already-guarded `measure_bar_compression` scalars (no re-opening `base_df`, no fresh divide where the box/ATR guard is absent). Coerce each input with `pd.isna(...)` (EC-2, never truthiness — `bool(np.nan)` is True) and collapse to neutral `1.0` the instant ANY required spread ratio is missing — disambiguate `tight_bar_pct == 0.0` (real "no tight bars") from missing (None ratios). Self-referential ramps only (spread/box, spread/ATR, tight-bar % are already box/ATR-normalized) — no absolute bar-width scale, reuse `_ramp`/`_clamp`. Thread `bar_compression` into `score_setup` as ONE optional keyword (default neutral) and apply the multiplier on `box_tightness_ratio` **strictly inside `if settings.CANDLE_SPREAD_AWARE:`** so the flag-off path is textually unchanged (no stray `×1.0`, no re-round, no expression reorder — an ULP drift trips `shadow_diff --check`). Grade is multiplicative in `[floor,1]` → can only preserve or discount, never inflate (grades-not-vetoes).

---

### 6. Wire `bar_compression` at the single eval-chain call site

| | |
|---|---|
| **Domain** | Martin Fowler × Carmack — EC-3 fold (one shared implementation); Cross-ref: Ramírez P1 |
| **Ref** | `references/refactoring.md` → Principle 7 / conventions EC-3 |
| **Depends on** | Task 5 |

Pass `measurements["bar_compression"]` into the single `score_setup` call in `_score_eval_context` (evaluation.py:448). Both eval-twins (live `_evaluate_ticker` + seed `_evaluate_at_date`) route through this one call, so they inherit the term with no copy — preserving the eval-fold parity. Do not add a second call site or touch `_measure_base_context` math.

---

### 7. Tests — anchors, brick, grade, flag-off parity, eval-fold

| | |
|---|---|
| **Domain** | Wes McKinney × Carmack — Determinism/byte-parity (P7); Cross-ref: Hunt P9 (anchors are the tripwire) |
| **Ref** | `references/quality-llm.md` → Principle 7 |
| **Depends on** | Tasks 2, 3, 4, 5, 6 |

Add/keep tests in `tests/test_market_structure.py` (L2) and `tests/test_scoring.py` (candle): the SOS real-hold + near-R reclassification (a far-above-R markup no longer SOS; an AEF/BHF-style breach-and-hold still SOS; a TITN-style run-and-fail = one upthrust), the new `test` detector (touch-of-S-that-holds vs a breakdown), the candle grade (neutral 1.0 on missing metrics, discounts a messy/wide-bar texture, preserves a clean one), `score_setup` flag-off byte-identity (box_tightness/total/tier unchanged), and the existing eval-fold parity test stays green.

---

### 8. Render upgrade + eyeball contact sheet (Track A before/after + Track B A/B)

| | |
|---|---|
| **Domain** | Karri Saarinen × Vitaly Friedman × Carmack — Color/typography/spacing legibility + operator-trust workflow |
| **Ref** | `references/quality-ui.md` → P2/P4/P5 ; `references/quality-ux.md` → P8/P9 |
| **Depends on** | Tasks 4, 5 |

Extend `tools/l2_staircase_render.py` (and a small candle A/B tool): one fixed, distinguishable color per event CLASS (springs/tests get their own non-status hue; never reuse red for both breach_S and upthrust); each zone drawn as an AREA with its class word labelled and a class with zero events drawing nothing; overlapping zones resolved by lane/band (R-events top, S-events bottom, low consistent alpha so the bars/rails stay visible). Surface the full set as ONE grouped artifact: Track-A anchors (AEF/NMAI/AMRZ/TITN/BHF/SEI) **before/after** the SOS recalibration on identical geometry, each captioned with its name + expected verdict; Track-B candle A/B (TITN/DHX/IX) flag-off vs flag-on at identical scale/bar-density with the numeric `box_tightness` on each panel and the expected direction shown. Group Track A apart from Track B (independent accept/reject decisions); make non-sign-off frictionless (record which anchor was rejected + why; re-render regenerates the comparable set).

---

### 9. Gates + surface — byte-parity tripwire, then hand to the operator

| | |
|---|---|
| **Domain** | Wes McKinney × Troy Hunt × Carmack — Byte-parity tripwire / tamper detection |
| **Ref** | `references/quality-llm.md` → P7 ; `references/security.md` → Principle 9 |
| **Depends on** | Tasks 7, 8 |

After every step run `pytest -q`, `tools.shadow_diff --check` (MUST stay "no canonical drift" — L2 is wired to nothing live and the candle flag is off; treat ANY drift as a containment failure to diagnose, never `--capture`), and `core.archive.seed_recall --check` (the AEF/BHF/NMAI/TITN anchors are the determinism tripwire — an anchor flip is a slicing/lookahead regression, not a tuning result). Surface the contact sheet for the operator's chart-eyeball; commit to `engine/l2-event-reader`; do NOT merge/push; do NOT lock any calibration (the SOS thresholds, the candle anchors, the flag flip) without the operator's sign-off.

---

## Risks & Watchpoints

- **Fowler / Hunt — Two hats (don't muddy what moved what):** keep the SOS calibration commit logically distinct from the flag-gated candle commit. The first is eyeball-validated and moves the tool render; the second must be flag-off byte-identical.
- **McKinney — Copy-vs-view (P5):** the new `test`/assembler windows must read columns by value (`.values.astype(float)`) and never assign a derived column onto a `base_df` slice that may be a view; `.copy()` first if a working column is ever needed. A SettingWithCopy mutation perturbs a downstream metric and breaks shadow parity in a hard-to-trace way.
- **Leach — Non-persistence (P3/P5):** this branch persists nothing new (the `_base_median_spread_*` are already archived). Do NOT let a measure-only event zone quietly become a `setup_archive` column here; if a future pass persists one, it must be additive-nullable `ADD COLUMN` + `pd.isna` read-coercion.
- **McKinney — `tight_bar_pct` 0.0 ambiguity:** 0.0 is returned both for "no tight bars" (real, should discount) and as the empty-base default; disambiguate by whether the spread ratios are None before treating it as data.

---

## External Setup Required

No external setup required. All tasks are within the codebase; the only out-of-band step is the operator's chart-eyeball sign-off on the surfaced renders (Task 9), which the workflow waits for and never auto-decides.

---

## Summary

| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | Settings: flag + calibration constants (inert) | Ramírez | — |
| 2 | Calibrate `measure_resistance_events` (real-hold + near-R) | McKinney | 1 |
| 3 | New `test` support-rail detector (sibling brick) | Fowler | 2 |
| 4 | Unified event assembler (index-aligned, deterministic) | Fowler / McKinney | 3 |
| 5 | Candle grade helper + thread into `score_setup` (flag-gated) | McKinney / Ramírez | 1 |
| 6 | Wire `bar_compression` at the single call site | Fowler | 5 |
| 7 | Tests (anchors, brick, grade, flag-off parity, fold) | McKinney | 2,3,4,5,6 |
| 8 | Render upgrade + eyeball contact sheet | Saarinen / Friedman | 4,5 |
| 9 | Gates + surface for operator eyeball | McKinney / Hunt | 7,8 |

## Verdict

The single most important domain here is **McKinney's numerical correctness** — every real risk lives in the engine math: the right-edge-honest hold (no lookahead), the box-relative near-R bound (the ADR −0.73 bug-class waiting to recur on the wrong axis), the one-index-origin merge of bricks that slice from different frames, and the flag-off byte-parity of the candle term. **Start with Task 1 → 2**: the SOS calibration is the highest-value, most-constrained change and it stands alone (measure-only, eyeball-gated). Build the candle track (5 → 6) in parallel conceptually but commit it separately behind its default-off flag so the two hats never blur. The whole pass is recall-safe by construction — the discipline is to *prove* it each step (shadow byte-identical, seed anchors held) and to *surface, not decide* the calibration. Carmack would say: the math is the product; render it, let the operator's eye be the judge, and don't move a single canonical float you didn't mean to.
