"""The sentence-token archive family (consolidation-method Tasks 8/9,
``SENTENCE_ARCHIVE_ENABLED``, dark) — the EC-17 acceptance through the REAL
cascade, with the EC-32 input-tied assertion and its mutation probe.

Flag-off: the result row carries NO sentence keys (the family archives NULL —
byte-identity on canonical surfaces rides the standing shadow guards).
Flag-on: a real fixture fire measures the folded tape end-to-end — tokens are
signed closed-set members, spans are dates on the elected window's own index,
and the episode-channel records agree with the event-map episode tape the
SAME evaluation archived (the input-tied identity: two serializations of one
read). The mutation probe proves that identity has teeth.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from core.pipeline.screener import _evaluate_ticker
from engine_alpha.structure.event_vocabulary import assert_token
from tools.marks_corpus import _FROZEN_BREADTH
from tools.marks_corpus import _load_fixture as _load_marks_fixture
from tools.replay import fixture_frame

pytestmark = pytest.mark.regression


def _vlo_fire_frame():
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"]
             if x["status"] == "hit" and x["key"].startswith("VLO"))
    sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
        :pd.Timestamp(e["first_fire"])]
    return e["ticker"], sliced, float(e["spy_6m_return"])


def test_flag_defaults_dark():
    assert settings.SENTENCE_ARCHIVE_ENABLED is False


def test_flag_off_result_carries_no_sentence_keys():
    ticker, sliced, spy = _vlo_fire_frame()
    off = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)
    assert isinstance(off, dict)
    assert not [k for k in off if k.startswith("_sentence_")], (
        "flag-off must spread {} — the family's archive state is NULL, "
        "never empty strings or zeros")


def test_flag_on_measures_the_sentence_end_to_end(monkeypatch):
    monkeypatch.setattr(settings, "SENTENCE_ARCHIVE_ENABLED", True)
    ticker, sliced, spy = _vlo_fire_frame()
    on = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)
    assert isinstance(on, dict)
    records = json.loads(on["_sentence_tokens"])
    assert on["_sentence_n_tokens"] == len(records) >= 1
    assert isinstance(on["_sentence_nan_bars"], int)
    frame_dates = {str(d.date()) for d in sliced.index}
    for rec in records:
        assert_token(rec["word"], rec["verdict"])  # signed members, at read
        # NOT "if span is not None" (round-three completeness critic,
        # 2026-09-01): a tolerant guard SKIPS the very record a missing rebase
        # produces, so the assertion below could never see one. The
        # per-channel roster test underneath is the general form.
        assert rec["span"] is not None, (
            f"the {rec['source']} channel's {rec['word']} serialized a null "
            "span - it never reached the window ruler")
        assert all(d in frame_dates for d in rec["span"]), (
            f"token span {rec['span']} names a date outside the frame")
    # EC-32 input-tied identity: the sentence's episode-channel records are
    # the SAME read the event-map family archived in this evaluation — the
    # two serializations must agree span for span.
    em_tape = json.loads(on["_event_map_episodes"])
    epi_records = [r for r in records if r["source"] == "episode"]
    assert [r["span"] for r in epi_records] == [e["span"] for e in em_tape], (
        "the sentence's episode records diverged from the event-map tape — "
        "two reads of one substrate must serialize identically")
    assert len(epi_records) >= 1


def test_a_measurement_failure_nulls_the_family_and_keeps_the_row(monkeypatch):
    """Council review 2026-09-01, finding 5: the family REFUSES by raising
    (the write-time closed-set assert, the fold's vocabulary-miss refusal) and
    those are exactly the types the one guarded eval chain's skip-guard
    catches — so one lagging word-table row would turn every setup carrying
    that event into a counted crash and delete the fire from the night AND the
    archive. An additive family may never subtract the row: the fire survives,
    the family degrades to its declared NULL state, and the drop is COUNTED so
    an error stays distinguishable from an honest refusal."""
    import engine_alpha.structure.event_vocabulary as ev
    from engine_alpha import evaluation

    monkeypatch.setattr(settings, "SENTENCE_ARCHIVE_ENABLED", True)

    def refusing_serialize(unified, window_dates):
        # Verbatim the real mint's refusal on an unsigned word (ValueError —
        # in the skip-guard's own catch set).
        raise ValueError("event_vocabulary: word 'ceiling_rest' is not a "
                         "member of the signed closed set")

    monkeypatch.setattr(ev, "serialize_sentence", refusing_serialize)
    before = evaluation.SENTENCE_DROPS["count"]
    ticker, sliced, spy = _vlo_fire_frame()
    row = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)

    assert isinstance(row, dict), (
        "the fire vanished — a sentence-family raise subtracted the row")
    assert not [k for k in row if k.startswith("_sentence_")], (
        "the family must NULL together, never half-measured")
    assert evaluation.SENTENCE_DROPS["count"] == before + 1, (
        "the drop must be counted — a silent NULL is indistinguishable from "
        "an honest refusal")


def test_the_label_knowable_rides_the_elected_window_ruler(monkeypatch):
    """Council review 2026-09-01, finding 10b: the label layer's knowable
    stamps arrive df-absolute and are rebased onto the elected window (bar 0 =
    the box start) before they are dated. The elected box here opens 426
    trading days into the frame, so a missing or wrong rebase lands off the
    ruler and serializes as an honest null — which every other assertion in
    this file survives. This pins the DATE."""
    monkeypatch.setattr(settings, "SENTENCE_ARCHIVE_ENABLED", True)
    ticker, sliced, spy = _vlo_fire_frame()
    row = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)

    assert row["_phase_b_start_date"] != str(sliced.index[0].date()), (
        "a zero-offset elected box would make this pin vacuous")
    records = json.loads(row["_sentence_tokens"])
    # Identified by its SPAN (already on the window ruler, so the rebase
    # cannot move it) — the knowable stamp is the value under test, and this
    # upthrust only becomes knowable after its span closes.
    rec = next(r for r in records
               if r["source"] == "puzzle" and r["word"] == "upthrust"
               and r["span"] == ["2026-05-07", "2026-05-21"])
    assert rec["knowable"] == "2026-05-27"


def _ms_inner_fire_frame():
    """The corpus's marked fire whose elected read carries an inner box — the
    mini-consolidation channel's live specimen (the VLO fire elects none)."""
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "MS:2026-06-04")
    sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
        :pd.Timestamp(e["first_fire"])]
    return e["ticker"], sliced, float(e["spy_6m_return"])


def test_the_mini_consolidation_rides_the_elected_window_ruler(monkeypatch):
    """Finding 10b's twin, round two: the inner-box channel's detection bars
    arrive df-positional (start_bar = n - effective base length) and take the
    SAME rebase the label channel's knowable stamps take. Unrebased, the
    shelf's span runs off the right end of the ruler and serializes as an
    honest null — the operator's mini consolidation silently absent from every
    sentence while every other assertion in this file stays green. This pins
    the DATES, and the chronological place the rebase restores."""
    monkeypatch.setattr(settings, "SENTENCE_ARCHIVE_ENABLED", True)
    ticker, sliced, spy = _ms_inner_fire_frame()
    row = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)

    assert row["_phase_b_start_date"] != str(sliced.index[0].date()), (
        "a zero-offset elected box would make this pin vacuous")
    records = json.loads(row["_sentence_tokens"])
    inner = [r for r in records if r["source"] == "inner_box"]
    assert len(inner) == 1, "the specimen must carry exactly one shelf record"
    assert inner[0]["word"] == "mini_consolidation"
    assert inner[0]["span"] == ["2026-04-16", "2026-05-18"]
    # The tape is ORDERED on raw spans, so an unrebased shelf also sorts past
    # every other word: landing on the ruler puts it back in the sentence.
    pos = next(i for i, r in enumerate(records) if r["source"] == "inner_box")
    assert pos < len(records) - 1, (
        "the shelf sorted to the tail — its span is still off the ruler")


@pytest.mark.parametrize("frame_of, channels, stamped", [
    (_vlo_fire_frame, {"puzzle", "episode"}, {"puzzle", "episode"}),
    (_ms_inner_fire_frame, {"puzzle", "episode", "inner_box"},
     {"puzzle", "episode"}),
], ids=["vlo_no_inner_box", "ms_with_inner_box"])
def test_every_declared_channel_lands_on_the_window_ruler(
        monkeypatch, frame_of, channels, stamped):
    """Round-three completeness critic, 2026-09-01 — the CLASS behind the
    half-applied rebase, not another instance of it.

    The mint nulls an off-ruler span deliberately (an honest absence beats a
    guessed date), and until now it did so silently while every span assertion
    in this file was written ``if rec["span"] is not None`` — so a channel
    whose bars never got rebased was SKIPPED, not caught, and finding 10b hid
    in that gap through a whole council review. Both halves are closed: the
    serializer now names the channel on the log, and this test asserts the
    positive property instead of tolerating the negative one — the specimen's
    channel roster is DECLARED, every declared channel must be present, and
    every record it emits must have reached the window ruler.

    Two specimens because the roster differs and only ONE of them can express
    an inner-box regression: the VLO fire elects no inner box, so a test that
    saw only VLO would stay green through exactly the defect that was shipped.

    Round four (2026-09-01) extends the same generalisation to the CAUSALITY
    STAMP, the sibling that was still nulling in silence: only one hard-coded
    instance pin (one specimen, one upthrust) inspected ``knowable`` at all, so
    a whole channel losing its stamps was skipped rather than caught — the
    exact gap finding 10b hid in on the span side. ``stamped`` declares which
    channels must carry stamps at all on this specimen (the MS shelf sits at
    the right edge, honestly in progress with no knowable day yet).
    """
    monkeypatch.setattr(settings, "SENTENCE_ARCHIVE_ENABLED", True)
    ticker, sliced, spy = frame_of()
    row = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)
    records = json.loads(row["_sentence_tokens"])
    frame_dates = {str(d.date()) for d in sliced.index}

    assert {r["source"] for r in records} == channels, (
        "the specimen's channel roster changed — a channel that stops "
        "emitting is a reading move, not a refactor")
    off_ruler = sorted({r["source"] for r in records if r["span"] is None})
    assert not off_ruler, (
        f"channel(s) {off_ruler} serialized null spans: their bars never "
        "reached the elected window's ruler, so the operator's events are "
        "silently missing from the sentence while every count still looks "
        "measured. The mint's own log names each one")
    for rec in records:
        assert all(d in frame_dates for d in rec["span"]), (
            f"the {rec['source']} channel's {rec['word']} span {rec['span']} "
            "names a date outside the judged window")

    # The stamp leg, the same shape: a record that DECLARES itself settled
    # (in_progress False) has a knowable day by construction, so a null one
    # means the stamp never reached the ruler — and downstream that null is
    # indistinguishable from the honest "not knowable yet" of a record still
    # in progress, which is what made it invisible.
    assert {r["source"] for r in records
            if r["knowable"] is not None} == stamped, (
        "a channel stopped carrying causality stamps entirely — either its "
        "bars were never rebased onto the elected window, or the stamps "
        "stopped being read. The mint's own log names each dropped one")
    lost = sorted({(r["source"], r["word"]) for r in records
                   if r["in_progress"] is False and r["knowable"] is None})
    assert not lost, (
        f"{lost} settled on a day the sentence cannot name: a record that is "
        "not in progress has a knowable bar, so a null stamp here is a lost "
        "one, not an honest unknown")
    for rec in records:
        assert rec["knowable"] is None or rec["knowable"] in frame_dates, (
            f"the {rec['source']} channel's {rec['word']} knowable "
            f"{rec['knowable']} names a date outside the judged window")


def test_mutation_probe_the_input_tie_has_teeth(monkeypatch):
    """EC-32: prove the episode-agreement assertion is not input-blind —
    poison the sentence block's episode reader and the identity must break
    (a poisoned fold that still 'agreed' would mean the assertion tests
    nothing)."""
    import engine_alpha.structure.event_vocabulary as ev

    monkeypatch.setattr(settings, "SENTENCE_ARCHIVE_ENABLED", True)
    ticker, sliced, spy = _vlo_fire_frame()
    baseline_row = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)
    em_tape = json.loads(baseline_row["_event_map_episodes"])
    assert em_tape, "fixture fire must carry episodes for the probe to bite"

    real_unify = ev.unify_events
    calls = {"n": 0}

    def poisoned_unify(**kw):
        # Starve ONLY the fold's episode channel (the event-map family's own
        # tape stays measured) — the two serializations must now disagree.
        calls["n"] += 1
        kw["episode_read"] = {"episodes": [], "n_episodes": 0,
                              "nan_bars": 0, "n_bars": 1}
        return real_unify(**kw)

    monkeypatch.setattr(ev, "unify_events", poisoned_unify)
    poisoned_row = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)
    records = json.loads(poisoned_row["_sentence_tokens"])
    epi_records = [r for r in records if r["source"] == "episode"]
    assert calls["n"] >= 1
    assert [r["span"] for r in epi_records] != [e["span"] for e in em_tape], (
        "the poisoned fold produced an 'agreeing' sentence — the "
        "input-tied assertion is blind and the cascade has no teeth")
