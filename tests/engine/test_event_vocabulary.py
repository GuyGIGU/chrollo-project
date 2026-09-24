"""The ONE-vocabulary projection (engine_alpha.structure.events.event_vocabulary).

Literal-fixture tests (Beck: expected values stated, never computed): the
inputs are hand-written reader-output dicts, the expectations are typed out.
The module is DARK (no engine consumer) - these tests are its only cascade
until later program tasks repoint consumers under the reader-pin gate.
"""
import copy

import pytest

from engine_alpha.structure.events.event_vocabulary import (
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
    # Three-state law (Task 3): a reader that never ran leaves its companion
    # NULL (None) — an absent read must never fabricate a zero.
    assert unify_events() == {"events": [], "n_puzzle": 0, "n_episode": 0,
                              "n_inner": 0,
                              "episode_nan_bars": None,
                              "episode_n_bars": None}
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
    from engine_alpha.structure.events.event_vocabulary import window_span

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
#     InnerBox.position == "at_ceiling" (the ruled FOUR-value attribute since
#     the 2026-08-30 touching_both ruling) — and since Task 9 landed (below)
#     it IS a folded tape record (word mini_consolidation, position riding).
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
    assert (rec["word"], rec["verdict"]) == ("markup", "breached")


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
    assert (rec["word"], rec["verdict"]) == ("sos", "breached")
    assert rec["raw"]["consolidation"] is True


# --- Task 9: the mini-consolidation (shelf) tape record ----------------------
# One literal fixture per RULED position (2026-08-29/30 rails-are-areas +
# the 2026-08-30 touching_both ruling: FOUR values), plus the knowability
# legs. The detection dicts mirror select_inner_box's output.

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


def test_shelf_mid_range_on_support_and_touching_both_fold_with_their_ruled_values():
    for pos in ("mid_range", "on_support", "touching_both"):
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


def test_every_declared_episode_outcome_folds_to_its_signed_verdict():
    # The mirror loop (council review 2026-08-30, Beck): read_rail_episodes
    # genuinely emits all four outcomes, and a mutation mapping failed->held
    # (a breached support reading as held on the tape) or dropping the
    # unreadable row must go red here, in the dark module's only cascade.
    from engine_alpha.structure.events.event_vocabulary import VERDICT_BY_EPISODE_OUTCOME

    assert set(VERDICT_BY_EPISODE_OUTCOME) == {
        "completed", "failed", "open", "unreadable"}
    for outcome, verdict in VERDICT_BY_EPISODE_OUTCOME.items():
        out = unify_events(episode_read={"episodes": [
            {"rail": "S", "outcome": outcome, "start_bar": 0, "end_bar": 3,
             "posture": False}]})
        assert len(out["events"]) == 1
        rec = out["events"][0]
        assert rec["word"] == "support_test"
        assert rec["verdict"] == verdict
    # The signed translations, typed out (never derived from the table under
    # test): a failed S episode is BREACHED, unreadable stays unreadable.
    assert VERDICT_BY_EPISODE_OUTCOME["failed"] == "breached"
    assert VERDICT_BY_EPISODE_OUTCOME["unreadable"] == "unreadable"


# ── the closed token sets + write-time assert (consolidation-method Task 1) ──

def test_words_and_verdicts_are_the_signed_closed_sets_literal():
    # Literal (Beck): the signed vocabulary spelled out — a word appearing
    # here without an operator signing row (or vanishing without a re-ruling)
    # is exactly the drift this pin exists to catch. Signed in full
    # 2026-08-30 (decisions.md word-table rows).
    from engine_alpha.structure.event_vocabulary import VERDICTS, WORDS

    assert WORDS == ("lps", "markup", "mini_consolidation", "range",
                     "resistance_test", "sos", "spring", "support_test",
                     "touch_and_pivot", "upthrust")
    assert VERDICTS == ("breached", "held", "open", "unreadable")


def test_the_sets_derive_from_the_declared_tables_never_a_retype():
    # EC-33: membership DERIVES from the declared tables, so extending a
    # table extends the sets by construction — every value a table can emit
    # is a member.
    from engine_alpha.structure.event_vocabulary import (
        VERDICT_BY_EPISODE_OUTCOME,
        VERDICTS,
        WORD_BY_EPISODE_RAIL,
        WORD_IN_PROGRESS_BY_RAIL,
        WORD_MINI_CONSOLIDATION,
        WORDS,
    )

    for word, verdict in WORD_BY_PUZZLE_TYPE.values():
        if word is not None:
            assert word in WORDS
        if verdict is not None:
            assert verdict in VERDICTS
    for word in (*WORD_IN_PROGRESS_BY_RAIL.values(),
                 *WORD_BY_EPISODE_RAIL.values(), WORD_MINI_CONSOLIDATION):
        assert word in WORDS
    for verdict in VERDICT_BY_EPISODE_OUTCOME.values():
        assert verdict in VERDICTS


def test_assert_token_accepts_every_signed_pair_and_the_unjudged_state():
    from engine_alpha.structure.event_vocabulary import (
        VERDICTS, WORDS, assert_token)

    for word in WORDS:
        assert_token(word, None)          # unjudged is legal (a rest, a range)
        for verdict in VERDICTS:
            assert_token(word, verdict)


def test_assert_token_refuses_an_unsigned_word_and_verdict():
    from engine_alpha.structure.event_vocabulary import assert_token

    # "holding_shelf" is the RETIRED term (operator naming ruling 2026-08-18)
    # — it survives only as frozen STORED vocabulary (AP-12), never as a
    # sentence token; "gave" is the pre-signing verdict the operator replaced
    # with "breached" (2026-08-30). Both must refuse at mint time (EC-55).
    with pytest.raises(ValueError, match="signed"):
        assert_token("holding_shelf", "held")
    with pytest.raises(ValueError, match="verdict"):
        assert_token("lps", "gave")


def test_every_folded_record_passes_the_write_time_assert():
    # The fold and the closed sets can never drift apart: every record the
    # projection emits — puzzle, episode, and the mini-consolidation — is a
    # member pair by construction.
    from engine_alpha.structure.event_vocabulary import assert_token

    out = unify_events(
        box_events=PUZZLE, role_labels=LABELS, episode_read=EPISODES,
        inner_box={"start_bar": 3, "base_len": 4, "position": "at_ceiling",
                   "position_distances": {"top_vs_r_atr": -0.2,
                                          "bottom_vs_s_atr": 1.1}})
    assert out["n_inner"] == 1
    for rec in out["events"]:
        assert_token(rec["word"], rec["verdict"])


# ── the translation contract (consolidation-method Task 2) ──────────────────

def test_every_channel_declares_its_skeleton():
    # The skeleton contract: a word's substrate is DECLARED per channel, and
    # market_structure's HH/HL labels are excluded by contract (their pivot
    # order scales with frame length — not truncation-stable, so no channel
    # may stand a sentence word on them).
    from engine_alpha.structure.event_vocabulary import BASIS_CONSTANTS

    assert BASIS_CONSTANTS["puzzle"]["skeleton"] == "collapsed_swing_walk"
    assert BASIS_CONSTANTS["episode"]["skeleton"] == "none_bar_level"
    assert BASIS_CONSTANTS["inner_box"]["skeleton"] == "inner_box_election"
    for channel in BASIS_CONSTANTS.values():
        assert "skeleton" in channel


def test_episode_records_carry_the_causality_stamps():
    out = unify_events(episode_read={"episodes": [
        {"rail": "S", "outcome": "completed", "start_bar": 1, "end_bar": 6,
         "posture": False, "knowable_bar": 9, "in_progress": False},
        {"rail": "R", "outcome": "open", "start_bar": 19, "end_bar": 24,
         "posture": True, "knowable_bar": None, "in_progress": True},
    ]})
    completed, open_rec = out["events"]
    assert completed["knowable_bar"] == 9 and completed["in_progress"] is False
    assert open_rec["knowable_bar"] is None and open_rec["in_progress"] is True
    # The right edge stays honestly UNDETERMINED: an unresolved engagement
    # renders its rail word with verdict open — never a pre-typed outcome
    # (the operator's 2026-08-30 "the bars afterwards determine the meaning").
    assert open_rec["verdict"] == "open"


def test_absent_stamps_read_unknown_never_falsely_settled():
    # A malformed/stamp-less input dict folds with None stamps — unknown,
    # never a fabricated settled identity (the fail-closed direction).
    out = unify_events(episode_read=EPISODES)   # fixture episodes: no stamps
    for rec in out["events"]:
        assert rec["knowable_bar"] is None
        assert rec["in_progress"] is None


# ── the three-state data law at the fold (consolidation-method Task 3) ──────

def test_readability_companion_lifts_measured_values_and_zero_is_evidence():
    # Explicit zero = measured-empty evidence (the reader ran, every verdict
    # bar finite) — distinguishable from the absent reader's None by law.
    out = unify_events(episode_read={"episodes": [], "n_episodes": 0,
                                     "nan_bars": 0, "n_bars": 40})
    assert out["episode_nan_bars"] == 0
    assert out["episode_n_bars"] == 40
    nan_out = unify_events(episode_read={"episodes": [], "n_episodes": 0,
                                         "nan_bars": 3, "n_bars": 40})
    assert nan_out["episode_nan_bars"] == 3


# ── the sentence archive family (consolidation-method Task 8) ───────────────

def test_sentence_archive_values_live_and_seed_mapping():
    from engine_alpha.structure.event_vocabulary import (
        SENTENCE_COLUMN_SQL, sentence_archive_values)

    live_row = {"_sentence_tokens": "[]", "_sentence_n_tokens": 0.0,
                "_sentence_nan_bars": 2}
    out = sentence_archive_values(live_row.get, prefixed=True)
    assert set(out) == set(SENTENCE_COLUMN_SQL)
    assert out["sentence_tokens"] == "[]"
    assert out["sentence_n_tokens"] == 0          # explicit zero = evidence
    assert isinstance(out["sentence_n_tokens"], int)
    seed_out = sentence_archive_values({"sentence_n_tokens": 3}.get,
                                       prefixed=False)
    assert seed_out["sentence_n_tokens"] == 3
    assert seed_out["sentence_tokens"] is None     # NULL = not measured
    # NaN scrubs at the pandas boundary (EC-2)
    nan_out = sentence_archive_values({"_sentence_nan_bars": float("nan")}.get,
                                      prefixed=True)
    assert nan_out["sentence_nan_bars"] is None


def test_serialize_sentence_date_anchors_and_the_family_cells():
    import json as _json

    import pandas as pd

    from engine_alpha.structure.event_vocabulary import serialize_sentence

    dates = pd.bdate_range("2026-01-05", periods=30)
    # Offset ZERO — the one live caller's declaration (the sentence's ruler is
    # the elected window anchored at the box start). The nonzero-offset
    # conversion arithmetic is pinned one layer down, on ``window_span``.
    unified = unify_events(
        box_events=PUZZLE, role_labels=LABELS,
        episode_read={"episodes": EPISODES["episodes"], "n_episodes": 2,
                      "nan_bars": 0, "n_bars": 30},
        puzzle_operands={"box_start_in_window": 0})
    cells = serialize_sentence(unified, dates)
    assert set(cells) == {"sentence_tokens", "sentence_n_tokens",
                          "sentence_nan_bars"}
    assert cells["sentence_n_tokens"] == 5
    assert cells["sentence_nan_bars"] == 0        # measured-empty is evidence
    records = _json.loads(cells["sentence_tokens"])
    assert len(records) == 5
    # Date anchors, never bar indexes (the serialization law).
    epi = [r for r in records if r["source"] == "episode"][0]
    assert epi["span"] == [str(dates[1].date()), str(dates[6].date())]
    puz = [r for r in records if r["source"] == "puzzle"][0]
    assert puz["span"] == [str(dates[2].date()), str(dates[5].date())]
    # The puzzle knowable stamp (box bar 11) dates on the window ruler too.
    assert puz["knowable"] == str(dates[11].date())


def test_serialize_sentence_off_ruler_span_is_honest_null():
    # The still-reachable honest-null path now that an absent offset refuses
    # outright (below): a record whose span lands OFF the judged window's own
    # index serializes null rather than a guessed date. Bars 8/11 and 20/24
    # sit past a ten-day window's right edge; bars 2/5 do not.
    import json as _json

    import pandas as pd

    from engine_alpha.structure.event_vocabulary import serialize_sentence

    dates = pd.bdate_range("2026-01-05", periods=10)
    unified = unify_events(box_events=PUZZLE, role_labels=LABELS,
                           episode_read={"episodes": [], "n_episodes": 0,
                                         "nan_bars": 0, "n_bars": 10},
                           puzzle_operands={"box_start_in_window": 0})
    records = _json.loads(
        serialize_sentence(unified, dates)["sentence_tokens"])
    assert [r["span"] for r in records] == [
        [str(dates[2].date()), str(dates[5].date())], None, None], (
        "a span that cannot reach the window ruler must serialize null — "
        "never a guessed date")


_CHANNELS = ("puzzle", "episode", "inner_box")

# The multi-channel serialization fixture. Both WARNING pins below exist to
# keep ONE promise - the line NAMES the channel that lost the value, so the
# next unrebased channel is found in minutes rather than at analysis time -
# and a single-channel fixture cannot tell a correct name from a hard-coded
# one (round-four verifier, 2026-09-01). All THREE declared channels ride this
# one read, and two WORDS appear in two channels each ('support_test' in the
# episode and puzzle channels, 'resistance_test' in the episode and puzzle
# channels), so the word cannot stand in for the channel either.
_MULTI_CHANNEL_EPISODES = [
    # On the ruler at ten days, span AND stamp - the control record.
    {"rail": "S", "outcome": "completed", "start_bar": 0, "end_bar": 3,
     "posture": False, "knowable_bar": 4, "in_progress": False},
    # Off it, span and stamp both - the window-origin channel's loss.
    {"rail": "R", "outcome": "completed", "start_bar": 12, "end_bar": 16,
     "posture": False, "knowable_bar": 17, "in_progress": False},
]
# The inner (mini-consolidation) channel's record: span 10-15, stamp 16.
_MULTI_CHANNEL_INNER = {"start_bar": 10, "base_len": 6, "R": 9.6, "S": 8.9,
                        "position": "at_ceiling",
                        "position_distances": {"r_atr": -0.4, "s_atr": 3.9}}


def _multi_channel_serialization(periods):
    """The mint driven over all three channels on a ``periods``-day window.

    At TEN days the tape reads, in order: the episode ``support_test`` (span
    0-5 -> on the ruler, stamp 4 -> on it), the puzzle ``support_test`` (span
    2-5 on, stamp 11 OFF - the critic's specimen), the puzzle
    ``touch_and_pivot`` (8-11 off, stamp 15 off), the inner-box
    ``mini_consolidation`` (10-15 off, stamp 16 off), the episode
    ``resistance_test`` (12-16 off, stamp 17 off) and the puzzle
    ``resistance_test`` (20-24 off, honestly in progress with no stamp to
    lose). Four spans and four stamps fall off the ruler, across all three
    channels, while two records keep theirs.

    At THIRTY days every one of them converts - the same records, the same
    channels, no warnings at all.
    """
    import json as _json

    import pandas as pd

    from engine_alpha.structure.event_vocabulary import serialize_sentence

    dates = pd.bdate_range("2026-01-05", periods=periods)
    unified = unify_events(
        box_events=PUZZLE, role_labels=LABELS,
        episode_read={"episodes": _MULTI_CHANNEL_EPISODES, "n_episodes": 2,
                      "nan_bars": 0, "n_bars": periods},
        inner_box=_MULTI_CHANNEL_INNER,
        puzzle_operands={"box_start_in_window": 0},
        inner_operands={"at_right_edge": False, "box_start_in_window": 0})
    records = _json.loads(
        serialize_sentence(unified, dates)["sentence_tokens"])
    return records, dates


def _vocabulary_warnings(caplog, phrase):
    return [r.message for r in caplog.records
            if r.name == "chrollo.engine.event_vocabulary"
            and r.levelname == "WARNING" and phrase in r.message]


def _assert_names_only(line, channel):
    """The load-bearing half of both pins: the line names THIS channel and no
    other. A hard-coded channel name passes the 'names a channel' half and
    fails here."""
    assert f"the {channel} channel's" in line, (
        f"the line does not name the {channel} channel: {line!r}")
    for other in _CHANNELS:
        if other != channel:
            assert f"the {other} channel's" not in line, (
                f"the line names the {other} channel for a record the "
                f"{channel} channel lost: {line!r}")


def _channels_named(lines):
    return sorted({ch for ch in _CHANNELS
                   for line in lines if f"the {ch} channel's" in line})


def test_the_off_ruler_span_null_is_named_on_the_log_never_silent(caplog):
    """The nulling above is HONEST but must never be SILENT — and until now
    nothing pinned that: the round-four critic deleted the whole
    ``_log.warning`` call from ``serialize_sentence`` and the family's 51 tests
    stayed green, while flag_ledger row 46 promises the operator this line as a
    trial-night expectation. Pinned the house way (the loud-degrade precedent
    at ``tests/test_strategy_read.py``'s
    ``test_out_of_range_bar_degrades_empty_and_logs_loudly`` — caplog.at_level
    on the named logger).

    The line has to NAME the channel: one record off the ruler is a read at the
    edge, a whole channel off it is a caller that never rebased, and the
    archive's null looks identical either way. That half is the load-bearing
    one and it is pinned over a fixture carrying all THREE channels — on a
    single-channel fixture a hard-coded name reads exactly like a correct one
    (round-four verifier, 2026-09-01).
    """
    with caplog.at_level("WARNING", logger="chrollo.engine.event_vocabulary"):
        records, _ = _multi_channel_serialization(10)
    # Anti-vacuity, both ways: four spans really nulled out on this fixture and
    # two records kept theirs, so "warn always" cannot pass either.
    assert [r["span"] for r in records].count(None) == 4
    assert [r["span"] for r in records].count(None) < len(records)

    lines = _vocabulary_warnings(caplog, "honest null span")
    assert len(lines) == 4, (
        "the promised off-ruler WARNING is missing - an archived null span is "
        "honest, a SILENT one is undetectable")
    # Typed out, per record: the channel that lost it, the word, the converted
    # span and the ruler it was measured from.
    for line, (channel, said) in zip(lines, [
            ("puzzle", "'touch_and_pivot' span [8, 11] (origin box)"),
            ("inner_box", "'mini_consolidation' span [10, 15] (origin box)"),
            ("episode", "'resistance_test' span [12, 16] (origin window)"),
            ("puzzle", "'resistance_test' span [20, 24] (origin box)")]):
        _assert_names_only(line, channel)
        assert f"the {channel} channel's {said}" in line
        assert "10-trading-day judged window" in line
        assert "never rebased onto the elected window" in line
    assert _channels_named(lines) == sorted(_CHANNELS), (
        "every declared channel lost a span on this fixture, so every one of "
        "them must appear on the log - a name that never varies is a "
        "hard-coded one")


def test_the_off_ruler_knowable_stamp_is_named_on_the_log_never_silent(caplog):
    """The span's SIBLING, in the same function (round-four critic,
    2026-09-01): "a record with knowable_bar: 500 against a 10-day window
    serialized knowable: None with zero log output while its span converted
    fine". A null ``knowable`` downstream is indistinguishable from the honest
    "not knowable yet" of a record still in progress, so a stamp the reader DID
    make and that then failed to reach the ruler must say so on the same log,
    in the same shape, naming the same channel — the channel it actually lost
    it in, which only a multi-channel fixture can tell apart.
    """
    with caplog.at_level("WARNING", logger="chrollo.engine.event_vocabulary"):
        records, _ = _multi_channel_serialization(10)

    # THE critic's specimen: the span converted fine, the stamp did not.
    settled = records[1]
    assert (settled["source"], settled["word"]) == ("puzzle", "support_test")
    assert settled["span"] is not None
    assert settled["knowable"] is None
    # Its same-worded neighbour in ANOTHER channel kept both — the word alone
    # can never say which channel lost a stamp.
    control = records[0]
    assert (control["source"], control["word"]) == ("episode", "support_test")
    assert control["span"] is not None and control["knowable"] is not None
    # ... and the in_progress wave, which never had a stamp to lose, must NOT
    # be reported: an honestly unknowable record is not a broken ruler.
    assert records[5]["knowable"] is None
    assert records[5]["in_progress"] is True

    lines = _vocabulary_warnings(caplog, "honest null causality stamp")
    assert len(lines) == 4, (
        "a knowable stamp that existed and then nulled out must be named on "
        "the log - exactly like the span beside it")
    for line, (channel, said) in zip(lines, [
            ("puzzle", "'support_test' knowable bar 11 (origin box)"),
            ("puzzle", "'touch_and_pivot' knowable bar 15 (origin box)"),
            ("inner_box", "'mini_consolidation' knowable bar 16 (origin box)"),
            ("episode", "'resistance_test' knowable bar 17 (origin window)")]):
        _assert_names_only(line, channel)
        assert f"the {channel} channel's {said}" in line
        assert "10-trading-day judged window" in line
        assert "never rebased onto the elected window" in line
    assert _channels_named(lines) == sorted(_CHANNELS), (
        "every declared channel lost a stamp on this fixture, so every one of "
        "them must appear on the log")


def test_a_knowable_stamp_on_the_ruler_is_serialized_and_never_reported(caplog):
    """The other direction, so the pins above cannot pass by warning always:
    the SAME six records on a thirty-day window all convert, so every span and
    every existing stamp lands and the log stays empty for all three
    channels."""
    with caplog.at_level("WARNING", logger="chrollo.engine.event_vocabulary"):
        records, dates = _multi_channel_serialization(30)
    assert [r["source"] for r in records] == [
        "episode", "puzzle", "puzzle", "inner_box", "episode", "puzzle"]
    assert [r["knowable"] for r in records] == [
        str(dates[4].date()), str(dates[11].date()), str(dates[15].date()),
        str(dates[16].date()), str(dates[17].date()), None]
    assert [r["span"] for r in records].count(None) == 0
    assert _vocabulary_warnings(caplog, "honest null") == []


# ── the two realistic RE-INTRODUCTIONS of the same defect ──────────────────
# The pins above bite on DELETION of the warning. Round-four verifier,
# 2026-09-01: they must also bite on the two shapes the defect comes back in —
# a channel-blind line (one channel's loss reported under another's name), and
# a bounds check that only guards the RIGHT edge, which is worse than a
# silent null because a negative bar index wraps to a real date from the wrong
# end of the window and archives a confidently WRONG day.

def _three_channel_read(*, puzzle_span=(2, 5), puzzle_knowable=4,
                        episode_span=(0, 3), episode_knowable=4,
                        inner_start=1, inner_len=4, n_bars=10):
    """One read carrying all three channels, every record on a ten-day ruler
    unless a caller moves it off. The knobs are per channel, so exactly one
    channel at a time can lose a span or a stamp."""
    return unify_events(
        box_events=[{"type": "test", "rail": "S",
                     "zone_start": puzzle_span[0], "zone_end": puzzle_span[1],
                     "anchor_bar": puzzle_span[0],
                     "valley_bar": puzzle_span[0], "resolution": "held"}],
        role_labels={"labels": [{"role": "test",
                                 "knowable_bar": puzzle_knowable,
                                 "in_progress": False,
                                 "election_dependent": False}],
                     "n_labels": 1},
        episode_read={"episodes": [
            {"rail": "R", "outcome": "completed",
             "start_bar": episode_span[0], "end_bar": episode_span[1],
             "posture": False, "knowable_bar": episode_knowable,
             "in_progress": False}],
            "n_episodes": 1, "nan_bars": 0, "n_bars": n_bars},
        inner_box={"start_bar": inner_start, "base_len": inner_len,
                   "R": 9.6, "S": 8.9, "position": "at_ceiling",
                   "position_distances": {"r_atr": -0.4, "s_atr": 3.9}},
        puzzle_operands={"box_start_in_window": 0},
        inner_operands={"at_right_edge": False, "box_start_in_window": 0})


def _serialize_ten_day(unified):
    import json as _json

    import pandas as pd

    from engine_alpha.structure.event_vocabulary import serialize_sentence

    dates = pd.bdate_range("2026-01-05", periods=10)
    return _json.loads(
        serialize_sentence(unified, dates)["sentence_tokens"]), dates


@pytest.mark.parametrize("channel, kwargs", [
    ("puzzle", {"puzzle_span": (12, 15)}),
    ("episode", {"episode_span": (12, 16)}),
    ("inner_box", {"inner_start": 12}),
], ids=["puzzle_off", "episode_off", "inner_box_off"])
def test_the_span_warning_names_the_channel_that_lost_it(caplog, channel,
                                                         kwargs):
    """One channel off the ruler at a time, the other two on it. A line that
    named a fixed channel would pass on one parameter and fail on the other
    two — which is exactly what the old single-channel fixture could not do."""
    with caplog.at_level("WARNING", logger="chrollo.engine.event_vocabulary"):
        records, _ = _serialize_ten_day(_three_channel_read(**kwargs))
    lost = [r for r in records if r["span"] is None]
    assert [r["source"] for r in lost] == [channel], (
        "the fixture must strand exactly the parametrised channel")

    lines = _vocabulary_warnings(caplog, "honest null span")
    assert len(lines) == 1, "one lost span, one line"
    _assert_names_only(lines[0], channel)


@pytest.mark.parametrize("channel, kwargs", [
    ("puzzle", {"puzzle_knowable": 40}),
    ("episode", {"episode_knowable": 40}),
    ("inner_box", {"inner_start": 6}),      # span 6-9 on the ruler, stamp 10 off
], ids=["puzzle_off", "episode_off", "inner_box_off"])
def test_the_stamp_warning_names_the_channel_that_lost_it(caplog, channel,
                                                          kwargs):
    """The stamp leg of the same parametrisation: every span still converts,
    so only the causality stamp is lost and only one channel loses it."""
    with caplog.at_level("WARNING", logger="chrollo.engine.event_vocabulary"):
        records, _ = _serialize_ten_day(_three_channel_read(**kwargs))
    assert [r["span"] for r in records].count(None) == 0, (
        "this leg strands the STAMP only - every span must still convert")
    lost = [r for r in records if r["knowable"] is None]
    assert [r["source"] for r in lost] == [channel]

    lines = _vocabulary_warnings(caplog, "honest null causality stamp")
    assert len(lines) == 1, "one lost stamp, one line"
    _assert_names_only(lines[0], channel)


@pytest.mark.parametrize("channel, kwargs, span", [
    ("puzzle", {"puzzle_span": (-4, -1)}, [-4, -1]),
    ("episode", {"episode_span": (-3, -1)}, [-3, -1]),
], ids=["box_origin", "window_origin"])
def test_a_span_below_the_ruler_is_reported_and_never_wraps(caplog, channel,
                                                            kwargs, span):
    """Off the ruler in the OTHER direction, on both span origins.

    The bounds check is ``0 <= bar < n`` at both ends, and the lower half is
    the load-bearing one: a check rewritten as ``bar < n`` would let a negative
    bar index through, and Python would hand it a REAL date from the wrong end
    of the window — a confidently wrong day in the archive, with no line on the
    log, which is strictly worse than the honest null this warning exists to
    announce.
    """
    with caplog.at_level("WARNING", logger="chrollo.engine.event_vocabulary"):
        records, dates = _serialize_ten_day(_three_channel_read(**kwargs))
    wrapped = [str(dates[span[0]].date()), str(dates[span[1]].date())]
    assert wrapped == [str(dates[10 + span[0]].date()),
                       str(dates[10 + span[1]].date())]   # what wrapping gives
    assert [r["span"] for r in records].count(wrapped) == 0, (
        f"a negative bar wrapped to {wrapped} - the window's own TAIL dates "
        "archived as if the reader had named them, and no line on the log")
    lost = [r for r in records if r["span"] is None]
    assert [r["source"] for r in lost] == [channel]

    lines = _vocabulary_warnings(caplog, "honest null span")
    assert len(lines) == 1
    _assert_names_only(lines[0], channel)
    assert f"span {span} " in lines[0], (
        "the line must show the bars it refused, negative ones included")


def test_a_knowable_stamp_below_the_ruler_is_reported_and_never_wraps(caplog):
    """The stamp's twin of the case above: a negative knowable bar is off the
    ruler too, and must null with a line rather than date to the wrong end of
    the window."""
    with caplog.at_level("WARNING", logger="chrollo.engine.event_vocabulary"):
        records, dates = _serialize_ten_day(
            _three_channel_read(episode_knowable=-2))
    assert [r["span"] for r in records].count(None) == 0
    wrapped = str(dates[-2].date())
    assert wrapped == str(dates[8].date())          # what wrapping would give
    assert wrapped not in [r["knowable"] for r in records], (
        "a negative knowable bar wrapped to a real date from the window's "
        "TAIL - the archive cannot tell that apart from a measured stamp")
    lost = [r for r in records if r["knowable"] is None]
    assert [r["source"] for r in lost] == ["episode"]

    lines = _vocabulary_warnings(caplog, "honest null causality stamp")
    assert len(lines) == 1
    _assert_names_only(lines[0], "episode")
    assert "knowable bar -2 " in lines[0]


def test_serialize_sentence_refuses_an_unsigned_token_at_mint():
    import pandas as pd

    from engine_alpha.structure.event_vocabulary import serialize_sentence

    dates = pd.bdate_range("2026-01-05", periods=10)
    bad = {"events": [{"word": "creek_jump", "verdict": "held",
                       "span": [0, 1], "source": "puzzle",
                       "origin": "window"}],
           "episode_nan_bars": 0}
    with pytest.raises(ValueError, match="signed"):
        serialize_sentence(bad, dates)


# ── the two single-caller trusts, refused (council review 2026-09-01, #13) ──

def test_serialize_sentence_refuses_a_nonzero_declared_offset():
    # The tape's ORDER is decided upstream on RAW spans (box-relative for the
    # puzzle/inner channels, window-relative for episodes). That is genuinely
    # chronological only while the two rulers share an origin — a caller
    # anchoring elsewhere would archive correctly-dated but WRONGLY-ORDERED
    # sentences, with nothing to tell the reader afterwards.
    import pandas as pd

    from engine_alpha.structure.event_vocabulary import serialize_sentence

    dates = pd.bdate_range("2026-01-05", periods=30)
    unified = unify_events(
        box_events=PUZZLE, role_labels=LABELS,
        episode_read={"episodes": EPISODES["episodes"], "n_episodes": 2,
                      "nan_bars": 0, "n_bars": 30},
        puzzle_operands={"box_start_in_window": 4})
    with pytest.raises(ValueError, match="WRONGLY-ORDERED"):
        serialize_sentence(unified, dates)
    # The inner (mini-consolidation) channel is box-origin too — same refusal.
    inner = unify_events(
        inner_box=_detection("at_ceiling", -0.4, 3.9),
        episode_read={"episodes": [], "n_episodes": 0, "nan_bars": 0,
                      "n_bars": 30},
        inner_operands={"at_right_edge": False, "box_start_in_window": 7})
    with pytest.raises(ValueError, match="WRONGLY-ORDERED"):
        serialize_sentence(inner, dates)


def test_serialize_sentence_refuses_an_absent_declared_offset():
    # The round-two completeness critic (2026-09-01): the nonzero guard read
    # ``not in (None, 0)``, so an ABSENT declaration was ADMITTED — and absent
    # means the two rulers are not KNOWN to share an origin. That is the same
    # ordering pathology with the dates removed: the span nulls out and the
    # shuffle becomes undetectable downstream. A box-origin record must carry
    # an EXPLICIT zero; absence is a refusal, not a pass.
    import pandas as pd

    from engine_alpha.structure.event_vocabulary import serialize_sentence

    dates = pd.bdate_range("2026-01-05", periods=30)
    undeclared = unify_events(
        box_events=PUZZLE, role_labels=LABELS,
        episode_read={"episodes": EPISODES["episodes"], "n_episodes": 2,
                      "nan_bars": 0, "n_bars": 30})
    assert all("box_start_in_window" not in (r.get("basis") or {})
               for r in undeclared["events"] if r["origin"] == "box")
    with pytest.raises(ValueError, match="ABSENT declaration"):
        serialize_sentence(undeclared, dates)
    # The inner channel again — box-origin, so the same refusal.
    inner = unify_events(
        inner_box=_detection("at_ceiling", -0.4, 3.9),
        episode_read={"episodes": [], "n_episodes": 0, "nan_bars": 0,
                      "n_bars": 30},
        inner_operands={"at_right_edge": False})
    with pytest.raises(ValueError, match="ABSENT declaration"):
        serialize_sentence(inner, dates)
    # ... and the EXPLICIT zero the one live caller declares still passes.
    declared = unify_events(
        box_events=PUZZLE, role_labels=LABELS,
        episode_read={"episodes": EPISODES["episodes"], "n_episodes": 2,
                      "nan_bars": 0, "n_bars": 30},
        puzzle_operands={"box_start_in_window": 0})
    assert serialize_sentence(declared, dates)["sentence_n_tokens"] == 5


def test_serialize_sentence_refuses_measured_tokens_without_the_companion():
    # The fourth, undeclared family state: measured tokens + a measured count
    # beside a NULL readability companion. Every three-state query downstream
    # reads that row as "not measured" on one cell and "measured" on two — so
    # the mint refuses it rather than letting the producer invent it.
    import pandas as pd

    from engine_alpha.structure.event_vocabulary import serialize_sentence

    dates = pd.bdate_range("2026-01-05", periods=30)
    unified = unify_events(box_events=PUZZLE, role_labels=LABELS,
                           puzzle_operands={"box_start_in_window": 0})
    assert unified["episode_nan_bars"] is None      # no episode channel
    with pytest.raises(ValueError, match="readability companion"):
        serialize_sentence(unified, dates)


# ── the signed vocabulary inside the frozen identity (review #6) ────────────

def test_vocabulary_manifest_is_the_derived_projection_the_freeze_hashes():
    # An epoch must partition MEANING, not just settings: the family's law is
    # "different reader vocabularies = different epochs, no backfill", so a
    # signed re-wording has to rotate engine_config_version. Derived from the
    # ONE declaration (EC-33), never a second copy of the tables — and the
    # projection covers the MAPPINGS, not only the derived value sets.
    from engine_alpha.freeze.manifest import collect_manifest
    from engine_alpha.structure.event_vocabulary import (
        VERDICT_BY_EPISODE_OUTCOME,
        VERDICTS,
        WORD_BY_EPISODE_RAIL,
        WORD_IN_PROGRESS_BY_RAIL,
        WORD_MINI_CONSOLIDATION,
        WORDS,
        vocabulary_manifest,
    )

    from engine_alpha.structure.event_vocabulary import BASIS_CONSTANTS

    block = vocabulary_manifest()
    assert block == {
        "words": list(WORDS),
        "verdicts": list(VERDICTS),
        "puzzle_type_words": {etype: list(pair) for etype, pair
                              in WORD_BY_PUZZLE_TYPE.items()},
        "in_progress_rail_words": dict(WORD_IN_PROGRESS_BY_RAIL),
        "episode_rail_words": dict(WORD_BY_EPISODE_RAIL),
        "episode_outcome_verdicts": dict(VERDICT_BY_EPISODE_OUTCOME),
        "mini_consolidation_word": WORD_MINI_CONSOLIDATION,
        # Round three: the per-channel basis is identity too — it rides in
        # every archived token's ``basis`` cell and its span_origin decides
        # how that token's span may be read at all.
        "channel_basis": {channel: dict(props) for channel, props
                          in BASIS_CONSTANTS.items()},
    }
    assert collect_manifest()["SENTENCE_VOCABULARY"] == block


def test_the_signed_assignment_is_pinned_literal_not_only_its_value_sets():
    # Beck-literal, the round-two companion to the closed-set pin above: the
    # SETS say which words exist, this says which word each reader event MEANS.
    # The operator's pending signings re-assign inside the existing sets, so a
    # sets-only pin (and a sets-only epoch block) sees nothing move. Word table
    # signed in full 2026-08-30 (decisions.md), verdict axis the same day.
    from engine_alpha.structure.event_vocabulary import (
        VERDICT_BY_EPISODE_OUTCOME, WORD_BY_EPISODE_RAIL)

    assert WORD_BY_PUZZLE_TYPE == {
        "spring":      ("spring", "held"),
        "test":        ("support_test", "held"),
        "failed":      ("support_test", "breached"),
        "lps":         ("lps", None),
        "SOS":         ("sos", "breached"),
        "markup":      ("markup", "breached"),
        "upthrust":    ("upthrust", "held"),
        "rejection":   ("touch_and_pivot", "held"),
        "range":       ("range", None),
        "in_progress": (None, "open"),
    }
    assert WORD_BY_EPISODE_RAIL == {"S": "support_test",
                                    "R": "resistance_test"}
    assert VERDICT_BY_EPISODE_OUTCOME == {"completed": "held",
                                          "failed": "breached",
                                          "open": "open",
                                          "unreadable": "unreadable"}


def test_a_signed_re_wording_rotates_the_engine_config_version(monkeypatch):
    # The teeth: re-word ONE declared cell and the hash must move. Without
    # this block a post-flip re-wording would mint new-worded rows under the
    # old epoch stamp, and with backfill forbidden the mixed population could
    # never be partitioned again.
    import engine_alpha.structure.event_vocabulary as ev
    from engine_alpha.freeze.manifest import manifest_hash

    before = manifest_hash()
    monkeypatch.setattr(ev, "WORDS", ev.WORDS + ("a_freshly_signed_word",))
    assert manifest_hash() != before


def test_a_re_ruling_inside_the_closed_sets_rotates_the_version(monkeypatch):
    # The round-two teeth (completeness critic 2026-09-01): the epoch block
    # hashed the derived word/verdict VALUE SETS, so a re-ruling that
    # re-assigns INSIDE those sets — spring's verdict held -> breached, two
    # signed words swapped between reader events, the two rails swapped —
    # changed what every archived sentence SAYS and rotated nothing. That is
    # exactly the shape of the operator's pending word signings, and with no
    # backfill EVER the re-meaning'd rows would land under the old stamp with
    # nothing left to partition the mixed population by.
    import engine_alpha.structure.event_vocabulary as ev
    from engine_alpha.freeze.manifest import manifest_hash

    before = manifest_hash()
    re_rulings = (
        ("WORD_BY_PUZZLE_TYPE", dict(ev.WORD_BY_PUZZLE_TYPE,
                                     spring=("spring", "breached"))),
        ("WORD_BY_PUZZLE_TYPE", dict(ev.WORD_BY_PUZZLE_TYPE,
                                     test=("touch_and_pivot", "held"),
                                     rejection=("support_test", "held"))),
        ("WORD_BY_EPISODE_RAIL", {"S": "resistance_test",
                                  "R": "support_test"}),
        ("VERDICT_BY_EPISODE_OUTCOME", dict(ev.VERDICT_BY_EPISODE_OUTCOME,
                                            failed="held")),
    )
    for name, re_ruled in re_rulings:
        monkeypatch.setattr(ev, name, re_ruled)
        # Anti-vacuity: each re-ruling stays strictly INSIDE the signed sets,
        # so the derived sets are byte-identical and the MAPPING is the only
        # thing that can be carrying the rotation.
        assert ev._declared_words() == ev.WORDS, name
        assert ev._declared_verdicts() == ev.VERDICTS, name
        assert manifest_hash() != before, name
        monkeypatch.undo()
    assert manifest_hash() == before


def test_a_pure_reordering_of_a_declared_table_rotates_nothing(monkeypatch):
    # The other half of the guarantee, chosen deliberately: these tables are
    # LOOKUPS nothing reads positionally, so row order carries no meaning and
    # a cosmetic reshuffle must NOT mint an epoch (an epoch partitions meaning,
    # and a spurious one splits a cohort that could have been pooled). Same
    # split as the taxonomy block: TA_GRADE_CHAPTER_ORDER is hashed as a list
    # because chapter order IS ruled meaning; these are hashed as mappings.
    import engine_alpha.structure.event_vocabulary as ev
    from engine_alpha.freeze.manifest import manifest_hash

    before = manifest_hash()
    monkeypatch.setattr(ev, "WORD_BY_PUZZLE_TYPE",
                        dict(reversed(list(ev.WORD_BY_PUZZLE_TYPE.items()))))
    monkeypatch.setattr(ev, "VERDICT_BY_EPISODE_OUTCOME",
                        dict(reversed(
                            list(ev.VERDICT_BY_EPISODE_OUTCOME.items()))))
    # Anti-vacuity: the reshuffle really happened (a no-op patch would pass).
    assert list(ev.WORD_BY_PUZZLE_TYPE) != list(WORD_BY_PUZZLE_TYPE)
    assert manifest_hash() == before


# ── the projection's OWN completeness (round-three critic, 2026-09-01) ───────

def test_a_re_declared_channel_basis_rotates_the_engine_config_version(
        monkeypatch):
    # The round-three teeth, the critic's experiment verbatim: the hashed
    # projection hand-enumerated four tables plus one constant and nothing
    # derived that list, so ``BASIS_CONSTANTS`` sat OUTSIDE the frozen identity
    # — and it is identity twice over. It rides verbatim in every archived
    # token's ``basis`` cell, and ``span_origin`` is the field the mint's
    # offset guard keys on: flip the puzzle channel's from "box" to "window"
    # and every box-relative span is suddenly read as already window-relative,
    # i.e. every archived puzzle date means something else. That must rotate
    # the epoch, exactly like a re-wording.
    import engine_alpha.structure.event_vocabulary as ev
    from engine_alpha.freeze.manifest import manifest_hash

    before = manifest_hash()
    re_declarations = (
        ("puzzle", "span_origin", "window"),      # the critic's own move
        ("episode", "breach_basis", "extremes_vs_local_swing"),
        ("inner_box", "skeleton", "collapsed_swing_walk"),
    )
    for channel, field, value in re_declarations:
        monkeypatch.setattr(ev, "BASIS_CONSTANTS", {
            **ev.BASIS_CONSTANTS,
            channel: {**ev.BASIS_CONSTANTS[channel], field: value}})
        # Anti-vacuity, both directions: the re-declaration really landed, and
        # the signed word/verdict declarations are untouched — so the basis
        # block is the only thing that can be carrying the rotation.
        assert ev.BASIS_CONSTANTS[channel][field] == value
        assert ev.WORD_BY_PUZZLE_TYPE == WORD_BY_PUZZLE_TYPE
        assert ev._declared_words() == ev.WORDS
        assert manifest_hash() != before, (channel, field)
        monkeypatch.undo()
    assert manifest_hash() == before


def test_a_new_declared_table_cannot_sit_outside_the_hashed_identity(
        monkeypatch):
    # Closing the CLASS, not the instance: the next declaration added to this
    # module must not be able to repeat BASIS_CONSTANTS' silent omission. The
    # projection registry is pinned against the module's ACTUAL declarations,
    # so a new table that is neither projected nor excluded-on-the-record
    # refuses loudly — at the manifest, which is where the epoch is decided.
    import engine_alpha.structure.event_vocabulary as ev
    from engine_alpha.freeze.manifest import manifest_hash

    before = manifest_hash()
    monkeypatch.setattr(ev, "WORD_BY_SOME_LATER_READER",
                        {"drift": "spring"}, raising=False)
    assert "WORD_BY_SOME_LATER_READER" in ev._declared_constant_names()
    with pytest.raises(ValueError, match="outside the hashed vocabulary"):
        ev.vocabulary_manifest()
    with pytest.raises(ValueError, match="outside the hashed vocabulary"):
        manifest_hash()          # the freeze refuses WITH it — one identity
    monkeypatch.undo()
    assert manifest_hash() == before

    # The mirror leg, the freeze manifest's own posture for a vanished settings
    # key: a registry row naming a declaration that no longer exists refuses
    # too, so a rename cannot quietly drop a table out of the identity.
    monkeypatch.delattr(ev, "WORD_MINI_CONSOLIDATION")
    with pytest.raises(ValueError, match="no longer exist"):
        ev.vocabulary_manifest()
    monkeypatch.undo()

    # ... and the one declaration excluded ON THE RECORD stays excluded: the
    # archive column table says WHERE a measured cell lands, never what a
    # sentence says, so re-typing a column must NOT mint a spurious epoch
    # (a spurious epoch permanently splits a cohort that could be pooled).
    assert "SENTENCE_COLUMN_SQL" in ev._MANIFEST_NON_IDENTITY
    monkeypatch.setattr(ev, "SENTENCE_COLUMN_SQL",
                        dict(ev.SENTENCE_COLUMN_SQL, sentence_tokens="BLOB"))
    assert manifest_hash() == before


def test_a_declared_set_is_a_declaration_not_an_escape_hatch(monkeypatch):
    """The guard's own RECOGNISED-SHAPE hole (round-four critic, 2026-09-01),
    verbatim his injections: "injecting an upper-case SET, an upper-case
    frozenset, or a lower-case dict onto the live module leaves manifest_hash()
    at 46c2b413... with no refusal — the derivation recognises a declaration
    only by isinstance(value, (dict, tuple, list, str, int, float))".

    A closed set of signed words is the most natural shape the NEXT declaration
    here takes (``WORDS``/``VERDICTS`` are tuples only because they are sorted
    for a stable projection), so the hole sat directly in front of the next
    thing anyone would write — and this guard is the only thing standing
    between a re-meaning'd vocabulary and rows minted under a stale epoch,
    because the family forbids backfill EVER.
    """
    import engine_alpha.structure.event_vocabulary as ev
    from engine_alpha.freeze.manifest import manifest_hash

    before = manifest_hash()
    for shape in ({"drift_word"}, frozenset({"drift_word"})):
        monkeypatch.setattr(ev, "WORDS_BY_SOME_LATER_READER", shape,
                            raising=False)
        assert "WORDS_BY_SOME_LATER_READER" in ev._declared_constant_names(), (
            f"a {type(shape).__name__} declaration is invisible to the "
            "completeness guard - it can sit outside the hashed identity "
            "silently, which is the whole class this guard exists to close")
        with pytest.raises(ValueError, match="outside the hashed vocabulary"):
            ev.vocabulary_manifest()
        with pytest.raises(ValueError, match="outside the hashed vocabulary"):
            manifest_hash()      # the freeze refuses WITH it — one identity
        monkeypatch.undo()
    assert manifest_hash() == before

    # The critic's third injection, stated honestly rather than closed: a
    # LOWER-case name is not a declaration in this module — helpers, the logger
    # and the readers' functions are lower-case, and the derivation excludes
    # them by name on purpose (a case-blind rule would sweep in __doc__,
    # __name__ and __builtins__). So it neither refuses nor rotates, and the
    # convention is the contract.
    monkeypatch.setattr(ev, "words_by_some_later_reader", {"drift": "spring"},
                        raising=False)
    assert "words_by_some_later_reader" not in ev._declared_constant_names()
    assert manifest_hash() == before
