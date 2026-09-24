"""The Power-Play census battery (program Task 3): hand-reasoned episode
discovery and first-legal-look arithmetic, honest-absence rows, partitioned
forward horizons, determinism, the lookahead tripwire speaking on every output
mode (EC-31), and the sealed-output guard (EC-14).

The frames are SYNTHETIC and hand-reasoned — expected bar positions are derived
from the construction arithmetic below, never from running the tool (Beck P1).
Election OUTCOMES on synthetic tape are deliberately not pinned (that is the
engine's business and belongs to the species acceptance battery on frozen real
frames); the census's own mechanics are what this battery constrains."""
import json
import os

import numpy as np
import pandas as pd
import pytest

from _paths import REPO_ROOT
from config import settings
from tools.research import power_play_census as census

# ── the hand-reasoned pole frame ────────────────────────────────────────────
# pre   [0, 400)   : linear 40 -> 50
# pole  [400, 440) : linear 50 -> 100          peak at 439 (High 100.5)
# AR    [440, 447) : linear 98 -> 88.5         AR low at 446 (Low 88.0)
# shelf [447, 465) : alternating 90 / 92      (shelf ATR10 = exactly 2.5)
# brk   465        : close 104 — clears the RULED departure wall
#                    (peak 100.5 + 1×ATR10 2.5 = 103.0) decisively
# tail  [466, 476) : 103.5
# High = Close + 0.5, Low = Close - 0.5, constant volume 200k.
#
# Screen expectations (construction arithmetic): one episode, climax=439,
# ar=446, breakout=465. First legal look with skip=5:
#   clock 20 -> max(446+20+4, 439+20+5) = 470  (> 465: not watched pre-breakout)
#   clock 8  -> max(446+8+4,  439+8+5)  = 458  (< 465: watchable)
#   clock 40 -> max(490, 484) = 490 >= 476 bars: pending
_PEAK, _AR, _BRK, _N = 439, 446, 465, 476


def _pole_frame():
    closes = np.empty(_N)
    closes[:400] = 40 + 10 * np.arange(400) / 399
    closes[400:440] = 50 + 50 * np.arange(40) / 39
    closes[440:447] = np.linspace(98, 88.5, 7)
    shelf = np.arange(447, 465)
    closes[447:465] = np.where(shelf % 2 == 0, 90.0, 92.0)
    closes[465] = 104.0
    closes[466:] = 103.5
    idx = pd.bdate_range("2024-06-03", periods=_N)
    return pd.DataFrame({"Open": closes, "High": closes + 0.5,
                         "Low": closes - 0.5, "Close": closes,
                         "Volume": 200_000.0}, index=idx)


def _drift_frame():
    closes = 50 + 15 * np.arange(_N) / (_N - 1)          # +30% over 2y: no pole
    idx = pd.bdate_range("2024-06-03", periods=_N)
    return pd.DataFrame({"Open": closes, "High": closes + 0.4,
                         "Low": closes - 0.4, "Close": closes,
                         "Volume": 200_000.0}, index=idx)


@pytest.fixture(scope="module")
def frames():
    return {"POLE": _pole_frame(), "DRIFT": _drift_frame()}


@pytest.fixture(scope="module")
def result(frames):
    return census.run_census(frames, clocks=[20, 8, 40])


def test_screen_finds_exactly_the_hand_reasoned_episode(frames):
    eps = census.screen_episodes(frames)
    assert len(eps) == 1
    ep = eps[0]
    idx = frames["POLE"].index
    assert ep["ticker"] == "POLE"
    assert ep["climax_date"] == str(idx[_PEAK].date())
    assert ep["ar_date"] == str(idx[_AR].date())
    assert ep["breakout_date"] == str(idx[_BRK].date())
    assert ep["gain"] == pytest.approx(100.5 / 49.5 - 1, abs=0.01)
    assert ep["depth"] == pytest.approx((100.5 - 88.0) / 100.5, abs=0.005)


def test_first_legal_look_arithmetic(frames):
    assert settings.STRUCTURE_EDGE_SKIP_BARS == 5      # the arithmetic's basis
    ep = census.screen_episodes(frames)[0]
    # The synthetic dip DEEPENS monotonically into its final AR (446), so the
    # as-of-consistent walk and the final-AR closed form agree here — the
    # hand-pinned values are the walls themselves.
    assert census.first_legal_look(ep, 20, frames["POLE"]) == 470
    assert census.first_legal_look(ep, 8, frames["POLE"]) == 458


def test_first_legal_look_is_asof_consistent_not_hindsight():
    # A LATE-deepening reaction (2026-08-17 review, McKinney): bar 440
    # confirms with a shallow low (94.5), bars 441-452 hold above it, bar 453
    # prints the deeper FINAL low (88.5). At clock 8 (skip 5) the walk clears
    # the shallow running AR's age wall on day 452 — before the deep low even
    # exists — so the first legal look is 452; the refuted hindsight form
    # (final AR 453) would have claimed max(453+8+4, 439+8+5) = 465, a
    # 13-session bias on exactly the short clocks the ruling sweeps.
    n = 470
    closes = np.empty(n)
    closes[:400] = 40 + 10 * np.arange(400) / 399
    closes[400:440] = 50 + 50 * np.arange(40) / 39
    closes[440] = 95.0                     # confirms: thr = 100.5 * 0.95
    closes[441:453] = 96.5
    closes[453] = 89.0                     # the late, deeper final AR
    closes[454:] = 92.0
    idx = pd.bdate_range("2024-06-03", periods=n)
    frame = pd.DataFrame({"Open": closes, "High": closes + 0.5,
                          "Low": closes - 0.5, "Close": closes,
                          "Volume": 200_000.0}, index=idx)
    eps = census.ticker_episodes("LATE", frame, census.POLE_MIN_GAIN,
                                 census.POLE_WINDOW_BARS)
    ep = next(e for e in eps if e["climax_date"] == str(idx[439].date()))
    assert ep["ar_date"] == str(idx[453].date())     # hindsight identity kept
    assert census.first_legal_look(ep, 8, frame) == 452   # the as-of answer


def test_clock_walls_pending_and_absence_rows(result, frames):
    idx = frames["POLE"].index
    by_clock = {r["clock"]: r for r in result["rows"] if r["ticker"] == "POLE"}
    assert by_clock[20]["verdict"] == "not_watched_clock"
    assert by_clock[20]["first_legal_look"] == str(idx[470].date())
    assert by_clock[20]["watchable_pre_breakout"] is False
    assert by_clock[40]["verdict"] == "pending"
    assert by_clock[40]["first_legal_look"] is None
    assert by_clock[8]["watchable_pre_breakout"] is True
    assert by_clock[8]["verdict"] in ("elected_episode", "elected_other",
                                      "no_election", "refused_universe")


def test_breakout_on_the_first_legal_look_is_not_watched():
    # EC-34, the census half (2026-08-17 review, finding 11): the frozen MAN
    # story is an EQUALITY — first legal look ON breakout day — and
    # watchability is STRICTLY-before; a one-bar flip of the comparison
    # would inflate exactly the column the clock ruling reads.
    brk = 460                                 # == first legal look at clock 10
    n = 476
    closes = np.empty(n)
    closes[:400] = 40 + 10 * np.arange(400) / 399
    closes[400:440] = 50 + 50 * np.arange(40) / 39
    closes[440:447] = np.linspace(98, 88.5, 7)
    shelf = np.arange(447, brk)
    closes[447:brk] = np.where(shelf % 2 == 0, 90.0, 92.0)
    closes[brk] = 104.0        # departs the ruled wall (100.5 + 2.5) decisively
    closes[brk + 1:] = 103.5
    idx = pd.bdate_range("2024-06-03", periods=n)
    frame = pd.DataFrame({"Open": closes, "High": closes + 0.5,
                          "Low": closes - 0.5, "Close": closes,
                          "Volume": 200_000.0}, index=idx)
    result = census.run_census({"EDGE": frame}, clocks=[10, 9])
    by_clock = {r["clock"]: r for r in result["rows"]}
    on_the_day = by_clock[10]                 # look 460 == breakout 460
    assert on_the_day["first_legal_look"] == on_the_day["breakout"]
    assert on_the_day["watchable_pre_breakout"] is False
    assert on_the_day["verdict"] == "not_watched_clock"
    one_before = by_clock[9]                  # look 459 < breakout 460
    assert one_before["watchable_pre_breakout"] is True
    assert one_before["verdict"] != "not_watched_clock"


def test_verdicts_are_the_closed_set_and_counts_add_up(result):
    for row in result["rows"]:
        assert row["verdict"] in census.VERDICTS
    for clock in (20, 8, 40):
        counts = result["per_clock"][str(clock)]
        assert sum(counts[v] for v in census.VERDICTS) == result["episodes"]


def test_forward_horizons_start_at_the_clock_and_partition(result):
    row = next(r for r in result["rows"] if r["clock"] == 8)
    # The frame is CONSTRUCTED to pass prep — if a prep change ever starts
    # refusing it, this battery's only horizon coverage must fail LOUDLY,
    # never skip itself away (2026-08-17 review, Beck).
    assert row["verdict"] != "refused_universe", \
        "synthetic frame no longer passes universe prep — rebuild it"
    # as-of pos 458; h10 -> 468 exists (complete), h20 -> 478 >= 476 (partial).
    assert row["fwd_10_complete"] is True and row["fwd_10"] > 0
    assert row["fwd_20"] is None and row["fwd_20_complete"] is False


def test_drift_frame_yields_no_rows(result):
    assert not [r for r in result["rows"] if r["ticker"] == "DRIFT"]


def test_determinism(frames, result):
    again = census.run_census(frames, clocks=[20, 8, 40])
    assert json.dumps(again, sort_keys=True) == json.dumps(result, sort_keys=True)


def test_identity_stamps(result):
    assert len(result["engine_config_version"]) == 64
    assert len(result["marks_fingerprint"]) == 64      # the real (empty) artifact
    assert result["pricing"]["elections_planned"] == result["episodes"] * 3


def test_lookahead_tripwire_voids_and_speaks(frames, monkeypatch, capsys):
    assert census._no_lookahead(frames["POLE"], frames["POLE"].index[-1])
    assert not census._no_lookahead(frames["POLE"], frames["POLE"].index[100])

    def poisoned(raw, as_of):                          # frame past its as-of
        return (frames["POLE"], 1.0), None
    monkeypatch.setattr(census, "prepared_frame_with_reason", poisoned)
    void = census.run_census(frames, clocks=[8])
    assert void["tripwire"].startswith("VOID: lookahead")
    census.report(void)                                # the verdict must PRINT
    out = capsys.readouterr().out
    assert "VOID" in out and "do not rule" in out


def test_sealed_out_path_refused(tmp_path):
    sealed = os.path.join(str(REPO_ROOT), "docs", "marks", "census.json")
    with pytest.raises(ValueError, match="sealed"):
        census.save({"rows": []}, sealed)
    fine = tmp_path / "census.json"
    census.save({"rows": []}, str(fine))               # a scratch path is fine
    assert json.loads(fine.read_text())["rows"] == []


# ── the departure wall (dark knob; S1 misfile evidence, 2026-08-18) ─────────

def _hug_frame():
    """The pole frame with a peak-hugging crossing (0.2 above the 100.5
    peak, inside one ATR) before the real departure close at bar 465."""
    closes = _pole_frame()["Close"].to_numpy().copy()
    closes[455:465] = 100.7          # the hug: 0.2 above the peak, ~ATR 1-2
    closes[465] = 106.0              # the departure: > peak + 1*ATR10
    idx = pd.bdate_range("2024-06-03", periods=_N)
    return pd.DataFrame({"Open": closes, "High": closes + 0.5,
                         "Low": closes - 0.5, "Close": closes,
                         "Volume": 200_000.0}, index=idx)


def test_departure_wall_ignores_peak_hugging_crossings(monkeypatch):
    # The drift-up misfile, hand-reasoned: closes crossing the pole peak
    # (100.5) by 0.2 — inside one ATR — are base-building; the resolution is
    # the DEPARTURE close. The RULED production value is 1.0 (operator
    # 2026-08-18); 0.0 is the retained legacy close-above-peak branch.
    from engine_alpha.structure.context.power_play import ticker_episodes

    df = _hug_frame()
    assert settings.POWER_PLAY_BREAKOUT_DEPARTURE_ATR == 1.0   # the ruling
    departed = ticker_episodes("HUG", df, 0.9, 40)
    assert [e["peak"] for e in departed] == [_PEAK]
    assert departed[0]["breakout"] == 465         # only the departure resolves

    monkeypatch.setattr(settings, "POWER_PLAY_BREAKOUT_DEPARTURE_ATR", 0.0)
    legacy = ticker_episodes("HUG", df, 0.9, 40)
    assert [e["peak"] for e in legacy] == [_PEAK]     # same episode identity
    assert legacy[0]["ar"] == departed[0]["ar"]
    assert legacy[0]["breakout"] == 455           # the hug bar resolved it then


def test_run_overrides_scope_the_screen_not_just_the_elections():
    # The first wall A/B ran as a silent no-op: the lever wrapped elections
    # while the breakout wall is consumed at SCREEN time. Pin the fix: an
    # override to the LEGACY wall must land in the sidecar's own rows
    # (production is the ruled departure wall, so the two runs differ).
    df = _hug_frame()
    legacy = census.run_census(
        {"HUG": _hug_frame()}, clocks=[8],
        extra_overrides={"POWER_PLAY_BREAKOUT_DEPARTURE_ATR": 0.0})
    assert legacy["rows"][0]["breakout"] == str(df.index[455].date())
    production = census.run_census({"HUG": _hug_frame()}, clocks=[8])
    assert production["rows"][0]["breakout"] == str(df.index[465].date())


# ── the experiment lever (--override; occupancy relaxation, 2026-08-18) ─────

def test_override_rejects_unknown_settings_names():
    # A typo'd name must die at argv parsing — never run an hours-long sweep
    # under a no-op "relaxation".
    with pytest.raises(SystemExit):
        census.main(["--override", "NOT_A_REAL_SETTING=1", "--plan"])


def test_overrides_reach_the_election_and_stamp_the_sidecar(frames, monkeypatch):
    captured = []
    real = census.read_structure_under

    def spy(df, atr, overrides):
        captured.append(dict(overrides))
        return real(df, atr, overrides)

    monkeypatch.setattr(census, "read_structure_under", spy)
    extra = {"EQ_MIN_COVERAGE": 0.0}
    result = census.run_census(frames, clocks=[8], extra_overrides=extra)
    # Stamped: a relaxed run can never masquerade as the production read.
    assert result["params"]["extra_overrides"] == extra
    # Reached: every election ran under the derived clock keys PLUS the lever.
    assert captured and all(o.get("EQ_MIN_COVERAGE") == 0.0 for o in captured)
    assert all(o.get("MIN_BASE_DAYS") == 8 for o in captured)
