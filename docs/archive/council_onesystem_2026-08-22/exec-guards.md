# Guard-hardening execution — 2026-08-22 council (Beck F1/P3, Friedman F2, Hunt sealed-set + dep-lock)

Executor run, main working tree (UNCOMMITTED — the chair commits). 7 files: 5 edited, 2 new.
Interpreter: `.\.venv\Scripts\python.exe` throughout. No engine/scoring code touched; no backend booted.

## Fix 1 — doctrine gate pytest plumbing (Beck F1, P1)

**NEW `tests/test_doctrine_audit.py`** (8 tests, hermetic, `test_pointer_audit.py` pattern).
`tools/doctrine_audit.py` itself needed **zero refactor** — `_audit_setup` was already importable
with an injected check collector.

- (a) Signature pins on every seam the audit spies/calls, via `inspect.signature`:
  - `bricks._cause_is_up` pinned to `["df", "root", "pbs", "terminal_floor"]` — the spied seam
    of the arity trap (9fbbca3). The spy is deliberately `*args/**kwargs`-transparent, so a seam
    change would not crash it — it would silently change what the captured value MEANS; the pin
    makes that a named RED. Plus a source tripwire: `"bricks._cause_is_up"` must appear in the
    tool, so a re-pointed spy forces the pin to move in the same change.
  - `read_structure` leading params `["df", "atr"]` + the `trace` kwarg (the vetoed-vs-refused
    read depends on it); `evaluation._prepare_eval_frame` pinned to `["df"]`; the two settings
    knobs the audit reads asserted present.
- (b) One committed synthetic frame (40 bars: climax 120@2, AR 98@4, box@6, R-anchor 110@8,
  S-anchor 100@12, spring 99@20 reclaimed 100.5@21, LPS 30–34, inner 102/108@10) driven through
  the FULL check battery via `_audit_setup` with `run_audit`'s own check-collector shape. Zero
  violations asserted AND a guard-the-guard: all 23 applied invariants (A1–A3, B1–B6, C1–C6,
  D1–D4, D6–D7, E1–E2) must actually have been APPLIED (an emptied battery cannot pass vacuously).
  D5 covered by the bite-proof; the `cause_up=None` no-terminality-claim skip is pinned as its
  own test (the Tested-DEAD root.kind keying stays dead).
- (c) Four bite-proofs, one per mutated leg (EC-27 — the test names WHICH invariant refused):
  inverted rails → B1; OVERSHOOT_R LPS under its rail → D5; post-climax poke → A3;
  moved payload rail → B6.

The full live-payload audit stays offline, exactly as scoped.

## Fix 2 — graduation-drift ADVISORY (Friedman F2, P1 — advisory only, NO re-pin)

**`tools/marks_corpus.py`**: new `_graduation_drift_advisory(sealed_count)`, called at the end of
`check_corpus()` — it can never touch the gate's verdict (whole body in try/except, returns None).

- EC-13 honored — nothing re-typed: fingerprint via the ONE recipe
  (`tools.calibration_harness.load_box_marks`, the export's own loader), pin imported from
  `tools.guided_list_export.OPERATOR_APPROVED_FINGERPRINT`, DB path from `database._DB_PATH`
  (the one `__file__`-anchored path).
- Read-only by construction: `sqlite3.connect("file:...?mode=ro", uri=True)` behind a SQLAlchemy
  `creator=` engine (URI percent-encoding via `pathname2url` — the repo path contains a space).
  Verified during build: a write attempt on that connection raises
  `attempt to write a readonly database`.
- Absent DB → prints nothing (hermetic checkouts/CI stay green); any internal failure → silent
  return. Drifted → exactly one line.

Rendered live this run (gate still PASS, exit 0):

    ratchet held: 28/33 pinned hits still fire; every expected miss still misses.
    PASS

    ADVISORY: the live calibration-marks DB (34 box marks, +1 vs the 33 sealed) has drifted past the graduation pin - a graduation event is owed (tools.guided_list_export refuses until the operator re-pins).

## Fix 3 — sealed-set additions (Hunt P2, EC-44)

**`tools/_bootstrap.py` `_SEALED_FILES`** += three ruling records:
`docs/decisions.md`, `docs/anchor_marks_ruling_2026-08-14.md`, `docs/htf_edge_verdict_2026-07-04.md`.

Docs-root sweep result: examined `climax_anchor_diagnosis_2026-08-19.md`,
`rail_program_close_2026-07.md`, `guided_list_read_2026-07-24.md`, `edge_read_2026-07-22.md` —
all are evidence/analysis reports or program close-outs, not operator ground-truth/ruling corpora;
left out deliberately. `flag_ledger.md` also considered and left out: it is a working decision
surface trued up per EC-15 (routinely edited), not an append-only ruling corpus — flag for the
chair if a broader reading of EC-44 is wanted.

**`tests/test_calibration_harness.py`** `test_json_output_refuses_the_sealed_dirs` extended with
the three new files including EC-35 case variants (`Decisions.MD`,
`Anchor_Marks_Ruling_…`, `HTF_Edge_Verdict_….MD`).

## Fix 4 — geometry module skip → assertion (Beck P3)

**`tests/test_invariants.py` (~40–61 only)**: `_structures_from_fixture` now returns
`(structures, dropped)` counting prep-refusal + ATR-exception drops (a None Structure is NOT a
drop — the engine is free not to fire). The module fixture's `pytest.skip` replaced with two
assertions: `len(structures) >= _MIN_FIXTURE_STRUCTURES` (30) and
`dropped == _FIXTURE_DROPPED_BASELINE` (0).

Baseline measured this run over the committed fixture: **37 tickers → 33 structures,
0 dropped at prep/ATR, 4 legitimate non-fires** — recorded in the module comment with the
re-measure rule (only at a deliberate EC-29 fixture recapture). Floor set at 30 (below the
measured 33): catches green-by-skip and coverage collapse without turning the property suite
into a fire-forcing pin; the dropped-count equality is strict — any NEW silent drop goes red.

## Fix 5 — dependency lock (Hunt P2)

**NEW `requirements.lock`**: `pip freeze` of the ChrolloDashboard venv (67 pins — pandas 3.0.3,
numpy 2.5.1, scipy 1.18.0, SQLAlchemy 2.0.51, fastapi 0.139.2, yfinance 1.2.1, …) under a 3-line
header: a RECORD for disaster recovery (`pip install -r requirements.txt -c requirements.lock`),
NOT an installation default change, upgrades stay deliberate per AP-4.
**`requirements.txt`**: exactly one comment line added pointing at the lock; nothing else touched.

## Verification

- `py_compile` on all 5 touched/new .py files: OK.
- `pytest tests/test_doctrine_audit.py tests/test_invariants.py tests/test_calibration_harness.py
  tests/test_marks_corpus.py -q` → **63 passed in 15.7s** (0 failed, 0 skipped).
- `python -m tools.marks_corpus --check` → **PASS, exit 0**, ratchet 28/33 held, advisory rendered
  (output quoted above).

Files changed: `tools/_bootstrap.py`, `tools/marks_corpus.py`, `tests/test_invariants.py`,
`tests/test_calibration_harness.py`, `requirements.txt` (edited);
`tests/test_doctrine_audit.py`, `requirements.lock` (new). Nothing else touched; nothing committed.
