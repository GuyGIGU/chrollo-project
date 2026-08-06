"""Election-trace export (Surface the Read Task 4) — the exporter's laws.

The raw trace never leaves the engine; ONE summarizer decides "how far did it
get"; sentences render from leg NUMBERS through the operator vocabulary, never
``detail`` prose; the archive/payload cells round-trip with honest NULLs.
"""
from __future__ import annotations

import json

import pandas as pd

from config import settings
from engine_alpha.structure.trace_export import (
    ELECTION_TRACE_COLUMN_SQL,
    election_trace_archive_values,
    election_trace_chart_fields,
    export_election_trace,
    leg_sentence,
    terminal_verdict,
)


def _df(n=30, start="2026-05-01"):
    idx = pd.bdate_range(start, periods=n)
    return pd.DataFrame({"Close": [10.0] * n}, index=idx)


# ── the summarizer ───────────────────────────────────────────────────────────

def test_terminal_verdict_elected_wins():
    cascade = [
        {"verdict": "rejected", "stage": "width", "legs": []},
        {"verdict": "elected", "stage": "selection"},
    ]
    assert terminal_verdict(cascade) == {"passed": True}


def test_terminal_verdict_picks_the_deepest_stage_then_the_later_record():
    cascade = [
        {"verdict": "rejected", "stage": "occupancy",
         "legs": [{"leg": "lower_dwell", "measured": 0.10, "threshold": 0.15}]},
        {"verdict": "rejected", "stage": "width",
         "legs": [{"leg": "width", "measured": 0.31, "threshold": 0.25}]},
        {"verdict": "rejected", "stage": "occupancy",
         "legs": [{"leg": "mid_dwell", "measured": 0.61, "threshold": 0.45}]},
    ]
    v = terminal_verdict(cascade)
    assert v["passed"] is False
    assert v["stage"] == "occupancy"
    # later same-depth record wins the tie -> mid_dwell, not lower_dwell
    assert v["sentences"] == ["time in the middle third 0.61 vs cap 0.45"]


def test_terminal_verdict_empty_cascade_is_honest():
    assert terminal_verdict([]) == {"passed": False, "stage": None, "sentences": []}
    assert terminal_verdict(None) == {"passed": False, "stage": None, "sentences": []}


def test_stage_depth_derives_from_the_one_owning_declaration():
    """Council F9: the depth registry is DERIVED from box_trace.CASCADE_STAGES —
    a hand-typed subset shipped drifted on day one (missing the two policy
    kills). Every producable rejected stage must rank."""
    from engine_alpha.structure.box_trace import CASCADE_STAGES
    from engine_alpha.structure.trace_export import _STAGE_DEPTH

    assert set(_STAGE_DEPTH) == set(CASCADE_STAGES)
    # The policy kills reject framings that already PASSED every pair gate —
    # they must outrank every gate death.
    for policy in ("rescue_unused", "dethroned"):
        assert _STAGE_DEPTH[policy] > _STAGE_DEPTH["traversal"]
        assert _STAGE_DEPTH[policy] > _STAGE_DEPTH["story"]


def test_terminal_verdict_policy_kills_outrank_gate_deaths():
    """A dethroned/rescue-discarded candidate got FURTHER than a width kill —
    the epitaph must name the policy stage, not the shallow gate."""
    cascade = [
        {"verdict": "rejected", "stage": "dethroned", "legs": []},
        {"verdict": "rejected", "stage": "width",
         "legs": [{"leg": "width", "measured": 0.31, "threshold": 0.25}]},
    ]
    assert terminal_verdict(cascade)["stage"] == "dethroned"
    cascade = [
        {"verdict": "rejected", "stage": "rescue_unused", "legs": []},
        {"verdict": "rejected", "stage": "occupancy",
         "legs": [{"leg": "coverage", "measured": 0.4, "threshold": 0.6}]},
    ]
    assert terminal_verdict(cascade)["stage"] == "rescue_unused"


def test_terminal_verdict_unregistered_stage_surfaces_loudly():
    """A NEW cascade stage shipped without registering in CASCADE_STAGES must
    surface as the terminal story (deepest), never sink below a width kill."""
    cascade = [
        {"verdict": "rejected", "stage": "future_stage", "legs": []},
        {"verdict": "rejected", "stage": "traversal",
         "legs": [{"leg": "traversal_count", "measured": 1, "threshold": 2}]},
    ]
    assert terminal_verdict(cascade)["stage"] == "future_stage"


# ── the sentence vocabulary ──────────────────────────────────────────────────

def test_leg_sentence_formats_in_the_native_quantum():
    assert leg_sentence({"leg": "respect_run", "measured": 7, "threshold": 5}) \
        == "longest run outside the rails 7 bars vs cap 5"
    assert leg_sentence({"leg": "coverage", "measured": 0.55, "threshold": 0.6}) \
        == "window occupancy 0.55 vs floor 0.60"


def test_leg_sentence_kill_site_unknown_is_an_em_dash_never_fabricated():
    s = leg_sentence({"leg": "crash", "measured": None, "threshold": 0.75})
    assert "—" in s and "0.75" in s


def test_leg_sentence_unknown_leg_renders_verbatim_never_blank():
    s = leg_sentence({"leg": "future_leg", "measured": 1, "threshold": 2})
    assert s.startswith("future_leg:") and s.strip()


def test_near_threshold_kill_never_renders_as_an_equal_pass():
    """Council F9: 0.798 vs floor 0.80 rendered '0.80 vs 0.80' — a refusal
    whose numbers read as a pass. Precision widens until the strings differ;
    genuinely equal values stay at the native two decimals."""
    s = leg_sentence({"leg": "respect_share", "measured": 0.798, "threshold": 0.80})
    assert "0.798" in s and "0.800" in s
    same = leg_sentence({"leg": "respect_share", "measured": 0.80, "threshold": 0.80})
    assert "0.80 vs floor 0.80" in same


def test_leg_sentences_never_carry_engineer_vocabulary():
    """The wire vocabulary law: no settings-constant names (CONSTANT_CASE
    tokens), no retired jargon words — as whole words, plain chart language."""
    import re

    from engine_alpha.structure.trace_export import _LEG_PHRASES

    for leg, phrase in _LEG_PHRASES.items():
        assert not re.search(r"\b[A-Z][A-Z_]{2,}\b", phrase), (leg, phrase)
        for banned in ("creek", "ice", "buec", "mini-bc"):
            assert not re.search(rf"\b{banned}\b", phrase, re.IGNORECASE), (leg, phrase)


# ── the export shape ─────────────────────────────────────────────────────────

def _trace_fixture():
    return [
        {   # root 0: died at the box election
            "root_index": 0, "climax_bar": 2, "ar_bar": 4, "kind": "BC",
            "outcome": "no_box", "box": None,
            "box_cascade": [
                {"verdict": "rejected", "stage": "width", "R": 12.0, "S": 9.0,
                 "cand_start": 5, "legs": [
                     {"leg": "width", "measured": 0.33, "threshold": 0.25}]},
            ],
        },
        {   # root 1: complete — the elected story
            "root_index": 1, "climax_bar": 8, "ar_bar": 10, "kind": "BC",
            "outcome": "complete",
            "box": {"R": 11.5, "S": 10.0, "start_bar": 10},
            "box_cascade": [
                {"verdict": "rejected", "stage": "occupancy", "cand_start": 11,
                 "legs": [{"leg": "coverage", "measured": 0.4, "threshold": 0.6}]},
                {"verdict": "valid", "stage": None, "cand_start": 10,
                 "R": 11.5, "S": 10.0, "rescued": False},
                {"verdict": "elected", "stage": "selection", "cand_start": 10,
                 "R": 11.5, "S": 10.0, "rescued": False},
            ],
        },
    ]


def test_export_is_date_anchored_and_compact():
    df = _df()
    out = export_election_trace(_trace_fixture(), df)
    assert out is not None
    r0, r1 = out["roots"]
    assert r0["climax"] == str(df.index[2].date())
    assert r0["outcome"] == "no_box"
    assert r0["refused"] == {"width": 1}
    assert r0["furthest"]["stage"] == "width"
    assert r1["outcome"] == "complete"
    assert "furthest" not in r1          # a completed root needs no epitaph
    e = out["elected"]
    assert e["root_index"] == 1
    assert e["start"] == str(df.index[10].date())
    assert e["R"] == 11.5 and e["S"] == 10.0
    assert e["n_valid"] == 2 and e["rescued"] is False
    # no bar index anywhere on the wire
    blob = json.dumps(out)
    assert "_bar" not in blob
    assert len(blob) < 2000               # compact, not the raw trace


def test_export_empty_trace_is_none():
    assert export_election_trace([], _df()) is None
    assert export_election_trace(None, _df()) is None


def test_elected_start_is_the_published_backextended_geometry():
    """Council F9: the drawn box's left rail is the back-extended start_bar;
    exporting the elected record's raw cand_start names a date the chart
    contradicts whenever back-extension fired. The fixture makes them differ."""
    df = _df()
    trace = [{
        "root_index": 0, "climax_bar": 2, "ar_bar": 4, "kind": "BC",
        "outcome": "complete",
        "box": {"R": 11.5, "S": 10.0, "start_bar": 8},   # walked left to bar 8
        "box_cascade": [
            {"verdict": "elected", "stage": "selection", "cand_start": 12,
             "R": 11.5, "S": 10.0, "rescued": False, "backext_bars": 4},
        ],
    }]
    e = export_election_trace(trace, df)["elected"]
    assert e["start"] == str(df.index[8].date())     # published, not cand_start
    assert e["backext_bars"] == 4                    # and the story says so


def test_elected_start_falls_back_to_cand_start_without_a_box_brief():
    df = _df()
    trace = [{
        "root_index": 0, "climax_bar": 2, "ar_bar": 4, "kind": "BC",
        "outcome": "complete", "box": None,
        "box_cascade": [
            {"verdict": "elected", "stage": "selection", "cand_start": 12,
             "R": 11.5, "S": 10.0, "rescued": False},
        ],
    }]
    e = export_election_trace(trace, df)["elected"]
    assert e["start"] == str(df.index[12].date())
    assert "backext_bars" not in e


def test_fired_root_narrates_the_resolved_phase_a_died_roots_keep_the_seed():
    """Council F9: the chart overlay and the strategy read use the RESOLVED
    climax→AR bridge; the trace's fired root must narrate the same pair while
    died roots keep the seed swing (the walk's honest history)."""
    df = _df()
    trace = [
        {"root_index": 0, "climax_bar": 2, "ar_bar": 4, "kind": "BC",
         "outcome": "no_box", "box": None, "box_cascade": []},
        {"root_index": 1, "climax_bar": 8, "ar_bar": 10, "kind": "BC",
         "resolved_climax_bar": 9, "resolved_ar_bar": 11,
         "outcome": "complete", "box": {"R": 11.5, "S": 10.0, "start_bar": 11},
         "box_cascade": [
             {"verdict": "elected", "stage": "selection", "cand_start": 11,
              "R": 11.5, "S": 10.0, "rescued": False}]},
    ]
    out = export_election_trace(trace, df)
    assert out["roots"][0]["climax"] == str(df.index[2].date())   # seed kept
    assert out["roots"][1]["climax"] == str(df.index[9].date())   # resolved
    assert out["roots"][1]["ar"] == str(df.index[11].date())


def test_no_lps_root_carries_no_epitaph_and_bad_bars_degrade_to_none():
    """A no_lps root's cascade PASSED (the walk died at Phase D — the outcome
    states it); and an out-of-range/None bar anchors to None, never raises."""
    df = _df()
    trace = [{
        "root_index": 0, "climax_bar": 999, "ar_bar": None, "kind": "BC",
        "outcome": "no_lps", "box": {"R": 11.5, "S": 10.0, "start_bar": 10},
        "box_cascade": [
            {"verdict": "valid", "stage": None, "cand_start": 10,
             "R": 11.5, "S": 10.0, "rescued": False}],
    }]
    out = export_election_trace(trace, df)
    r = out["roots"][0]
    assert "furthest" not in r          # only no_box roots get the epitaph
    assert r["climax"] is None and r["ar"] is None
    assert out["elected"] is None       # no complete root -> nothing elected


# ── archive / payload round-trip ─────────────────────────────────────────────

def test_archive_and_chart_projections_share_null_fidelity():
    assert set(ELECTION_TRACE_COLUMN_SQL) == {"election_trace"}
    cell = json.dumps({"roots": [], "elected": None})
    live = election_trace_archive_values({"_election_trace": cell}.get, prefixed=True)
    assert live["election_trace"] == cell
    seed = election_trace_archive_values({"election_trace": cell}.get, prefixed=False)
    assert seed["election_trace"] == cell
    absent = election_trace_archive_values({}.get, prefixed=True)
    assert absent["election_trace"] is None          # NULL = never captured
    parsed = election_trace_chart_fields({"_election_trace": cell}.get)
    assert parsed["election_trace"] == {"roots": [], "elected": None}
    broken = election_trace_chart_fields({"_election_trace": "{nope"}.get)
    assert broken["election_trace"] is None          # unreadable, degraded


# ── the dark default ─────────────────────────────────────────────────────────

def test_flag_ships_dark():
    """EC-8: the export ships default-off; the flip is an operator decision
    gated on the re-measured scan cost (see flag_ledger.md)."""
    assert settings.ELECTION_TRACE_EXPORT_ENABLED is False
