"""Surface-the-Read guard battery (plan Task 12) — Beck.

The narrative surface's one product is trust, so every fact the operator will
grade concordance against is proven here at the REAL cascade:

1. **Archive ↔ payload parity, per field, through one real evaluation** — the
   archived cell and the served field come from the same extraction by
   construction (one producer); this asserts the two OUTPUTS stay
   value-identical (the tape surviving its parse round-trip included), so any
   future re-wiring of assembly must keep the fact, not the plumbing.
2. **Flag-off honesty** — with EVENT_MAP off the result carries no narrative
   keys and the projection serves the whole family as None ("not measured",
   never an echoed default, EC-26); with the trace flag at its dark default
   no `_election_trace` key exists.
3. **Trace export happy path through the real cascade (EC-17)** — only the
   dark flag forced on, a pinned Guided-List hit fires with a parseable,
   date-anchored trace whose elected block matches the fire, and the rest of
   the result is byte-identical to the flag-off leg (per identity, never an
   aggregate).
4. **The serve boundary's legs stay distinguishable (EC-27)** — a malformed
   JSON cell degrades that one field to None per row while measured scalars
   survive, so "tape unreadable", "not measured", and "nothing happened" can
   never collapse into one silence.

Fully OFFLINE: committed marks-corpus fixtures only.
"""
from __future__ import annotations

import json
import sys

import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import pandas as pd  # noqa: E402

from config import settings  # noqa: E402
from core.pipeline.screening.screener import _evaluate_ticker  # noqa: E402
from engine_alpha.structure.events.event_map import (  # noqa: E402
    EVENT_MAP_COLUMN_SQL,
    event_map_archive_values,
    narrative_chart_fields,
)
from engine_alpha.structure.box.trace_export import (  # noqa: E402
    election_trace_archive_values,
    election_trace_chart_fields,
)
from tools.marks_corpus import _FROZEN_BREADTH  # noqa: E402
from tools.marks_corpus import _load_fixture as _load_marks_fixture  # noqa: E402
from tools.replay import fixture_frame  # noqa: E402

pytestmark = pytest.mark.regression


# Three pinned identities: the two story-caused fires (the only rows whose
# admission profile travels) + one ordinary-election hit resolved at runtime.
_STORY_HITS = {"NKTR:2026-04-10", "YPF:2026-05-18"}


def _pinned_results(n_ordinary=1):
    frames, baseline = _load_marks_fixture()
    hits = [e for e in baseline["setups"] if e["status"] == "hit"]
    chosen = [e for e in hits if e["key"] in _STORY_HITS]
    chosen += [e for e in hits if e["key"] not in _STORY_HITS][:n_ordinary]
    out = []
    for e in chosen:
        sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
            :pd.Timestamp(e["first_fire"])]
        result = _evaluate_ticker(e["ticker"], sliced, float(e["spy_6m_return"]),
                                  _FROZEN_BREADTH)
        assert isinstance(result, dict), f"{e['key']}: pinned hit did not fire"
        out.append((e, result))
    return out


def test_archive_and_payload_tell_one_story_per_fire():
    for e, result in _pinned_results():
        archived = event_map_archive_values(result.get, prefixed=True)
        served = narrative_chart_fields(result.get)
        assert set(served) == set(EVENT_MAP_COLUMN_SQL)
        for col in EVENT_MAP_COLUMN_SQL:
            if col == "event_map_episodes":
                cell = archived[col]
                expected = json.loads(cell) if cell is not None else None
                assert served[col] == expected, (
                    f"{e['key']}: the tape did not survive its round trip")
            else:
                assert served[col] == archived[col], (
                    f"{e['key']}: {col} diverges between archive and payload")
        # The story-caused fires carry their admitting evidence; the payload
        # reads the same underscore keys the writer archives.
        if e["key"] in _STORY_HITS:
            assert result["_elected_pool"] == "story"
            assert result["_story_admission_profile"], (
                f"{e['key']}: a story fire must carry its admission sentence")


def test_event_map_flag_off_serves_not_measured_never_defaults(monkeypatch):
    frames, baseline = _load_marks_fixture()
    hit = next(e for e in baseline["setups"]
               if e["status"] == "hit" and e["key"] not in _STORY_HITS)
    sliced = fixture_frame(frames, hit["key"], hit["ticker"]).loc[
        :pd.Timestamp(hit["first_fire"])]
    monkeypatch.setattr(settings, "EVENT_MAP_ENABLED", False)
    result = _evaluate_ticker(hit["ticker"], sliced,
                              float(hit["spy_6m_return"]), _FROZEN_BREADTH)
    assert isinstance(result, dict), "the hit must fire regardless of the flag"
    assert not any(k.startswith("_event_map_") for k in result), (
        "flag-off result leaked narrative keys")
    served = narrative_chart_fields(result.get)
    assert all(v is None for v in served.values()), (
        "flag-off must serve the whole family as None (not measured), "
        "never an echoed default")


def test_trace_export_dark_default_leaves_no_key_and_flag_on_is_additive(monkeypatch):
    assert settings.ELECTION_TRACE_EXPORT_ENABLED is False
    frames, baseline = _load_marks_fixture()
    hit = next(e for e in baseline["setups"]
               if e["status"] == "hit" and e["key"] not in _STORY_HITS)
    sliced = fixture_frame(frames, hit["key"], hit["ticker"]).loc[
        :pd.Timestamp(hit["first_fire"])]
    spy = float(hit["spy_6m_return"])

    off = _evaluate_ticker(hit["ticker"], sliced, spy, _FROZEN_BREADTH)
    assert isinstance(off, dict) and "_election_trace" not in off

    monkeypatch.setattr(settings, "ELECTION_TRACE_EXPORT_ENABLED", True)
    on = _evaluate_ticker(hit["ticker"], sliced, spy, _FROZEN_BREADTH)
    assert isinstance(on, dict) and "_election_trace" in on

    # Flag-off parity per identity: the export is ADDITIVE — every other key
    # is byte-identical.
    on_minus = {k: v for k, v in on.items() if k != "_election_trace"}
    assert on_minus == off, (
        f"{hit['key']}: the trace export changed the evaluation it narrates")

    # The captured story is real: parseable, date-anchored, elected block
    # coherent with the fire (EC-17: the acceptance path through the real
    # cascade, production values, only this flag forced on).
    exported = json.loads(on["_election_trace"])
    assert exported["roots"], "an elected fire must narrate at least one root"
    assert exported["roots"][-1]["outcome"] == "complete"
    elected = exported["elected"]
    assert elected is not None and elected["start"] is not None
    assert elected["R"] is not None and elected["S"] is not None
    assert "_bar" not in on["_election_trace"], "bar indexes must never ride the wire"

    # The projections agree with each other on both legs (one producer).
    assert election_trace_archive_values(on.get, prefixed=True)["election_trace"] \
        == on["_election_trace"]
    assert election_trace_chart_fields(on.get)["election_trace"] == exported
    assert election_trace_chart_fields(off.get)["election_trace"] is None


def test_strategy_read_happy_path_through_the_real_cascade(monkeypatch):
    """EC-17 for the strategy-read flag (plan Task 13): a pinned Guided-List
    hit through the REAL evaluation entry point, production values, ONLY this
    flag forced on — the two raw measures land, the flag-off leg is
    byte-identical per identity, and the values are coherent with the fire's
    own geometry (floor below climax; the 0/1 an int, never a bool-shaped
    surprise)."""
    assert settings.STRATEGY_READ_ENABLED is False  # ships dark (EC-8)
    frames, baseline = _load_marks_fixture()
    hit = next(e for e in baseline["setups"]
               if e["status"] == "hit" and e["key"] not in _STORY_HITS)
    sliced = fixture_frame(frames, hit["key"], hit["ticker"]).loc[
        :pd.Timestamp(hit["first_fire"])]
    spy = float(hit["spy_6m_return"])

    off = _evaluate_ticker(hit["ticker"], sliced, spy, _FROZEN_BREADTH)
    assert isinstance(off, dict)
    assert not any(k.startswith("_strategy_") for k in off), (
        "flag-off result leaked strategy keys")

    monkeypatch.setattr(settings, "STRATEGY_READ_ENABLED", True)
    on = _evaluate_ticker(hit["ticker"], sliced, spy, _FROZEN_BREADTH)
    assert isinstance(on, dict)
    depth = on["_strategy_correction_depth_pct"]
    held = on["_strategy_floor_above_ar"]
    # SIGNED by design: negative = the floor holds above the climax bar's
    # high (a selling-climax recovery shape — ALB); positive = the classic
    # cut below an uptrend's climax. Bounded above by 1 (S > 0) and finite.
    assert isinstance(depth, float) and -10.0 < depth < 1.0, (
        f"{hit['key']}: implausible correction depth {depth!r}")
    assert held in (0, 1) and type(held) is int

    on_minus = {k: v for k, v in on.items() if not k.startswith("_strategy_")}
    assert on_minus == off, (
        f"{hit['key']}: the strategy read changed the evaluation it measures")

    from engine_alpha.structure.context.strategy_read import strategy_archive_values
    archived = strategy_archive_values(on.get, prefixed=True)
    assert archived == {"strategy_correction_depth_pct": depth,
                        "strategy_floor_above_ar": held}
    dark = strategy_archive_values(off.get, prefixed=True)
    assert all(v is None for v in dark.values())


def test_serve_boundary_legs_stay_distinguishable():
    from domains.archive.schemas import SetupOut

    base = dict(id=1, ticker="T", scan_date="2026-08-04", setup_type="LPS",
                tier="A", score=100.0)
    # Tape unreadable: ONLY the JSON field degrades; measured scalars survive.
    broken = SetupOut.model_validate({**base, "event_map_completed_s": 2,
                                      "event_map_episodes": "{not json"})
    assert broken.event_map_episodes is None
    assert broken.event_map_completed_s == 2
    # Measured: the cell parses to structure on the wire.
    tape = json.dumps([{"rail": "S", "outcome": "completed", "posture": False,
                        "span": ["2026-05-01", "2026-05-02"],
                        "knowable": "2026-05-05"}])
    ok = SetupOut.model_validate({**base, "event_map_completed_s": 1,
                                  "event_map_episodes": tape,
                                  "election_trace": json.dumps({"roots": [], "elected": None})})
    assert ok.event_map_episodes[0]["rail"] == "S"
    assert ok.election_trace == {"roots": [], "elected": None}
    # Not measured: absent stays None — never a fabricated empty tape.
    absent = SetupOut.model_validate(base)
    assert absent.event_map_episodes is None
    assert absent.event_map_completed_s is None


def test_serve_boundary_degrades_wrong_container_shapes_per_row():
    """Council review 2026-08-05, finding 8: a cell holding syntactically VALID
    JSON of the wrong container must degrade that row's field to None like the
    not-JSON leg — never escape the validator to 500 the whole list at
    response-model time. One anomalous archive row must never blank the
    archive browse."""
    from domains.archive.schemas import SetupOut

    base = dict(id=1, ticker="T", scan_date="2026-08-04", setup_type="LPS",
                tier="A", score=100.0)
    # episodes cell must be a LIST — a dict, scalar, or string payload degrades.
    for wrong in (json.dumps({"rail": "S"}), json.dumps(7), json.dumps("tape")):
        row = SetupOut.model_validate({**base, "event_map_completed_s": 2,
                                       "event_map_episodes": wrong})
        assert row.event_map_episodes is None
        assert row.event_map_completed_s == 2   # scalars still survive
    # trace cell must be a DICT — a list or scalar degrades.
    for wrong in (json.dumps([1, 2]), json.dumps(0)):
        row = SetupOut.model_validate({**base, "election_trace": wrong})
        assert row.election_trace is None
