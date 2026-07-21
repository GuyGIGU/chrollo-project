"""Agreement metrics pins (Task 8) — every expected verdict hand-reasoned in
advance on tiny mark+read pairs, tolerance edges included; never derived by
running the replay and pasting its output."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine_alpha.election_identity import rails_match, same_election
from tools.agreement import (
    OUTCOMES,
    fired_inside_window,
    grade_mark,
    rail_distances,
    span_overlap,
    tally,
)

MARK = dict(verdict="box", resistance=12.0, support=10.0,
            box_start_date="2026-01-05", box_end_date="2026-04-15",
            as_of_date="2026-04-15")
READ = dict(R=12.1, S=9.95, box_start_date="2026-01-12", box_end_date="2026-04-15")


def test_exact_match_and_tolerance_edge():
    # Box height 2.0, default tol 10% = 0.20 in price. R off by 0.1, S by
    # 0.05: match. Push S to exactly the edge (0.20): still a match
    # (<=). One tick beyond: disagree.
    g = grade_mark(MARK, READ)
    assert g["outcome"] == "match" and g["rails_within_tol"]
    at_edge = {**READ, "S": 10.0 - 0.20}
    assert grade_mark(MARK, at_edge)["outcome"] == "match"
    beyond = {**READ, "S": 10.0 - 0.2001}
    g = grade_mark(MARK, beyond)
    assert g["outcome"] == "disagree" and not g["rails_within_tol"]
    assert g["rail_distances"]["s_frac"] == pytest.approx(0.10005)


def test_span_overlap_gates_match():
    # Rails agree but the engine read a young box over a sliver of the drawn
    # cause: overlap below the floor = disagree (the VLO young-June-box case).
    young = {**READ, "box_start_date": "2026-04-01"}
    g = grade_mark(MARK, young)
    assert g["outcome"] == "disagree"
    assert g["span_overlap"] < 0.5


def test_no_read_and_negative_verdicts():
    assert grade_mark(MARK, None)["outcome"] == "engine_no_read"
    neg = dict(verdict="no_structure", as_of_date="2026-04-15")
    assert grade_mark(neg, None)["outcome"] == "negative_upheld"
    assert grade_mark(neg, READ)["outcome"] == "negative_violated"
    wrong = dict(verdict="engine_wrong", as_of_date="2026-04-15")
    assert grade_mark(wrong, READ)["outcome"] == "negative_violated"


def test_vetoed_cause_absent_attributes_the_drop():
    # A box the engine elects nothing at: a plain no-root -> engine_no_read;
    # the cause-before-effect veto firing -> vetoed_cause_absent (attributable).
    assert grade_mark(MARK, None)["outcome"] == "engine_no_read"
    assert grade_mark(MARK, None, vetoed=True)["outcome"] == "vetoed_cause_absent"
    # `vetoed` is meaningful ONLY when the engine read nothing: a real read
    # still grades on geometry, and a negative verdict still upholds.
    assert grade_mark(MARK, READ, vetoed=True)["outcome"] == "match"
    neg = dict(verdict="no_structure", as_of_date="2026-04-15")
    assert grade_mark(neg, None, vetoed=True)["outcome"] == "negative_upheld"
    # A vetoed box stays in the denominator exactly where its engine_no_read
    # would have — the split changes attribution, never the ratios.
    graded = [grade_mark(MARK, READ),                 # match
              grade_mark(MARK, None, vetoed=True),    # vetoed_cause_absent
              grade_mark(MARK, None)]                 # engine_no_read
    t = tally(graded)
    assert t["counts"]["vetoed_cause_absent"] == 1
    assert t["n_scored_boxes"] == 3
    assert t["surfaced_over_scored"] == pytest.approx(1 / 3)
    assert t["match_over_scored"] == pytest.approx(1 / 3)


def test_precedence_basis_then_edge():
    assert grade_mark(MARK, READ, basis_ok=False)["outcome"] == "basis_mismatch"
    # Drawn span starts before the frame's left edge: not a disagreement.
    g = grade_mark(MARK, None, frame_start="2026-02-01")
    assert g["outcome"] == "edge_uncertain"
    # basis_mismatch outranks edge_uncertain.
    assert grade_mark(MARK, None, basis_ok=False,
                      frame_start="2026-02-01")["outcome"] == "basis_mismatch"


def test_nan_and_malformed_are_loud_never_scored():
    with pytest.raises(ValueError):
        grade_mark({**MARK, "resistance": float("nan")}, READ)
    with pytest.raises(ValueError):
        rail_distances(10.0, 12.0, 11.0, 10.5)  # inverted drawn rails
    with pytest.raises(ValueError):
        span_overlap("2026-04-15", "2026-01-05", "2026-01-01", "2026-02-01")


def test_span_overlap_math():
    assert span_overlap("2026-01-01", "2026-01-10",
                        "2026-01-01", "2026-01-10") == 1.0
    assert span_overlap("2026-01-01", "2026-01-10",
                        "2026-02-01", "2026-02-10") == 0.0
    # 6 shared days over a 15-day union.
    assert span_overlap("2026-01-01", "2026-01-10",
                        "2026-01-05", "2026-01-15") == pytest.approx(6 / 15)


def test_fired_inside_window_honors_knowability():
    assert fired_inside_window("2026-04-10", None, "2026-04-15")
    assert not fired_inside_window(None, None, "2026-04-15")
    # Fired before the mark says it was fairly knowable: does not count.
    assert not fired_inside_window("2026-04-01", "2026-04-09", "2026-04-15")
    assert fired_inside_window("2026-04-09", "2026-04-09", "2026-04-15")


def test_tally_states_every_denominator():
    graded = [grade_mark(MARK, READ),                         # match
              grade_mark(MARK, None),                         # engine_no_read
              grade_mark(dict(verdict="no_structure",
                              as_of_date="2026-04-15"), None),  # upheld
              grade_mark(MARK, READ, basis_ok=False)]         # excluded
    t = tally(graded)
    assert t["n_marks"] == 4 and t["n_scored_boxes"] == 2
    assert t["match_over_scored"] == 0.5
    assert t["upheld_over_negatives"] == 1.0
    assert t["n_excluded"] == 1
    assert set(t["counts"]) == set(OUTCOMES)  # zero-count cells still present


def test_tally_headline_is_concordance_not_replication():
    # Operator doctrine (2026-07-11): a read whose rails differ beyond
    # tolerance still SURFACED the setup at his pick — it counts in the
    # headline; the geometric match stays a separate diagnostic tier.
    off_read = {**READ, "R": 18.0}               # same read, R far off (3.0 box-heights)
    graded = [grade_mark(MARK, READ),            # match
              grade_mark(MARK, off_read),        # disagree — but surfaced
              grade_mark(MARK, None)]            # engine_no_read
    t = tally(graded)
    assert t["counts"]["disagree"] == 1
    assert t["surfaced_over_scored"] == pytest.approx(2 / 3)
    assert t["match_over_scored"] == pytest.approx(1 / 3)


def test_same_election_identity():
    a = dict(R=93.70, S=85.53, box_start_date="2025-07-10")
    assert same_election(a, dict(a))
    # Epsilon wobble within 10% of box height: the SAME reading.
    assert same_election(a, {**a, "R": 93.90})
    # A different box start DATE is a different reading, however close.
    assert not same_election(a, {**a, "box_start_date": "2025-07-11"})
    assert not same_election(a, {**a, "S": 60.0})
    with pytest.raises(ValueError):
        rails_match(float("inf"), 85.0, 93.0, 85.0)


def test_ungraded_rows_stay_inside_the_closed_set():
    from tools.agreement import ungraded
    row = ungraded("basis_mismatch", "no frozen frame matches")
    assert row["outcome"] in OUTCOMES and "detail" in row
    with pytest.raises(ValueError):
        ungraded("basis_mismtach", "typo'd literal must fail HERE, not in tally")
