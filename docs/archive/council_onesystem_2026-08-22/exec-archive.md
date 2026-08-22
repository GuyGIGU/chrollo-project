# Executor report — archive lane (Leach findings 2, 3, 5, 6, 7)

Basis: main @ dd4c0ab working tree (shared with sibling executors; only the files
below touched by this lane). Live DB read via sqlite3 URI mode=ro only; backend
never booted; docs/marks/ and tests/baselines/ untouched.

## Fixes landed

### F2 (P2) — trigger-rate maturity gate at the reporter
`core/archive/analyze.py` `_perf_row`: the trigger-rate statistic now counts a
row only once its verdict is FINAL — `triggered=1` (a touch is final the moment
it happens) or `triggered=0` with the full horizon elapsed
(`bars_to_date >= HORIZON_BARS`, imported from `core.archive.outcomes` — the one
source). Semantics stated in a comment at the predicate. One reporter-side
predicate; no schema change, no history rewrite; a pre-migration DB lacking
`bars_to_date` degrades to the ungated legacy mean. The composition section's
winners-gallery bias detector (trig_rate > 0.97) deliberately NOT touched — it
measures population bias, not performance.

Live census at fix time (mode=ro, 2026-08-23): fires split = **973 immature
zeros / 0 matured zeros / 7,855 touched** — the 973 matches the finding exactly;
no untouched row has matured yet (live scans began 2026-06-01), so today the
gated rate reads from final verdicts only, which is the honest answer.

### F5 (P3) — analyze.py read-only contract enforced by the connection
`load_archive` now opens `file:{path}?mode=ro` (uri=True) — the same pattern as
`seed_recall.load_seed_rows`. A future write attempt errors loudly instead of
the contract holding by discipline.

### F6 (P3) — seed --force preserves operator curation
`core/archive/seed.py`: the existing/force branch now routes through a small
`_overwrite_existing(existing, values)` helper that skips `_CURATION_COLUMNS =
("quality_label", "notes")` — a re-seed refreshes measurements, never wipes a
hand-edited note or re-graded label. New rows still get the writer's
`quality_label='perfect'` auto-fill. Shape of the code kept; the helper exists
so the exclusion is unit-testable.

### F7 (P3) — hermetic fixture rebuild guarded + stamped
`core/archive/seed_recall.py` `build_hermetic_fixture`:
- refuses (RuntimeError, names EC-29) when the fixture already exists unless
  `reseal=True`; the refusal fires BEFORE any download (test-proven);
- every build writes a `<fixture>.meta.json` sidecar stamping the covered
  ticker set, the missing set, and the UTC freeze date;
- CLI: new `--reseal-fixture` flag modifies `--build-fixture`
  (usage-error alone); `--build-fixture` help states the refusal.

### F3 (P3) — would_be_score / would_be_tier DELETED
- `webapp/backend/archive_models.py`: the two Column declarations removed; the
  model docstring's NULL-until-measured claim replaced with the retirement
  record (a refused framing has no election context to score — unfillable by
  design).
- `webapp/backend/services/startup.py` `_MIGRATIONS`: two one-off
  `ALTER TABLE near_miss_archive DROP COLUMN` entries appended, following the
  score_oscillation / puzzle_* precedent verbatim (idempotent via the runner's
  "no such column" skip marker).
- `tools/near_miss_report.py`: the would-be-tier fallback branch deleted; the
  row keeps its "never elected, never fired" counterfactual line and the
  would-be **trigger** outcome line (that column stays — it has a real writer).

**Live-DB finding worth the chair's eye:** verified via mode=ro that the live
`near_miss_archive` (1,123 rows, 45 cols) **never even materialized the pair**
— the columns exist only in the model, so the DROP reads as already-applied on
the live DB and destroys nothing anywhere. The load-bearing half of the
retirement is therefore the MODEL removal: without it, the next backend boot's
ADD-only auto-migrator would have materialized the unwritable pair onto the
live DB. The DROP stays registered for any DB where a boot did materialize it
(and against pre-drop-backup resurrection).

## Files changed (10)

Source (6):
- `core/archive/analyze.py` (F2 + F5)
- `core/archive/seed.py` (F6)
- `core/archive/seed_recall.py` (F7)
- `webapp/backend/archive_models.py` (F3 — the pair only)
- `webapp/backend/services/startup.py` (F3 — DROP entries only)
- `tools/near_miss_report.py` (F3 — fallback branch only)

Tests (4):
- `tests/test_analyze_reporter_gates.py` (NEW — maturity gate incl. inclusive
  boundary + no-final-verdict → None + legacy degrade; mode=ro read + write
  refusal)
- `tests/test_seed_force_curation.py` (NEW — curation preserved, measurements
  refreshed; exclusion list pinned to real model columns)
- `tests/test_seed_recall.py` (4 tests added — refusal-before-download,
  reseal rebuild + sidecar stamp, first-build-no-flag, flag-alone usage error)
- `tests/test_near_miss_archive.py` (removed the would_be-NULL assertion; added
  the retirement pin — model must not re-grow the pair + DROPs registered — and
  the pre-drop-DB convergence + idempotent re-run test, matching the
  test_startup_migrations idiom/skip-marker contract)

## Verification

- `py_compile`: all 10 touched files clean.
- Archive suites: `test_analyze_reporter_gates + test_analyze_dedup +
  test_analyze_anchor_seam + test_suggested_weights + test_seed_force_curation +
  test_seed_recall + test_seed_recall_hermetic + test_seeding_refusals +
  test_startup_migrations` → **60 passed**.
- Near-miss suites: `test_near_miss_{archive,report,outcomes,deferred,guards,
  ruling,wiring}` → **37 passed**.
- Adjacent suites that read `_MIGRATIONS`: `test_backend_services + test_htf`
  → **96 passed**.
- DROP idempotency: proven both by the new raw-sqlite test (apply → converge;
  re-apply → exactly a skip-marker error) and by the live-DB fact that the
  runner will hit "no such column" on first boot (the skip path).
- Total: **193 passed, 0 failed.** No baselines, marks, or the live DB written.
