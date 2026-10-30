"""Classifier tripwire for the Market & Sector Health Board.

The regression ratchets prove ONLY that the fires are untouched — they do NOT watch the
classifier's own output. These tests are therefore the load-bearing tripwire on the health
path: they pin each state (the box states on his own sealed charts, read through the reader
door — decision B of the retirement, Fri 30/10/2026), the precedence ladder's totality +
exclusivity (exactly one closed-set state per member), the degenerate-input guards, and
frame isolation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config import settings
from core.pipeline.context.health_board import (
    HEALTH_STATE_ORDER,
    HealthState,
    InsufficientHistoryError,
    MemberHealth,
    classify_member,
    classify_universe_members,
)


def _frame(closes, band=0.6, start="2023-01-02"):
    """OHLCV frame from a close list, small High/Low band, business-day index."""
    closes = np.asarray(closes, dtype=float)
    idx = pd.date_range(start, periods=len(closes), freq="B")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes + band,
            "Low": closes - band,
            "Close": closes,
            "Volume": np.full(len(closes), 1_000_000.0),
        },
        index=idx,
    )


def _worked_box(tail=None, tail_bars=6, S=113.0, R=125.0, n_pre=170,
                markup_bars=40, ar_bars=8, osc_cycles=8, osc_bars=6):
    """Background uptrend -> markup leg -> automatic reaction -> a range that oscillates
    113-125 rail-to-rail, then a flat ``tail``. The universe door refuses this frame (the
    last close sits under its 50-day average), so it reads as the boxless fallback."""
    closes = list(np.linspace(50, 95, n_pre))              # background trend (builds SMA200)
    closes += list(np.linspace(95, 128, markup_bars))       # markup leg to the climax
    closes += list(np.linspace(128, 113, ar_bars))          # automatic reaction
    for _ in range(osc_cycles):
        closes += list(np.linspace(S + 1, R - 1, osc_bars))  # up-limb
        closes += list(np.linspace(R - 1, S + 1, osc_bars))  # down-limb
    closes += [(S + R) / 2 if tail is None else tail] * tail_bars
    return _frame(closes)


# --------------------------------------------------------------------------
# The closed-set contract
# --------------------------------------------------------------------------

def test_state_set_is_exactly_seven_in_decision_proximity_order():
    assert len(HealthState) == 7
    assert HEALTH_STATE_ORDER == (
        "near_resistance", "post_breakout_markup", "near_support",
        "consolidating", "trending", "deep_correction", "no_structure",
    )
    # The str mixin makes each member its own JSON-safe wire string.
    assert HealthState.NEAR_RESISTANCE == "near_resistance"
# --------------------------------------------------------------------------
# Each state is reachable: the box states on his own sealed charts (the reader's
# parent box through the door), the boxless states on synthetic frames
# --------------------------------------------------------------------------

def _sealed(key, cut=0):
    """One sealed chart (tests/baselines/marks_corpus.parquet), its last ``cut`` days removed."""
    from core.calibration.replay import load_sealed_fixture

    frames, _ = load_sealed_fixture()
    df = frames[key]
    return df.iloc[:-cut] if cut else df


def test_near_resistance_his_alb_closes_within_a_line_area_of_r():
    # ALB to Mon 13/04/2026: the parent 182.80 / 156.04, the last close 185.43 — over R, but by less
    # than half a daily range, so the member is coiled AT the ceiling, not through it.
    mh = classify_member(_sealed("ALB:2026-04-13"))
    assert mh.state is HealthState.NEAR_RESISTANCE
    assert (mh.R, mh.S, mh.base_len) == (182.8, 156.04, 46)
    assert mh.box_pos == 1.0983 and mh.breakout_extension is None
    assert mh.distance_to_high_pct == -0.0999


def test_consolidating_his_anet_closes_inside_the_rails():
    mh = classify_member(_sealed("ANET:2026-09-25"))
    assert mh.state is HealthState.CONSOLIDATING
    assert (mh.R, mh.S, mh.base_len) == (214.89, 187.03, 37)
    assert 0.30 < mh.box_pos < 0.80 and mh.breakout_extension is None


def test_near_support_his_clov_a_day_earlier_sits_on_the_floor():
    # CLOV cut to Mon 26/10/2026: the close 4.56 against S 4.50 — within a line area of the floor.
    mh = classify_member(_sealed("CLOV:2026-10-27", cut=1))
    assert mh.state is HealthState.NEAR_SUPPORT
    assert (mh.R, mh.S) == (5.18, 4.5)
    assert mh.box_pos == 0.0882 and mh.breakout_extension is None


def test_post_breakout_markup_his_dsgn_reports_the_extension_above_r():
    mh = classify_member(_sealed("DSGN:2026-03-31"))
    assert mh.state is HealthState.POST_BREAKOUT_MARKUP
    assert (mh.R, mh.S, mh.base_len) == (10.31, 9.0, 79)
    assert mh.breakout_extension == 0.0324 and mh.box_pos == 1.2557


def test_trending_is_clean_uptrend_with_no_box():
    mh = classify_member(_frame(list(np.linspace(50, 150, 300))))
    assert mh.state is HealthState.TRENDING
    assert mh.R is None and mh.S is None and mh.base_len == 0


def test_deep_correction_from_large_drawdown():
    closes = list(np.linspace(50, 150, 200)) + list(np.linspace(150, 90, 100))  # ~40% off the high
    mh = classify_member(_frame(closes))
    assert mh.state is HealthState.DEEP_CORRECTION
    assert mh.distance_to_high_pct is not None and mh.distance_to_high_pct < -0.30


def test_no_structure_is_the_total_fallback():
    # A member the universe door refuses (the last close under its 50-day average) that
    # is neither deep in correction nor trending: no box is read, the fallback.
    frame = _worked_box(tail=119.0)
    mh = classify_member(frame)
    assert mh.state is HealthState.NO_STRUCTURE
    assert mh.R is None and mh.S is None and mh.base_len == 0
    assert mh.distance_to_high_pct is not None and mh.distance_to_high_pct > -0.30


# --------------------------------------------------------------------------
# Precedence ladder: drawdown-first, exclusivity, the box through the door
# --------------------------------------------------------------------------

def test_drawdown_is_classified_before_the_box(monkeypatch):
    # His ANET holds a box and sits ~4% below its high. Tighten the deep-correction floor so
    # that drawdown alone dominates — proving drawdown is checked BEFORE the box read.
    plain = classify_member(_sealed("ANET:2026-09-25"))
    assert plain.state is HealthState.CONSOLIDATING
    monkeypatch.setattr(settings, "HEALTH_DEEP_CORRECTION_DRAWDOWN", -0.02)
    deep = classify_member(_sealed("ANET:2026-09-25"))
    assert deep.state is HealthState.DEEP_CORRECTION


def test_the_box_is_the_readers_parent_through_the_door(monkeypatch):
    """The board reads the reader's own record: what read_record holds as the parent is the box."""
    from engine_alpha import reader

    seen = {}
    real = reader.read_record

    def spy(ticker, df, **kwargs):
        read = real(ticker, df, **kwargs)
        seen["parent"] = read.parent
        return read

    monkeypatch.setattr(reader, "read_record", spy)
    mh = classify_member(_sealed("ANET:2026-09-25"))
    parent = seen["parent"]
    assert (mh.R, mh.S) == (round(parent.resistance.price, 2), round(parent.support.price, 2))


def test_a_member_the_door_refuses_has_no_box(monkeypatch):
    from engine_alpha import reader

    monkeypatch.setattr(reader, "read_record", lambda ticker, df, **k: None)
    mh = classify_member(_sealed("ANET:2026-09-25"))
    assert mh.state in (HealthState.TRENDING, HealthState.NO_STRUCTURE)
    assert mh.R is None and mh.S is None and mh.base_len == 0


def test_the_line_area_is_half_a_daily_range(monkeypatch):
    """near_resistance / near_support = the last close within LINE_WORD_AREA_ATR daily ranges of R or S:
    with no area at all his ALB (closing OVER R) reads as broken out, not coiled."""
    from engine_alpha import two_eyes_numbers as M

    monkeypatch.setattr(M, "LINE_WORD_AREA_ATR", 0.0)
    assert classify_member(_sealed("ALB:2026-04-13")).state is HealthState.POST_BREAKOUT_MARKUP
    monkeypatch.setattr(M, "LINE_WORD_AREA_ATR", 0.5)
    assert classify_member(_sealed("ALB:2026-04-13")).state is HealthState.NEAR_RESISTANCE


def test_every_state_is_a_single_valid_closed_set_member():
    frames = [
        _sealed("ALB:2026-04-13"), _sealed("ANET:2026-09-25"), _sealed("CLOV:2026-10-27", cut=1),
        _sealed("DSGN:2026-03-31"), _frame(list(np.linspace(50, 150, 300))),
        _frame(list(np.linspace(50, 150, 200)) + list(np.linspace(150, 90, 100))),
        _worked_box(tail=119.0),
    ]
    states = set()
    for df in frames:
        mh = classify_member(df)
        assert isinstance(mh, MemberHealth)
        assert isinstance(mh.state, HealthState)  # exactly one, from the closed set
        states.add(mh.state)
    assert states == set(HealthState), "every state of the closed set is reached once"


# --------------------------------------------------------------------------
# Guards: short history, degenerate values, frame isolation
# --------------------------------------------------------------------------

def test_short_history_raises_insufficient_history():
    with pytest.raises(InsufficientHistoryError):
        classify_member(_frame(list(np.linspace(50, 60, 150))))  # < 200 bars


def test_non_finite_prices_never_crash_and_stay_in_the_closed_set():
    # The classifier reads the LAST close; inf there must take the isfinite guard,
    # not poison the box_pos math downstream.
    frame = _sealed("ANET:2026-09-25")
    frame.iloc[-1, frame.columns.get_loc("Close")] = np.inf
    mh = classify_member(frame)  # must not raise
    assert mh.state is HealthState.NO_STRUCTURE  # degraded gracefully off the guard
    assert mh.box_pos is None


def test_classify_member_does_not_mutate_the_caller_frame():
    df = _sealed("ANET:2026-09-25")
    cols_before = list(df.columns)
    snapshot = df.copy(deep=True)
    classify_member(df)
    assert list(df.columns) == cols_before  # no ATR_10 leaked onto the caller's frame
    assert "ATR_10" not in df.columns
    pd.testing.assert_frame_equal(df, snapshot)  # values untouched


# --------------------------------------------------------------------------
# Universe orchestration: per-member isolation + honest unreadable bucket
# --------------------------------------------------------------------------

class _FakeUniverse:
    ticker_csv = "unused.csv"
    index_symbols = ()


def test_classify_universe_members_isolates_failures(monkeypatch):
    box = _sealed("ANET:2026-09-25")                    # AAA: classifies (a box)
    short = _frame(list(np.linspace(50, 60, 150)), start=str(box.index[0].date()))  # BBB: short history
    # Concatenate into a MultiIndex panel keyed by ticker; the shorter frame pads
    # with NaN beyond its length and is dropped back to 150 bars by the reader.
    panel = pd.concat({"AAA": box, "BBB": short}, axis=1, sort=True)

    monkeypatch.setattr(
        "core.pipeline.universe.tickers.get_cached_tickers",
        lambda _csv: ["AAA", "BBB", "CCC"],  # CCC has no column in the panel
    )
    monkeypatch.setattr("core.pipeline.context.health_board._resolve", lambda _u: _FakeUniverse())

    members, unreadable = classify_universe_members(panel, _FakeUniverse())

    assert set(members) == {"AAA"}
    assert members["AAA"].state is HealthState.CONSOLIDATING
    reasons = {row["ticker"]: row["reason"] for row in unreadable}
    assert reasons == {"BBB": "short_history", "CCC": "not_available"}


# --------------------------------------------------------------------------
# Payload builder + artifact contract (Task 5) — no buy language, atomic ride
# --------------------------------------------------------------------------

def _fake_universe_at(path):
    class _U:
        key = "us_sectors"
        universe_type = "us_sectors"
        def artifact_path(self):
            return str(path)
    return _U()


def test_build_health_payload_shape_carries_no_buy_language():
    from core.pipeline.screening.dashboard import build_health_payload

    box = _sealed("ALB:2026-04-13")  # near_resistance, has a box
    panel = pd.concat({"XLE": box}, axis=1)
    members = {"XLE": classify_member(box)}
    payload = build_health_payload(members, [{"ticker": "ZZZ", "reason": "short_history"}], panel, _FakeUniverse())

    assert payload["member_count"] == 2  # 1 classified + 1 unreadable
    assert [m["ticker"] for m in payload["members"]] == ["XLE"]
    row = payload["members"][0]
    assert row["state"] == "near_resistance"
    assert row["R"] is not None and row["S"] is not None and row["base_len"] > 0
    assert row["candles"] and row["volumes"]  # daily bars for the reused card
    # The "no buy language" contract, enforced at the emit site: a health member
    # carries NO score / tier / trigger / setup / sub_scores field.
    for banned in ("score", "tier", "trigger", "setup", "sub_scores", "Score", "Tier"):
        assert banned not in row
    assert payload["unreadable"] == [{"ticker": "ZZZ", "reason": "short_history"}]


def test_generate_dashboard_flag_off_omits_health_key(tmp_path, monkeypatch):
    import core.pipeline.screening.dashboard as dash

    out = tmp_path / "screener_data_us_sectors.json"
    monkeypatch.setattr(dash, "resolve_universe", lambda _u: _fake_universe_at(out))

    # Empty results (the ETF-universe common case); no health board passed.
    dash.generate_dashboard(pd.DataFrame(), data=None, tickers=None,
                            market_context={}, universe=_FakeUniverse(), health_board=None,
                            scan_date="2026-08-05")
    import json
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert "health_board" not in doc  # byte-identical to today's empty artifact


def test_generate_dashboard_rides_health_board_into_same_artifact(tmp_path, monkeypatch):
    import json
    import core.pipeline.screening.dashboard as dash
    from core.pipeline.screening.dashboard import build_health_payload

    out = tmp_path / "screener_data_us_sectors.json"
    monkeypatch.setattr(dash, "resolve_universe", lambda _u: _fake_universe_at(out))

    box = _sealed("ANET:2026-09-25")
    panel = pd.concat({"XLE": box}, axis=1)
    payload = build_health_payload({"XLE": classify_member(box)}, [], panel, _FakeUniverse())

    # Empty firing results, but a health board present → one atomic write carries both.
    dash.generate_dashboard(pd.DataFrame(), data=None, tickers=None,
                            market_context={}, universe=_FakeUniverse(), health_board=payload,
                            scan_date="2026-08-05")
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert "health_board" in doc
    assert doc["chart_data"] == {} and doc["ordered_tickers"] == []  # firing side untouched
    assert doc["health_board"]["members"][0]["state"] == "consolidating"


def test_generate_dashboard_publishes_the_exact_scan_identity(tmp_path, monkeypatch):
    """Council review 2026-08-05 finding 2: the payload's scan_identity must
    carry EXACTLY the threaded scan_date (the archive writer's key), the
    universe's own type, and a non-empty engine_config_version — re-deriving
    the date inside the writer (the midnight-straddle split) or dropping the
    thread must fail here."""
    import json
    import core.pipeline.screening.dashboard as dash

    out = tmp_path / "screener_data_us_sectors.json"
    monkeypatch.setattr(dash, "resolve_universe", lambda _u: _fake_universe_at(out))

    dash.generate_dashboard(pd.DataFrame(), data=None, tickers=None,
                            market_context={}, universe=_FakeUniverse(),
                            health_board=None, scan_date="2001-02-03")
    ident = json.loads(out.read_text(encoding="utf-8"))["scan_identity"]
    assert ident["scan_date"] == "2001-02-03"   # verbatim, never re-derived
    assert ident["universe_type"] == "us_sectors"
    assert isinstance(ident["engine_config_version"], str) and ident["engine_config_version"]


# --------------------------------------------------------------------------
# Orchestration gate (Task 4) — the two guards that keep the health board OFF the
# byte-parity-locked us_equities artifact. shadow_diff / seed_recall watch the
# classifier OUTPUT, not this gate; with HEALTH_BOARD_ENABLED now live the
# universe_type check is the SOLE thing sparing us_equities, so pin it directly.
# --------------------------------------------------------------------------

def _boom_if_classified(monkeypatch):
    """Make the classifier explode if reached, so a passing test proves the gate
    short-circuited BEFORE any read touched the panel (not merely that it returned
    an empty payload)."""
    def _explode(*_a, **_k):  # pragma: no cover - must never run behind the gate
        raise AssertionError("classify_universe_members ran behind the gate")
    monkeypatch.setattr("core.pipeline.context.health_board.classify_universe_members", _explode)


def test_maybe_build_health_board_skips_equities_even_when_flag_on(monkeypatch):
    from core.pipeline.screening import scan_job
    from core.pipeline.universe.descriptor import DEFAULT_UNIVERSE_TYPE

    class _Equities:
        key = "us_equities"
        universe_type = DEFAULT_UNIVERSE_TYPE

    monkeypatch.setattr(settings, "HEALTH_BOARD_ENABLED", True)
    _boom_if_classified(monkeypatch)

    # Flag ON, but the equities universe → None (never a health_board key on the
    # byte-parity-locked us_equities artifact) AND the classifier is never reached.
    assert scan_job._maybe_build_health_board(pd.DataFrame(), _Equities()) is None


def test_maybe_build_health_board_returns_none_when_flag_off(monkeypatch):
    from core.pipeline.screening import scan_job

    class _Sectors:
        key = "us_sectors"
        universe_type = "us_sectors"

    monkeypatch.setattr(settings, "HEALTH_BOARD_ENABLED", False)
    _boom_if_classified(monkeypatch)

    # Flag OFF → None even for a non-equities universe (artifact byte-identical to
    # today) AND the classifier is never reached.
    assert scan_job._maybe_build_health_board(pd.DataFrame(), _Sectors()) is None
