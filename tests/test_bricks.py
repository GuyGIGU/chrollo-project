import numpy as np
import pandas as pd

from core.structure.bricks import (
    EquilibriumBox,
    RootSwing,
    _enforce_bc_downswing,
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


def test_validate_equilibrium_trace_narrates_the_pair_cascade():
    # A wide climax pair descending into a genuinely worked range: the cascade
    # must record the wide framing rejected by NAME and the worked pair elected
    # — the engine is never blind to why it chose the pair it chose.
    crash = [120, 118, 140, 120, 110, 104]            # one-way leg into the base
    worked = [101, 103, 105, 107, 109, 107, 105, 103] * 4
    df = _ohlc_from_closes(crash + worked)
    root = RootSwing("BC", 0, 1, 141.0, 100.0, 0.29, 1)

    trace: list = []
    box = validate_equilibrium(df, root, 1.0, trace=trace)

    assert box is not None
    assert trace, "the election must narrate its cascade"
    elected = [r for r in trace if r["verdict"] == "elected"]
    assert len(elected) == 1
    # bars are df-positional: the elected pair IS the box the engine returned
    assert elected[0]["cand_start"] == box.start_bar
    assert elected[0]["R"] == box.R and elected[0]["S"] == box.S
    assert "earliest-of-valid" in elected[0]["detail"]
    # the wide crash framing was examined and rejected with a named gate
    rejected = [r for r in trace if r["verdict"] == "rejected"]
    assert any(r["stage"] == "width" for r in rejected)
    assert all(r["stage"] and r["detail"] for r in rejected)


def test_backext_extends_elected_start_to_the_earliest_shared_rail_pivot(monkeypatch):
    # Gap #3: TWO early valleys touch the elected S rail (Low 100 = S) before
    # the anchor pair, every bar in between inside the buffered band. The
    # election alone can't propose either start (pinned to the anchor pair);
    # the flag-gated shared-rail back-extension must walk onto the EARLIEST
    # qualifying pivot (bar 1), not the nearer one (bar 4).
    from config import settings

    pre = [105, 101, 105, 106, 101, 106]      # S-touch valleys @1 AND @4
    worked = [101, 103, 105, 107, 109, 107, 105, 103] * 4
    df = _ohlc_from_closes(pre + worked)
    root = RootSwing("BC", 0, 0, 110.0, 100.0, 0.1, 0)

    monkeypatch.setattr(settings, "BOX_BACKEXT_ENABLED", False, raising=False)
    baseline = validate_equilibrium(df, root, 1.0)
    assert baseline is not None
    pinned_start = baseline.start_bar
    assert pinned_start > 4                    # the pair pins past both valleys

    monkeypatch.setattr(settings, "BOX_BACKEXT_ENABLED", True, raising=False)
    trace: list = []
    box = validate_equilibrium(df, root, 1.0, trace=trace)

    assert box is not None
    assert box.start_bar == 1                  # the EARLIEST pivot, not bar 4
    assert box.R == baseline.R and box.S == baseline.S   # rails untouched
    assert box.base_len == baseline.base_len + (pinned_start - 1)
    elected = [r for r in trace if r["verdict"] == "elected"]
    assert len(elected) == 1
    assert elected[0]["backext_bars"] == pinned_start - 1
    assert "shared-rail" in elected[0]["detail"]


def test_backext_requires_a_band_conforming_span(monkeypatch):
    # An early S-touching valley, but a spike between it and the elected start
    # breaks band conformance — the extension must NOT bridge across
    # non-conforming bars (the shakeout/upthrust guard; note WDI-class descent
    # legs are excluded by the rail re-touch requirement, not by this check —
    # they band-conform but never re-touch a rail).
    from config import settings

    pre = [105, 101, 105, 113, 105, 106]      # spike @3: High 114 > R + buf
    worked = [101, 103, 105, 107, 109, 107, 105, 103] * 4
    df = _ohlc_from_closes(pre + worked)
    root = RootSwing("BC", 0, 0, 110.0, 100.0, 0.1, 0)

    monkeypatch.setattr(settings, "BOX_BACKEXT_ENABLED", True, raising=False)
    trace: list = []
    box = validate_equilibrium(df, root, 1.0, trace=trace)

    assert box is not None
    assert box.R == 110.0 and box.S == 100.0
    assert box.start_bar > 3                   # never extended across the spike
    elected = [r for r in trace if r["verdict"] == "elected"]
    assert len(elected) == 1
    assert "backext_bars" not in elected[0]


def _rail_frame(bars):
    """Hand-built OHLC frame for direct backext_shared_rail unit tests:
    ``bars`` is a list of (high, low) tuples."""
    return pd.DataFrame({
        "Open": [(h + l) / 2 for h, l in bars],
        "High": [h for h, l in bars],
        "Low": [l for h, l in bars],
        "Close": [(h + l) / 2 for h, l in bars],
        "Volume": [1000.0] * len(bars),
    })


def test_backext_pivot_must_touch_its_own_rail_kind(monkeypatch):
    # A VALLEY hovering at R (its Low ~ R after an upthrust: high-shelf drift
    # under the rail, not worked support) must NOT anchor an extension — rail
    # matching is kind-aware (peak~R / valley~S), the worked-cause-vs-drift
    # distinction the lever exists for. The span from the valley conforms, so
    # only the kind check blocks; a kind-blind mutation would extend to bar 2.
    from config import settings
    from core.structure.box_primitives import backext_shared_rail

    bars = [
        (112.0, 108.0),   # 0
        (115.0, 111.0),   # 1: upthrust peak — way above R, no match
        (110.3, 109.8),   # 2: valley, Low 109.8 within tol of R=110 — wrong rail
        (110.2, 110.0),   # 3
        (109.0, 108.0),   # 4   monotone drift down to cand_start:
        (107.5, 106.0),   # 5   no further pivots, span [2:8] fully
        (106.5, 105.0),   # 6   band-conforming
        (106.4, 104.5),   # 7
    ]
    eq_df = _rail_frame(bars)
    monkeypatch.setattr(settings, "BOX_BACKEXT_ENABLED", True, raising=False)

    assert backext_shared_rail(eq_df, 110.0, 100.0, 8, 1.0) == 8


def test_backext_span_includes_the_pivot_bar_and_the_last_bar(monkeypatch):
    # Conformance is judged over [pivot_bar, cand_start): a wide shakeout bar
    # at EITHER edge must block the extension — the qualifying pivot's own bar
    # (its High can breach R+buf even while its Low touches S) and the bar
    # just before the pinned start.
    from config import settings
    from core.structure.box_primitives import backext_shared_rail

    monkeypatch.setattr(settings, "BOX_BACKEXT_ENABLED", True, raising=False)

    filler = [(106.0, 104.0), (105.5, 103.8), (106.2, 104.2),
              (105.8, 104.0), (106.0, 104.1), (105.9, 104.0)]

    # Pivot bar itself breaches: valley Low 99.8 touches S, but High 111 > R+buf.
    wide_pivot = [(105.0, 100.4), (111.0, 99.8)] + filler
    assert backext_shared_rail(_rail_frame(wide_pivot), 110.0, 100.0, 8, 1.0) == 8

    # Right edge breaches: clean S-touch valley @1, spike at cand_start - 1.
    spike_edge = [(105.0, 100.4), (105.0, 99.8)] + filler[:-1] + [(111.2, 104.0)]
    assert backext_shared_rail(_rail_frame(spike_edge), 110.0, 100.0, 8, 1.0) == 8

    # Control: the same clean S-touch valley with a fully conforming span DOES
    # anchor the extension (proves the two rejections above are the breaches).
    clean = [(105.0, 100.4), (105.0, 99.8)] + filler
    assert backext_shared_rail(_rail_frame(clean), 110.0, 100.0, 8, 1.0) == 1


def test_backext_applies_to_the_diagnostic_mirror_too(monkeypatch):
    # The detect_boxes/find_outer_box path (phase_b_zigzag) must frame the SAME
    # extended box as the live reader, or diagnostic tools drift from
    # production when the flag is on.
    from config import settings
    from core.structure.box_primitives import phase_b_zigzag

    pre = [105, 101, 105, 106, 105, 106]
    worked = [101, 103, 105, 107, 109, 107, 105, 103] * 4
    df = _ohlc_from_closes(pre + worked)
    eval_df = df.iloc[:-5]           # the frame find_outer_box hands it

    monkeypatch.setattr(settings, "BOX_BACKEXT_ENABLED", False, raising=False)
    off = phase_b_zigzag(eval_df, 0, len(df), atr_override=1.0)
    assert len(df) - off[0] > 1      # pinned to the anchor pair

    monkeypatch.setattr(settings, "BOX_BACKEXT_ENABLED", True, raising=False)
    on = phase_b_zigzag(eval_df, 0, len(df), atr_override=1.0)
    assert len(df) - on[0] == 1      # the shared-rail pivot, same as the live reader
    assert on[1] == off[1] and on[2] == off[2]   # rails untouched


def test_backext_flag_off_is_inert(monkeypatch):
    # Flag OFF: byte-identical to the pinned election (the shadow guard's
    # invariant, asserted here at unit level too — regardless of the shipped
    # default, which the operator flips).
    from config import settings

    pre = [105, 101, 105, 106, 105, 106]
    worked = [101, 103, 105, 107, 109, 107, 105, 103] * 4
    df = _ohlc_from_closes(pre + worked)
    root = RootSwing("BC", 0, 0, 110.0, 100.0, 0.1, 0)

    monkeypatch.setattr(settings, "BOX_BACKEXT_ENABLED", False, raising=False)
    trace: list = []
    box = validate_equilibrium(df, root, 1.0, trace=trace)

    assert box is not None
    assert box.start_bar > 1
    elected = [r for r in trace if r["verdict"] == "elected"]
    assert len(elected) == 1
    assert "backext_bars" not in elected[0]
    assert "shared-rail" not in (elected[0]["detail"] or "")


def test_validate_equilibrium_trace_explains_a_no_box_rejection():
    # When no pair qualifies, the cascade says WHY for every pair examined —
    # a "no_box" outcome is a narrated verdict, not a silent drop. (The frame
    # must be long enough to reach pair enumeration: mid-hugging chop that
    # fails occupancy/coverage on every framing.)
    chop = [100, 102] + [106, 109, 107, 108] * 7
    df = _ohlc_from_closes(chop)
    root = RootSwing("BC", 0, 0, 110.0, 100.0, 0.1, 0)

    trace: list = []
    assert validate_equilibrium(df, root, 1.0, trace=trace) is None
    assert trace, "rejection must still narrate the pairs it examined"
    assert all(r["verdict"] == "rejected" for r in trace)
    assert all(r["stage"] and r["detail"] for r in trace)


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


def test_find_spring_accepts_phase_c_spring(_flat_ohlc):
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


def test_find_spring_returns_none_for_shallow_undercut(_flat_ohlc):
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


def _lps_frame_with_window(window):
    """Build an LPS-shaped frame whose final window is the given (H, L, C) bars."""
    rows = []
    for _ in range(26):
        rows.append({
            "Open": 105.0, "High": 110.0, "Low": 100.0, "Close": 105.0,
            "Spread": 10.0, "Volume": 1000.0, "Vol_50": 1000.0,
        })
    for high, low, close in window:
        rows.append({
            "Open": close, "High": high, "Low": low, "Close": close,
            "Spread": high - low, "Volume": 500.0, "Vol_50": 1000.0,
        })
    return pd.DataFrame(rows)


def test_find_lps_diagnose_returns_lps_and_rejects_tuple(monkeypatch):
    monkeypatch.setattr("config.settings.LPS_LENGTH_MIN", 4)
    monkeypatch.setattr("config.settings.LPS_LENGTH_MAX", 4)
    df = _lps_frame(lps_volume=500.0)
    box = _box(start_bar=26, base_len=4, r_anchor_bar=26, s_anchor_bar=26)

    lps, rejects = find_lps(df, box, 2.0, diagnose=True)

    assert lps is not None          # same election as the non-diagnose path
    assert rejects is not None      # the detector's reject counter rides along


def test_find_lps_diagnose_reports_rejects_when_none(monkeypatch):
    monkeypatch.setattr("config.settings.LPS_LENGTH_MIN", 4)
    monkeypatch.setattr("config.settings.LPS_LENGTH_MAX", 4)
    df = _lps_frame(lps_volume=950.0)   # high pullback volume -> vol_contraction reject
    box = _box(start_bar=26, base_len=4, r_anchor_bar=26, s_anchor_bar=26)

    lps, rejects = find_lps(df, box, 2.0, diagnose=True)

    assert lps is None
    assert sum(rejects.values()) >= 1   # the trace can report WHY it failed


def test_find_lps_peak_down_gate_on_rejects_trough_not_last(monkeypatch):
    """Flag ON rejects a window that ends on an up-move (operator definition:
    LPS = first-bar High -> last-bar Low must be a peak that goes down)."""
    monkeypatch.setattr("config.settings.LPS_LENGTH_MIN", 4)
    monkeypatch.setattr("config.settings.LPS_LENGTH_MAX", 4)
    monkeypatch.setattr("config.settings.LPS_REQUIRE_PEAK_DOWN", True)
    monkeypatch.setattr("config.settings.LPS_PEAK_DOWN_TOL_BOX", 0.10)
    df = _lps_frame_with_window([
        (108.0, 106.5, 107.0),
        (107.0, 104.5, 105.5),
        (106.0, 103.5, 104.0),
        (105.5, 105.0, 105.2),  # last_low far above window_low
    ])
    box = _box(start_bar=26, base_len=4, r_anchor_bar=26, s_anchor_bar=26)
    assert find_lps(df, box, 2.0) is None


def test_find_lps_peak_down_gate_on_rejects_peak_not_first(monkeypatch):
    """Flag ON rejects a window whose peak is NOT the first bar (price climbs
    into a later high before pulling back — the GSL/MTX/TRIN/PRA shape)."""
    monkeypatch.setattr("config.settings.LPS_LENGTH_MIN", 4)
    monkeypatch.setattr("config.settings.LPS_LENGTH_MAX", 4)
    monkeypatch.setattr("config.settings.LPS_REQUIRE_PEAK_DOWN", True)
    monkeypatch.setattr("config.settings.LPS_PEAK_DOWN_TOL_BOX", 0.10)
    df = _lps_frame_with_window([
        (107.0, 106.0, 106.5),
        (109.0, 105.0, 106.0),  # window_high in the MIDDLE, not the first bar
        (106.0, 103.5, 104.0),
        (105.0, 102.5, 104.0),
    ])
    box = _box(start_bar=26, base_len=4, r_anchor_bar=26, s_anchor_bar=26)
    assert find_lps(df, box, 2.0) is None


def test_find_lps_peak_down_gate_on_still_accepts_clean_peak_to_trough(monkeypatch):
    """Flag ON does NOT touch a clean peak-to-trough LPS (the user-good cases
    GTX/RMAX/SMG/RRR/PLXS/MTRX shape)."""
    monkeypatch.setattr("config.settings.LPS_LENGTH_MIN", 4)
    monkeypatch.setattr("config.settings.LPS_LENGTH_MAX", 4)
    monkeypatch.setattr("config.settings.LPS_REQUIRE_PEAK_DOWN", True)
    monkeypatch.setattr("config.settings.LPS_PEAK_DOWN_TOL_BOX", 0.10)
    df = _lps_frame_with_window([
        (108.0, 106.5, 107.0),  # first bar IS the peak
        (107.0, 105.0, 105.5),
        (106.0, 103.5, 104.0),
        (105.0, 102.5, 104.0),  # last bar IS the trough
    ])
    box = _box(start_bar=26, base_len=4, r_anchor_bar=26, s_anchor_bar=26)
    assert find_lps(df, box, 2.0) is not None


def test_find_lps_rescue_markup_gate_on_rejects_steep_runup(monkeypatch):
    """Gate ON rejects a rising_support_shelf that is really a steep markup leg
    (OHI-class: the low merely launched from support, then price ran up to a new
    high). net advance (last Close - first Close)/box = (105.5-101.5)/10 = 0.40."""
    monkeypatch.setattr("config.settings.LPS_LENGTH_MIN", 4)
    monkeypatch.setattr("config.settings.LPS_LENGTH_MAX", 4)
    monkeypatch.setattr("config.settings.LPS_SCAN_OFFSET_MAX", 1)
    monkeypatch.setattr("config.settings.LPS_RESCUE_MAX_ADVANCE_BOX", 0.21)
    df = _lps_frame_with_window([
        (103.0, 101.0, 101.5),   # window low at support; launch point
        (104.0, 102.0, 103.0),
        (105.0, 103.0, 104.0),
        (106.0, 104.0, 105.5),   # last_low >> window_low (rescue shape), closes near a new high
    ])
    box = _box(start_bar=26, base_len=4, r_anchor_bar=26, s_anchor_bar=26)
    assert find_lps(df, box, 2.0) is None


def test_find_lps_rescue_markup_gate_off_is_unchanged(monkeypatch):
    """Gate OFF (None = default) leaves the rescue untouched: the same rising
    shelf is still elected, so the gate is recall-safe by default."""
    monkeypatch.setattr("config.settings.LPS_LENGTH_MIN", 4)
    monkeypatch.setattr("config.settings.LPS_LENGTH_MAX", 4)
    monkeypatch.setattr("config.settings.LPS_SCAN_OFFSET_MAX", 1)
    monkeypatch.setattr("config.settings.LPS_RESCUE_MAX_ADVANCE_BOX", None)
    df = _lps_frame_with_window([
        (103.0, 101.0, 101.5),
        (104.0, 102.0, 103.0),
        (105.0, 103.0, 104.0),
        (106.0, 104.0, 105.5),
    ])
    box = _box(start_bar=26, base_len=4, r_anchor_bar=26, s_anchor_bar=26)
    assert find_lps(df, box, 2.0) is not None


def test_find_lps_rescue_markup_gate_on_keeps_gradual_shelf(monkeypatch):
    """Gate ON does NOT touch a gradual (near-flat) ascending-support shelf --
    the genuine rising_support_shelf the rescue exists to catch. net advance
    (102.2-102.0)/10 = 0.02, well under the 0.21 ceiling."""
    monkeypatch.setattr("config.settings.LPS_LENGTH_MIN", 4)
    monkeypatch.setattr("config.settings.LPS_LENGTH_MAX", 4)
    monkeypatch.setattr("config.settings.LPS_SCAN_OFFSET_MAX", 1)
    monkeypatch.setattr("config.settings.LPS_RESCUE_MAX_ADVANCE_BOX", 0.21)
    df = _lps_frame_with_window([
        (103.0, 101.0, 102.0),   # window low at support
        (103.2, 101.5, 102.2),
        (103.4, 102.0, 102.3),
        (103.0, 101.5, 102.2),   # last_low > window_low (rescue), near-flat closes
    ])
    box = _box(start_bar=26, base_len=4, r_anchor_bar=26, s_anchor_bar=26)
    assert find_lps(df, box, 2.0) is not None


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


def test_enforce_bc_downswing_repairs_upswing_overlay():
    # A BC climax stranded at a low altitude (80) wired to a box-level AR (110)
    # paints an up-swing; the guard relocates the climax to the run-up high (120).
    closes = [100.0] * 130
    closes[90] = 120.0    # prominent run-up high feeding the box
    closes[95] = 80.0     # stale low-altitude BC "climax"
    closes[100] = 110.0   # box-level reaction the AR was wired to
    df = _ohlc_from_closes(closes, band=0.0)
    root = RootSwing("BC", 95, 100, 120.0, 80.0, 0.1, 5)
    box = _box(start_bar=100, base_len=30)

    climax, ar = _enforce_bc_downswing(df, root, box, 95, 100)
    assert (climax, ar) == (90, 100)
    assert df["High"].iloc[climax] > df["High"].iloc[ar]   # now a genuine DOWN swing


def test_enforce_bc_downswing_leaves_valid_downswing():
    closes = [100.0] * 130
    closes[95] = 120.0    # BC climax already a real high
    closes[100] = 105.0   # reaction below it
    df = _ohlc_from_closes(closes, band=0.0)
    root = RootSwing("BC", 95, 100, 120.0, 105.0, 0.1, 5)
    box = _box(start_bar=100, base_len=30)

    assert _enforce_bc_downswing(df, root, box, 95, 100) == (95, 100)


def test_enforce_bc_downswing_leaves_sc_upswing():
    # Selling climax (low) -> rally high is a legitimately UP overlay; untouched.
    closes = [100.0] * 130
    closes[95] = 80.0
    closes[100] = 110.0
    df = _ohlc_from_closes(closes, band=0.0)
    root = RootSwing("SC", 95, 100, 110.0, 80.0, 0.1, 5)
    box = _box(start_bar=100, base_len=30)

    assert _enforce_bc_downswing(df, root, box, 95, 100) == (95, 100)


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
