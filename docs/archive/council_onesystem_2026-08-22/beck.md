# Beck (tests) — One-System consolidation review, 2026-08-22-2250

Lane: the test suite as it relates to version consolidation + test-quality bug hunt.
Method: read every suite touching the legacy/V2 seam, the seven offline guards, the
trend-terminal battery; AST-scanned all of tests/ for assertion-free tests; read-only
git inspection of `proposal/first-legal-look-fix`. No repo file modified except this one.

---

## A. The version-pin census: which tests keep parallel versions alive

Answer to the lane question — "where does my domain hold two things that answer the same
question": the test suite deliberately holds BOTH epochs of the score path alive (flag-off
tripwires, the legacy ladder's band tests, the frontend cap mirror's parity test), and that
is correct TODAY because the legacy path IS the rollback (flip checklist §2). The disease
is not that these pins exist — it is that the staged retirement they are waiting for has no
executed test-move plan, and one of its written assumptions has been falsified since
(finding 4). The complete pin census, with the disposition each needs at the retirement wave:

| Test | What it pins | Disposition at retirement |
|---|---|---|
| tests/test_frontend_score_caps.py:41-49 (cap sweep + mirror-exists) | setupScoreMath.js SUB_SCORE_CAPS mirror | RETIRES with the file |
| tests/test_frontend_score_caps.py:52-61 (LPS-grade cap) | a LIVE v2-era consumer (lens LPS grade) reading the legacy mirror | REWRITE against a new wire field (finding 4) |
| webapp/frontend/src/components/setupStoryRows.test.js:4,73,189 | same live consumer, JS side | REWRITE against the wire field, same change |
| tests/test_scoring.py:543 test_ta_score_v2_flag_off_leaks_no_v2_keys | flag-off scorer byte-identity | RETIRES with TA_SCORE_V2 |
| tests/test_scoring.py:564 test_score_setup_emits_no_v2_keys_under_either_flag | producer partition under both flags | REWRITE: drop the flag loop, keep "score_setup is v1-only" while score_setup exists |
| tests/test_scoring.py:378-401 calculate_tier band + width-cap tests | the LEGACY tier ladder | REWRITE against calculate_structure_tier FIRST (finding 3 — the live ladder has zero direct tests) |
| tests/test_scoring.py:838 emitted-keys two-producer partition | the two-producer epoch | REWRITE as single-epoch registry equality |
| tests/test_score_taxonomy.py:183-187 | flag-off/on emitted-key split | REWRITE unconditional |
| tests/test_dashboard_wire.py:80-109+ (FLAG_OFF_WIRE_KEYS, 150-key snapshot + off-leak test) | the flag-off wire contract | off-leg RETIRES; re-pin the single-state wire key set as a conscious seam edit; if legacy fields (raw Score, sub-score pills) leave the payload, the shadow baseline recapture happens at that SAME seam commit (EC-29) |
| tests/test_ta_grade_cascade.py:163 test_flag_off_cascade_emits_no_v2_fields | flag-off canonical row | RETIRES; the EC-17 happy path (line 49) drops its monkeypatch and becomes the unconditional acceptance test |
| tests/test_ta_grade_ab.py (7 tests) + tools/ta_grade_ab.py | the flip A/B instrument (needs a legacy leg to compare) | ARCHIVE tool + tests together; EC-15 ledger update in the same change |
| tests/test_fired_tags.py:187 | forces V2 on for one warning test | trivial cleanup (drop the monkeypatch) |
| webapp/frontend/src/components/tagResolver.test.js:6 | TAG_CATALOG from setupTagsData.js | STAYS — the presentational catalog survives the deletion wave; only its import home may move |
| webapp/frontend/src/testManifest.test.js | the hand-enumerated npm test list | STAYS — it self-enforces the package.json edits when JS test files are deleted |
| tests/test_invariants.py:441 flag-ledger sweep | dark-table ↔ settings lock-step | STAYS unchanged — TA_SCORE_V2 (currently True, so outside the Dark sweep) moves to the ledger's Retired section when deleted |

Other parallel versions and their test posture (census extension, no moves needed now):

- **Story-form species read** (the refused a3397a5 flip): correctly caged as a dark lane,
  not a test-pinned twin — tests/test_resistance_contraction.py:113 pins the flag dark,
  :109 proves the paying read never consults the species form, :40 gives every leg its
  wrong-side refusal (EC-34), and tests/test_power_play_preset.py:63-72 pins it into the
  frozen manifest. No test blocks deleting the form if the operator rules kill; the
  graduation A/B program owns the flip. From the test seat: this is what a single-system
  lane SHOULD look like.
- **AR_FIRST_REACTION_ENABLED** (DO-NOT-FLIP, kill-by 2026-09-15):
  tests/test_analyze_anchor_seam.py pins its analysis partition; if the flag is deleted at
  kill-by, that module retires with it — name it in the kill commit.
- **first_legal_look** (`proposal/first-legal-look-fix`): main's suite pins the CURRENT
  (edge-reserve-biased) walk with exact as-of values — tests/test_power_play_census.py:91-92
  (`== 470`, `== 458`), :119 (`== 452`), :157, and tests/test_power_play_lane.py:134,234.
  The branch adds its own spec (tests/test_first_legal_look.py, 148 lines) and fixes the
  engine + census docstrings but does NOT touch these pins (finding 8).
- **tags helper fold** (engine_alpha/scoring/tags.py:67): the wire's traversal_density
  literal is promised to fold onto the tags helper "at the legacy-deletion wave (task 15)" —
  tests/test_fired_tags.py:121 already links the density rule to its settings twin, so the
  fold has a ready guard; just keep it in the retirement task list.
- **Dead knobs at weight 0** (rs_bonus/uptrend_bonus): pinned as EXISTING (at cap 0) by the
  taxonomy lock-step tests (tests/test_score_taxonomy.py:23-40) and the wire snapshot —
  deleting a dead term means registry + archive-column + mirror moves in one change; the
  registry tests will enforce that, which is the correct direction.

## B. Offline-guard inventory: pytest vs outside, dark-gate risk

| Guard | Real gate in pytest? | CI step? | Dark-gate risk |
|---|---|---|---|
| tools/pointer_audit | YES — tests/test_pointer_audit.py runs `dangling_links()` for real, with its own guard-the-guard (`>50 docs`) and bite proofs | via pytest | LOW |
| tools/shadow_diff | YES — tests/test_regression_guards.py:52 runs `check_baseline()` end-to-end | explicit step too (quality.yml:56) | LOW |
| tools/negative_corpus | YES — tests/test_negative_corpus.py:42 runs `check_corpus()` for real, plus the flag-on two-form leg | explicit step too (quality.yml:67) | LOW |
| tools/cause_veto_corpus | YES — tests/test_cause_veto_bite.py:40 runs both directions for real, with bite-proofs of the bite-proof | via pytest | LOW |
| core.archive.seed_recall --hermetic-check | NO — pytest carries plumbing only (tests/test_seed_recall_hermetic.py: fixture committed, baseline mirrors fresh, guard bites — no engine replay) | HARD gate at quality.yml:84 (the ~25-min replay) | MEDIUM — see finding 2 |
| tools/marks_corpus --check | NO — pytest plumbing only, under a monkeypatched evaluator (tests/test_marks_corpus.py) | HARD gate at quality.yml:95 (~35s replay) | MEDIUM — see finding 2 |
| tools/doctrine_audit --check | NO — nothing in pytest even imports it (the only mention is a docstring, tests/test_pointer_audit.py:3) | NO CI step at all (needs the live payload + live cache) | HIGH — see finding 1; it has already gone silently dark once (re-lit at 9fbbca3) |

## C. Trend-terminal suite state (item 3)

Confirmed: tests/test_trend_terminal_gate.py holds exactly 24 tests in the three declared
layers (flag-off inert / real-election effect / rule arithmetic + floor), all synthetic and
offline. The mutation-hardening is real and documented in the suite itself:
test_already_printed_carries_a_box_that_maturity_could_never_save (line 334) records the
three surviving mutants found 2026-08-20 and pins the `bar >= term` equality clause with a
frame where maturity cannot rescue — the equality (MATX handover-bar) case that cost a
Guided-List hit. Tested-DEAD discipline is encoded (line 254: price can never move the
verdict — overshoot magnitude stays dead). The flag is pinned dark (line 104) and pinned to
rotate the frozen manifest on flip (line 111).

The 2026-08-31 date in the ledger (docs/flag_ledger.md row `TREND_TERMINAL_BOX_GATE_ENABLED`)
is the FLAG's kill-by, and per the ledger's own corrected record the unblock is NOT another
eyeball — the 2026-07-28 eyeball happened (IRMD/IART/CYRX ruled KEEP, "It's not wrong; it's
early"); what is owed is the `segment_trends` box-blindness fix + a fresh A/B, and the marks
ask was withdrawn 2026-08-19 in favor of the mechanised climax-anchor diagnosis. Nine days
out, the realistic kill-by outcomes are extend-with-ruling or kill; "parked" is not one of
them (finding 5 covers the missing decisions.md row that any of those outcomes needs).
If the flag is killed and the gate code deleted, layers 2-3 retire with the code and layer 1
with the flag; the flag-ledger sweep (tests/test_invariants.py:441) will force the ledger's
Retired row automatically.

## D. Test-theatre hunt (item 4)

Honest verdict: this suite is unusually disciplined. An AST scan of all of tests/ for
assertion-free test functions returned 10 candidates; on inspection all but the two below
are sound patterns (helper-delegated asserts like `_approx`, `pd.testing.assert_frame_equal`,
raise-if-touched inert sentinels, explicit `raise AssertionError`). EC-34 wrong-side
coverage exists where it is law (tests/test_fired_tags.py:75 one refusal per rule KIND;
tests/test_resistance_contraction.py:40 per-leg refusals). The two soft spots and the
structural gaps are the findings below.

---

FINDING:
- Title: The doctrine gate is the only guard with zero automated execution, and it has already gone silently dark once
- File: tools/doctrine_audit.py:234-284 (the `bricks._cause_is_up` spy); .github/workflows/quality.yml (no step); tests/ (no import anywhere — only a docstring mention at tests/test_pointer_audit.py:3)
- Principle: quality-testing P1 (a test that never failed proves nothing) + P10; the repo's own dark-gate precedent (fix commit 9fbbca3 "it had been asserting nothing")
- Severity: P1
- What's wrong: Of the seven offline guards it is the only one with no pytest presence and no CI step, and it monkey-patches an engine seam by direct assignment — the exact arity/signature trap that already made it assert nothing for a day. It is also the ONE gate that proves the reading is RIGHT rather than merely unchanged.
- Consequence: The next engine signature change on a spied seam silently blinds the doctrine battery again, and nothing goes red anywhere; every self-referential gate (shadow/recall/marks) stays green while a doctrinally wrong read ships.
- Fix: Commit a cheap pytest plumbing module on the test_pointer_audit.py pattern: import the tool, assert the spied seams' signatures still match what the spy expects, and drive one committed synthetic frame through the check battery with a bite-proof (a deliberately wrong structure must produce a violation). The full live-payload audit stays offline — the plumbing must not.

FINDING:
- Title: The two HARD corpus replays live only in CI, and CI only fires on push — main is 7 commits ahead of origin
- File: .github/workflows/quality.yml:84-96 (the only real runs); tests/test_seed_recall_hermetic.py:1-20 and tests/test_marks_corpus.py:1-11 (plumbing only, the marks plumbing under a monkeypatched evaluator); .council/council.config.md Gates (runs `pytest -m "not network"` only)
- Principle: quality-testing P11 Predictive ("if your oracle says deploy and deployment fails, you stop believing your oracle"); EC-29's regression ground truth (Guided-List names no longer firing) is exactly what these two gates watch
- Severity: P2
- What's wrong: The hermetic seed-recall and marks-corpus ratchets — the must-fire gates — never run the engine in pytest (deliberate, for speed), so the only automated executions are CI steps that have not fired for the 7 unpushed commits now on main; the council gate battery doesn't run them either. Note quality.yml itself records the marks replay at ~35s — the "too slow for pytest" rationale holds for seed-recall (minutes) but is stale for marks.
- Consequence: A ratchet regression (a pinned operator mark or seed winner going dark) can land on main and stay invisible for the whole unpushed window; the dark-gate class recurs at the process level even though each tool is healthy.
- Fix: Add the two commands to the council-config gate list and AGENTS.md's verify list (marks_corpus at ~35s can also become a slow-marked pytest test), and treat "push main" as part of closing any engine change so the CI gates actually fire.

FINDING:
- Title: The LIVE tier ladder has zero direct tests — its band edges and width cap ride entirely on the retiring legacy twin
- File: engine_alpha/scoring/scoring.py:649-662 (calculate_structure_tier — no test anywhere names it); tests/test_scoring.py:378-401 (band + width-cap tests pin calculate_tier, the legacy ladder, only)
- Principle: quality-testing P4 (test what might break — effort inverted vs risk) + P6 (mutation resistance)
- Severity: P2
- What's wrong: Since the 2026-08-09 flip the serialized Tier comes from calculate_structure_tier over TIER_*_STRUCT, but the only behavioral tests of band mapping and the S_MAX_BOX_WIDTH demotion target the legacy function; the shared `_apply_tier_ladder` shape is covered solely through the twin scheduled for deletion.
- Consequence: Today a wrong STRUCT cut or a lost width cap on the live Tier surfaces only as shadow-baseline drift (a change detector, not a spec — it cannot say which side is right); at the retirement wave, deleting the calculate_tier tests as "legacy" drops tier banding to zero behavioral coverage.
- Fix: Rewrite the two band/width-cap tests against calculate_structure_tier with the STRUCT cuts (hand-derived expected letters, not values read off the implementation) — do it now or as the first commit of the retirement wave, never as part of the deletion itself.

FINDING:
- Title: The retirement plan's "delete as ONE unit" was falsified by the 2026-08-12 lens fusion — the pin suite now guards a LIVE consumer of the legacy mirror
- File: docs/ta_grade_flip_checklist_2026-08.md:125-130 (the deletion unit); webapp/frontend/src/components/setupStoryRows.js:33,74 (live LPS grade divides by SUB_SCORE_CAPS.lps_tightness); tests/test_frontend_score_caps.py:52-61; webapp/frontend/src/components/setupStoryRows.test.js:4,73,189
- Principle: EC-42 (earlier promises re-verified against later work) + EC-28 (the wire carries verdicts, never rules)
- Severity: P2
- What's wrong: The checklist (written at the flip build) says setupScoreMath.js deletes wholesale with the legacy path, and AGENTS.md repeats "retires with the legacy path" — but the operator's 2026-08-12 lens ruling wired the LIVE LPS grade to that same cap mirror, and the pin test's own third assertion now exists specifically to guard that live surface.
- Consequence: Executing the deletion wave as written breaks the lens's LPS grade (the panel the operator reads first); alternatively the mirror survives retirement as an unowned EC-28 violation (a cap re-declared client-side with its "legacy remnant" justification gone).
- Fix: Before or with the deletion wave, move the LPS-grade fraction server-side (an EC-28 wire addition — the engine already owns lps_tightness and its cap); then split the pin suite: the parametrized cap sweep retires with the file, the LPS-cap test and setupStoryRows.test.js are rewritten against the new wire field; update the checklist's deletion unit in the same change.

FINDING:
- Title: The trend-terminal kill-by decision rests on a ruling that still has no decisions.md row
- File: docs/flag_ledger.md row `TREND_TERMINAL_BOX_GATE_ENABLED` (line 27 — the ledger itself flags "⚠ this ruling has NO decisions.md row"); docs/decisions.md (append-only target)
- Principle: EC-15/EC-16 (decision surfaces updated with executed outcomes; evidence in committed paths); quality-testing P10 (the spec is the constraint)
- Severity: P2
- What's wrong: The 2026-07-28 operator ruling (IRMD/IART/CYRX KEEP, "It's not wrong; it's early") — the ruling the whole box-blind diagnosis and the withdrawal of the eyeball unblock rest on — survives only inside the ledger row's prose, self-flagged as owing its operator-confirmed decisions.md row, with the kill-by nine days out.
- Consequence: Whatever happens at 2026-08-31 (extend, kill, or flip after the segment_trends fix), the decision record it depends on is not in the append-only book; a future session can re-litigate the gate from scratch — the exact "missed twice" failure decisions.md exists to prevent.
- Fix: Get the operator to confirm the one-paragraph 2026-07-28 ruling into decisions.md before the kill-by is adjudicated; the 24-test suite itself needs no changes (state confirmed in section C).

FINDING:
- Title: The geometry-invariant module can go silently vacuous on its committed fixture
- File: tests/test_invariants.py:40-61 (per-ticker `continue` on prep/ATR failure; module fixture `pytest.skip` when zero structures)
- Principle: quality-testing P6 (tests that don't discriminate are costs without benefits); the suite's own "fail LOUDLY, never skip" doctrine (tests/test_regression_guards.py:37)
- Severity: P3
- What's wrong: The ~10 geometry property tests skip — not fail — if the committed deterministic fixture ever yields no structures, and each ticker is dropped silently on any prep/ATR exception; a committed fixture can never legitimately produce a skip.
- Consequence: A prep-shape or ATR-column change that zeroes the structure yield turns the whole geometry battery green-by-skip; the shadow guard would catch structure LOSS on canonical fields but not a partial silent erosion of this module's coverage.
- Fix: Replace the skip with an assertion of a minimum structure count (the pointer-audit "guard the guard" pattern) and count dropped tickers, asserting the drop count stays at the frozen baseline's number.

FINDING:
- Title: The live/seed twin-parity test tolerates the exact divergence it exists to catch
- File: tests/test_scoring.py:954-979 (test_e3_eval_twins_agree_on_setup_quality)
- Principle: quality-testing P6 (mutation resistance) + P5 (missing variant: the disagreement case)
- Severity: P3
- What's wrong: The sweep `continue`s whenever exactly ONE twin fires (a real live/seed drift — the grossest parity break — passes silently), returns after the first agreeing ticker, and falls through to `pytest.skip` on a committed deterministic fixture if none agree.
- Consequence: A regression that makes the seed twin stop firing on names the live path fires (or vice versa) leaves this test green; fixture rot demotes it to a skip instead of a red.
- Fix: Assert the two twins' fire SETS agree across the whole fixture, compare setup_quality on every agreeing name (not just the first), and fail — never skip — when the fixture produces no comparable pair.

FINDING:
- Title: The first-legal-look fix branch leaves main's exact as-of pins untouched — reconciliation is part of the merge gate
- File: tests/test_power_play_census.py:91-92,119,126,157 and tests/test_power_play_lane.py:134,234 (exact pins: 470/458/452 and date equalities) vs `proposal/first-legal-look-fix` (adds tests/test_first_legal_look.py; does not touch either file)
- Principle: quality-testing P1 (expected values must be independently reasoned, not copied from the implementation)
- Severity: P3
- What's wrong: Main's pins encode the CURRENT walk's answers as ground truth; the branch's oracle says 12% of looks move earlier under the fix, yet it changes no existing pin — either the synthetic fixtures sit outside the biased region (fine, but unproven in the branch) or the branch is red against main's suite.
- Consequence: If the pins are stale copies of the biased implementation, merging could either fail visibly (annoying but honest) or — worse — the fixtures never exercised the reserve edge and the old pins keep passing without ever having discriminated the bug the fix addresses.
- Fix: At the merge ruling (McKinney's lane decides the merge itself), run the two power-play suites against the branch engine and record which pins moved; any pin that moves gets its new value hand-derived from the fixture's geometry in the merge commit, and at least one main-suite case should sit ON the reserve edge so the fixed behavior is pinned outside the branch's own test file.

---

Totals: 8 findings — 1 P1, 4 P2, 3 P3.
