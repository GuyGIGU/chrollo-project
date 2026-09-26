"""Unit tests for core.backtest.event_study — calendar-time CAR aggregation."""
import numpy as np
import pandas as pd

from core.backtest import event_study as es


def test_calendar_time_mean_equals_mean_of_date_means_and_deflates_t():
    # Two clustered dates: 3 fires each, perfectly correlated within a date.
    abn = pd.DataFrame({
        "scan_date": ["2022-01-07"] * 3 + ["2022-02-04"] * 3,
        "tier": ["S"] * 6,
        "car_5": [0.10, 0.10, 0.10, -0.02, -0.02, -0.02],
    })
    out = es.aggregate_calendar_time(abn, horizons=[5])
    b = out[5]
    # Calendar-time mean = mean of the two per-date means = mean([0.10, -0.02]).
    assert abs(b["car_mean_ct"] - 0.04) < 1e-12
    assert abs(b["car_mean_cs"] - 0.04) < 1e-12
    assert b["n_dates"] == 2
    assert b["n_fires"] == 6
    # Clustering inflates the naive cross-sectional t above the calendar-time t.
    assert b["t_cs"] is not None and b["t_ct"] is not None
    assert abs(b["t_cs"]) > abs(b["t_ct"])


def test_single_date_has_no_calendar_time_se():
    abn = pd.DataFrame({
        "scan_date": ["2022-01-07"] * 4,
        "car_10": [0.05, 0.07, 0.03, 0.09],
    })
    b = es.aggregate_calendar_time(abn, horizons=[10])[10]
    assert b["n_dates"] == 1
    assert b["se_ct"] is None and b["t_ct"] is None   # need >= 2 dates
    assert abs(b["car_mean_ct"] - 0.06) < 1e-12       # single-date mean


def test_fire_abnormal_returns_matches_hand_computation():
    idx = pd.bdate_range("2022-01-03", periods=6)
    tkr = pd.Series([100.0, 110.0, 121.0, 121.0, 121.0, 121.0], index=idx)
    spy = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0, 100.0], index=idx)  # flat market
    panel = pd.concat({"TKR": tkr.to_frame("Close"),
                       "SPY": spy.to_frame("Close")}, axis=1)
    fires = pd.DataFrame({"ticker": ["TKR"], "scan_date": [idx[0]], "tier": ["A"]})
    abn = es.fire_abnormal_returns(fires, panel, horizons=[1, 2])
    # Flat SPY -> abnormal == raw ticker return.
    assert abs(float(abn["car_1"].iloc[0]) - 0.10) < 1e-9   # 110/100 - 1
    assert abs(float(abn["car_2"].iloc[0]) - 0.21) < 1e-9   # 121/100 - 1


def test_fire_abnormal_subtracts_market():
    idx = pd.bdate_range("2022-01-03", periods=4)
    tkr = pd.Series([100.0, 110.0, 110.0, 110.0], index=idx)
    spy = pd.Series([100.0, 104.0, 104.0, 104.0], index=idx)  # market +4%
    panel = pd.concat({"TKR": tkr.to_frame("Close"),
                       "SPY": spy.to_frame("Close")}, axis=1)
    fires = pd.DataFrame({"ticker": ["TKR"], "scan_date": [idx[0]]})
    abn = es.fire_abnormal_returns(fires, panel, horizons=[1])
    # 10% raw - 4% market = 6% abnormal.
    assert abs(float(abn["car_1"].iloc[0]) - 0.06) < 1e-9


def test_recent_fire_nan_beyond_available_bars():
    idx = pd.bdate_range("2022-01-03", periods=4)
    tkr = pd.Series([100.0, 110.0, 120.0, 130.0], index=idx)
    spy = pd.Series([100.0, 100.0, 100.0, 100.0], index=idx)
    panel = pd.concat({"TKR": tkr.to_frame("Close"),
                       "SPY": spy.to_frame("Close")}, axis=1)
    # Scan on the 3rd bar -> only 1 forward bar exists; horizon 5 must be NaN.
    fires = pd.DataFrame({"ticker": ["TKR"], "scan_date": [idx[2]]})
    abn = es.fire_abnormal_returns(fires, panel, horizons=[1, 5])
    assert not np.isnan(float(abn["car_1"].iloc[0]))
    assert np.isnan(float(abn["car_5"].iloc[0]))


def test_anchor_at_alternate_date_col_for_trigger_gated_read():
    # The trigger-gated read reuses fire_abnormal_returns anchored at trigger_date.
    idx = pd.bdate_range("2022-01-03", periods=8)
    tkr = pd.Series([100, 100, 100, 110, 121, 121, 121, 121], dtype=float, index=idx)
    spy = pd.Series([100, 100, 100, 100, 100, 100, 100, 100], dtype=float, index=idx)
    panel = pd.concat({"TKR": tkr.to_frame("Close"),
                       "SPY": spy.to_frame("Close")}, axis=1)
    # Anchor at the breakout day (idx[3], price 110) instead of the scan day.
    fires = pd.DataFrame({"ticker": ["TKR"], "trigger_date": [idx[3]]})
    abn = es.fire_abnormal_returns(fires, panel, horizons=[1], date_col="trigger_date")
    # From 110 -> 121 is +10% abnormal (flat SPY); confirms the anchor moved.
    assert abs(float(abn["car_1"].iloc[0]) - 0.10) < 1e-9
    assert "trigger_date" in abn.columns


def test_build_event_study_segments_by_tier_and_regime():
    abn = pd.DataFrame({
        "scan_date": ["2022-01-07", "2022-01-07", "2022-02-04", "2022-02-04"],
        "tier": ["S", "A", "S", "A"],
        "spy_trend": ["uptrend", "uptrend", "downtrend", "downtrend"],
        "car_20": [0.12, 0.04, -0.05, 0.01],
    })
    res = es.build_event_study(abn, horizons=[20])
    assert res["horizons"] == [20]
    assert set(res["by_tier"].keys()) == {"S", "A"}
    assert set(res["by_spy_trend"].keys()) == {"uptrend", "downtrend"}
    # Tier S over its two dates: mean([0.12, -0.05]) = 0.035.
    assert abs(res["by_tier"]["S"][20]["car_mean_ct"] - 0.035) < 1e-12
