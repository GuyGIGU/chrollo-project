# Spec — Engine Reading-Quality Pass E2: Chronological Assembly + Trace (the puzzle)

**Tier:** Feature · **Lane:** engine (serial; owns shadow + seed-recall baselines) · **Branch:** `engine/l2-event-reader`
**Nature:** measure → render → **operator chart-eyeball** → tune. The engine surfaces an explainable read; it does not auto-decide and does not gate.

## Problem & Why

E1 finished the L2 **pieces**: `read_box_events(df, box, atr_val)` returns a flat, deterministically-ordered list of **independent** Wyckoff event zones inside the equilibrium box — `spring` (Phase C breach-S-reclaim), `test` (S touch that holds), `SOS` / `markup` / `upthrust` / `range` / `rejection` / `in_progress` (R-rail waves), and `lps` (Phase-D support test). Each is detected on its own geometry; **none is gated on another**.

What is still missing is the **read** the operator actually wants: the screener should "read a chart like a professional" — not just list pieces, but **assemble them chronologically into the Wyckoff puzzle** and **explain the read**. Today the pieces are an unordered bag with no narrative: no notion of the bullish chronology (spring → SOS → LPS), no phase segmentation, no completeness tally, and no human-readable trace of *why the structure reads the way it does*.

E2 is the **assembly layer** (roadmap L2→L3 bridge / the `(Structure, trace)` keystone, restricted to the box). It consumes E1's pieces and emits an assembled, explainable narrative — **measure-only**. It is **not** the scorer: wiring this read into the live score is E3, which is separately gated on (a) the operator's eyeball of these reads and (b) the matured multi-regime data that does not exist until ~mid-July.

## Scope

**In scope**
- A new measure-only `assemble_box_narrative(df, box, atr_val, *, v_bar=None)` in `core/structure/metrics.py` that consumes `read_box_events` and returns a structured, JSON-friendly narrative:
  - the chronological event list (passthrough of the E1 pieces);
  - a **spine** = the best-of-class canonical bullish pieces (the spring, the first confirmed SOS, the LPS), each with its box-relative bar and the per-event quality fields E1 already measured, or `None` when absent;
  - a **completeness** tally (count of distinct canonical pieces present, 0–4 over spring/SOS/LPS/test) — a descriptive count, **never a gate**;
  - a **chronology** read (`intact` / `partial` / `absent`) describing whether the bullish order spring < SOS < LPS holds — descriptive, never a gate;
  - a **terminal** read (e.g. `upthrust_terminal`) so the TITN case — a run-up that tops in one upthrust with zero SOS — reads correctly;
  - **phase spans** (B / C / D) derived from the shared V (deepest staircase valley);
  - an explainable **`trace`**: an ordered list of plain-language lines naming each event, its box-relative bar, and its role in the read.
- Extend the L2 audit/render tooling to print the assembled narrative + trace, and produce the calibration-set reads for operator eyeball.
- Tests in `tests/test_market_structure.py` covering: clean bullish chronology → `intact`; TITN-class upthrust-terminal → no SOS in the spine, `upthrust_terminal=True`, chronology `partial`; degenerate box → well-formed empty narrative; the completeness tally is a count not a gate; determinism of best-of-class selection and tie-breaks; the trace lines match the assembled spine.

**Out of scope (non-goals)**
- Wiring any of this into live firing, eligibility, score, or tier — that is **E3** (the first baseline-moving change; flag-gated; validated against matured data).
- Re-detecting or re-calibrating any event (E1 owns the piece geometry; E2 only reads and orders the pieces). No change to `read_box_events`, `measure_resistance_events`, `measure_support_tests`, `find_spring`, `find_lps`, or the SOS thresholds.
- Any change to the scoring engine, scoring weights, or which setups fire.
- Flipping the candle-spread flag or locking the SOS thresholds (still operator-gated from E1).

**Assumptions (unconfirmed — flag if wrong)**
- The narrative is a **single new measure-only function** consuming E1, not a refactor of the live `read_structure` narrative engine; it shares the same V definition (`_deepest_valley_bar`) E1 already uses, so the SOS stage-gate, the LPS Phase-D gate, and the phase segmentation cannot desync.
- "Best SOS" for the spine = the **first chronological** confirmed SOS (the creek-jump that opens markup); later held reaches are continuation, not the sign of strength. Deterministic tie-breaks throughout.
- E2 ships as its own commit on the same branch; E3 is a later, separately-gated session.

---

## Story 1 — Assemble the pieces into a chronological puzzle

**When** the engine has the independent event pieces for a box, **I want** them assembled into a single chronological narrative with a clear spine, **so** I read the structure as a story (cause → spring → strength → last support), not an unordered bag of zones.

- **Given** a box with a spring, a confirmed SOS, and an LPS in bullish order, **When** `assemble_box_narrative` runs, **Then** the spine carries that spring, that SOS, and that LPS (each with its box-relative bar and E1 quality fields) and `chronology = "intact"`.
- **Given** multiple confirmed SOS waves, **When** the spine is built, **Then** the spine SOS is the **first chronological** confirmed SOS (the creek-jump), deterministically, and the later held reaches remain visible in the event list but are not the spine SOS.
- **Given** an event class with no qualifying piece, **When** the narrative is built, **Then** that spine slot is `None` and nothing is fabricated to complete the sequence (the absence is reported, not patched).
- **Given** the same box and inputs, **When** the narrative is built twice, **Then** the result is byte-identical (deterministic best-of-class selection and ordering; no wall-clock / RNG).

## Story 2 — Read the chronology and completeness as grades, never gates

**When** I look at a setup's assembled read, **I want** the bullish chronology and the count of present pieces surfaced as descriptive quality signals, **so** richer/cleaner setups read higher without any structurally-clean setup being rejected for a missing piece.

- **Given** the full bullish chronology spring → SOS → LPS in order, **When** assembled, **Then** `chronology = "intact"` and `completeness` counts each present canonical piece — and **no** field rejects or filters the setup.
- **Given** a partial chronology (e.g. spring + LPS, no SOS), **When** assembled, **Then** `chronology = "partial"` and the narrative still assembles fully (a missing piece lowers completeness, never vetoes).
- **Given** none of the canonical bullish pieces present, **When** assembled, **Then** `chronology = "absent"` and the narrative is still well-formed (events list + trace), reporting what *is* there.
- **Negative** — **Given** any narrative output, **When** inspected, **Then** it contains **no** boolean/threshold that another layer could read as a pass/fail filter on the setup (E3 will weight these as additive confidence; E2 must not encode a veto).

## Story 3 — Read the terminal outcome (the TITN upthrust case)

**When** a run-up tops out and fails rather than holding, **I want** the assembled read to show one terminal upthrust and zero SOS, **so** the headline anchor (TITN's run to ~25 = one upthrust wave) reads as the operator sees it.

- **Given** TITN's run-up that ends in a non-recovering breach (E1 reads it as one `upthrust`, zero `SOS`), **When** assembled, **Then** the spine SOS is `None`, `upthrust_terminal = True`, the spring/test/LPS pieces still populate the read, and `chronology = "partial"` (spring → LPS, no SOS).
- **Given** a box that resolves up and holds (a real SOS, no terminal failure), **When** assembled, **Then** `upthrust_terminal = False` and the spine SOS is populated.
- **Negative** — **Given** a terminal upthrust, **When** assembled, **Then** the upthrust does **not** suppress or delete the independently-detected spring/test/LPS pieces (independence preserved through assembly).

## Story 4 — Emit an explainable trace and surface it for eyeball

**When** the narrative reads a chart a certain way, **I want** a plain-language trace of each step and the affected anchor charts rendered, **so** I can verify the *reasoning*, not just the verdict, before any of it is ever wired to score.

- **Given** an assembled narrative, **When** the trace is produced, **Then** it is an ordered list of plain-language lines, one per spine/phase step, each naming the event, its box-relative bar, and its role (e.g. "C[bar 14]: spring — breach S, reclaimed in 3 bars"; "→ chronology intact, completeness 3/4").
- **Given** the calibration/anchor set (AEF, NMAI, AMRZ, TITN, BHF, SEI) plus a sample of live fires, **When** the work reaches a checkpoint, **Then** each assembled narrative + trace is produced and surfaced with the known anchors called out (NMAI spring, TITN one-upthrust/zero-SOS).
- **Negative** — **Given** an unresolved operator disagreement on a read, **When** deciding whether to proceed to E3, **Then** E3 is **not** started — the read is re-tuned/re-surfaced first.

---

## Boundaries

✅ **Always**
- Keep the assembled narrative **measure-only** (imported by nothing in `core/pipeline`; wired to no live firing/eligibility/score/tier).
- Reuse E1's pieces and the shared `_deepest_valley_bar` V; do not re-detect or re-calibrate events.
- Keep `pytest`, `shadow_diff --check` (no canonical drift), and `seed_recall --check` green after every step.
- Keep all selection/ordering deterministic; surface renders and wait for the operator's read before E3.

⚠️ **Ask first** (surface, do not auto-decide)
- Starting E3 (wiring these reads into the score) — gated on operator eyeball of E2 reads *and* matured data.
- Any change that would move a canonical shadow field (Score, Tier, Box Width, LPS Length, Base Len, _R, _S, trigger).

🚫 **Never**
- Encode any veto/gate in the narrative — chronology and completeness are descriptive grades only.
- Fabricate a missing piece to complete a sequence; gate one event on another.
- Change `read_box_events` / the E1 detectors / the SOS thresholds, re-weight scoring, merge/push to `main`, or touch the E0 `analyze.py` / `test_analyze_dedup.py` work or the unrelated `specs/market-sector-health-board.md`.

## Success Metrics
- `assemble_box_narrative` reads the calibration set correctly: NMAI shows a Phase-C spring in the spine; TITN shows zero SOS + `upthrust_terminal=True` + spring/test/LPS present; a clean bullish setup reads `chronology=intact`.
- Completeness and chronology are descriptive (no veto); independence of pieces preserved through assembly.
- Trace is human-readable and matches the assembled spine; renders surfaced for operator eyeball.
- All gates green (pytest, shadow byte-identical, seed_recall PASS); committed to `engine/l2-event-reader`, not merged/pushed; E3 left explicitly gated.

---
*After implementing, compare results against each acceptance criterion above and list any unmet requirements.*
