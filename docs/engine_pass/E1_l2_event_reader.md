# Engine pass — E1: finish the L2 event reader

**Lane:** engine (serial — only one engine session at a time; owns shadow/seed baselines).
**Nature:** NOT sit-back-and-watch. This is **measure → render → operator eyeball → tune**, iterated.
The session produces staircase/event renders and *surfaces* them; it must not auto-decide
calibration — it waits for the operator's chart read at each step (this is how every prior L2
iteration was tuned: AEF SOS, AMRZ over-fire, TITN upthrust-wave).

## Launch setup (command center wires this)
```
git worktree add ../chrollo-E1 -b engine/l2-event-reader main
# the audit/render tools replay real tickers → copy in the runtime data (gitignored):
#   market_data_cache_5y.parquet   (the 5y panel)
#   webapp/backend/trading_journal.db   (archive, for the calibration tickers' setups)
```

## Kickoff prompt (paste into the fresh worktree's session)

```text
You are working on Chrollo (Wyckoff/VCP structure-reader). Branch: engine/l2-event-reader off main.
This is the ENGINE lane — you own the shadow/seed-recall baselines; no other engine session runs
concurrently. This is NOT sit-back-and-watch: it is measure → render → OPERATOR EYEBALL → tune,
iterated. Produce renders and SURFACE them; do not auto-decide calibration — wait for the operator's
chart read at each step.

GOAL: Finish the L2 "events off the staircase" reader — the discrete, INDEPENDENTLY-detected Wyckoff
event ZONES later layers assemble into the puzzle. (1) Calibrate the existing
measure_resistance_events so it stops over-firing in active/extended boxes, and (2) add the remaining
event bricks (spring, test, LPS, upthrust). ALL MEASURE-ONLY — wired to nothing live, so shadow/seed
MUST stay byte-identical. Chronological assembly (E2) and the graded sub-score (E3) are OUT of scope.

LOAD FIRST: recall memories project_market_structure_reader (THE spec + operator-corrected taxonomy —
load-bearing), project_reading_roadmap (grades-not-vetoes), project_phase_c_detector,
project_lps_peak_down. Read core/structure/metrics.py (read_box_staircase + measure_resistance_events),
core/structure/market_structure.py (L0 HH/HL), core/structure/bricks.py (find_spring, find_lps),
core/structure/lps.py (detect_lps), core/structure/phase_d.py. Eyeball tools:
tools/l2_staircase_audit.py + tools/l2_staircase_render.py.

OPERATOR-CORRECTED TAXONOMY — bake this in, do NOT re-derive (the operator corrected it repeatedly):
- Events are AREAS (excursion zone + recovery), not single bars — a 1-bar poke and a multi-bar linger
  are the same class. The staircase swing LOCATES the event; you measure the zone around it.
- Detect every event INDEPENDENTLY on its own geometry — NEVER gate one on another. The bullish
  chronology spring→SOS→LPS is a QUALITY GRADE when present, never a definition or gate.
- SOS = a strong push UP through R, confirmed ONLY by a HOLD afterward
  (a mini-consolidation / LPS that proves the strength stuck). Continuation (another higher high) is
  NOT confirmation — just more running. RETROACTIVE: a whole running wave that ENDS IN AN UPTHRUST is
  ONE upthrust (none of those pushes were SOS). Shakeout-tolerant: a hold that dips then RECOVERS
  still holds; only a non-recovering breakdown fails it.
- upthrust = breach ABOVE R that FAILS back into the range (distribution mirror / false break).
- spring = breach BELOW S that RECLAIMS (Phase C); test = touch of S that HOLDS.
- LPS detected INDEPENDENTLY (detect_lps window) — do NOT gate it on SOS (operator was explicit).
- STAGE-GATING: SOS and LPS are noted only on the RIGHT SIDE / Phase D (right of the V = the deepest
  staircase valley that opens the right side). A held R-reach LEFT of the V is ordinary Phase-B
  range-building (type 'range'), NOT an SOS. Tests + upthrusts are stage-agnostic (anywhere).

WORK (measure-only; gate + eyeball after each):
1. Calibrate measure_resistance_events over-firing (today e.g. AMRZ fires 15 SOS, many at price WAY
   above R = post-breakout markup, wave_bars=1). The two fixes the operator already identified:
   (a) "held" must be a REAL mini-consolidation / tightening, not merely "no collapse in 6 bars" — a
       shallow range pullback currently counts as a hold; detect genuine consolidation.
   (b) Bound SOS to reaches NEAR R (a break above R tests the rail); reaches far above R are markup, not
       SOS — classify them markup/none, not SOS (these may also be stale/extended boxes).
   Keep the wave-based terminal-outcome model (running wave → upthrust if it ends in a non-recovering
   breakdown, SOS if it ends in a confirmed hold, in_progress at the edge), shakeout-tolerant.
2. Add the remaining event bricks (each independent, AREA-based, measure-only):
   - spring: reuse find_spring (already a bounded-excursion, linger-tolerant reclaim detector).
   - test:   touch of S that holds (stage-agnostic).
   - LPS:    reuse detect_lps (already a multi-bar window) — independent; Phase-D-gated for the LPS.
   - upthrust: breach_R that fails back into the low zone (stage-agnostic).
3. Render the calibration set with tools/l2_staircase_render.py (AEF, NMAI, AMRZ, TITN, BHF, SEI — the
   memory's worked examples) → SURFACE the renders → incorporate the operator's corrections →
   re-render. Repeat until the operator signs off. Known anchors that must hold: AEF Jun-16 = the real
   SOS; NMAI Jun-9 = the spring (valley breach_S that reclaims); TITN run-up to ~25 = ONE upthrust wave
   (zero SOS); AMRZ over-firing drops to a sane count.

GATES each step: python -m pytest -q ; python -m tools.shadow_diff --check (MUST stay
"no canonical drift" — L2 is wired to nothing live, so ANY drift = a bug → STOP and diff, do not
--capture) ; python -m core.archive.seed_recall --check. Add/keep tests in
tests/test_market_structure.py.

CONSTRAINTS: MEASURE-ONLY — do not wire L2 into the live evaluation/score (that's E3, a separate
gated session). Do NOT re-add the absolute-ATR V-arm check to the spring detector (tight-box bias —
see project_phase_c_detector). Geometry stays the only veto; these reads become graded evidence
later, never gates. Do not touch config/settings.py scoring weights (no re-weight here) or the live
eval chain. For THIS session, metrics.py + tests/test_market_structure.py + tools/l2_* +
tools/fidelity/l2/ are YOUR workspace.

DONE: commit to engine/l2-event-reader — calibrated measure_resistance_events + the new
spring/test/LPS/upthrust event zones, all measure-only, with tests; shadow/seed byte-identical; a
render set the operator has eyeballed + signed off. Report a per-event verdict + the calibration-set
read. Do NOT merge to main or push — the operator integrates after review.
```

## Where this sits
- **E0** (analyze.py episode-dedup) — done by command center, under adversarial verification.
- **E1** (this) — finish the event *pieces*, measure-only.
- **E2** — chronological assembly + trace (the puzzle). Depends on E1.
- **E3** — wire the puzzle as a graded additive sub-score (first baseline-moving change; flag-gated;
  validate against the ~07-15+ matured/multi-regime data).
