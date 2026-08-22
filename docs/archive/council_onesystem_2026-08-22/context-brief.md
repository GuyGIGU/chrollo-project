# Context Brief — "One System" consolidation review + research (whole repo)

## Decision this run must produce                                [TOP = highest signal]

The operator has ruled: **"we aren't adding more VERSIONS of the code that try to solve the same
thing. We are developing ONE system that can recognize setups based on price-action patterns I
describe. I need a solution that can read it, understand it, and output them to me."**

This run produces the DEFINITIVE consolidation answer:

1. **A complete census of every parallel "version"** in this repo — code twins, legacy paths kept
   alive next to their replacements, parked branches, refused-but-kept flips, uncommitted patches,
   stashes — each with a ruling recommendation: **MERGE / DELETE / FOLD / KEEP-WITH-REASON**.
   "Parked indefinitely" is NOT an allowed verdict; that is the disease.
2. **The architecture answer**: does the current shape (structure measures → scoring judges →
   pipeline coordinates; measure-first bonus lanes; flag protocol; marks corpora; A/B graduation)
   actually support "operator describes a pattern in words → the ONE engine reads it live" — and
   where exactly does that loop today FORK versions instead of evolving the one system?

- The one question each worker answers in their lane: **"where does my domain hold two things
  that answer the same question, and what is the single-system fix?"** Plus your normal
  P1/P2/P3 bug-hunting in your lane — this is also a full review.
- Out of scope: implementing fixes (this run rules; implementation is a follow-up);
  changing scoring weights/tier thresholds; anything touching sealed corpora (`docs/marks/`);
  booting the backend; placing trades (IBKR is read-only, never violate).

## Landscape                                                     [MIDDLE = reference detail]

**What this is:** Chrollo — a Wyckoff/VCP/LPS stock screener. Python engine
(`engine_alpha/structure/` = geometry facts, `engine_alpha/scoring/` = opinion,
`core/pipeline/` = conductor, `core/archive/` = books of record), FastAPI backend
(`webapp/backend/`), React 19 + Vite frontend (`webapp/frontend/src/`, plain JSX). Weights live
in `config/settings.py`. Theory doc = `docs/strategy_alpha.md`; implementation doc =
`docs/engine_reference.md`; rulings + Tested-DEAD graveyard = `docs/decisions.md` (append-only).

**Grounding facts (phase-1 gates, measured 2026-08-22):**
- Working tree CLEAN at main `dd4c0ab`; main is 7 commits ahead of origin (unpushed).
- eslint: PASS (exit 0). Full pytest: running, expected green (1,624 passed at the merge hours ago).
- Live archive: 9,438 rows; only 3 rows carry species data (NNBR/QTTB/BRKR, all admitted_dark,
  scan 2026-08-19). The species preset is LIVE.

**THE VERSION CENSUS SEED (verified 2026-08-22 — workers extend/verify, don't re-derive):**

Branches, `main-unique-commits/branch-unique-commits` vs main:
- `proposal/first-legal-look-fix` — 0/1, commit `80efa9f` 2026-08-20. A CORRECTNESS fix to
  `first_legal_look` in `engine_alpha/structure/power_play.py` (edge-reserve bias; oracle-validated
  65 exact/0 late vs legacy 1/66; zero effect on all 3 live species rows; census "missed by clock"
  107→12, elections 5→0 at clock 8). Sitting unmerged as a second version of live engine code.
- `engine/ta-score-v2` — 433/2, last 2026-07-02: "P3.5 Wave-1 tag-fold — spring term (flag-gated)".
  TA_SCORE_V2 itself is LIVE on main; these 2 commits never merged. Superseded or stranded?
- `wip/audit-tool-tweaks` — 362/1, 2026-07-13: structure_case_audit + phase_a_pip_diff enhancements.
- `wip/pivot-canon-2026-07` — 109/1, 2026-07-27: parked last-supper-pivot + wyckoff-canon session.
- `wip/signal-edge-backtest` — 391/1, 2026-07-13: signal-edge framework (deflated Sharpe, event study).
- `worktree-council-p2-followups` — 462/1, 2026-06-30: council P2 follow-ups. Likely re-landed on
  main another way (check `git cherry` / content equivalence).
- `git stash stash@{0}`: "foreign: last_supper_pivot hunk (other session) - evaluation.py".
- Remote-only branches (13, all old feature branches already merged or superseded) — low priority,
  list them for hygiene only.

In-CODE parallel versions known before this run (verify + extend):
- **Legacy score path vs TA_SCORE_V2**: V2 flipped live 2026-08-09/10; the legacy path's staged
  retirement never executed. `webapp/frontend/src/components/setupScoreMath.js` is the frozen
  legacy remnant, deliberately test-pinned by `tests/test_frontend_score_caps.py` ("retires with
  the legacy path"). Where else does the legacy path live (engine, wire, frontend, archive columns)?
- **Story-form vs ratchet-form species read**: the STORY-FORM flip was attempted + REFUSED
  (`a3397a5` reverted; shadow_diff caught WCC electing a 2.2× wider box). The refused form still
  exists in code as the story lane. Is it one system with a graded lane, or a second version?
- **atr_squeeze not ADR-rebased** while box tightness was rebased — a measurement twin left behind.
- **Climax-anchor defect** (mechanised 2026-08-19, one ruling open) — polarity keyed via a
  Tested-DEAD keying; the fix is designed but not landed.
- Sub-scores demoted to weight 0 (rs, uptrend) — dead knobs still computed?
- Dark flags never flipped (AR first-reaction DO-NOT-FLIP with kill-by 2026-09-15; others?).

**The operator→engine pattern loop as built** (the research half): operator describes/draws →
calibration marks DB (editable, operator-owned) → per-mark human-gated export to sealed
`docs/marks/` corpus (EC-9) → harness/census evidence (sidecars only, EC-46) → measure-first dark
flag (EC-8 full protocol) → A/B + cost bound → operator flip ruling → live. Conventions EC-3/EC-18/
EC-28/EC-43 already outlaw twins. The question is where practice diverges from this law.

**Settled decisions — DO NOT re-litigate** (from conventions.md + docs/decisions.md):
- All AP-1..AP-10 accepted patterns (read conventions.md at repo root before flagging anything).
- AP-5: the JS↔Python fill-ledger twin is deliberate. AP-8: story-admission read vs archive
  substrate read are DIFFERENT bases by design. AP-10: window presets through the one scoped
  override is the pattern, not a smell.
- The Tested-DEAD table in `docs/decisions.md` — never re-propose a dead lever.
- Bull-only corpus is the relevant population (operator rule); flag sample SIZE, not regime.
- Textbook Wyckoff/Minervini fidelity is NOT a success criterion.

## Worker assignments (lane = ONLY yours; budget ~30-60k tokens each)

- **Fowler (refactoring)**: the in-code version census on main. Legacy-vs-V2 score path (full
  extent: engine, config, wire, frontend), setupScoreMath.js, EC-3/EC-18/EC-28/EC-43 sweep for
  twins born since the last review, dead knobs still computed, folds promised but not executed.
  Reads: engine_alpha/, config/settings.py, core/, webapp/frontend/src/components/setupScoreMath.js.
- **McKinney (numerical)**: the engine read itself. Rule on `proposal/first-legal-look-fix`
  DEFINITIVELY (merge or kill — read the branch diff `git diff main..proposal/first-legal-look-fix`,
  judge correctness). The species story-vs-ratchet duality. atr_squeeze rebase twin. Climax-anchor
  state. Lookahead/determinism bugs anywhere in engine_alpha/. Is the read ONE pipeline?
- **Beck (tests)**: which tests pin parallel versions alive (test_frontend_score_caps.py and
  anything else); what test moves a legacy-path retirement needs; offline guards not in pytest
  (doctrine_audit arity trap precedent); trend-terminal suite state; test debt blocking consolidation.
- **Ramírez (backend)**: webapp/backend/ — routes/services serving BOTH legacy and V2 verdicts;
  wire duplication; what the staged retirement of the legacy path means server-side; general
  backend bug hunt (sync handlers are intentional, AP; scheduler TZ America/New_York is intentional).
- **Dodds (frontend)**: webapp/frontend/src/ — every consumer of legacy vs V2 grade fields;
  EC-28 sweep (any rule re-declared client-side); setupScoreMath.js retirement path from the
  consumer side; general frontend bug hunt (null-safety via utils/format.js fx guard is law).
- **Leach (data integrity)**: core/archive/ + webapp/backend/database.py + models. Archive columns
  belonging to retired/legacy paths; species columns; closed-set enforcement (EC-19/22/23);
  what legacy-path retirement means for 9,438 books-of-record rows (answer: columns stay, writers
  stop? rule it). SQLite/parquet integrity bugs.
- **Hunt (security/hygiene)**: the branch+stash+worktree census as RISK. For each of the 6 local
  branches: is the payload content already on main (`git cherry -v main <branch>`, diff the payload)?
  What is stranded? The stash. 7 unpushed commits on main (single-copy risk). Sealed-corpus guard
  coverage during a consolidation. Supply chain quick pass.
- **Performance**: what the parallel paths COST. Does the scan compute legacy+V2 both? Species
  lane cost? Dead sub-scores at weight 0 still computed? Frontend double-render from dual grade
  sources? Quantify wins from retirement. core/pipeline/ hot-path pass.
- **Saarinen (UI)**: does the operator SEE one verdict? Screener/watchlist/calibration surfaces
  showing legacy grade vs TA grade vs tier — competing truths on screen. Instrument-panel
  coherence per DESIGN.md. Narrow lane; if clean, say so in one line.
- **Friedman (UX — THE RESEARCH SEAT)**: the operator→engine loop end to end. Walk the real
  artifacts: calibration workbench → marks DB → sealed corpus → census/A-B → flag ledger →
  decisions.md → flip. Where does describing a NEW pattern today force a fork (proposal branch,
  refused flip kept as code, patch on disk) instead of a lane in the one system? Design the
  definitive intake shape: "operator describes pattern → it becomes a measure-first lane in THE
  engine" with the existing conventions (EC-8/9/15/16/42/43/45/46) as rails. This is the
  operator's actual ask — treat it as the deepest lane in the run.

## Hard constraints — DO NOT FORGET                              [BOTTOM = re-surfaced signal]

- **NEVER**: place/modify trades; set IBKR_LIVE_CONFIRMED/IBKR_AUTO_CONNECT; boot the backend
  (no uvicorn / start_dashboard.bat — importing main in a subprocess is allowed); install services.
- **READ-ONLY RUN**: workers read and report; NO edits to repo files, NO commits, NO checkouts
  that would touch the working tree (use `git show`/`git diff` for branch content, never
  `git checkout`). The live DB (`webapp/backend/trading_journal.db`) may be read via
  `mode=ro` URI only.
- Interpreter for any Python: `.\.venv\Scripts\python.exe` — NEVER bare `python`.
- `docs/decisions.md` is append-only; `docs/marks/` is sealed; do not propose editing either's history.
- Check `docs/decisions.md` Tested-DEAD + conventions.md AP-* BEFORE proposing any lever/finding.
- Findings in PLAIN ENGLISH, no code dumps. Stay in your lane. Cite file:line.
- Write full output to your assigned file under
  `C:\Users\User\Documents\Projects\Chrollo Project\.council\review-output\2026-08-22-2250\`;
  return ONLY one line: "Wrote <persona>.md — N items (counts by severity)".
