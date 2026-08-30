"""The ONE-vocabulary projection (engine_alpha.structure.event_vocabulary).

Literal-fixture tests (Beck: expected values stated, never computed): the
inputs are hand-written reader-output dicts, the expectations are typed out.
The module is DARK (no engine consumer) - these tests are its only cascade
until later program tasks repoint consumers under the reader-pin gate.
"""
import copy

import pytest

from engine_alpha.structure.event_vocabulary import (
    WORD_BY_PUZZLE_TYPE,
    unify_events,
)

# Hand-written reader outputs - shapes copied from the readers' documented
# contracts, values invented and literal.
PUZZLE = [
    {"type": "test", "rail": "S", "zone_start": 2, "zone_end": 5,
     "anchor_bar": 3, "valley_bar": 3, "resolution": "held"},
    {"type": "rejection", "rail": "R", "zone_start": 8, "zone_end": 11,
     "anchor_bar": 9, "peak_bar": 9, "resolution": "held"},
    {"type": "in_progress", "rail": "R", "zone_start": 20, "zone_end": 24,
     "anchor_bar": 22, "peak_bar": 22},
]
LABELS = {"labels": [
    {"role": "test", "knowable_bar": 11, "in_progress": False,
     "election_dependent": False},
    {"role": "rejection", "knowable_bar": 15, "in_progress": False,
     "election_dependent": False},
    {"role": "in_progress", "knowable_bar": None, "in_progress": True,
     "election_dependent": False},
], "n_labels": 3}
EPISODES = {"episodes": [
    {"rail": "S", "outcome": "completed", "start_bar": 1, "end_bar": 6,
     "posture": False},
    {"rail": "R", "outcome": "open", "start_bar": 19, "end_bar": 24,
     "posture": True},
]}


def test_folds_both_sources_into_one_chronological_stream():
    out = unify_events(box_events=PUZZLE, role_labels=LABELS,
                       episode_read=EPISODES)
    assert out["n_puzzle"] == 3 and out["n_episode"] == 2
    got = [(r["word"], r["verdict"], r["source"], r["span"]) for r in out["events"]]
    assert got == [
        ("support_test", "held", "episode", [1, 6]),      # S episode
        ("support_test", "held", "puzzle", [2, 5]),       # S test wave
        ("touch_and_pivot", "held", "puzzle", [8, 11]),   # R graze
        ("resistance_test", "open", "episode", [19, 24]),  # open R episode
        ("resistance_test", "open", "puzzle", [20, 24]),   # in_progress R wave
    ]


def test_label_stamps_ride_the_matching_wave():
    out = unify_events(box_events=PUZZLE, role_labels=LABELS)
    puz = [r for r in out["events"] if r["source"] == "puzzle"]
    assert [r["knowable_bar"] for r in puz] == [11, 15, None]
    assert [r["in_progress"] for r in puz] == [False, False, True]


def test_label_count_mismatch_drops_all_stamps_never_misattributes():
    short = {"labels": LABELS["labels"][:2], "n_labels": 2}
    out = unify_events(box_events=PUZZLE, role_labels=short)
    for r in out["events"]:
        assert r.get("labels_unaligned") is True
        assert "knowable_bar" not in r


def test_absent_readers_fold_as_nothing_never_fabricate():
    assert unify_events() == {"events": [], "n_puzzle": 0, "n_episode": 0,
                              "n_inner": 0}
    out = unify_events(episode_read=EPISODES)
    assert out["n_puzzle"] == 0 and len(out["events"]) == 2


def test_unknown_emitted_value_fails_loudly_never_coins_a_word():
    with pytest.raises(ValueError, match="puzzle type"):
        unify_events(box_events=[{"type": "creek_jump", "rail": "R",
                                  "zone_start": 0, "zone_end": 1,
                                  "anchor_bar": 0}])
    with pytest.raises(ValueError, match="episode outcome"):
        unify_events(episode_read={"episodes": [
            {"rail": "S", "outcome": "collapsed", "start_bar": 0, "end_bar": 1}]})


def test_inputs_are_not_mutated_and_raw_is_the_source_dict():
    puzzle = copy.deepcopy(PUZZLE)
    episodes = copy.deepcopy(EPISODES)
    before_p, before_e = copy.deepcopy(puzzle), copy.deepcopy(episodes)
    out = unify_events(box_events=puzzle, role_labels=None, episode_read=episodes)
    assert puzzle == before_p and episodes == before_e
    puz = [r for r in out["events"] if r["source"] == "puzzle"]
    assert puz[0]["raw"] is puzzle[0]   # by reference, unmodified


def test_basis_and_origin_ride_every_record():
    out = unify_events(
        box_events=PUZZLE, role_labels=LABELS, episode_read=EPISODES,
        puzzle_operands={"R": 10.0, "S": 5.0, "atr": 1.0,
                         "box_start_in_window": 4},
        episode_operands={"R": 10.0, "S": 5.0, "atr": 1.25,
                          "window_end": "2026-08-27"},
    )
    puz = [r for r in out["events"] if r["source"] == "puzzle"]
    epi = [r for r in out["events"] if r["source"] == "episode"]
    for r in puz:
        assert r["origin"] == "box"
        assert r["basis"]["zone_geometry"] == "box_relative"
        assert r["basis"]["breach_basis"] == "extremes_vs_local_swing"
        assert r["basis"]["atr"] == 1.0
    for r in epi:
        assert r["origin"] == "window"
        assert r["basis"]["zone_geometry"] == "atr_fixed"
        assert r["basis"]["breach_basis"] == "close_vs_rail"
        assert r["basis"]["atr"] == 1.25   # F9: two ATRs stay distinguishable


def test_window_span_converts_on_declared_offset_and_refuses_without():
    from engine_alpha.structure.event_vocabulary import window_span

    with_offset = unify_events(
        box_events=PUZZLE, episode_read=EPISODES,
        puzzle_operands={"box_start_in_window": 4})
    puz = [r for r in with_offset["events"] if r["source"] == "puzzle"]
    epi = [r for r in with_offset["events"] if r["source"] == "episode"]
    # Puzzle span [2,5] at box offset 4 -> window [6,9]; episodes verbatim.
    assert window_span(puz[0]) == [6, 9]
    assert window_span(epi[0]) == [1, 6]

    without = unify_events(box_events=PUZZLE)
    puz = [r for r in without["events"] if r["source"] == "puzzle"]
    assert window_span(puz[0]) is None   # refuses, never guesses


# ---------------------------------------------------------------------------
# PLAN-one-event-map Task 8 — the coverage proof. The operator refused to rule
# "bars sitting above resistance" in the blanket: the treatment depends on what
# the bars ARE — "are theese bars an LPS? an UPTHRUST that recovers later into
# the base? a mini consolidation that rests on the resistance? forming a double
# base?" These tests prove the folded vocabulary can NAME each context (the
# 2026-08-30 rest/departure/undetermined contract), so a future dispatcher has
# a context to read. The TREATMENT stays Program 2 — nothing here judges.
#
# Honest coverage statement (the proof's other half):
#   * LPS, recovering upthrust, departure (markup), and the undetermined right
#     edge are folded tape records TODAY — proven below.
#   * "a mini consolidation that rests on the resistance" is named by
#     InnerBox.position == "at_ceiling" (the ruled three-value attribute, dark)
#     — it becomes a folded TAPE record only when Task 9's shelf event lands;
#     until then the tape cannot carry it and says so here rather than faking.
#   * "forming a double base" is named by the chain reader (chain.py, dark) —
#     a STRUCTURE-level read deliberately outside this rail-event tape's axis.
# ---------------------------------------------------------------------------

def test_context_lps_is_nameable_on_the_tape():
    out = unify_events(box_events=[
        {"type": "lps", "rail": "S", "phase": "D", "zone_start": 30,
         "zone_end": 34, "anchor_bar": 32, "swing_type": "holding_shelf"}])
    rec = out["events"][0]
    assert rec["word"] == "lps"
    assert rec["verdict"] is None          # a rest, not a rail verdict
    assert rec["raw"]["swing_type"] == "holding_shelf"   # stored spelling rides


def test_context_recovering_upthrust_is_nameable_on_the_tape():
    # A breach above R that failed back into the range: the word carries the
    # event, the verdict says the rail HELD (price came back inside).
    out = unify_events(box_events=[
        {"type": "upthrust", "rail": "R", "zone_start": 10, "zone_end": 14,
         "anchor_bar": 12, "peak_bar": 12, "resolution": "failed"}])
    rec = out["events"][0]
    assert (rec["word"], rec["verdict"]) == ("upthrust", "held")


def test_context_departure_is_nameable_and_distinct_from_a_rest():
    # "part of a bigger swing upwards" = bars clearly continue up = markup.
    out = unify_events(box_events=[
        {"type": "markup", "rail": "R", "zone_start": 40, "zone_end": 48,
         "anchor_bar": 44, "peak_bar": 44, "resolution": "held"}])
    rec = out["events"][0]
    assert (rec["word"], rec["verdict"]) == ("markup", "gave")


def test_context_right_edge_is_undetermined_never_pretyped():
    # "The bars after wards determine the meaning" — at the right edge there
    # is no afterwards yet: the word stays the engagement, the verdict OPEN.
    out = unify_events(box_events=[
        {"type": "in_progress", "rail": "R", "zone_start": 50, "zone_end": 54,
         "anchor_bar": 52, "peak_bar": 52}])
    rec = out["events"][0]
    assert (rec["word"], rec["verdict"]) == ("resistance_test", "open")
    assert rec["word"] not in ("upthrust", "sos", "markup")


def test_context_completed_rest_on_resistance_is_the_sos_hold():
    # A breach that HELD with a consolidation near R — the completed form of
    # "resting on resistance" the wave reader can already type.
    out = unify_events(box_events=[
        {"type": "SOS", "rail": "R", "zone_start": 20, "zone_end": 27,
         "anchor_bar": 22, "peak_bar": 22, "resolution": "held",
         "consolidation": True}])
    rec = out["events"][0]
    assert (rec["word"], rec["verdict"]) == ("sos", "gave")
    assert rec["raw"]["consolidation"] is True


# --- Task 9: the mini-consolidation (shelf) tape record ----------------------
# One literal fixture per RULED position (2026-08-29/30: three values), plus
# the knowability legs. The detection dicts mirror select_inner_box's output.

def _detection(position, r_atr, s_atr):
    return {"start_bar": 10, "base_len": 6, "R": 9.6, "S": 8.9,
            "position": position,
            "position_distances": None if position is None
            else {"r_atr": r_atr, "s_atr": s_atr}}


def test_shelf_at_ceiling_is_a_tape_record_with_position_and_distances():
    out = unify_events(inner_box=_detection("at_ceiling", -0.4, 3.9),
                       inner_operands={"at_right_edge": False})
    assert out["n_inner"] == 1
    rec = out["events"][0]
    assert rec["word"] == "mini_consolidation"
    assert rec["position"] == "at_ceiling"
    assert rec["position_distances"] == {"r_atr": -0.4, "s_atr": 3.9}
    assert rec["verdict"] is None            # a rest, not a rail verdict
    assert rec["span"] == [10, 15] and rec["anchor"] == 15
    assert rec["origin"] == "box"
    assert rec["basis"]["breach_basis"] == "rail_proximity"
    assert rec["knowable_bar"] == 16 and rec["in_progress"] is False
    assert rec["election_dependent"] is True


def test_shelf_mid_range_and_on_support_fold_with_their_ruled_values():
    for pos in ("mid_range", "on_support"):
        out = unify_events(inner_box=_detection(pos, -2.0, 0.3),
                           inner_operands={"at_right_edge": False})
        assert out["events"][0]["position"] == pos


def test_shelf_at_right_edge_is_in_progress_never_a_settled_identity():
    rec = unify_events(inner_box=_detection("at_ceiling", -0.2, 4.1),
                       inner_operands={"at_right_edge": True})["events"][0]
    assert rec["in_progress"] is True and rec["knowable_bar"] is None
    # And an UNDECLARED edge reads as in_progress — the fail-closed direction.
    rec = unify_events(inner_box=_detection("at_ceiling", -0.2, 4.1))["events"][0]
    assert rec["in_progress"] is True and rec["knowable_bar"] is None


def test_shelf_refused_position_rides_as_none_never_fabricated():
    rec = unify_events(inner_box=_detection(None, None, None),
                       inner_operands={"at_right_edge": False})["events"][0]
    assert rec["position"] is None and rec["position_distances"] is None


def test_every_declared_puzzle_type_folds_without_error():
    # EC-22 spirit at the projection: every legal emitted type produces a
    # folded record (the two None-word rows resolve through the rail table).
    for etype in WORD_BY_PUZZLE_TYPE:
        out = unify_events(box_events=[{"type": etype, "rail": "S",
                                        "zone_start": 0, "zone_end": 1,
                                        "anchor_bar": 0}])
        assert len(out["events"]) == 1
        assert out["events"][0]["word"]
