"""Agreement-harness bite proofs (Task 9) — a scorer nobody has seen fail
proves nothing. Forced-never-match must report zero agreement, forced-always
must report full; a malformed row aborts the batch NAMING the offender; and a
full grading pass leaves the marks byte-identical (the path of least
resistance to better numbers must never be 'correct' the ground truth)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402
from models import CalibrationMark, CalibrationMarkEvent  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import webapp.backend.frame_store as frame_store  # noqa: E402
from engine_alpha.evaluation import EVAL_ERROR  # noqa: E402
from tools import agreement, replay  # noqa: E402
from tools.calibration_harness import (  # noqa: E402
    FIRED_EVENT_TAIL_SESSIONS,
    FIRED_WALK_MAX_SESSIONS,
    FIRED_WINDOW_SESSIONS,
    HARNESS_POLICY_VERSION,
    _print_delta,
    _refuse_sealed_output,
    fired_one,
    grade_one,
    load_marks,
    marks_fingerprint,
    parse_variant,
)


def _loader(frame):
    """A fake frame_store.load_frame honoring its digest-resolved signature."""
    return lambda ticker, as_of, digest=None: frame


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    sess = sessionmaker(bind=engine)()
    yield sess
    sess.close()
    engine.dispose()


def _frozen_frame():
    idx = pd.date_range("2026-01-05", "2026-04-15", freq="B")
    closes = [11.0] * len(idx)
    return pd.DataFrame({"Open": closes, "High": [c + 1 for c in closes],
                         "Low": [c - 1 for c in closes], "Close": closes,
                         "Volume": [1e6] * len(idx)}, index=idx)


_FROZEN = _frozen_frame()
_DIGEST = frame_store.ohlcv_digest(_FROZEN)


def _add_mark(session, **overrides):
    now = datetime(2026, 4, 15, tzinfo=timezone.utc)
    fields = dict(ticker="BODI", as_of_date="2026-04-15", label="",
                  verdict="box", resistance=12.0, support=10.0,
                  box_start_date="2026-01-05", box_end_date="2026-04-15",
                  data_regime="as_traded", engine_config_version="test",
                  anchor_close=11.0, frame_digest=_DIGEST,
                  created_at=now, updated_at=now)
    fields.update(overrides)
    session.add(CalibrationMark(**fields))
    session.commit()


def _election_returning(structure, seen_snaps=None):
    """A fake snapped election: every variant sees ``structure`` on the
    as-of session, never snapped. ``seen_snaps`` records the snap_back the
    harness asked for (the per-verdict policy pin)."""
    def _run(frozen, as_of, variants, snap_back=5):
        if seen_snaps is not None:
            seen_snaps.append(snap_back)
        df = frozen.loc[:pd.Timestamp(as_of)]
        return (df, 1.0, [structure for _ in variants]), df.index[-1], 0
    return _run


class _Read:
    """Engine-read stand-in shaped like a Structure (R/S/box.start_bar)."""
    def __init__(self, R, S, start_bar):
        self.R, self.S = R, S
        self.box = type("B", (), {"start_bar": start_bar})()


def test_bite_forced_never_match(session):
    _add_mark(session)
    _add_mark(session, as_of_date="2026-04-14", verdict="no_structure",
              resistance=None, support=None,
              box_start_date=None, box_end_date=None)
    marks = load_marks(session)
    rows = [grade_one(m, [{}], frame_loader=_loader(_FROZEN),
                      election=_election_returning(None))[0] for m in marks]
    t = agreement.tally(rows)
    assert t["counts"]["match"] == 0
    assert t["counts"]["engine_no_read"] == 1      # the box mark: no read
    assert t["counts"]["negative_upheld"] == 1     # the negative: upheld


def test_bite_forced_always_match(session):
    _add_mark(session)
    marks = load_marks(session)
    exact = _Read(R=12.0, S=10.0, start_bar=0)  # bar 0 = 2026-01-05 = drawn start
    rows = [grade_one(m, [{}], frame_loader=_loader(_FROZEN),
                      election=_election_returning(exact))[0] for m in marks]
    assert agreement.tally(rows)["match_over_scored"] == 1.0


def test_negatives_grade_at_the_asserted_session_only(session):
    # The snap-back walk is a BOX policy; hunting prior sessions to convict a
    # negative would bias upheld_over_negatives (Council finding 6).
    _add_mark(session, as_of_date="2026-04-14", verdict="no_structure",
              resistance=None, support=None,
              box_start_date=None, box_end_date=None)
    _add_mark(session)  # the box mark, as-of 04-15
    seen = []
    for m in load_marks(session):  # ordered by as_of: negative first
        grade_one(m, [{}], frame_loader=_loader(_FROZEN),
                  election=_election_returning(None, seen_snaps=seen))
    assert seen == [0, replay.SNAP_BACK_SESSIONS]


def test_unresolved_digest_grades_basis_mismatch(session, tmp_path, monkeypatch):
    # Through the REAL digest-resolved loader: a mark whose digest matches no
    # frozen rendering is named, never replayed on other bars.
    import frame_store as bare_frame_store
    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    monkeypatch.setattr(bare_frame_store, "FRAMES_DIR", str(tmp_path))
    frame_store.freeze_frame("BODI", "2026-04-15", _FROZEN)
    _add_mark(session, frame_digest="0" * 64)
    row = grade_one(load_marks(session)[0], [{}],
                    election=_election_returning(None))[0]
    assert row["outcome"] == "basis_mismatch"
    assert "no frozen frame matches" in row["detail"]
    # And the matching digest resolves fine through the same real loader.
    session.query(CalibrationMark).first().frame_digest = _DIGEST
    session.commit()
    row = grade_one(load_marks(session)[0], [{}],
                    election=_election_returning(None))[0]
    assert row["outcome"] == "engine_no_read"


def test_malformed_row_aborts_naming_the_offender(session):
    # Valid to the DDL but invalid to the shared judgment: span past as-of.
    _add_mark(session, box_end_date="2026-05-01", label="stale")
    with pytest.raises(ValueError) as err:
        load_marks(session)
    assert "BODI" in str(err.value) and "'stale'" in str(err.value)
    assert "after as_of_date" in str(err.value)


def test_full_grading_pass_is_read_only(session):
    # The pin covers EVERY mark column and the events rows (the fingerprint
    # canonicalizes the whole mark dict, order-free): the path of least
    # resistance to better numbers must never be to "correct" ground truth.
    _add_mark(session)
    _add_mark(session, as_of_date="2026-04-14", verdict="no_structure",
              resistance=None, support=None,
              box_start_date=None, box_end_date=None)
    before = marks_fingerprint(load_marks(session))
    for m in load_marks(session):
        grade_one(m, [{}, {"BAND_RAILS_ENABLED": True}],
                  frame_loader=_loader(_FROZEN),
                  election=_election_returning(None))
        fired_one(m, [{}, {"BAND_RAILS_ENABLED": True}],
                  frame_loader=_loader(_FROZEN), evaluate=lambda t, s: None)
    session.expire_all()
    assert marks_fingerprint(load_marks(session)) == before


def test_json_output_refuses_the_sealed_dirs(tmp_path):
    # ONE shared guard (tools._bootstrap.refuse_sealed_output) covers BOTH
    # sealed populations: the docs/marks corpus AND the ratchet baselines.
    import os
    for sealed in (os.path.join(str(ROOT), "docs", "marks", "report.json"),
                   os.path.join(str(ROOT), "tests", "baselines", "report.json")):
        with pytest.raises(ValueError) as err:
            _refuse_sealed_output(sealed)
        assert "sealed" in str(err.value)
    # Case variants refuse too — Chrollo deploys on case-insensitive NTFS,
    # where `docs/Marks/…` opens the REAL sealed directory (2026-08-08
    # review, finding 15; the guard normcases both sides).
    for cased in (os.path.join(str(ROOT), "docs", "Marks", "report.json"),
                  os.path.join(str(ROOT), "Tests", "BASELINES", "report.json")):
        with pytest.raises(ValueError):
            _refuse_sealed_output(cased)
    # The docs-root corpus FILES seal too — the append-only ruling artifacts
    # a mistyped --out would truncate (2026-08-17 review, Hunt), incl. the
    # EC-35 case variant.
    for corpus in (os.path.join(str(ROOT), "docs", "power_play_marks_2026-08.json"),
                   os.path.join(str(ROOT), "docs", "Power_Play_Marks_2026-08.JSON"),
                   os.path.join(str(ROOT), "docs", "trend_end_marks_2026-08.json"),
                   os.path.join(str(ROOT), "docs", "phase_c_marks_2026-07.json"),
                   # The operator's 40 sheet verdicts, sealed at landing (EC-44).
                   os.path.join(str(ROOT), "docs", "power_play_verdicts_2026-08-18.json")):
        with pytest.raises(ValueError):
            _refuse_sealed_output(corpus)
    _refuse_sealed_output(str(tmp_path / "report.json"))  # elsewhere: fine
    _refuse_sealed_output(os.path.join(str(ROOT), "docs", "some_note.json"))


def test_fingerprint_is_order_free_and_content_bound(session):
    _add_mark(session)
    _add_mark(session, ticker="KLAC", as_of_date="2025-09-11",
              box_start_date="2025-07-18", box_end_date="2025-09-11",
              resistance=95.0, support=87.74)
    a = marks_fingerprint(load_marks(session))
    b = marks_fingerprint(list(reversed(load_marks(session))))
    assert a == b
    session.query(CalibrationMark).filter_by(ticker="KLAC").first().resistance = 95.5
    session.commit()
    assert marks_fingerprint(load_marks(session)) != a


def test_parse_variant():
    assert parse_variant("BAND_RAILS_ENABLED=true") == {"BAND_RAILS_ENABLED": True}
    assert parse_variant("X=2.5") == {"X": 2.5}
    with pytest.raises(ValueError):
        parse_variant("JUSTAFLAG")


# ---------------------------------------------------------------- fired (v2)
def _fire_result(R=12.0, S=10.0):
    """The fields fired_one reads off a full-pipeline firing result."""
    return {"Tier": "A", "Score": 77.0, "_R": R, "_S": S}


def _evaluate_firing_from(first_fire, result=None):
    """Fires on every session at/after ``first_fire``; None (no setup) before."""
    def _run(ticker, sliced):
        if sliced.index[-1] >= pd.Timestamp(first_fire):
            return result or _fire_result()
        return None
    return _run


def test_fired_reports_the_first_fire_in_the_default_window(session):
    _add_mark(session)
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_evaluate_firing_from("2026-04-09"))[0]
    assert frag["fired"] is True
    assert frag["fire_date"] == "2026-04-09"      # the EARLIEST fire, not just any
    assert frag["fire_tier"] == "A"
    assert frag["fire_rails_within_tol"] is True  # fired at his rails


def test_fired_no_fire_walks_the_whole_bounded_window(session):
    _add_mark(session)
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=lambda t, s: None)[0]
    assert frag["fired"] is False
    assert frag["fired_sessions_walked"] == FIRED_WINDOW_SESSIONS
    assert frag["fired_window"][1] == "2026-04-15"  # window ends at as-of


def test_fired_knowable_from_sets_the_window(session):
    # The mark's own declaration overrides the default bound: a fire long
    # before the 10-session window but at/after knowable_from still counts.
    _add_mark(session, knowable_from_date="2026-02-02")
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_evaluate_firing_from("2026-02-02"))[0]
    assert frag["fired"] is True
    assert frag["fire_date"] == "2026-02-02"
    assert frag["fired_window"][0] == "2026-02-02"


def test_fired_grades_box_marks_only(session):
    # BOTH negative verdicts assert a no-read at ONE session (grade_one
    # policy); window-hunting sessions to convict one would bias the rate.
    _add_mark(session, as_of_date="2026-04-14", verdict="no_structure",
              resistance=None, support=None,
              box_start_date=None, box_end_date=None)
    _add_mark(session, as_of_date="2026-04-13", verdict="engine_wrong",
              resistance=None, support=None,
              box_start_date=None, box_end_date=None)

    def _never(ticker, sliced):
        raise AssertionError("negative marks are never window-walked")

    for mark in load_marks(session):
        frags = fired_one(mark, [{}, {"BAND_RAILS_ENABLED": True}],
                          frame_loader=_loader(_FROZEN), evaluate=_never)
        assert frags == [None, None], mark["verdict"]


def test_fired_digest_resolves_through_the_real_loader(session, tmp_path, monkeypatch):
    # Frozen-or-refuse through the REAL digest-resolved loader (the grade_one
    # twin): a restated mark must never be silently walked on other bars.
    import frame_store as bare_frame_store
    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    monkeypatch.setattr(bare_frame_store, "FRAMES_DIR", str(tmp_path))
    frame_store.freeze_frame("BODI", "2026-04-15", _FROZEN)
    _add_mark(session, frame_digest="0" * 64)
    frag = fired_one(load_marks(session)[0], [{}],
                     evaluate=lambda t, s: _fire_result())[0]
    assert frag["fired"] is None
    assert "basis" in frag["fired_detail"]
    # And the matching digest resolves and walks through the same real loader.
    session.query(CalibrationMark).first().frame_digest = _DIGEST
    session.commit()
    frag = fired_one(load_marks(session)[0], [{}],
                     evaluate=lambda t, s: _fire_result())[0]
    assert frag["fired"] is True


def test_fired_eval_error_aborts_the_walk(session):
    # A crash poisons the whole window: a LATER fire must never overwrite the
    # crash verdict — that would inflate the pops-up-live numerator on
    # exactly the marks where the eval chain is regressing.
    _add_mark(session)

    def _crash_then_fire(ticker, sliced):
        if sliced.index[-1] <= pd.Timestamp("2026-04-02"):
            return EVAL_ERROR
        return _fire_result()

    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_crash_then_fire)[0]
    assert frag["fired"] is None
    assert "EVAL_ERROR at 2026-04-02" in frag["fired_detail"]


def test_fired_default_evaluate_wires_the_frozen_scalars_in_order(session, monkeypatch):
    # Every other test injects a fake evaluate; this pins the PRODUCTION
    # closure — argument order matters because a swapped pair would stamp
    # Tier/Score under a fictitious +50% SPY regime with no error anywhere.
    import engine_alpha.evaluation as evaluation
    _add_mark(session)
    calls = []

    def _capture(ticker, sliced, spy_6m_return, breadth_pct):
        calls.append((ticker, spy_6m_return, breadth_pct))
        return _fire_result()

    monkeypatch.setattr(evaluation, "_evaluate_ticker", _capture)
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN))[0]
    assert frag["fired"] is True
    assert calls == [("BODI", 0.0, 0.5)]  # spy_6m first, breadth second


def test_fired_variant_flags_set_during_walk_and_restored(session):
    from config import settings
    _add_mark(session)
    prior = settings.BAND_RAILS_ENABLED
    seen = []

    def _peek(ticker, sliced):
        seen.append(settings.BAND_RAILS_ENABLED)
        return _fire_result()   # fire on the first session -> one eval per variant

    fired_one(load_marks(session)[0], [{}, {"BAND_RAILS_ENABLED": True}],
              frame_loader=_loader(_FROZEN), evaluate=_peek)
    assert seen == [prior, True]
    assert settings.BAND_RAILS_ENABLED == prior


def test_fired_on_a_different_structure_is_diagnosed(session):
    _add_mark(session)
    other = _fire_result(R=20.0, S=17.0)
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_evaluate_firing_from("2026-04-02", result=other))[0]
    assert frag["fired"] is True                   # headline: the ticker surfaced
    assert frag["fire_rails_within_tol"] is False  # diagnostic: not his rails
    # The fired rails ride along, so a near-miss is distinguishable from a
    # genuinely different base without re-running the eval.
    assert (frag["fire_R"], frag["fire_S"]) == (20.0, 17.0)


def test_fired_rail_tolerance_is_referenced_to_the_drawn_box_height(session):
    # Doctrine: tolerances are fractions of the DRAWN box height. Drawn 12/10
    # gives tol 0.2; engine R=12.21 is off by 0.21 -> off-tol. (Referenced to
    # the taller ENGINE box the same rails would pass — the marginal case the
    # diagnostic exists to separate.)
    _add_mark(session)
    near = _fire_result(R=12.21, S=10.0)
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_evaluate_firing_from("2026-04-02", result=near))[0]
    assert frag["fire_rails_within_tol"] is False


def test_fired_at_the_inner_box_counts_as_his_rails(session):
    # A fire whose LPS re-anchored to the tighter inner box IS a fire at that
    # shelf: when the operator marked the inner pair, the diagnostic must not
    # misread it as a different structure just because parent _R/_S differ.
    _add_mark(session)
    inner_fire = {**_fire_result(R=20.0, S=8.0), "_lps_in_inner": True,
                  "_inner_R": 12.0, "_inner_S": 10.0}
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_evaluate_firing_from("2026-04-02", result=inner_fire))[0]
    assert frag["fire_rails_within_tol"] is True
    assert frag["fire_lps_in_inner"] is True
    assert (frag["fire_inner_R"], frag["fire_inner_S"]) == (12.0, 10.0)
    # Without the inner re-anchor, off-tol parent rails stay off-tol.
    no_anchor = {**inner_fire, "_lps_in_inner": False}
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_evaluate_firing_from("2026-04-02", result=no_anchor))[0]
    assert frag["fire_rails_within_tol"] is False


def test_fired_knowable_from_narrows_too(session):
    # Hindsight never penalizes the point-in-time read: the walk STARTS at
    # knowable_from, so a pre-knowable fire is never even visited and the
    # first legitimate fire is the one reported.
    _add_mark(session, knowable_from_date="2026-04-10")
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_evaluate_firing_from("2026-04-02"))[0]
    assert frag["fired_window"][0] == "2026-04-10"
    assert frag["fire_date"] == "2026-04-10"
    assert frag["fired"] is True


def test_fired_flags_restored_when_the_walk_raises(session):
    # _evaluate_ticker converts only six exception types to EVAL_ERROR;
    # anything else propagates mid-walk — the variant flag must not leak
    # into every subsequent measurement in the process.
    from config import settings
    _add_mark(session)
    prior = settings.BAND_RAILS_ENABLED

    def _boom(ticker, sliced):
        raise RuntimeError("engine crash mid-walk")

    with pytest.raises(RuntimeError):
        fired_one(load_marks(session)[0], [{"BAND_RAILS_ENABLED": True}],
                  frame_loader=_loader(_FROZEN), evaluate=_boom)
    assert settings.BAND_RAILS_ENABLED == prior


def _long_frame():
    idx = pd.date_range("2024-01-05", "2026-04-15", freq="B")
    closes = [11.0] * len(idx)
    return pd.DataFrame({"Open": closes, "High": [c + 1 for c in closes],
                         "Low": [c - 1 for c in closes], "Close": closes,
                         "Volume": [1e6] * len(idx)}, index=idx)


def test_fired_deep_knowable_window_clamps_to_the_faithful_basis_zone(session):
    # The nightly evaluates a trailing-2y daily frame off the 5y cache; a
    # frozen chart frame carries bounded lead-in, so early walked sessions
    # would replay on a thinner left edge than live (the root walk is
    # left-edge-sensitive). Those sessions are walked OUT and the clamp is
    # NAMED — a thin-basis no-fire must never deflate the headline.
    _add_mark(session, knowable_from_date="2025-06-02")
    frag = fired_one(load_marks(session)[0], [{}],
                     frame_loader=_loader(_long_frame()),
                     evaluate=lambda t, s: None)[0]
    assert "fired_window_clamped" in frag
    assert "2026-01-09" <= frag["fired_window"][0] <= "2026-01-13"
    assert frag["fired"] is False


def test_fired_young_ticker_frame_never_clamps(session):
    # A frame the 2y trim cannot cut IS the ticker's full history: the live
    # nightly saw the same bars, so every session is a faithful basis. (The
    # window here stays under FIRED_WALK_MAX_SESSIONS — the size cap is a
    # separate, named policy pinned in its own test below.)
    _add_mark(session, knowable_from_date="2026-03-02")
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=lambda t, s: None)[0]
    assert "fired_window_clamped" not in frag
    assert frag["fired_window"][0] == "2026-03-02"


# ------------------------------------------------- policy v2 (Family-7 fix)
def _add_lps_event(session, start, end):
    mark = session.query(CalibrationMark).order_by(CalibrationMark.id.desc()).first()
    session.add(CalibrationMarkEvent(mark_id=mark.id, event_type="lps",
                                     start_date=start, end_date=end,
                                     source="operator"))
    session.commit()


def test_fired_walk_covers_the_marked_lps_event_window(session):
    # A mark typed weeks after its breakout (the MS/NGL class) is graded where
    # the setup was LIVE: the marked-LPS span + a small tail joins the walk,
    # so a fire there counts — with the engine byte-identical. Expected values
    # hand-specified from the diagnosis, not read off the code: the walk must
    # visit 2026-02-02 (event start) and report the 02-03 fire as FIRST.
    _add_mark(session)
    _add_lps_event(session, "2026-02-02", "2026-02-05")
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_evaluate_firing_from("2026-02-03"))[0]
    assert frag["fired"] is True
    assert frag["fire_date"] == "2026-02-03"
    assert frag["fired_window"][0] == "2026-02-02"
    assert frag["fired_window"][1] == "2026-04-15"  # as-of tail still walked
    # And with no fire anywhere, the walk covers exactly the union:
    # event span (4 sessions) + tail (5) + trailing window (10) = 19.
    no_fire = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                        evaluate=lambda t, s: None)[0]
    assert no_fire["fired_sessions_walked"] == 4 + FIRED_EVENT_TAIL_SESSIONS + FIRED_WINDOW_SESSIONS


def test_fired_walk_cap_keeps_oldest_and_names_the_clamp(session):
    # An event span wider than the cap: the OLDEST sessions are kept (the fire
    # is reported at the first night anyway) and the clamp is NAMED.
    _add_mark(session)
    _add_lps_event(session, "2026-01-05", "2026-04-15")
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=lambda t, s: None)[0]
    assert frag["fired_sessions_walked"] == FIRED_WALK_MAX_SESSIONS
    assert frag["fired_window"][0] == "2026-01-05"
    assert "capped at the oldest" in frag["fired_window_clamped"]


def test_fired_grades_rails_and_span_at_the_fire_session(session):
    # Policy v2: the fire session's own read grades rail/span agreement —
    # a result carrying its box-start date yields a span overlap against the
    # DRAWN span ending at the fire date, and per-rail distances ride along.
    _add_mark(session)
    firing = {**_fire_result(R=12.0, S=10.0),
              "_phase_b_start_date": "2026-01-05"}
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_evaluate_firing_from("2026-04-09", result=firing))[0]
    assert frag["fire_box_start_date"] == "2026-01-05"
    # drawn 01-05..04-15 (101 days) vs fired 01-05..04-09 (95 days): 95/101
    assert frag["fire_span_overlap"] == pytest.approx(95 / 101, abs=1e-4)
    assert frag["fire_rail_distances"] == {"r_frac": 0.0, "s_frac": 0.0}


def test_fired_canned_result_without_box_dates_stays_gradable(session):
    # A result lacking _phase_b_start_date (older archive shapes) must not
    # crash or block the fire verdict — the span figure is simply absent.
    _add_mark(session)
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_evaluate_firing_from("2026-04-09"))[0]
    assert frag["fired"] is True
    assert "fire_span_overlap" not in frag
    assert frag["fire_rail_distances"] == {"r_frac": 0.0, "s_frac": 0.0}


def test_fired_binding_gate_margin_picks_the_tightest_gate(session):
    # respect sits +0.11 over its 0.80 floor; upper dwell only +0.01 over its
    # 0.15 floor -> the binding gate is upper_dwell. Hand-specified margins.
    _add_mark(session)
    firing = {**_fire_result(), "_eq_respect_frac": 0.91,
              "_eq_close_lower_dwell": 0.30, "_eq_close_upper_dwell": 0.16,
              "_eq_close_mid_dwell": 0.40}
    frag = fired_one(load_marks(session)[0], [{}], frame_loader=_loader(_FROZEN),
                     evaluate=_evaluate_firing_from("2026-04-09", result=firing))[0]
    assert frag["fire_gate_margin"] == {"gate": "upper_dwell", "margin": 0.01}


def test_backend_fired_signature_carries_the_policy_version():
    # The chip cache key must rotate when grading SEMANTICS change even though
    # no numeric constant moved and the engine hash never rotates.
    from webapp.backend.services.calibration_fired import _fired_sig
    assert f"v{HARNESS_POLICY_VERSION}:" in _fired_sig()


def test_delta_attribution_names_exactly_the_moved_axis(capsys):
    base = {"marks_fingerprint": "f" * 64, "engine_config_version": "e" * 64,
            "harness_policy_version": HARNESS_POLICY_VERSION,
            "generated_at": "2026-07-16T00:00:00+00:00",
            "variants": {"baseline": {"rows": [
                {"mark": "MS@2026-06-04", "outcome": "engine_no_read",
                 "fired": False}]}}}
    prev = {**base, "harness_policy_version": 1,
            "variants": {"baseline": {"rows": [
                {"mark": "MS@2026-06-04", "outcome": "engine_no_read",
                 "fired": False}]}}}
    cur = {**base, "variants": {"baseline": {"rows": [
        {"mark": "MS@2026-06-04", "outcome": "engine_no_read",
         "fired": True}]}}}
    _print_delta(cur, prev)
    out = capsys.readouterr().out
    assert "MEASUREMENT moved" in out
    assert "GROUND TRUTH" not in out and "ENGINE moved" not in out
    assert "fired False -> True" in out


def test_run_fired_stamps_policy_and_keeps_variant_fragments_aligned(
        session, tmp_path, monkeypatch):
    # run(--fired) merges fired fragments into grade rows by variant INDEX;
    # the A/B question ("did the flag change the pops-up-live verdict?") is
    # only answerable if that alignment holds and the policy is stamped.
    import json

    import engine_alpha.evaluation as evaluation
    import database
    import frame_store as bare_frame_store
    from config import settings
    from tools import calibration_harness as harness

    monkeypatch.setattr(frame_store, "FRAMES_DIR", str(tmp_path))
    monkeypatch.setattr(bare_frame_store, "FRAMES_DIR", str(tmp_path))
    frame_store.freeze_frame("BODI", "2026-04-15", _FROZEN)
    _add_mark(session)
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    # The stub fires only under the LIVE default (band-rails ON since the
    # 2026-07-16 flip); the variant turns the flag OFF, so baseline fires and
    # the variant doesn't — the same A/B polarity the alignment check needs.
    def _fires_baseline_only(ticker, sliced, spy_6m_return, breadth_pct):
        return _fire_result() if settings.BAND_RAILS_ENABLED else None

    monkeypatch.setattr(evaluation, "_evaluate_ticker", _fires_baseline_only)
    out = tmp_path / "report.json"
    harness.run(None, ["BAND_RAILS_ENABLED=false"], str(out), fired=True)
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["fired_policy"]["window_sessions"] == FIRED_WINDOW_SESSIONS
    # EC-9 self-identification: the report NAMES the population it scored and
    # stamps a fingerprint of the exact marks set, or two reports are silently
    # incomparable / the editable marks could be mislabelled the sealed corpus.
    assert report["population"] == "calibration_marks"
    assert isinstance(report["marks_fingerprint"], str) and len(report["marks_fingerprint"]) == 64
    base = report["variants"]["baseline"]["rows"][0]
    variant = report["variants"]["BAND_RAILS_ENABLED=false"]["rows"][0]
    assert base["fired"] is True and base["fire_date"] == "2026-04-02"
    assert variant["fired"] is False
