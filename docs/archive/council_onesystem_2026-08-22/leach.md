# Leach — Data Integrity (core/archive, database.py, models, startup migrations)

Review basis: main @ dd4c0ab, clean tree. Live DB read via sqlite3 URI mode=ro only.
Lane: core/archive/ (writer, forward_returns, analyze, seed, purge + near-miss/outcomes/episodes),
webapp/backend/database.py + archive_models.py + models.py, services/startup.py migrations.

## Census corrections (measured against the live DB this run)

The brief's grounding facts have drifted — use these numbers:

- setup_archive holds **9,952 rows** (not 9,438): screener 9,906 / seed 45 / manual 1;
  us_equities 9,879 / us_sectors 73 / commodities_etf **0** (the commodities universe has
  never archived a row — worth one confirmation that this is the intended gate state, not
  a silently-disabled archive lane).
- **12 rows** now carry species data (pp_state: admitted_dark + refused_clock), not 3 —
  the live preset has been stamping since the 08-19 flip.
- near_miss_archive holds 1,123 rows; live values span 6 of the 8 ruled failing legs
  ('window' and 'crash' have never fired live — both have committed producing tests, so
  this is population fact, not an EC-22 breach.)
- Identity integrity: the live 3-col unique key (ticker, scan_date, universe_type) is
  present as an index and **zero duplicate identities** exist in either table.
- Engine epochs in the archive: 15+ distinct engine_config_version values plus a 2,044-row
  pre-versioning NULL cohort; analyze.py's epoch partition machinery handles this correctly.

---

FINDING 1:
- Title: The archive ruling for legacy-path retirement — columns stay, writers CANNOT stop stamping, and two election sites must move at the same seam
- File: webapp/backend/archive_models.py:115-116; core/archive/writer.py:474-483; core/archive/seed.py (best-by-score election, ~line 300 and _scan_back_seeds); core/pipeline/screener.py:327; engine_alpha/scoring/scoring.py:630-663
- Principle: quality-postgres P1 (constraints are assertions), EC-18, EC-29
- Severity: P2
- What's wrong: This is the lane's ruling, stated precisely. Column ownership: (a) LEGACY-only = `score` (the raw ~122-pt sum) and the legacy tier ladder behind `calculate_tier`; (b) SHARED = every other `score_*` term column — these feed BOTH the legacy sum and the V2 grade's chapters, so they are inputs of the one system, not legacy remnants; (c) V2-only = ta_grade, ta_grade_raw, setup_completeness/chronology/upthrust_terminal, score_spring, score_story_*, lps_shrink_frac, lps_window_classification, story_richness_rate, trend_base_count, inter_base_width_ratio, fired_tags; (d) demoted dead knobs = score_uptrend_bonus / score_rs_bonus, stamped literal 0.0 on all 2,895 recent rows; (e) retired programs (score_oscillation, puzzle_*) are ALREADY dropped by explicit one-off migrations — no residue. Crucially, `score` and `tier` are NOT NULL in the model, so writers physically cannot "stop stamping" them without a full table rebuild; and the raw sum is computationally free because its terms are computed for the V2 grade anyway. The real coupling: the seed scan-back election (seed_archive and _scan_back_seeds pick "the day the screener fired best" by the LEGACY score) and the live screener ranking (sort by 'Score') both key on the legacy sum while the operator-facing verdict is the V2 grade — retirement that removes the raw sum breaks or silently re-keys both elections and the hermetic recall guard's ground truth.
- Consequence: A naive "delete the legacy score" retirement either violates the NOT NULL model contract, silently changes which day the seed gallery pins as the fire, or invalidates the recall baselines without a seam.
- Fix: Rule it as: all columns STAY as history (append-only books, 9,952 rows untouched, no backfill ever); writers KEEP stamping score/tier exactly as today; retire only the legacy LADDER path (flag-off calculate_tier callers), the wire's legacy fields, and the frontend re-derivation. IF the operator later wants the raw sum itself gone, that is a named seam commit that must simultaneously: relax score to nullable via rebuild, re-key seed election + screener ranking to the ONE live basis, recapture the seed-recall/hermetic baselines (EC-29), and stamp a new epoch.
- Ruling-recommendation for version-sites: KEEP the archive columns + stamping (books of record; zero marginal cost); FOLD the two score-keyed election sites onto the live ranking basis at the retirement seam, never before and never separately.

FINDING 2:
- Title: `triggered` means two different things in the two maturation lanes, and the report card averages the immature zeros
- File: core/archive/forward_returns.py:214-231 (fires' write); core/archive/near_miss_outcomes.py:150-166 (three-state write); core/archive/analyze.py:557,575 (trig.mean over the blend)
- Principle: EC-23 / EC-18 (one implementation of a ruled judgment predicate); quality-postgres P4 (NULL semantics)
- Severity: P2
- What's wrong: The fires' updater stamps `triggered=0` from the first forward bar and lets nightly recompute converge it, so 0 means "not YET (as of last maturation)". The near-miss lane — after the 2026-07-26 review — deliberately writes the three-state form: 1 on touch, 0 only once the row has matured through the full 60-bar window, NULL while still maturing. Measured live: **973 fire rows carry triggered=0 while bars_to_date < 60**. analyze's `_perf_row` computes trig_rate as a plain mean over the blend, so every segment's trigger rate is deflated by exactly the still-maturing tail — which today is MOST of the archive (live scans only began 2026-06-01; only 44 rows are past 100 days).
- Consequence: The operator's report card systematically understates trigger rates for recent cohorts, worst in the newest (most decision-relevant) segments; and any consumer joining fires against near-misses reads one column name with two vocabularies.
- Fix: Short term, gate the reporter's trigger-rate on maturity (bars_to_date >= horizon or triggered=1) — one predicate, no schema change, no rewriting history. Long term, fold the fires onto the near-miss three-state semantics at a flip seam (the write already recomputes nightly, so the column converges to the new vocabulary without backfill).
- Ruling-recommendation for version-sites: FOLD — the near-miss lane's three-state form is the ruled one (review 2026-07-26 finding 7); the fires' two-state form is the older twin that should retire at a seam. The reporter gate is safe to land immediately.

FINDING 3:
- Title: `would_be_score` / `would_be_tier` are declared, rendered, and unwritable — no code path ever fills them
- File: webapp/backend/archive_models.py:556-557; tools/near_miss_report.py:85 (the only reader); core/archive/near_miss_writer.py (writer never sets them)
- Principle: EC-22 (an advertised capability the system does not have)
- Severity: P3
- What's wrong: 0 of 1,123 live rows populated; a repo-wide search finds no writer — only the model declaration and a report fallback. The model docstring itself concedes "a refused framing has no election context to score", i.e. the columns are unfillable by the lane's own design.
- Consequence: Schema advertises a measurement that cannot exist; the report's "would-be tier" branch is dead code that reads as a pending feature forever ("parked indefinitely" — the disease this run exists to cure).
- Fix: Either build the filler (a post-hoc scoring of the refused framing — doubtful given the docstring's own reasoning) or drop the pair via an explicit one-off DROP in _MIGRATIONS (both columns are empty, nothing is lost) and delete the report fallback branch.
- Ruling-recommendation for version-sites: DELETE — the columns are empty and the lane's own documentation argues they can never be honestly filled.

FINDING 4:
- Title: The Wave-2 box-walk's interesting half has never fired in production — trend_base_count is 1 on all 3,150 measured rows, inter_base_width_ratio is NULL on all 9,952
- File: engine_alpha/structure/market_structure.py:587-666 (producer — out of my lane, handing off); archive evidence: setup_archive census this run
- Principle: EC-22 spirit (every legal value producible through the REAL producer); measure-first contract
- Severity: P3
- What's wrong: Across every V2-era fire, the predecessor walk has never once admitted a predecessor base: the count never exceeds 1 and the ratio never populates. The committed tests drive count>=2 only through monkeypatched walk structures, not the real segmentation end-to-end. Either the fleet genuinely never fires on a 2nd-or-later base (possible but surprising across ~3 months and 3,150 measured rows — Minervini names count bases 1 through 4), or the predecessor admission predicate is dead-on-arrival and the archive is accumulating a permanently-inert measurement.
- Consequence: When the operator's A/B eventually consults inter_base_width_ratio, there will be zero observations — a whole charter measurement silently absent from the books.
- Fix: One read-only census probe: run the real walk over a handful of names known to be on base 2/3 (the marks corpora have them) and see whether count>=2 ever emerges. If not, the admission predicate is the defect. McKinney's lane owns the producer; the archive evidence is what this seat certifies.
- Ruling-recommendation for version-sites: KEEP the columns (measure-first contract, NULL is honest) — but the producer must be verified or the lane is theater.

FINDING 5:
- Title: analyze.py opens the books of record read-write despite its read-only contract
- File: core/archive/analyze.py:238-241
- Principle: quality-postgres P1 (defence in depth); the tool's own header ("Read-only: never writes to the DB")
- Severity: P3
- What's wrong: `load_archive` uses a plain sqlite3 connection, not the mode=ro URI this very review is required to use. The existence check above it prevents accidental DB creation, and today's queries are pure SELECTs — the contract holds by discipline alone, not by the connection.
- Consequence: A future edit (or an exception-path PRAGMA) could write the live archive from a "read-only" instrument with nothing refusing it; the read also holds no busy_timeout, so it can hit a transient "database is locked" during a concurrent checkpoint instead of waiting.
- Fix: Open with the read-only URI form (one line); that turns the docstring's promise into an enforced property and any future write attempt into a loud error.
- Ruling-recommendation for version-sites: KEEP (single reader, correct behavior today) — harden the connection.

FINDING 6:
- Title: seed --force overwrite resets operator curation on the re-seeded row
- File: core/archive/seed.py:~305-420 (the existing/force branch + archive_row_from_result auto-fill); webapp/backend/services/archive_queries.py:260-283
- Principle: quality-postgres P1; EC-7 spirit (operator ground truth is not writer-refreshable)
- Severity: P3
- What's wrong: On --force, the writer builds a full column dict — `quality_label` is unconditionally 'perfect' from overrides and `notes` auto-fills to None via the mapper (it is neither in overrides nor in _MANUAL_UNMAPPED_COLUMNS) — then setattr's every key onto the existing row. A re-seed therefore wipes any operator-edited note and resets a re-graded quality_label on that row.
- Consequence: No realized loss today (notes is all-NULL live; quality_label populated on only 46 rows, all plausibly 'perfect' seeds) — but the path silently destroys manual curation the day the operator annotates a seed row and anyone re-runs seeding with --force.
- Fix: On the overwrite branch, exclude the manual-curation columns (quality_label, notes) from the setattr loop — refresh measurements, preserve curation.
- Ruling-recommendation for version-sites: KEEP the writer; patch the overwrite branch.

FINDING 7:
- Title: The hermetic recall fixture rebuild is a one-command, unguarded baseline recapture
- File: core/archive/seed_recall.py:417-446 (build_hermetic_fixture), 680-682 (CLI dispatch)
- Principle: EC-29 (baselines recapture only at a flip/seam commit); EC-46 spirit (stamped evidence)
- Severity: P3
- What's wrong: `--build-fixture` unconditionally overwrites the committed fixture parquet with today's vendor data — no exists-refusal, no confirmation, no engine-manifest or population stamp in the artifact. The only backstop is git diff review, which EC-29 explicitly treats as the last line, not the mechanism; every other recapture instrument in this repo got a tool-side seam guard.
- Consequence: A casual or accidental rebuild silently moves the recall guard's ground truth — the exact mid-build reseal EC-29 exists to reject — and nothing in the artifact itself records which engine or seed population it froze.
- Fix: Refuse when the fixture already exists unless an explicit reseal flag is passed, and stamp the covered ticker set + freeze date (the population fingerprint) alongside the parquet.
- Ruling-recommendation for version-sites: KEEP the instrument (the hermetic gate is load-bearing); add the refusal + stamp.

---

## Verified clean (lane questions 2-4 — stating the negative space explicitly)

- **Closed-set enforcement (EC-19/22/23), all three legs present for every closed set.**
  elected_pool (fresh-DB CHECK + bricks._pool_label refusal + test_story_pool_guards),
  setup_chronology / lps_window_classification / fired_tags (CHECKs + ta_grade_archive_values
  refusals incl. allow_nan=False JSON + test_scoring/test_ta_grade_cascade refusal-and-landing
  tests), pp_state (CHECK + power_play_fields/power_play_archive_values refusals on both writer
  shapes + per-state producing battery + fresh-DB CHECK test), near-miss failing_leg/pool
  (born-with CHECKs live + writer refusals + tests). The live setup_archive DDL carries only the
  universe_type CHECK — expected: the table rebuild predates the later sets, SQLite cannot
  retrofit, and the documented operative constraint on the live DB is the write-time refusal.
  Live data audit: every closed-set column contains only legal labels. EC-23 pairs (triggered/
  trigger_date, pp_state/pp_clock, thirds pairs, zone pair, watchlist full-pin CHECK) write as
  units in every branch I traced.
- **Writer-family discipline (EC-30): all three setup_archive writers take all seven family
  producer splats** (sub_score, ta_grade, htf, event_map, election_trace, strategy, power_play):
  live writer.py:497-673, seed.py overrides block, and the manual route — and
  tests/test_archive_column_parity.py asserts the producers' presence PER WRITER via AST,
  including the manual route's declared-exclusion set. No writer is left to a raw model pass.
- **Upsert identity keys (EC-4): every writer filters on the full 3-col identity** (live
  writer.py:468-472, seed.py existence check, manual route archive_actions.py:98, near-miss on
  its 6-col framing identity + universe). Zero duplicate identities in either live table.
- **WAL / busy_timeout discipline:** every lane writer goes through make_sqlite_engine
  (busy_timeout first, WAL best-effort, synchronous=NORMAL, connect timeout 30); the two
  table-rebuild migrations (universe_type, watchlist ledger) are transactional DDL with WAL
  checkpoint + file backup + row-count drift check + correct stale-index handling; the ADD-only
  model-derived auto-migrator covers all three registered archive tables and forward_returns /
  seed / near-miss are each self-sufficient on an unbooted DB.
- **Parquet cache integrity:** panel writes are atomic (PID-suffixed temp + os.replace with
  bounded retry) under a cross-process file lock; the regime-mismatch guard forces cold refetch
  rather than mixing price regimes; unreadable parquet degrades to refetch, never a crash.
- **Forward-return maturation health:** 0 rows older than 100 days are missing 20d/60d outcomes;
  the re-touch predicate + 200-day age cap bound re-download correctly; the near-miss maturation
  is containment-wrapped so a lane failure can never mark the fires' run failed (EC-21).
- **NaN at the pandas boundary (EC-2):** ta_grade/power_play extractions scrub explicitly;
  compose_ta_grade quarantines non-finite at the term boundary; fired_tags serializes with
  allow_nan=False; analyze.py's groupers use fillna, not truthiness.
