import numpy as np
import pandas as pd

from core.structure.bricks import (
    EquilibriumBox,
    RootSwing,
    find_inner_box,
    find_lps,
    find_root_swing,
    find_spring,
    resolve_phase_a,
    validate_equilibrium,
)


def _ohlc_from_closes(closes, *, band=1.0, volume=1000.0):
    return pd.DataFrame({
        "Open": list(closes),
        "High": [c + band for c in closes],
        "Low": [c - band for c in closes],
        "Close": list(closes),
        "Volume": [volume] * len(closes),
    })


def _flat_ohlc(n, *, high=101.0, low=99.0, close=100.0, volume=1000.0):
    return pd.DataFrame([
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": volume}
        for _ in range(n)
    ])


def _box(**overrides):
    values = {
        "S": 100.0,
        "R": 110.0,
        "start_bar": 0,
        "base_len": 30,
        "box_width": 0.1,
        "quality": 1.0,
        "r_touches": 3,
        "s_touches": 3,
        "breach_days": 0,
        "r_anchor_bar": 0,
        "s_anchor_bar": 0,
        "n_full_traversals": 2,
        "traversal_density": 0.5,
    }
    values.update(overrides)
    return EquilibriumBox(**values)


def _piecewise_frame(points):
    closes = []
    for (start, start_val), (end, end_val) in zip(points, points[1:]):
        segment = np.linspace(start_val, end_val, end - start + 1)
        if closes:
            segment = segment[1:]
        closes.extend(segment.tolist())
    return _ohlc_from_closes(closes, band=0.0)


def test_find_root_swing_finds_next_anchor_and_can_advance():
    levels = list(np.linspace(50, 70, 210))
    levels += list(np.linspace(70, 100, 25)) + [98, 96, 94, 93, 95]
    levels += [101, 103, 105, 107, 109, 107, 105, 103] * 4
    levels += list(np.linspace(105, 130, 25)) + [127, 124, 121, 120, 122]
    levels += [121, 123, 125, 127, 129, 127, 125, 123] * 4
    df = _ohlc_from_closes([float(x) for x in levels])

    first = find_root_swing(df)
    second = find_root_swing(df, first.ar_bar + 1)

    assert first is not None
    assert first.kind == "BC"
    assert first.climax_bar < first.ar_bar
    assert first.R > first.S
    assert first.reaction_pct >= 0.05
    assert second is not None
    assert second.climax_bar > first.ar_bar


def test_find_root_swing_rejects_when_no_calibrated_anchor():
    df = _ohlc_from_closes([100.0] * 220)

    assert find_root_swing(df) is None


def test_validate_equilibrium_accepts_worked_range():
    worked = [101, 103, 105, 107, 109, 107, 105, 103] * 4
    df = _ohlc_from_closes(worked)
    root = RootSwing("BC", 0, 0, 110.0, 100.0, 0.1, 0)

    box = validate_equilibrium(df, root, 1.0)

    assert box is not None
    assert box.S == 100.0
    assert box.R == 110.0
    assert box.r_touches >= 3
    assert box.s_touches >= 3
    assert box.n_full_traversals >= 2
    assert box.traversal_density >= 0.08


def test_validate_equilibrium_rejects_dead_space_range():
    dead_space = (
        [100, 102]
        + [106, 109, 107, 108, 106, 109, 107, 108] * 2
        + [106, 109, 107, 108, 106, 109]
    )
    df = _ohlc_from_closes(dead_space)
    root = RootSwing("BC", 0, 0, 110.0, 100.0, 0.1, 0)

    assert validate_equilibrium(df, root, 1.0) is None


def test_find_inner_box_returns_tighter_recent_subrange_with_absolute_anchors():
    wide = [100, 106, 112, 118, 116, 110, 104, 102] * 5
    tight = [101, 103, 105, 107, 109, 107, 105, 103] * 5
    df = _ohlc_from_closes(wide + tight)
    parent = _box(start_bar=0, base_len=len(df), box_width=0.18)

    inner = find_inner_box(df, parent, 1.0)

    assert inner is not None
    assert inner.box_width < parent.box_width * 0.75
    assert inner.r_anchor_bar >= inner.start_bar
    assert inner.s_anchor_bar >= inner.start_bar
    assert inner.source in {"midpoint", "inner_climax"}


def test_find_inner_box_returns_none_for_uniformly_wide_base():
    worked = [101, 103, 105, 107, 109, 107, 105, 103] * 10
    df = _ohlc_from_closes(worked)
    parent = _box(start_bar=0, base_len=len(df), box_width=0.10)

    assert find_inner_box(df, parent, 1.0) is None


def test_find_inner_box_start_bar_matches_base_len():
    wide = [100, 106, 112, 118, 116, 110, 104, 102] * 5
    tight = [101, 103, 105, 107, 109, 107, 105, 103] * 5
    df = _ohlc_from_closes(wide + tight)
    parent = _box(start_bar=0, base_len=len(df), box_width=0.18)

    inner = find_inner_box(df, parent, 1.0)

    assert inner is not None
    assert inner.start_bar == len(df) - inner.base_len


def test_find_spring_accepts_phase_c_spring():
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 98.2
    df.loc[95, "Close"] = 98.9
    df.loc[96, "Low"] = 99.1
    df.loc[96, "Close"] = 99.2
    box = _box(S=99.0, R=101.0, start_bar=60, base_len=60, box_width=0.02)

    spring = find_spring(df, box, 1.0)

    assert spring is not None
    assert spring.tip_bar == 95
    assert spring.recovery_bar == 96
    assert spring.undercut_atr == 0.8
    assert spring.recovery_bars == 1
    assert spring.spring_type == "SPRING"


def test_find_spring_returns_none_for_shallow_undercut():
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 98.8
    df.loc[95, "Close"] = 98.9
    df.loc[96, "Close"] = 99.2
    box = _box(S=99.0, R=101.0, start_bar=60, base_len=60, box_width=0.02)

    assert find_spring(df, box, 1.0) is None


def _lps_frame(*, lps_volume):
    rows = []
    for _ in range(26):
        rows.append({
            "Open": 105.0,
            "High": 110.0,
            "Low": 100.0,
            "Close": 105.0,
            "Spread": 10.0,
            "Volume": 1000.0,
            "Vol_50": 1000.0,
        })
    for high, low, close in zip(
        [108.0, 107.0, 106.0, 105.0],
        [106.5, 105.0, 103.5, 102.5],
        [107.0, 105.5, 104.0, 104.0],
    ):
        rows.append({
            "Open": close,
            "High": high,
            "Low": low,
            "Close": close,
            "Spread": high - low,
            "Volume": lps_volume,
            "Vol_50": 1000.0,
        })
    return pd.DataFrame(rows)


def test_find_lps_accepts_compact_phase_d_lps(monkeypatch):
    monkeypatch.setattr("config.settings.LPS_LENGTH_MIN", 4)
    monkeypatch.setattr("config.settings.LPS_LENGTH_MAX", 4)
    df = _lps_frame(lps_volume=500.0)
    box = _box(start_bar=26, base_len=4, r_anchor_bar=26, s_anchor_bar=26)

    lps = find_lps(df, box, 2.0)

    assert lps is not None
    assert lps.low_bar == 29
    assert lps.start_bar == 26
    assert lps.end_bar == 30
    assert lps.zone_type == "INSIDE"
    assert lps.trigger == 105.0
    assert lps.length == 4


def test_find_lps_returns_none_when_detector_rejects(monkeypatch):
    monkeypatch.setattr("config.settings.LPS_LENGTH_MIN", 4)
    monkeypatch.setattr("config.settings.LPS_LENGTH_MAX", 4)
    df = _lps_frame(lps_volume=950.0)
    box = _box(start_bar=26, base_len=4, r_anchor_bar=26, s_anchor_bar=26)

    assert find_lps(df, box, 2.0) is None


def test_resolve_phase_a_prefers_local_bridge_into_box_start():
    df = _piecewise_frame([
        (0, 50.0),
        (20, 70.0),
        (40, 60.0),
        (60, 95.0),
        (80, 85.0),
        (94, 120.0),
        (100, 105.0),
        (120, 135.0),
        (139, 125.0),
    ])
    distant_root = RootSwing("BC", 10, 20, 70.0, 60.0, 0.1, 10)
    box = _box(start_bar=100, base_len=40)

    assert resolve_phase_a(df, distant_root, box, 1.0) == (94, 100)


def test_resolve_phase_a_falls_back_to_segmentation_root():
    df = _piecewise_frame([
        (0, 50.0),
        (50, 80.0),
        (70, 70.0),
        (95, 130.0),
        (110, 100.0),
        (125, 120.0),
        (149, 115.0),
    ])
    raw_root = RootSwing("BC", 10, 20, 70.0, 60.0, 0.1, 10)
    box = _box(start_bar=130, base_len=40)

    assert resolve_phase_a(df, raw_root, box, 1.0) == (95, 110)


def test_resolve_phase_a_last_resort_uses_raw_anchor():
    df = _ohlc_from_closes([100.0] * 80)
    raw_root = RootSwing("BC", 20, 25, 105.0, 100.0, 0.05, 5)
    box = _box(start_bar=50, base_len=30)

    # gap (50-20=30) is within the local bridge window (_SEG_LEAD_IN=60): the raw
    # anchor is local enough, so it is used unchanged.
    assert resolve_phase_a(df, raw_root, box, 1.0) == (20, 35)


def test_resolve_phase_a_localizes_stale_seed():
    # A seed root far beyond the local bridge window (an ancient scan origin) must
    # NOT paint a stale Phase A onto a recent box. With no bridge / segmentation
    # swing to find (flat frame), the fallback synthesizes a LOCAL climax -> AR
    # from the box run-up instead of returning the distant seed climax.
    df = _ohlc_from_closes([100.0] * 260)
    stale_root = RootSwing("BC", 10, 18, 105.0, 100.0, 0.05, 8)
    box = _box(start_bar=240, base_len=20)

    climax, ar = resolve_phase_a(df, stale_root, box, 1.0)
    assert ar == 240                         # AR anchors where Phase B opens
    assert 240 - climax <= 60                # climax is local (within _SEG_LEAD_IN)
    assert climax != stale_root.climax_bar   # specifically not the ancient seed
