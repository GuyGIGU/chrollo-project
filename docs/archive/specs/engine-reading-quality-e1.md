# Spec — Engine Reading-Quality Pass E1: L2 Event Reader + Candle-Spread Readability Grade

**Tier:** Feature · **Lane:** engine (serial; owns shadow + seed-recall baselines) · **Branch:** `engine/l2-event-reader`
**Nature:** measure → render → **operator chart-eyeball** → tune. The engine surfaces reads; it does not auto-decide calibration.

## Problem & Why

The screener reads structure but two reading-quality gaps remain:

1. **The L2 "events off the staircase" reader is unfinished.** `measure_resistance_events` over-fires SOS in active/extended boxes (AMRZ fires ~15 SOS, many on post-breakout markup far above the rail, `wave_bars=1`), because "held" currently means only "no collapse in ~6 bars" — a shallow range pullback wrongly counts as a hold. And the other Wyckoff events the later layers must assemble — spring, test, LPS, upthrust — are not yet emitted as independent zones.
2. **Box tightness is texture-blind.** Tightness is scored from box width alone (now ADR-relative). A base with wide-but-orderly bars (TITN: spread/box 0.34, spread/ATR 0.68) scores its width the same as a base with choppy bars (DHX: spread/box ~0.55). Structurally-clean volatile coils are under-credited; messy wide-bar bases are over-credited.

Both are **reading-quality** improvements that must enter the deterministic engine without moving its output until an operator eyeballs and signs off — consistent with the project's measure-first, grades-not-vetoes discipline.

## Scope

**In scope**
- Calibrate `measure_resistance_events` so SOS stops over-firing: (a) "held" must be a genuine mini-consolidation / tightening, not merely "no collapse"; (b) bound SOS to reaches **near R** — far-above-R reaches are markup, not creek-jumps.
- Add the remaining event-zone bricks, each **independent** and **area-based** (excursion zone + recovery), **measure-only**: spring, test, LPS (Phase-D-gated), upthrust.
- Add a **candle-spread readability grade** that multiplies the `box_tightness` sub-score, behind a new default-off flag, derived self-referentially from the base's own bar texture.
- Render the calibration/anchor set and surface it for operator eyeball.

**Out of scope (non-goals)**
- Chronological assembly of events into the puzzle (E2) and any graded puzzle sub-score that uses these events (E3).
- Wiring L2 events into live firing, eligibility, score, or tier.
- Any re-weighting of existing scoring weights, or any change to which setups fire.
- Flipping any calibration live without an operator eyeball (the flag flip and the SOS thresholds are operator-gated decisions, surfaced not committed-on).

**Assumptions (unconfirmed — flag if wrong)**
- The candle-spread grade is the second flag-gated tightness refinement (sibling to the now-live `TIGHTNESS_ADR_AWARE`); it ships **default-off** and is decided by the same chart-eyeball gate the ADR flip used.
- "Single task" = one branch, one council pipeline, one commit set — the two tracks share the engine-lane gates and the measure-first philosophy.

---

## Story 1 — Stop SOS over-firing in active/extended boxes

**When** I scan an active or already-broken-out box like AMRZ, **I want** the engine to stop labeling post-breakout markup pushes as SOS, **so** the L2 read shows genuine Phase-D creek-jumps that held — not running markup far above the rail.

- **Given** a box where a reach pushes far above R (price well beyond the rail, e.g. AMRZ `pkPos` 2.0–2.4), **When** `measure_resistance_events` classifies it, **Then** it is classified as markup / not-SOS, never SOS.
- **Given** a strong push up through R, **When** the bars after it are merely a shallow range pullback that does not collapse, **Then** that alone does **not** confirm an SOS — confirmation requires a genuine mini-consolidation / tightening hold.
- **Given** a Phase-D push that holds, then dips below the hold and **recovers**, **When** the hold is evaluated, **Then** the hold still counts (shakeout-tolerant); only a non-recovering breakdown fails it.
- **Given** a whole wave of strong higher-highs that ends in a non-recovering breakdown (TITN's run to ~25), **When** the wave is classified, **Then** the entire wave is **one upthrust** and contains **zero** SOS.
- **Given** AMRZ after calibration, **When** the events are counted, **Then** the SOS count drops from ~15 to a sane handful, with no SOS on reaches far above R.
- **Negative** — **Given** the genuine creek-jump anchors (AEF Jun-16, BHF Jun-16), **When** re-measured after calibration, **Then** each still reads as an SOS (the calibration tightens, it does not erase real SOS).

## Story 2 — Detect spring / test / LPS / upthrust as independent zones

**When** I eyeball a setup's structure, **I want** each Wyckoff event detected independently as an area-zone on its own geometry, **so** I see the full puzzle of pieces without any event being defined by another.

- **Given** a valley that breaches S and reclaims (NMAI Jun-9), **When** the reader runs, **Then** a **spring** zone is emitted covering the excursion-and-recovery area (not a single bar).
- **Given** a touch of S that holds (stage-agnostic, anywhere in the box), **When** the reader runs, **Then** a **test** zone is emitted.
- **Given** a support test that holds on the right side / Phase D, **When** the reader runs, **Then** an **LPS** zone is emitted, detected on its own window and **Phase-D-gated** — never gated on the presence of an SOS.
- **Given** a breach above R that fails back into the range, **When** the reader runs, **Then** an **upthrust** zone is emitted (stage-agnostic).
- **Given** the chronology spring → SOS → LPS is present, **When** events are detected, **Then** the chronology is treated as a future quality signal only — it is **never** a definition or gate for any single event.
- **Negative** — **Given** a setup with no qualifying event of a class, **When** the reader runs, **Then** zero zones of that class are emitted (no event is fabricated to complete a sequence).

## Story 3 — Grade box tightness on candle readability, not raw width

**When** a base has wide candles but clean rail-respecting structure (TITN), **I want** tightness graded on structural readability rather than absolute bar width, **so** volatile-but-clean coils aren't demoted and messy wide-bar bases (DHX) aren't promoted.

- **Given** the candle-spread flag is **off** (default), **When** any setup is scored, **Then** its `box_tightness` sub-score, total Score, and Tier are byte-identical to today.
- **Given** the flag is **on** and a base whose bars are quiet relative to its **own** box and ATR (TITN: spread/box 0.34, spread/ATR 0.68, tight-bar 0.77), **When** scored, **Then** its `box_tightness` is preserved (readability grade ≈ full credit).
- **Given** the flag is **on** and a base with the same R–S width but choppy interior bars (DHX-class, spread/box ~0.55), **When** scored, **Then** its `box_tightness` is discounted toward zero.
- **Given** a high-ADR stock with orderly bars, **When** the grade is computed, **Then** it is **not** penalized for absolute bar width — the grade reads each base against its own volatility, never a global bar-width threshold.
- **Negative** — **Given** the base-texture measures are missing/unavailable, **When** the grade is computed, **Then** it defaults to neutral (full credit, no discount) so the absence of data never silently demotes a setup.

## Story 4 — Surface every changed read for operator eyeball before locking

**When** the event read or the tightness grade changes a chart, **I want** the affected anchor charts rendered and surfaced for my review before any calibration is locked, **so** I sign off on the read, not the engine.

- **Given** the calibration set (AEF, NMAI, AMRZ, TITN, BHF, SEI), **When** the work reaches a checkpoint, **Then** a render of each is produced and surfaced with the known anchors called out.
- **Given** a candle-spread A/B comparison, **When** surfaced, **Then** it shows the same setup's tightness with the flag off vs on for the demote/promote exemplars (TITN, DHX, IX).
- **Negative** — **Given** an unresolved operator disagreement on a read, **When** deciding whether to lock the calibration, **Then** the calibration is **not** locked — the read is re-tuned and re-surfaced.

---

## Boundaries

✅ **Always**
- Keep every L2 event read **measure-only** (wired to nothing live) and the candle-spread grade **flag-default-off**.
- Keep `pytest`, `shadow_diff --check` (no canonical drift), and `seed_recall --check` green after every step.
- Route the candle-spread term through the single shared scoring call site so both eval-twins (live + seed) stay folded (EC-3).
- Detect each event on its own geometry; surface renders and wait for the operator's read.

⚠️ **Ask first** (surface, do not auto-decide)
- Flipping the candle-spread flag live, or locking the SOS "near R" / hold thresholds — these are operator chart-eyeball decisions.
- Anything that would move a canonical shadow field (Score, Tier, Box Width, _R, _S, trigger).

🚫 **Never**
- Wire L2 events into live firing/eligibility/score/tier (that is E3).
- Gate one event on another; use a global/absolute candle-width threshold instead of a self-referential one.
- Re-add the absolute-ATR "V-arm" amplitude check to the spring detector (tight-box bias).
- Re-weight existing scoring weights, merge/push to `main`, or touch the E0 `analyze.py` / `test_analyze_dedup.py` work.

## Success Metrics
- AMRZ SOS count drops from ~15 to a sane handful; AEF Jun-16 + BHF Jun-16 SOS, NMAI Jun-9 spring, and TITN-run-up = one-upthrust all hold.
- Spring/test/LPS/upthrust zones emitted independently and read correctly on the calibration set.
- Candle-spread flag-off: shadow byte-identical (containment). Flag-on: TITN/IX tightness preserved, DHX discounted; firing decisions unchanged.
- All gates green; the work is surfaced for operator eyeball, committed to `engine/l2-event-reader`, not merged/pushed.

---
*After implementing, compare results against each acceptance criterion above and list any unmet requirements.*
