# Archive

Completed planning and coordination artifacts, kept for the decision paper trail.
These are **not** operating docs — the sources of truth stay live at the repo root
and under `docs/` (`strategy_alpha.md`, `MAP.md`, `AGENTS.md`, `CLAUDE.md`, `deploy.md`,
`conventions.md`, `flag_ledger.md`, `engine_reference.md`, `decisions.md`).

Everything here describes work that already **shipped and merged** to `main`.

## The rule (2026-08-20 bloat sweep)

What lands here versus what leaves the tree at all:

- **ARCHIVE** = the file records a **decision or a measurement** — *why is the engine
  shaped this way*, or *was this lever already tried*. Its value survives zero
  references; a reader who never opens it is still protected by it existing.
- **DELETE** = process scaffolding or an undistilled capture. `git log` holds it.
- **UNTRACK** = regenerable output (renders, sidecars, scan dumps). It stays on disk,
  it just leaves git.

## Groups

- `PLAN-*.md` — Carmack-Council build plans whose features shipped; the durable spec for
  each lives on under `docs/archive/specs/` or in the code. `PLAN-event-tape.md` joined
  them in the 2026-08-20 sweep (moved from the repo root).
- `specs/` — the **13 finished implementation specs** (moved from the repo-root `specs/`,
  which no longer exists). Each one's feature is built and merged; they are kept because a
  spec states the accepted requirements a shipped behavior answers to.
- Archived **program and audit records** — `ROADMAP_2026-06.md`,
  `QUALITY_DOCTRINE_2026-07.md`, `algorithm_knob_audit.md`, `engine_alpha_release.md`,
  `solve-the-engine-flip-checklist.md`, `frontend_audit_2026-07-07.md`,
  `edge_read_2026-06-30.md`, `cockpit_teardown.md` (from the retired `docs/cockpit/`).
  Each closed its program; each is cited as evidence somewhere and so keeps resolving.
- `tools/` — **4 spent instruments whose event is over**: `heal_scan_dates_2026_08.py`
  (a one-shot archive heal, already executed), `anchor_bar_study.py`,
  `cluster_rail_validation.py`, `bar_dwell_ab.py` (each the computed half of a sealed
  pre-registered acceptance whose verdict is recorded in `docs/`). They are archived
  rather than deleted because a Tested-DEAD verdict is only re-checkable against the
  code that computed it. They are no longer importable as `tools.<name>`.
- `fidelity_grading_2026-06/` — the operator's **hand-graded `labels.csv`** plus its
  legend (`README.txt`) and the previously-spent artifacts under `spent/`. Hand grading
  is an operator measurement that cannot be regenerated, which is exactly the archive
  case; the render pipeline that consumed it is gone.
- `refactor_seed_recall_misses_codex.md`, `structure_reader_split_codex.md`,
  `structure_reader_upgrade_plan_for_claude.md` — a spent Codex↔Claude sprint-coordination
  cluster (2026-06-20), **deleted 2026-08-20** as process scaffolding under the rule above.
  Its one distilled result, `seed_recall_misses_findings.md`, stays; the LPS-variant work
  it tracked landed in `core/structure/`.

Git history retains full provenance; nothing here is load-bearing.
