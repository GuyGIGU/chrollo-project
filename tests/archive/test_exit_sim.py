"""Unit tests for core.backtest.exit_sim — scaled-exit R accounting."""
import pytest

from core.backtest import exit_sim as xs

LADDER = xs.DEFAULT_LADDER  # (3,0.5),(6,0.25),(8,0.25)


def _sim(opens, highs, lows, closes, entry=100.0, stop=90.0, mode="fixed", max_bars=60):
    return xs.simulate_scaled_exit(opens, highs, lows, closes, entry, stop,
                                   ladder=LADDER, stop_mode=mode, max_bars=max_bars)


def test_full_ladder_hits_five_r():
    # entry 100, stop 90, R=10 -> targets at 130/160/180, all hit bar 0.
    r = _sim([100], [185], [99], [180])
    assert r["reason"] == "targets"
    assert abs(r["realized_r"] - 5.0) < 1e-9          # 0.5*3 + 0.25*6 + 0.25*8
    assert abs(r["realized_ret"] - 0.5) < 1e-9        # 5R * (10/100)
    assert r["targets_hit"] == [3.0, 6.0, 8.0]


def test_immediate_stop_is_minus_one_r():
    # bar0 benign; bar1 low pierces the stop -> full -1R.
    r = _sim([100, 101], [105, 101], [99, 88], [102, 89])
    assert r["reason"] == "stop"
    assert abs(r["realized_r"] + 1.0) < 1e-9


def test_gap_down_through_stop_is_worse_than_minus_one():
    r = _sim([100, 85], [105, 86], [99, 84], [102, 85])
    assert r["reason"] == "gap_stop"
    assert abs(r["realized_r"] + 1.5) < 1e-9          # r_of(85) = -1.5


def test_entry_bar_low_does_not_stop():
    # A deep low on the ENTRY bar must NOT trigger the stop (low may predate entry).
    r = _sim([100], [131], [70], [130])   # 3R target also hits this bar
    assert 3.0 in r["targets_hit"]
    assert r["realized_r"] > 0             # not stopped despite low 70 < stop 90


def test_first_target_then_stop_fixed():
    # 3R fills bar0 (sell 50%); bar1 stop takes the rest at -1R.
    r = _sim([100, 101], [130, 120], [99, 88], [128, 89], mode="fixed")
    assert 3.0 in r["targets_hit"]
    assert abs(r["realized_r"] - (0.5 * 3.0 + 0.5 * -1.0)) < 1e-9   # +1.0R


def test_first_target_then_breakeven_stop():
    # breakeven: after 3R the stop moves to entry (100); bar1 low 95 stops remainder at 0R.
    r = _sim([100, 101], [130, 120], [99, 95], [128, 110], mode="breakeven")
    assert r["reason"] == "breakeven_stop"
    assert abs(r["realized_r"] - (0.5 * 3.0 + 0.5 * 0.0)) < 1e-9    # +1.5R


def test_horizon_exit_of_remainder():
    # 3R fills bar0; no further target/stop; remainder rides to the last close.
    r = _sim([100, 130], [130, 140], [99, 125], [128, 135], max_bars=2)
    # 0.5 at 3R  +  0.5 at r_of(135)=3.5  = 1.5 + 1.75
    assert r["reason"] == "horizon"
    assert abs(r["realized_r"] - (0.5 * 3.0 + 0.5 * 3.5)) < 1e-9


def test_trailing_runner_captures_beyond_the_cap():
    # ladder 50%@3R + 25%@6R, final 25% trails by 2R. Runner peaks at 11R then
    # reverses; the trail (11-2=9R) fills it at +9R -> 0.5*3+0.25*6+0.25*9 = 5.25R,
    # MORE than the 5.0R the fixed 3/6/8 ladder caps at.
    r = xs.simulate_scaled_exit(
        [100, 156, 206], [160, 210, 206], [99, 150, 170], [155, 205, 175],
        entry=100.0, stop=90.0, ladder=[(3.0, 0.5), (6.0, 0.25)],
        trail_r=2.0, max_bars=60)
    assert r["reason"] == "trail_stop"
    assert abs(r["realized_r"] - 5.25) < 1e-9


def test_trailing_runner_rides_to_horizon_if_never_stopped():
    # Monotonic rise; the trail is never touched, so the runner exits at the last
    # close (245 -> 14.5R): 0.5*3 + 0.25*6 + 0.25*14.5 = 6.625R.
    r = xs.simulate_scaled_exit(
        [100, 156, 196], [160, 200, 250], [99, 155, 195], [155, 195, 245],
        entry=100.0, stop=90.0, ladder=[(3.0, 0.5), (6.0, 0.25)],
        trail_r=2.0, max_bars=3)
    assert r["reason"] == "horizon"
    assert abs(r["realized_r"] - 6.625) < 1e-9


def test_degenerate_and_empty_return_none():
    assert _sim([100], [110], [90], [105], entry=100, stop=100) is None   # R<=0
    assert _sim([], [], [], []) is None


def test_parse_ladder():
    assert xs.parse_ladder("3:0.5,6:0.25,8:0.25") == [(3.0, 0.5), (6.0, 0.25), (8.0, 0.25)]
    with pytest.raises(ValueError):
        xs.parse_ladder("3:0.6,6:0.5")   # sums to 1.1
