# Fowler — refactoring seat — in-code version census on main (dd4c0ab)

Run 2026-08-22-2250. Lane: every place the code holds TWO things answering the same question.
Read-only; verified against conventions.md (AP-1..AP-10 respected; no Tested-DEAD lever re-proposed).

---

## SECTION 1 — THE VERSION CENSUS (legacy score path vs TA_SCORE_V2: full extent)

The staged retirement (docs/ta_grade_flip_checklist_2026-08.md §2) was never executed; the flag-ledger
row (docs/flag_ledger.md:64) still lists it Open: "the legacy path IS the rollback until the operator
declares the flip good." Thirteen days post-flip, here is EVERYTHING the retirement deletes, verified
file-by-file — plus two blockers the checklist does not know about (findings 2 and 3) and one defect
that has already broken the rollback the legacy path exists to provide (finding 1).

**Engine (deletes at retirement):**
- engine_alpha/scoring/scoring.py:630-646 — `calculate_tier`, the legacy raw-sum ladder (the shared
  `_apply_tier_ladder` shape at 608-627 stays; `calculate_structure_tier` keeps it).
- engine_alpha/scoring/__init__.py:11-15 — the `calculate_tier` export.
- engine_alpha/evaluation.py:612, 728-729, 968 — the three `TA_SCORE_V2` branches (the flag goes
  always-on, then the conditionals collapse).
- config/settings.py:643-646 — the legacy `TIER_S/A/B/C` cuts; config/settings.py:784 — the flag
  itself. Both are manifest-registered (engine_alpha/freeze/manifest.py:206-208, 242), so retirement
  is an engine_config_version rotation — a declared seam commit (EC-29 compliant by construction).

**Wire (mostly stays):**
- output/dashboard.py:346-372 — the key-absent v2 block becomes unconditional. The `score` field
  (dashboard.py:223) is an archived fact and can stay serialized, but must stop being the ranking
  (finding 2).
- output/dashboard.py:280-283 — the `traversal_density` wire literal folds onto the tags helper's
  derivation (engine_alpha/scoring/tags.py:62-72), exactly as tags.py's own comment promises
  (finding 5).

**Frontend (the checklist's "delete as ONE unit", verified still accurate EXCEPT finding 3):**
- webapp/frontend/src/components/setupScoreMath.js — whole file (cap mirror + Visual/Market pills
  math). BLOCKED by finding 3: setupStoryRows.js now imports it for a live v2 surface.
- webapp/frontend/src/components/setupTagsData.js — the fire rules, `firesAt`, `deriveTags`, and the
  frozen `TOUCH_VOL_Z_*` literal copies (35-37; verified still equal to their settings twins at
  config/settings.py:851-853, so deletion is drift-free today). `TAG_CATALOG` + labels/tones/groups
  survive per the checklist.
- webapp/frontend/src/components/wireVocabulary.js:181+ — `tagFlagsFromWire` (only consumer left is
  tagResolver's legacy branch).
- webapp/frontend/src/components/tagResolver.js:32-36 — the dual-epoch switch collapses to the
  verdict-projection path.
- webapp/frontend/src/components/ScoreBreakdown.jsx + the legacy-epoch branch in
  SetupStoryPanel.jsx:268-273 + the pill CSS.
- webapp/frontend/src/hooks/useScreenerFilters.js:140-150 — the `visual`/`market`/`rs` sorters;
  webapp/frontend/src/components/ScreenerToolbar.jsx:218-219 — their toolbar options. Note the `rs`
  sorter (useScreenerFilters.js:144) is a no-op TODAY on the live screener: it sorts by
  `sub_scores.rs_bonus`, which has archived as 0.0 on every row since the 2026-07-25 demotion — a
  toolbar control that does nothing (finding 6).

**Tests (move in the same commit):**
- tests/test_frontend_score_caps.py — retires with the mirror (or converts to pin whatever
  finding 3's fix leaves behind).
- webapp/frontend/src/components/tagResolver.test.js:8-15 — the legacy-route case; the switch test
  inverts to "absent fired_tags on a v2 build is a defect".
- tests/test_scoring.py:378-401 — the `calculate_tier` band tests retire with the function.
- The flag-off wire snapshot + cascade tripwires (tests/test_dashboard_wire.py,
  tests/test_ta_grade_cascade.py per checklist §"standing facts") lose their flag-off leg.
- webapp/frontend/src/components/setupStoryRows.test.js:73,189 — reworks with finding 3.

**Stays (not legacy, do not touch):**
- The archive columns (`score`, `score_rs_bonus`, `score_uptrend_bonus`, all per-term columns) —
  books of record; Leach's lane rules the columns, but nothing here needs deletion.
- taxonomy.py, tags.py, compose_ta_grade, `_apply_tier_ladder` — the one system.
- wireVocabulary.js (minus tagFlagsFromWire), tagTooltips.js, chapterStrip.js.

**RULING RECOMMENDATION: DELETE — execute the staged retirement.** Precondition per the ledger is the
operator's one-line blessing of the flip. Finding 1 below removes the last reason to wait: the
rollback the legacy path was being kept for is already broken, so today the repo carries the disease
(a second version) without the insurance it was priced at. Fix findings 1-3 in or before the
retirement commit. "Parked indefinitely" is what the last 13 days already were.

**Other version-sites censused in my lane, with rulings:**

- `detect_boxes` / `find_outer_box` (engine_alpha/structure/consolidation.py) vs the live
  narrative read (`read_structure`→bricks): **KEEP-WITH-REASON.** Not a copied walk — both compose
  from the same box_primitives; the health board (core/pipeline/health_board.py:128,170) is a
  documented SEPARATE looser read (different question: position-in-cycle, not fire), and parity is
  test-pinned (tests/test_bricks.py:259 — the two paths must frame the SAME box). This is the
  one-shared-implementation shape EC-3 asks for.
- `calculate_tier` vs `calculate_structure_tier`: **FOLD already done** (one `_apply_tier_ladder`
  shape, two cut-sets); the legacy caller retires per the census above.
- Demoted knobs rs/uptrend (SCORE_RS_BONUS=0, SCORE_UPTREND_BONUS=0, config/settings.py:877,884):
  **KEEP-WITH-REASON.** The raw inputs ARE archived (`excess_return_6m`, `yearly_return` —
  webapp/backend/archive_models.py:103-104), satisfying measure-first; the zero-cap terms flow
  through the registry's uniform arithmetic ("zero by arithmetic, never by special-casing" —
  taxonomy.structural_cap_sum), and the engine-side chips are dead by explicit rule
  (tags.py:82 `cap > 0`). No pointless scoring branch exists engine-side. The pointless remnants
  are all frontend-legacy and die in the census above.
- The `/calibration` re-weight advisory's hand-picked 6-term list
  (webapp/backend/routers/archive_calibration.py:301-305, 336-343): **KEEP-WITH-REASON.** Advisory
  display only, weights resolved live from settings at call time, never applied. One stale comment
  (finding 7).

---

## SECTION 2 — FINDINGS

FINDING 1:
- Title: The legacy chip path fires the demoted RS/Uptrend chips on every legacy-epoch row — the
  EC-8 rollback is silently broken
- File: webapp/frontend/src/components/setupTagsData.js:47-49 (vs engine_alpha/scoring/tags.py:82);
  born in commit 563dfb3 (2026-08-12)
- Principle: EC-18 (a ruled judgment predicate has exactly ONE implementation — the re-typed twin
  diverged); refactoring.md P5 (twin code paths)
- Severity: P1
- What's wrong: The engine's fraction rule guards `cap > 0` so zero-cap chips are dead by design;
  the frozen JS twin `firesAt` has no such guard, so with the mirror caps corrected 15→0 on
  2026-08-12 its test became "zero-or-anything >= zero" — true always. Every payload routed through
  the legacy derive branch (any row without `fired_tags`: pre-flip archive rows merged into the lens
  via ArchiveTab.jsx:141-143, pre-flip pinned watchlist payloads, and ANY flag-off/rollback run) now
  shows Strong RS and Uptrend chips regardless of measurement, and the tag filter counts them
  (both the chips and the filter consume the one resolver). No test catches it —
  tagResolver.test.js:8-15 asserts only that tight_lps is among the fired list, and that test's own
  fixture row fires the two spurious chips today. The tagResolver.js:33-34 comment ("stale caps
  deliberately untouched until deletion") was falsified by the same commit: the parity pin
  (tests/test_frontend_score_caps.py) forces the caps live while the freeze note claims them stale —
  two artifacts answering "what are the legacy caps" differently.
- Consequence: The rollback the legacy path is being KEPT for would light two false verdict chips on
  every live row the moment the operator flips TA_SCORE_V2 off — and does so today on every
  pre-flip row the operator reviews.
- Fix: Port the engine's zero-cap guard into `firesAt` (two lines in a file whose freeze already
  broke — restoring parity IS the freeze's purpose), rewrite the falsified tagResolver comment, and
  add one node test pinning demoted chips dead in the legacy epoch. Or simply execute the retirement,
  which deletes the path.
- Ruling-recommendation: DELETE (retire the path); the guard is the interim fix if retirement waits
  on the operator.

FINDING 2:
- Title: The screener still RANKS by the legacy raw sum while it TIERS by the v2 grade — two
  orderings, equal today only by accident
- File: core/pipeline/screener.py:327; engine_alpha/evaluation.py:546,722,728
- Principle: refactoring.md P5 (twin code paths / shotgun surgery); EC-28's spirit (one resolved
  verdict)
- Severity: P2
- What's wrong: `results_df.sort_values(by='Score')` orders the scan by the ~122-point legacy sum;
  the serialized tier comes from `ta_grade` on the 0-100 ladder. The two currently agree only
  because every divergence knob is still neutral: the grade is an affine map of (raw sum minus the
  per-run-constant breadth term), both warnings are 1.0 (settings.py:834,857), and all v2 term caps
  are 0. Nothing pins that equivalence.
- Consequence: The first operator A/B that assigns a warning cost or a story weight silently forks
  rank from grade — the operator's list order stops agreeing with the number printed on each card
  (the WCC rank-3-vs-19 class of surprise, this time permanent and unflagged).
- Fix: In (or before) the retirement commit, rank from `ta_grade` with a stable tiebreak, stated as
  part of the flip seam; until then a one-line comment at the sort naming the fragile equivalence.
- Ruling-recommendation: FOLD — one verdict, one ordering, at the retirement seam.

FINDING 3:
- Title: The retirement unit no longer closes — the lens's LPS grade imports the legacy cap mirror
- File: webapp/frontend/src/components/setupStoryRows.js:33,70-78; checklist
  docs/ta_grade_flip_checklist_2026-08.md:125-130
- Principle: EC-28 (no scoring cap re-declared in frontend JS; a needed number is a backend
  serialization addition); refactoring.md P6 (boundaries)
- Severity: P2
- What's wrong: `lpsGrade` — a LIVE v2-epoch surface on the story panel — divides `lps_tightness`
  by `SUB_SCORE_CAPS.lps_tightness` from setupScoreMath.js, a file the checklist deletes "as ONE
  unit." The consumer was added after the checklist was written (the 2026-08-12 lens build), so
  executing the retirement as written breaks the lens, and keeping it keeps a cap re-declared in JS
  doing client-side arithmetic — the exact shape EC-28 outlaws (the chapter fractions were moved
  engine-side citing EC-28 for precisely this reason; scoring.py:444-448).
- Consequence: Whoever executes the retirement hits a hidden dependency and either scope-creeps the
  commit or leaves the mirror alive "just for the LPS row" — the remnant regrows.
- Fix: Serialize the LPS earned-fraction from the engine (compose_ta_grade already resolves the
  chapter fractions there; one more resolved field), then setupStoryRows drops the import and the
  delete unit closes. Update the checklist's delete list in the same change (EC-42: promises are
  trued up when a sibling falsifies them).
- Ruling-recommendation: FOLD (engine-side), then DELETE per census.

FINDING 4:
- Title: An unpinned settings mirror in the narrative read — the cap-rot class, second instance
- File: webapp/frontend/src/components/narrativeRead.js:99 (vs config/settings.py:830)
- Principle: EC-3 (one shared implementation) / the test_frontend_score_caps.py precedent;
  refactoring.md P5
- Severity: P2
- What's wrong: `ZONE_COVERAGE_UNREADABLE = 0.5` hand-mirrors `STORY_UNREADABLE_ZONE_COVERAGE` —
  the floor at which the grade routes all-zero story counts to ABSENT. The node tests
  (narrativeRead.test.js:115-129) pin the JS literal to itself; nothing pins it to settings. The
  first mirror of this kind (SUB_SCORE_CAPS) drifted for three weeks before the 2026-08-12 review
  caught it, and got a cross-language parity test as the fix; this mirror never did.
- Consequence: A recalibration of the settings floor moves the grade's absent-routing while the
  lens caveat keeps firing at 0.5 — the caveat and the judgment it explains silently disagree.
- Fix: Extend the caps parity test's parse-and-compare pattern to this constant (cheapest), or
  serialize the caveat condition as an engine-stamped fact per EC-28.
- Ruling-recommendation: KEEP the display + add the pin now; FOLD onto the wire when the narrative
  family next gets a serialization pass.

FINDING 5:
- Title: The traversal_density derivation exists twice, fold promised for a wave that never came
- File: output/dashboard.py:280-283 and engine_alpha/scoring/tags.py:62-72
- Principle: EC-3 (fold twin code paths); refactoring.md P5
- Severity: P3
- What's wrong: Both sites compute the same rounded ratio from the trav counts; tags.py's own
  comment promises "the wire's own literal folds onto this helper at the legacy-deletion wave
  (task 15)" — a fold gated on a retirement that is 13 days overdue. The twin is benign today
  (same expression, near-same missing-guards) but it is a documented deferred fold aging in place.
- Consequence: A change to how density is derived (or rounded) lands in one site and not the other,
  and the chip verdict stops matching the wire fact it explains.
- Fix: The fold is independent of the flip — dashboard can call the one helper now. Execute it with
  the retirement, or immediately if retirement slips again.
- Ruling-recommendation: FOLD (with or before the retirement commit).

FINDING 6:
- Title: The RS sort is a dead control on the live screener
- File: webapp/frontend/src/hooks/useScreenerFilters.js:144; webapp/frontend/src/components/ScreenerToolbar.jsx:218-219
- Principle: refactoring.md P5 (Speculative Generality / dead weight); P1 economics
- Severity: P3
- What's wrong: The `rs` sorter orders by `sub_scores.rs_bonus`, which the engine has emitted as
  exactly 0.0 on every live row since the 2026-07-25 demotion — the comparator always returns 0, so
  the toolbar option reorders nothing and tells the operator nothing.
- Consequence: A control that silently does nothing erodes trust in the panel's other controls.
- Fix: Already on the checklist's delete list; if any RS ordering is still wanted it should key on
  the live `rs_rating` percentile (a real wire field), not the demoted score term.
- Ruling-recommendation: DELETE with the retirement unit.

FINDING 7:
- Title: A hand-typed total that no longer sums — "128 pts across the 6 core sub-scores"
- File: webapp/backend/routers/archive_calibration.py:319-324
- Principle: refactoring.md P4 (comments as deodorant / names+claims that lie); the taxonomy
  docstring's own law ("every hand-copied total in this codebase has eventually lied")
- Severity: P3
- What's wrong: The re-weighting comment claims the 6 core sub-scores cap at 128 points; their live
  caps (22+25+8+20+20+22) sum to 117. The CODE is right (weights resolve from settings at call
  time); only the prose carries a fossilized number.
- Consequence: An operator (or agent) reading the advisory surface's explanation calibrates their
  trust against a number that is wrong.
- Fix: Delete the number from the comment (say "re-normalize to preserve the current total of the
  six caps") — one line.
- Ruling-recommendation: MERGE the claim into the derived value (comment fix only).

FINDING 8:
- Title: The staged retirement itself — the master version-site, open past its own justification
- File: docs/flag_ledger.md:64 (Still open clause); docs/ta_grade_flip_checklist_2026-08.md:120-140
- Principle: refactoring.md P1 (the economics: this structure is actively slowing the team — three
  of this run's findings exist only because two paths are alive); EC-15/EC-42 (a decision record
  overtaken by events updates)
- Severity: P2
- What's wrong: The legacy path is kept as the rollback, but finding 1 shows the rollback no longer
  restores pre-flip behavior faithfully — the insurance has lapsed while the premium (dual-epoch
  switches, a frozen rules file, a cap mirror, extra test surface, this census) is still being paid.
  The operator's "ONE system" ruling makes this the highest-leverage deletion in the repo.
- Consequence: Every future frontend change pays the dual-epoch tax; every reviewer re-derives this
  census.
- Fix: Obtain the operator's flip-good declaration, then one retirement commit executing Section 1
  with findings 1-3 folded in; ledger row → Retired in the same change.
- Ruling-recommendation: DELETE (execute), with a named operator gate — not parked.

---

Census summary: 1 master DELETE (legacy path, 20+ sites enumerated), 3 FOLD (rank ordering, LPS
fraction, traversal twin), 4 KEEP-WITH-REASON (diagnostic detector, demoted-knob arithmetic,
advisory list, zone-coverage display pending pin), 0 parked.
