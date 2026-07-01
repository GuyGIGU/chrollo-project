# Kent Beck — Test Quality Audit (E3 faithfulness fix)

Scope: `tests/test_scoring.py` (rewritten `test_e3_eval_feeds_engine_elected_bricks`, new `test_ramp_zero_divisor_guard_returns_neutral`, flag-off `_boom` test), `tests/test_market_structure.py` (new sentinel three-state, new F3 upthrust-terminal range, updated `test_e2_no_veto_shaped_field`), cross-checked against `core/structure/metrics.py` and `core/scoring/scoring.py`.

Bottom line on the crux question: the rewritten identity test DOES pin the fix and WOULD catch a regression to re-detection — the `_nar_spy` captures the actual `lps=`/`spring=` kwargs the call site passes, and `assert seen["lps_arg"] is s.lps` is an object-identity check that fails the instant `evaluation.py` stops injecting the elected brick (the default sentinel `_DETECT` is not `s.lps`). This is behavioral and not tautological on the load-bearing dimension. The findings below are the residual gaps.

---

FINDING:
- Title: The `True` state of the `lps_pre_v_dropped` observable is never exercised
- File: tests/test_scoring.py:717-718; tests/test_market_structure.py:520
- Principle: Principle 5 (missing behavioral variant, #5) / Principle 6 (mutation resistance, #6)
- Severity: P2
- What's wrong: No test constructs a late-V injected LPS (elected LPS anchoring at/left of the parent V) and asserts `lps_pre_v_dropped is True`; the only `is True` assertion sits in an `else` branch (line 718) that fires only if a fixture ticker happens to gate-drop, and `test_e2_no_veto_shaped_field` merely asserts the KEY exists, never its truthy value.
- Consequence: The new observable — the whole reason the fix claims the elected LPS is "never silently dropped" — could compute `False` unconditionally (e.g. a broken `injected_lps is not _DETECT` guard, or the trace note dropped) and every test would still stay green.
- Fix: Add a direct `_box_events_with_meta` monkeypatch test that injects an LPS whose `start_bar <= v_bar` (so the Phase-D gate drops it) and asserts `lps_pre_v_dropped is True`, the LPS is absent from the spine, and the trace carries the note.

FINDING:
- Title: `exp_anchor` re-implements the production `_clip` formula rather than a reasoned value
- File: tests/test_scoring.py:714-716
- Principle: Principle 6 (assertions that duplicate production logic, #6) / Principle 1 (expected value derived from implementation)
- Severity: P3
- What's wrong: `exp_anchor = max(0, min(int(s.lps.low_bar) - int(s.box.start_bar), int(nar["base_n"]) - 1))` is a byte-copy of the impl's `_clip(llow)` (`metrics.py:1077-1078,1116`), so the anchor assertion passes by construction and cannot catch a wrong translation formula (only a wrong low_bar/start pairing).
- Consequence: If the box-relative translation regressed identically in both places (e.g. both used the wrong start), the assertion would still pass — it verifies "same math twice," not a known-correct anchor.
- Fix: The identity assertions (`seen["lps_arg"] is s.lps`) already carry the faithfulness pin, so this is a minor smell; if kept, anchor the expected value on a synthetic frame with a known elected `low_bar`/`start_bar` so the expected anchor is a hand-reasoned integer, not the impl expression.

FINDING:
- Title: F3 phase-guard test never asserts markup is unguarded from the Phase-B side in isolation — but it is covered
- File: tests/test_market_structure.py:332-350
- Principle: Principle 2 (behavioral, structure-insensitive, #2)
- Severity: P3 (not a defect — recorded as verified)
- What's wrong: Nothing is wrong. The third case (`markup` at `anchor_bar=6 < v_bar=8`, expected `False`) genuinely proves markup clears even when left of the V, i.e. it carries NO phase guard, directly distinguishing it from the guarded `range` term (Phase-B range at bar 6 stays `True`). The two `range` cases discriminate Phase-D-clears vs Phase-B-does-not.
- Consequence: None — a regression that added a `> v_bar` guard to markup would flip case 3 to `True` and fail the test; a regression that dropped the guard from `range` would flip the Phase-B range case to `False` and fail.
- Fix: None needed. The test is behavioral and mutation-resistant on all three arms.

FINDING:
- Title: Sentinel three-state test genuinely exercises all three states, including None-suppression — verified
- File: tests/test_market_structure.py:648-680
- Principle: Principle 6 (mutation resistance, #6) / Principle 2 (behavioral, #2)
- Severity: P3 (recorded as verified, no defect)
- What's wrong: Nothing. State (1) default→detect uses the monkeypatched `find_lps` (`low_bar=9` → anchor 9); state (2) injects a DIFFERENT brick (`low_bar=8` → anchor 8, distinct from the detected 9, so the assertion discriminates injection from re-detection); state (3) injects `None` and asserts `_lps(ev_none) == []` DESPITE `find_lps` being monkeypatched to return a valid LPS — a real suppression check. The `bricks.find_lps` monkeypatch reaches the leaf `from core.structure.bricks import ...` at call time (same pattern the passing `test_e2_deterministic_and_json_native` relies on).
- Consequence: None — a regression that ignored the `None` injection and re-detected would make state (3) find one LPS and fail; a regression that ignored the injected brick and re-detected in state (2) would produce anchor 9 not 8 and fail.
- Fix: None needed.

FINDING:
- Title: `_ramp` guard test omits the negative-value and None-input arms of the degenerate band
- File: tests/test_scoring.py:359-371
- Principle: Principle 5 (boundary/degenerate variants, #5)
- Severity: P3
- What's wrong: The guard sits BEFORE the `value is None or value <= zero_at` check (`scoring.py:40-43`), so the test correctly proves `full_at <= zero_at` short-circuits regardless of `value` for `value=0.5/1.0`, but it never passes `value=None` or a negative value through an inverted band to prove the ordering of the two guards is what makes it crash-safe.
- Consequence: If someone reordered the guards (value check first), `_ramp(None, 0.6, 0.4, 1.0)` would still return 0.0 via the None branch and this test would stay green while a genuinely different code path executes — the "guarded BEFORE the value check" contract in the comment is untested.
- Fix: Add `assert _ramp(None, 0.6, 0.4, 1.0) == 0.0` and one negative-value case through an inverted band to pin the pre-value ordering the comment claims.

---

Summary: 5 findings — 1 P2 (untested `lps_pre_v_dropped == True` observable), 4 P3 (2 verified-clean records for the sentinel + F3 tests, 1 tautology-risk on `exp_anchor`, 1 boundary gap on the `_ramp` guard). The core faithfulness pin is sound: the identity assertions on `lps_arg`/`spring_arg` are behavioral and would fail on a regression to parent-box re-detection. No always-green / mock-theatre / weakened-assertion smell in the rewrite — the old test's dropped inner-box comment was replaced by strictly STRONGER assertions (identity + spine-anchor + dropped-observable), not weaker ones.
