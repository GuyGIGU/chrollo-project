"""Contract tests for core.archive.result_adapter.seed_row_from_result.

The adapter maps the canonical live-evaluation result (the reader door's, `_`-prefixed)
to the unprefixed key shape the seed archive writer consumes. These tests pin:

1. The mapping RULES (strip leading underscore + explicit renames) — fast, no engine.
2. The seam's ONE consumer that reads adapter output by name: the seed scan-back election
   (`core.archive.seed._election_key`). A rename on either side must fail loudly here
   rather than silently degrade the election.
"""
from core.archive.result_adapter import seed_row_from_result


def test_adapter_strips_leading_underscore():
    out = seed_row_from_result(
        {"_adr_pct": 0.42, "_two_eyes_parent_r_price": 7.0,
         "_stage2_trend_pass": 1, "_two_eyes_has_mini": True}
    )
    assert out["adr_pct"] == 0.42
    assert out["two_eyes_parent_r_price"] == 7.0
    assert out["stage2_trend_pass"] == 1
    assert out["two_eyes_has_mini"] is True  # two_eyes_archive_values(..., prefixed=False) reads this


def test_adapter_applies_explicit_renames():
    canon = {
        "Setup": "LPS", "Tier": "A", "Score": 95, "Current Price": 12.3,
        "Box Width": 0.1, "Touches": 6, "ATR Ratio": 0.8, "Breach Days": 0,
        "_R": 13.0, "_S": 11.0, "_base_len": 40, "_lps_len": 3,
        "_r_anchor_bar": 5, "_s_anchor_bar": 2, "_bars_since_BC": 50,
        "_vol_contraction": 0.7, "_tightness_ratio": 0.9, "_sub_scores": {"box_tightness": 1},
    }
    out = seed_row_from_result(canon)
    assert out["setup_type"] == "LPS" and out["tier"] == "A" and out["score"] == 95
    assert out["current_price"] == 12.3 and out["box_width"] == 0.1
    assert out["touches"] == 6 and out["atr_ratio"] == 0.8 and out["breach_days"] == 0
    assert out["r_level"] == 13.0 and out["s_level"] == 11.0
    assert out["base_length"] == 40 and out["lps_length"] == 3
    assert out["r_anchor"] == 5 and out["s_anchor"] == 2 and out["bars_since_BC"] == 50
    # strip-pass fields the writer also reads
    assert out["vol_contraction"] == 0.7 and out["tightness_ratio"] == 0.9
    assert out["sub_scores"] == {"box_tightness": 1}


def test_adapter_does_not_mutate_input():
    canon = {"Setup": "LPS", "_R": 1.0}
    seed_row_from_result(canon)
    assert canon == {"Setup": "LPS", "_R": 1.0}


def test_election_elects_higher_grade_over_higher_score():
    """The scan-back election ranks on the grade first; a lower raw score cannot
    outrank a higher grade.

    Pins the defect fixed 2026-09-01: `_election_key` read the CANONICAL `_ta_grade`
    while every caller passes an adapter-stripped row, so the lookup missed on every
    candidate, defaulted to 0.0, and the election silently degraded to raw score alone.
    """
    from core.archive.seed import _election_key

    high_grade_low_score = seed_row_from_result({"_ta_grade": 61.2, "Score": 80.0})
    low_grade_high_score = seed_row_from_result({"_ta_grade": 55.0, "Score": 95.0})

    # The grade must actually resolve — under the defect both read 0.0.
    assert _election_key(high_grade_low_score)[0] == 61.2
    assert _election_key(high_grade_low_score) > _election_key(low_grade_high_score)


def test_election_falls_back_to_score_within_equal_grade():
    """Equal grades: the raw sum breaks the tie."""
    from core.archive.seed import _election_key

    richer = seed_row_from_result({"_ta_grade": 61.2, "Score": 95.0})
    leaner = seed_row_from_result({"_ta_grade": 61.2, "Score": 80.0})

    assert _election_key(richer) > _election_key(leaner)


def test_election_survives_an_ungraded_candidate():
    """A row the grader left ungraded elects at 0.0 rather than raising."""
    from core.archive.seed import _election_key

    assert _election_key(seed_row_from_result({"Score": 80.0})) == (0.0, 80.0)
    assert _election_key(seed_row_from_result({"_ta_grade": None, "Score": 80.0})) == (0.0, 80.0)
