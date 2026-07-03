# Structure-Reader Upgrade — Codex's lane (parallel with Claude)

**Branch:** `codex/simply-working-journal` (shared with Claude — read the protocol).
**Your half:** the **LPS / Phase-D / measurement** layer.
**Claude's half:** the **box / Phase-B** layer (`box_primitives.py`,
`consolidation.py`, the box parts of `bricks.py`, box diagnostics, the
recovered-support + high-shelf fallbacks for NKTR/PGC). **Do not touch those.**

Context lives in `docs/structure_reader_upgrade_plan_for_claude.md` (your own
handoff) and `docs/seed_recall_misses_findings.md`. This file is only the split +
your task list.

---

## X1 — DO THIS FIRST: commit your uncommitted LPS recovery
`lps.py` + `test_core_logic.py` are currently uncommitted (the GRDN/SILC/SYRE
recovery, 213 tests). Commit them now so the branch is clean and Claude isn't
working on top of an uncommitted `lps.py`.
- Scope the commit to `core/structure/lps.py`, `tests/test_core_logic.py`, and
  the three new docs (`seed_recall_misses_findings.md`,
  `structure_reader_upgrade_plan_for_claude.md`, `refactor_seed_recall_misses_codex.md`).
- **Exclude** the Track-2 journal/frontend files (`webapp/backend/models.py`,
  `routers/journal.py`, `schemas.py`, `services/auto_import.py`, all
  `webapp/frontend/*`) and the `*.db*` snapshots — use an explicit `git add`
  allowlist, never `git add -A`.
- Then run `python -m core.archive.seed_recall --fresh` and record the locked
  recall number in `seed_recall_misses_findings.md`.

## X2 — Pass 4: LPS swing-type labels (archive-first, NO gating)
Add to the `Lps` brick (`bricks.py`, the `Lps` dataclass + `find_lps` — your
region) and `lps.py`:
- `swing_type` ∈ {`terminal_valley`, `rising_support_shelf`, `buec_shelf`,
  `clean_downswing`, `undercut_rebound`} — classify the variant you already
  detect.
- raw fields: `lps_anchor_bar`/`_date`, `lps_low_bar`/`_date`,
  `lps_swing_depth_pct`/`_atr`/`_box` (anchor-high → elected-valley).
- Defaults keep existing consumers working; do **not** gate or score by type yet.

## X3 — Pass 5: Last Supper measurements (archive/UI context only)
`measure_bins` already emits `lps_stretch_atr` / `lps_stretch_box`. Add:
- `last_supper_pullback_from_extension_pct`, `last_supper_source_box_age`,
  `last_supper_reclaim_quality`.
- Surface as an archive field + optional UI **warning tag** (like "Heavy
  Resistance"). No hard reject, no score until outcomes prove a threshold.

## X4 — FOSL data-sensitivity diagnostic
FOSL fires in the targeted download but misses the full all-seed run. Diagnose
whether it's split-adjustment, a lookback-window-boundary effect, or
`fired_seeds_fresh` nondeterminism. This protects the reproducibility of the
shadow/seed guards. Read-only / diagnostic; report findings, don't "fix" by
loosening anything.

## X5 — (later, only if justified) Pass 1: `swing_events` vocabulary
Defer. It needs a `_collapse_swings` that doesn't exist yet (net-new). Build it
only once the box+LPS+spring duplication actually bites — not speculatively.

---

## Shared protocol (the one collision risk is `bricks.py`)
- In `bricks.py` you own the `Lps` dataclass + `find_lps`. **Claude owns
  `find_inner_box`, `validate_equilibrium`, `EquilibriumBox`/`InnerBox`.** Edit
  only your functions; if you must touch the shared import block or dataclass
  region, ping first. Commit small; **rebase, never parallel-clobber.**
- **Do not edit** (Claude's lane): `box_primitives.py`, `consolidation.py`,
  `tools/structure_case_audit.py`, the box parts of `bricks.py`.
- **Pass 6 (archive/UI payload) is LAST and joint.** You add
  `_lps_swing_type` / `_lps_anchor_date` / `_last_supper_*`; Claude adds
  `_box_source` / `_recovered_support` / `_high_shelf`. **Sequence** edits to
  `core/archive/writer.py` and `webapp/backend/archive_models.py` (no parallel
  edits to those two files) — coordinate who lands first.

## Validation contract (every step)
- `python -m py_compile <touched files>` · `python -m pytest tests/ -q` (≥213).
- `python -m tools.shadow_diff --check` must stay **GREEN** (Claude just
  re-baselined it; X2–X3 are archive-only so they must not drift the 31 frozen
  outputs).
- `core.archive.seed.fired_seeds_fresh(...)` targeted, then full
  `python -m core.archive.seed_recall --fresh` when behavior could change.
- **Non-goals (hard):** no global loosening of LPS/box gates, no
  `MAX_BOX_WIDTH` widening, no second `read_structure`, no scoring/tier changes,
  no re-baselining the shadow guard without Guy's sign-off.
