"""Event Map mechanical layer — Task 4 guards.

Pins the three load-bearing properties of ``engine_alpha.structure.event_map``:

1. **The in-box slice IS the staircase** — the tape's ``region == "box"`` swings,
   re-based and stripped of tape-only fields, equal ``read_box_staircase`` over
   ``df.iloc[box.start_bar:]`` byte-for-byte (the plan's widen-don't-fork rule).
2. **One walk, provably** — full-frame order-1 pivots filtered to a window equal
   the windowed walk's own pivots (the equality the slicing rests on).
3. **Causality stamps** — ``knowable_bar`` marks real commitment (truncating the
   frame at/after it reproduces the swing identically; before it, the swing is
   absent or provisional), the right-edge swing is ``in_progress``, and NaN bars
   are counted and fail closed.

Synthetic frames only — deterministic, instant. The corpus/panel-scale proof is
the Task-4 capture battery (staircase pre/post diff + tape projection), run as a
build step, not here.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from engine_alpha.structure.box_events import _EVENT_HOLD_MIN_BARS, read_box_staircase
from engine_alpha.structure.event_map import read_role_labels, read_swing_map
from engine_alpha.structure.pivots import _find_pivots

pytestmark = pytest.mark.regression

_TAPE_ONLY = ("region", "describes_bar", "knowable_bar", "in_progress",
              "edge_uncertain")


@dataclass
class _Box:
    start_bar: int
    R: float
    S: float
    base_len: int = 40      # only the > 0 guard reads it here


def _frame_from_path(path):
    """Bars whose High/Low straddle a piecewise path — pivots land exactly on
    the path's local extremes, so the expected skeleton is readable by eye."""
    path = np.asarray(path, dtype=float)
    return pd.DataFrame({"High": path + 0.5, "Low": path - 0.5})


def _zigzag_path(waypoints, n):
    """Piecewise-linear path through (bar, price) waypoints, length n."""
    bars = [b for b, _ in waypoints]
    prices = [p for _, p in waypoints]
    return np.interp(np.arange(n), bars, prices)


def _project_box_swings(tape, start):
    out = []
    for s in tape["swings"]:
        if s["region"] != "box":
            continue
        s = {k: v for k, v in s.items() if k not in _TAPE_ONLY}
        s["bar"] = int(s["bar"]) - start
        out.append(s)
    return out


def _demo_frame():
    """Downtrend into a worked box, with all three wave outcomes on the R rail:
    failed reaches (25/35/58), a held reach (46 — the pullback after it stays
    mid-box for >6 bars), and a right-edge reach (67) still unresolved."""
    n = 72
    path = _zigzag_path(
        [(0, 30.0), (4, 24.0), (7, 27.0), (11, 20.0),           # pre-box downtrend
         (14, 23.0), (18, 11.5),
         (20, 11.0), (25, 14.0), (30, 10.5), (35, 13.8),        # box S~10.5 R~14
         (40, 10.6), (46, 13.9), (52, 12.6), (58, 13.7),
         (63, 11.0), (67, 15.5), (69, 13.9), (71, 17.0)],       # right of the rail
        n)
    return _frame_from_path(path), _Box(start_bar=18, R=14.0, S=10.0)


def test_in_box_slice_is_byte_identical_to_staircase():
    df, box = _demo_frame()
    atr = 1.0
    tape = read_swing_map(df, box, atr)
    stair = read_box_staircase(df.iloc[box.start_bar:], box.R, box.S, atr)

    assert _project_box_swings(tape, box.start_bar) == stair["swings"]
    assert tape["box"] == {
        "n_swings": stair["n_swings"], "trend_state": stair["trend_state"],
        "counts": stair["counts"], "rail_to_rail": stair["rail_to_rail"],
        "is_zigzag": stair["is_zigzag"],
    }
    # The widening is additive: the pre-box trend is now readable too.
    assert tape["pre_box"]["n_swings"] >= 2
    assert all(s["bar"] <= box.start_bar for s in tape["swings"]
               if s["region"] == "pre_box")


def test_box_at_frame_start_has_empty_pre_view():
    df, _ = _demo_frame()
    box = _Box(start_bar=0, R=14.0, S=10.0)
    tape = read_swing_map(df, box, 1.0)
    stair = read_box_staircase(df, box.R, box.S, 1.0)
    assert tape["pre_box"]["n_swings"] == 0
    assert _project_box_swings(tape, 0) == stair["swings"]


def test_one_walk_pivot_window_equality():
    """The slicing hinge: full-frame order-1 pivots restricted to bars > start
    (and re-based) are EXACTLY the windowed walk's pivots."""
    rng = np.random.default_rng(7)
    for _ in range(25):
        mid = np.cumsum(rng.normal(0.0, 1.0, 140)) + 50.0
        spread = rng.uniform(0.2, 1.0, 140)
        highs, lows = mid + spread, mid - spread
        peaks, valleys = _find_pivots(highs, lows, 1)
        for start in (0, 4, 23, 61):
            wp, wv = _find_pivots(highs[start:], lows[start:], 1)
            assert [p - start for p in peaks if p >= start + 1] == wp
            assert [v - start for v in valleys if v >= start + 1] == wv


def test_knowable_bar_marks_real_commitment_and_edge_is_in_progress():
    df, box = _demo_frame()
    tape = read_swing_map(df, box, 1.0)
    swings = tape["swings"]
    assert swings, "demo frame must produce swings"

    committed = [s for s in swings if not s["in_progress"]]
    assert committed, "demo frame must commit swings"
    for s in committed:
        assert s["knowable_bar"] > s["describes_bar"] == s["bar"]
    # The frame's last swing has no committing reversal printed -> provisional.
    assert swings[-1]["in_progress"] and swings[-1]["knowable_bar"] is None
    # Left-edge rule: the frame's first swing is boundary-uncertain.
    assert swings[0].get("edge_uncertain") is True


def test_truncation_reproduces_committed_swings():
    """Contract §7 at the mechanical level: relabeling a truncated frame yields
    exactly the full frame's swings that were knowable inside the cut. (At view
    birth — fewer than 3 raw pivots in a window — the staircase guards emit
    nothing, so cuts start past the demo box's first traversal.)"""
    df, box = _demo_frame()
    full = read_swing_map(df, box, 1.0)

    def _sig(swings):
        return [(s["bar"], s["kind"], s["price"], s["label"], s["region"],
                 s["knowable_bar"]) for s in swings]

    for cut in range(34, len(df) + 1):
        trunc = read_swing_map(df.iloc[:cut], box, 1.0)
        got = _sig(s for s in trunc["swings"] if not s["in_progress"])
        want = _sig(s for s in full["swings"]
                    if s["knowable_bar"] is not None
                    and s["knowable_bar"] <= cut - 1)
        assert got == want, f"cut={cut}"


def test_nan_bars_are_counted_and_fail_closed():
    df, box = _demo_frame()
    df = df.copy()
    df.loc[df.index[40:43], ["High", "Low"]] = np.nan
    tape = read_swing_map(df, box, 1.0)
    assert tape["nan_bars"] == 3
    assert all(s["bar"] not in (40, 41, 42) for s in tape["swings"])


# ---------------------------------------------------------------------------
# Narrative-role layer (Task 5)
# ---------------------------------------------------------------------------

@dataclass
class _FakeLps:
    start_bar: int
    end_bar: int
    low_bar: int
    swing_type: str = "clean_downswing"


def _roles(df, box, atr=1.0, spring=None, lps=None):
    return read_role_labels(df, box, atr, spring=spring, lps=lps)["labels"]


def test_role_layer_requires_injected_bricks_and_honors_none():
    df, box = _demo_frame()
    with pytest.raises(TypeError):
        read_role_labels(df, box, 1.0)          # bricks are NOT optional
    labels = _roles(df, box)
    assert all(lbl["role"] not in ("spring", "lps") for lbl in labels), (
        "injected None must mean 'the engine elected none' — never a re-detect")


def test_wave_labels_are_tri_stated_and_stamped():
    df, box = _demo_frame()
    labels = _roles(df, box)
    waves = [lbl for lbl in labels if lbl["rail"] == "R"]
    assert waves, "demo frame must produce R-rail wave labels"
    for lbl in waves:
        assert lbl["resolution"] in ("held", "failed", "in_progress")
        if lbl["in_progress"]:
            assert lbl["knowable_bar"] is None
        else:
            # verdict + closure both printed, and never before the wave top.
            assert lbl["knowable_bar"] > lbl["anchor_bar"]
        assert not lbl["election_dependent"]
    # The demo tail climbs into the right edge: its final advance is unresolved.
    assert waves[-1]["resolution"] == "in_progress"


def test_held_wave_knowable_covers_hold_window_and_closure():
    """A held wave is knowable no earlier than the END of its printed hold
    window AND no earlier than the bar that stopped it being extendable."""
    df, box = _demo_frame()
    labels = _roles(df, box)
    held = [lbl for lbl in labels
            if lbl["rail"] == "R" and lbl["resolution"] == "held"
            and not lbl["in_progress"]]
    assert held, "demo frame must confirm at least one held wave"
    for lbl in held:
        top = lbl["anchor_bar"]
        assert lbl["knowable_bar"] >= top + _EVENT_HOLD_MIN_BARS


def test_test_labels_stamped_off_valley_commitment():
    df, box = _demo_frame()
    labels = _roles(df, box)
    tape = read_swing_map(df, box, 1.0)
    commits = {s["bar"]: s["knowable_bar"] for s in tape["swings"]
               if s["region"] == "box" and s["kind"] == "valley"}
    tests = [lbl for lbl in labels if lbl["rail"] == "S"
             and lbl["role"] in ("test", "failed", "in_progress")]
    assert tests, "demo frame must produce S-rail test labels"
    for lbl in tests:
        if lbl["in_progress"]:
            continue
        commit = commits.get(lbl["anchor_bar"])
        assert commit is not None and lbl["knowable_bar"] >= commit
        if lbl["resolution"] == "held":
            assert lbl["knowable_bar"] >= lbl["anchor_bar"] + _EVENT_HOLD_MIN_BARS


def test_injected_lps_is_frame_scoped():
    """The elected LPS label is knowable at the FRAME END — each frame's
    election re-issues it — and is flagged election-dependent."""
    df, box = _demo_frame()
    lps = _FakeLps(start_bar=58, end_bar=63, low_bar=63)
    labels = _roles(df, box, lps=lps)
    lps_labels = [lbl for lbl in labels if lbl["role"] == "lps"]
    assert len(lps_labels) == 1
    lbl = lps_labels[0]
    assert lbl["election_dependent"] is True
    assert lbl["resolution"] == "held"
    assert lbl["knowable_bar"] == len(df) - 1

    shorter = df.iloc[:68]
    lbl2 = [x for x in _roles(shorter, box, lps=lps) if x["role"] == "lps"][0]
    assert lbl2["knowable_bar"] == len(shorter) - 1


def test_role_truncate_relabel_invariance():
    """Beck's battery at unit scale: relabel a truncated frame — every
    election-independent label knowable inside the cut is identical."""
    df, box = _demo_frame()
    full = _roles(df, box)

    def _sig(labels, upto):
        return [(l["role"], l["rail"], tuple(l["describes"]), l["anchor_bar"],
                 l["resolution"], l["knowable_bar"])
                for l in labels
                if not l["election_dependent"] and not l["in_progress"]
                and l["knowable_bar"] <= upto]

    for cut in range(34, len(df) + 1):
        trunc = _roles(df.iloc[:cut], box)
        assert _sig(trunc, cut - 1) == _sig(full, cut - 1), f"cut={cut}"


def test_labels_are_chronologically_ordered():
    df, box = _demo_frame()
    labels = _roles(df, box, lps=_FakeLps(start_bar=58, end_bar=63, low_bar=63))
    starts = [lbl["describes"][0] for lbl in labels]
    assert starts == sorted(starts)
    for lbl in labels:
        assert lbl["describes"][0] <= lbl["describes"][1]
        assert lbl["describes"][0] <= lbl["anchor_bar"] <= lbl["describes"][1]


# ---------------------------------------------------------------------------
# Fire-path staging (Task 6) — EC-8 flag protocol
# ---------------------------------------------------------------------------

def _first_firing_fixture_ticker():
    """One real firing (ticker, frame, result, spy, breadth) off the committed
    shadow fixture — loud if the fixture stopped firing entirely."""
    from core.pipeline.evaluation import EVAL_ERROR
    from core.pipeline.screener import _evaluate_ticker
    from tools.shadow_diff import _load_fixture

    frames, scalars = _load_fixture()
    spy = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        result = _evaluate_ticker(ticker, df, spy, breadth)
        if result is not None and result is not EVAL_ERROR:
            return ticker, df, result, spy, breadth
    raise AssertionError("no shadow-fixture ticker fires — rebuild the fixture")


def test_event_map_flag_off_never_computes(monkeypatch):
    """EC-8 inert proof: with EVENT_MAP_ENABLED off (the default), a full
    per-ticker evaluation never touches the Event Map readers."""
    import engine_alpha.structure.event_map as em
    from config import settings

    assert settings.EVENT_MAP_ENABLED is False, "flag must ship dark"

    def _boom(*_a, **_k):
        raise AssertionError("Event Map computed while the flag is off")

    monkeypatch.setattr(em, "read_swing_map", _boom)
    monkeypatch.setattr(em, "read_role_labels", _boom)
    _ticker, _df, result, _spy, _breadth = _first_firing_fixture_ticker()
    assert result["Score"] > 0


def test_event_map_flag_on_is_additive_only(monkeypatch):
    """EC-8: flag-on changes NOTHING pre-existing — it only ADDS the
    underscore Event Map diagnostics to a firing result."""
    from config import settings
    from core.pipeline.screener import _evaluate_ticker

    ticker, df, off, spy, breadth = _first_firing_fixture_ticker()
    monkeypatch.setattr(settings, "EVENT_MAP_ENABLED", True)
    on = _evaluate_ticker(ticker, df, spy, breadth)

    assert {k: on[k] for k in off} == off, "a pre-existing field moved flag-on"
    assert set(on) - set(off) == {
        "_event_map_n_swings", "_event_map_pre_box_trend",
        "_event_map_n_labels", "_event_map_n_committed",
    }
    assert on["_event_map_n_swings"] > 0
    assert on["_event_map_n_labels"] >= on["_event_map_n_committed"] >= 0


def test_degenerate_inputs_return_empty_shape():
    df, box = _demo_frame()
    empty_keys = {"swings", "n_swings", "pre_box", "box", "start_bar",
                  "n_bars", "nan_bars"}
    for bad_df, bad_box, bad_atr in (
        (None, box, 1.0),
        (df.iloc[:0], box, 1.0),
        (df, None, 1.0),
        (df, _Box(start_bar=18, R=10.0, S=14.0), 1.0),   # inverted rails
        (df, box, 0.0),
        (df, box, float("nan")),
        (df, _Box(start_bar=len(df), R=14.0, S=10.0), 1.0),
    ):
        tape = read_swing_map(bad_df, bad_box, bad_atr)
        assert set(tape) == empty_keys and tape["swings"] == []


def test_event_map_archive_values_live_and_seed_mapping():
    """The tape-summary archive family (Task 7): the owning extraction maps a
    live (prefixed) or seed (unprefixed) row to exactly EVENT_MAP_COLUMN_SQL,
    NaN-scrubbed (EC-2), INTEGER cells as plain int, absent -> None (NULL)."""
    from engine_alpha.structure.event_map import EVENT_MAP_COLUMN_SQL, event_map_archive_values

    live_row = {"_event_map_n_swings": np.int64(7),
                "_event_map_pre_box_trend": "up",
                "_event_map_n_labels": float("nan")}
    out = event_map_archive_values(live_row.get, prefixed=True)
    assert set(out) == set(EVENT_MAP_COLUMN_SQL)
    assert out["event_map_n_swings"] == 7
    assert type(out["event_map_n_swings"]) is int      # np.int64 -> plain int
    assert out["event_map_pre_box_trend"] == "up"
    assert out["event_map_n_labels"] is None           # NaN scrubbed -> NULL
    assert out["event_map_n_committed"] is None        # absent -> "not measured"

    seed_out = event_map_archive_values({"event_map_n_swings": 3}.get, prefixed=False)
    assert seed_out["event_map_n_swings"] == 3
