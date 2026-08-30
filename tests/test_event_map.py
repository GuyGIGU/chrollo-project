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

from config import settings
from engine_alpha.structure.box_events import read_box_staircase
from engine_alpha.structure.event_map import (
    episode_sequence_stats,
    read_rail_episodes,
    read_role_labels,
    read_swing_map,
)
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
        assert lbl["knowable_bar"] >= top + settings.EVENT_HOLD_MIN_BARS


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
            assert lbl["knowable_bar"] >= lbl["anchor_bar"] + settings.EVENT_HOLD_MIN_BARS


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
    from engine_alpha.evaluation import EVAL_ERROR
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
    """EC-8 inert proof: the OFF branch stays compute-free. The flag is LIVE
    by default since 2026-07-25 (Event Map program Task 13) — this pins that
    the off branch remains a pure short-circuit, which every flag-off A/B
    replay and the parity contract depend on."""
    import engine_alpha.structure.event_map as em
    from config import settings

    monkeypatch.setattr(settings, "EVENT_MAP_ENABLED", False)
    # cause_maturity (veto, now live) is an INDEPENDENT legitimate caller of
    # read_swing_map (its Operand B), so hold the veto off to isolate the
    # EVENT_MAP flag under test — else the _boom fires for the wrong feature.
    monkeypatch.setattr(settings, "CAUSE_BEFORE_EFFECT_VETO_ENABLED", False)
    # The story pool is the one OTHER legitimate caller of the episode layer;
    # hold it off (its own compute-free proof lives in test_story_pool) so
    # the booms below cover the WHOLE family this flag gates.
    monkeypatch.setattr(settings, "STORY_POOL_ENABLED", False)

    def _boom(*_a, **_k):
        raise AssertionError("Event Map computed while the flag is off")

    monkeypatch.setattr(em, "read_swing_map", _boom)
    monkeypatch.setattr(em, "read_role_labels", _boom)
    monkeypatch.setattr(em, "read_rail_episodes", _boom)
    monkeypatch.setattr(em, "read_rail_episodes_arrays", _boom)
    monkeypatch.setattr(em, "episode_sequence_stats", _boom)
    monkeypatch.setattr(em, "story_admission", _boom)
    monkeypatch.setattr(em, "episode_substrate_fields", _boom)
    _ticker, _df, result, _spy, _breadth = _first_firing_fixture_ticker()
    assert result["Score"] > 0


def test_event_map_flag_on_is_additive_only(monkeypatch):
    """The map-ON parity contract as an executable assertion (EC-8 / plan
    Task 13): ON changes NOTHING pre-existing — fires, elections, and scores
    byte-identical; only the underscore Event Map diagnostics are ADDED.
    Both sides pinned explicitly (the flag ships LIVE since 2026-07-25)."""
    from config import settings
    from core.pipeline.screener import _evaluate_ticker

    monkeypatch.setattr(settings, "EVENT_MAP_ENABLED", False)
    ticker, df, off, spy, breadth = _first_firing_fixture_ticker()
    monkeypatch.setattr(settings, "EVENT_MAP_ENABLED", True)
    on = _evaluate_ticker(ticker, df, spy, breadth)

    # ONE declared exception, and it is the map's entire purpose: the v2 charter
    # measurement `_story_richness_rate` CONSUMES the map's completed-S/R and
    # alternation counts, so it necessarily reads differently without them. It
    # is measure-only (never scored — every SCORE_STORY_* is 0), it exists only
    # inside TA_SCORE_V2, and before the 2026-08-09 flip it was simply absent
    # from this comparison, which is why the blanket equality held then.
    map_consumers = {"_story_richness_rate"}
    assert ({k: on[k] for k in off if k not in map_consumers}
            == {k: v for k, v in off.items() if k not in map_consumers}), (
        "a pre-existing field moved flag-on")
    # The canonical outputs specifically — the contract's teeth, checked against
    # the same frozen list the shadow guard uses rather than a hand-typed twin.
    from tools.shadow_diff import CANONICAL_FIELDS
    for key in CANONICAL_FIELDS:
        assert on[key] == off[key], f"canonical field {key} moved flag-on"
    assert set(on) - set(off) == {
        "_event_map_n_swings", "_event_map_pre_box_trend",
        "_event_map_n_labels", "_event_map_n_committed",
        "_event_map_completed_s", "_event_map_completed_r",
        "_event_map_alternations", "_event_map_terminal_posture",
        "_event_map_terminal_drift", "_event_map_story_admitted",
        "_event_map_episode_nan_bars", "_event_map_zone_coverage",
        "_event_map_episode_profile", "_event_map_episodes",
    }
    assert on["_event_map_n_swings"] > 0
    assert on["_event_map_n_labels"] >= on["_event_map_n_committed"] >= 0
    # Substrate discipline (Task 10): explicit values on a measured fire —
    # zeros are evidence, never None; flags are 0/1 ints; the tape is JSON
    # whose span/knowable anchors are DATES, never bar indexes.
    import json as _json
    for k in ("_event_map_completed_s", "_event_map_completed_r",
              "_event_map_alternations", "_event_map_terminal_posture",
              "_event_map_terminal_drift", "_event_map_story_admitted",
              "_event_map_episode_nan_bars"):
        assert isinstance(on[k], int), f"{k} must be a plain int, got {type(on[k])}"
    tape = _json.loads(on["_event_map_episodes"])
    assert isinstance(tape, list)
    for entry in tape:
        assert set(entry) == {"rail", "outcome", "posture", "span", "knowable"}
        assert "-" in entry["span"][0]      # ISO date, not a bar index


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


def test_narrative_chart_fields_projects_the_same_family_with_a_parsed_tape():
    """The payload projection (Surface the Read): same extraction as the
    writers — same keys, same NULL fidelity — with ONLY the tape cell parsed
    from JSON text to structure. An unparseable tape degrades to None while
    the scalars stay measured (tape-unreadable ≠ not-measured)."""
    from engine_alpha.structure.event_map import EVENT_MAP_COLUMN_SQL, narrative_chart_fields

    tape = '[{"rail":"S","outcome":"completed","posture":false,' \
           '"span":["2026-05-01","2026-05-02"],"knowable":"2026-05-05"}]'
    live_row = {"_event_map_completed_s": np.int64(1),
                "_event_map_episode_profile": "S+",
                "_event_map_episodes": tape}
    out = narrative_chart_fields(live_row.get)
    assert set(out) == set(EVENT_MAP_COLUMN_SQL)
    assert out["event_map_completed_s"] == 1
    assert out["event_map_episodes"] == [
        {"rail": "S", "outcome": "completed", "posture": False,
         "span": ["2026-05-01", "2026-05-02"], "knowable": "2026-05-05"}]
    # Not measured: the whole family is None, tape included.
    absent = narrative_chart_fields({}.get)
    assert all(v is None for v in absent.values())
    # Tape unreadable: ONLY the tape drops to None; the scalars stay measured.
    broken = narrative_chart_fields(
        {"_event_map_completed_s": 2, "_event_map_episodes": "{not json"}.get)
    assert broken["event_map_episodes"] is None
    assert broken["event_map_completed_s"] == 2


# ---------------------------------------------------------------------------
# The rail-episode read (layer 3) — plan Task 3 guards
# ---------------------------------------------------------------------------

def _episode_frame(bars):
    """Explicit (high, low, close) rows — episode geometry readable by eye."""
    return pd.DataFrame({"High": [b[0] for b in bars],
                         "Low": [b[1] for b in bars],
                         "Close": [b[2] for b in bars]})


def _story_frame():
    """R=14 / S=10, atr=1.0 (zones at 13.5 / 10.5, breaks at 14.5 / 9.5):
    a completed S test [1,2], a completed R rejection [6,6], a failed S
    breakdown [10,12], and a terminal R engagement [16,17] closing above R."""
    bars = [
        (12.5, 11.5, 12.0),
        (12.5, 10.4, 10.6),   # S visit
        (12.0, 10.2, 10.8),   # S visit (same run)
        (12.5, 11.5, 12.0),   # confirm close >= S -> completed
        (12.5, 11.5, 12.2),
        (12.6, 11.6, 12.3),   # S episode identity fixed here (2 + 3)
        (13.6, 12.5, 13.2),   # R visit, no break, close back under R
        (12.8, 11.8, 12.0),   # confirm close <= R -> completed
        (12.5, 11.5, 12.1),
        (12.5, 11.5, 12.2),   # R episode identity fixed here (6 + 3)
        (12.4, 10.3, 10.4),   # S visit
        (11.0, 9.2, 9.3),     # breach below S - buf, close below S
        (10.0, 9.0, 9.2),     # still in zone, unreclaimed
        (11.5, 10.6, 11.0),
        (11.8, 10.8, 11.2),
        (12.0, 11.0, 11.5),   # failed S identity fixed here (12 + 3)
        (14.2, 13.0, 13.8),   # R visit
        (14.4, 13.6, 14.3),   # terminal: close above R -> posture
    ]
    return _episode_frame(bars), 14.0, 10.0, 1.0


def test_rail_episodes_type_outcomes_and_stamps():
    df, R, S, atr = _story_frame()
    read = read_rail_episodes(df, R, S, atr)
    eps = read["episodes"]
    assert [(e["rail"], e["outcome"], e["start_bar"], e["end_bar"],
             e["knowable_bar"], e["terminal_posture"]) for e in eps] == [
        ("S", "completed", 1, 2, 5, False),
        ("R", "completed", 6, 6, 9, False),
        ("S", "failed", 10, 12, 15, False),
        ("R", "open", 16, 17, None, True),
    ]
    # Contract stamps: verdict + identity irreversible only past the merge
    # horizon; the terminal episode is frame-scoped (in_progress).
    for e in eps:
        assert e["in_progress"] is (e["knowable_bar"] is None)
        if e["knowable_bar"] is not None:
            assert e["knowable_bar"] == e["end_bar"] + settings.EPISODE_MAX_GAP_BARS + 1
    assert read["nan_bars"] == 0

    st = episode_sequence_stats(read)
    assert (st["n_completed_s"], st["n_completed_r"], st["alternations"]) == (1, 1, 1)
    assert st["profile"] == "S+ R+ Sx R^"
    assert st["terminal_r_posture"] is True
    assert st["terminal_s_drift"] is False


def test_rail_episodes_as_of_counts_only_knowable():
    """The as-of rule reads a frame TRUNCATED at the decision bar (contract
    §1): completed history counts only episodes knowable by that edge. A
    sub-edge ``as_of_bar`` over a longer frame is REFUSED loudly — the
    terminal flags and profile are right-edge reads, so deriving decision-day
    state from a longer frame would be a silent lookahead in the exact
    predicate that gates story rescues."""
    df, R, S, atr = _story_frame()
    early = episode_sequence_stats(
        read_rail_episodes(df.iloc[:6], R, S, atr), as_of_bar=5)
    assert (early["n_completed_s"], early["n_completed_r"]) == (1, 0)
    both = episode_sequence_stats(
        read_rail_episodes(df.iloc[:10], R, S, atr), as_of_bar=9)
    assert (both["n_completed_s"], both["n_completed_r"]) == (1, 1)
    with pytest.raises(ValueError, match="below the frame edge"):
        episode_sequence_stats(read_rail_episodes(df, R, S, atr), as_of_bar=5)


def test_rail_episode_truncation_reproduces_committed_episodes():
    """Contract §7 at the episode level: relabeling a truncated frame yields
    exactly the full frame's episodes that were knowable inside the cut."""
    df, R, S, atr = _story_frame()
    full = read_rail_episodes(df, R, S, atr)["episodes"]

    def _sig(eps):
        return [(e["rail"], e["outcome"], e["start_bar"], e["end_bar"],
                 e["knowable_bar"]) for e in eps]

    for cut in range(1, len(df) + 1):
        trunc = read_rail_episodes(df.iloc[:cut], R, S, atr)["episodes"]
        got = _sig(e for e in trunc if not e["in_progress"])
        want = _sig(e for e in full
                    if e["knowable_bar"] is not None
                    and e["knowable_bar"] <= cut - 1)
        assert got == want, f"cut={cut}"


def test_rail_episode_tie_order_is_pinned_s_before_r():
    """One wide bar engages BOTH zones: a full (end, start) tie. The pinned
    deterministic rule keeps the S episode before the R episode."""
    bars = [
        (12.5, 11.5, 12.0),
        (13.6, 10.4, 12.0),   # touches both zones in one bar
        (12.5, 11.5, 12.0),   # confirms both: >= S and <= R
        (12.5, 11.5, 12.1),
        (12.5, 11.5, 12.2),
        (12.5, 11.5, 12.3),
    ]
    read = read_rail_episodes(_episode_frame(bars), 14.0, 10.0, 1.0)
    assert [(e["rail"], e["start_bar"], e["end_bar"]) for e in read["episodes"]] == [
        ("S", 1, 1), ("R", 1, 1)]
    assert episode_sequence_stats(read)["profile"] == "S+ R+"


def test_rail_episode_gap_merge_and_drift():
    """Visits separated by <= settings.EPISODE_MAX_GAP_BARS inside bars merge into ONE
    episode; an open terminal S episode >= 3 bars reads as terminal drift."""
    bars = [
        (12.5, 11.5, 12.0),
        (12.5, 10.4, 11.0),   # S visit
        (12.5, 11.5, 12.0),   # inside gap (1)
        (12.5, 11.5, 12.0),   # inside gap (2)
        (12.5, 10.3, 11.0),   # S visit again -> merges into [1,4]
        (12.5, 10.2, 10.4),   # S visit, runs to the edge
        (12.4, 10.1, 10.3),   # terminal
    ]
    read = read_rail_episodes(_episode_frame(bars), 14.0, 10.0, 1.0)
    eps = read["episodes"]
    assert len(eps) == 1
    assert (eps[0]["start_bar"], eps[0]["end_bar"], eps[0]["outcome"]) == (1, 6, "open")
    st = episode_sequence_stats(read)
    assert st["terminal_s_drift"] is True
    assert st["profile"] == "S0"


def test_rail_episode_degenerate_and_nan_inputs():
    assert read_rail_episodes(None, 14.0, 10.0, 1.0)["episodes"] == []
    df = _episode_frame([(12.5, 11.5, 12.0)] * 4)
    assert read_rail_episodes(df, 10.0, 14.0, 1.0)["episodes"] == []   # R <= S
    assert read_rail_episodes(df, 14.0, 10.0, None)["episodes"] == []

    bars = [
        (12.5, 11.5, 12.0),
        (float("nan"), float("nan"), float("nan")),   # unreadable bar
        (12.5, 10.4, 11.0),                            # S visit
        (12.5, 11.5, 12.0),                            # confirm -> completed
        (12.5, 11.5, 12.0),
        (12.5, 11.5, 12.0),
        (12.5, 11.5, 12.0),
    ]
    read = read_rail_episodes(_episode_frame(bars), 14.0, 10.0, 1.0)
    assert read["nan_bars"] == 1                       # counted loudly
    assert [(e["rail"], e["outcome"]) for e in read["episodes"]] == [
        ("S", "completed")]                            # NaN bar never visits


def test_story_admission_pins_the_ruled_form_option_a():
    """Operator ruling 2026-07-25 (Option A): >=2 completed support tests AND
    terminal resistance posture AND no terminal support drift. This truth
    table IS the mechanical drift check against the Reading Model's canonical
    spec — a predicate edit that no longer matches the ruled form fails here."""
    from engine_alpha.structure.event_map import story_admission

    base = {"n_completed_s": 2, "n_completed_r": 0, "alternations": 0,
            "terminal_s_drift": False, "terminal_r_posture": True}
    assert story_admission(base) is True
    assert story_admission({**base, "n_completed_s": 3}) is True
    assert story_admission({**base, "n_completed_s": 1}) is False
    assert story_admission({**base, "terminal_r_posture": False}) is False
    assert story_admission({**base, "terminal_s_drift": True}) is False
    # R-side completions neither required nor disqualifying (the v1 lesson:
    # the material legally ENDS at R; mid-window rejections are not demanded).
    assert story_admission({**base, "n_completed_r": 4}) is True


def test_rail_episode_split_side_of_the_merge_horizon():
    """EXACTLY settings.EPISODE_MAX_GAP_BARS + 1 inside bars between two same-rail
    visits do NOT merge — the split side of the horizon (the merging side is
    pinned above). An off-by-one that widens the merge collapses these two
    completed support tests into one and fails here: each episode keeps its
    own outcome and its own knowable stamp."""
    bars = [
        (12.5, 11.5, 12.0),
        (12.5, 10.4, 11.0),   # S visit A
        (12.5, 11.5, 12.0),   # inside (1) — also A's confirm -> completed
        (12.5, 11.5, 12.0),   # inside (2)
        (12.5, 11.5, 12.0),   # inside (3) -> beyond the merge horizon
        (12.5, 10.3, 11.0),   # S visit B — a SEPARATE episode
        (12.5, 11.5, 12.0),   # B's confirm -> completed
        (12.5, 11.5, 12.1),
        (12.5, 11.5, 12.2),
        (12.5, 11.5, 12.3),
    ]
    read = read_rail_episodes(_episode_frame(bars), 14.0, 10.0, 1.0)
    assert [(e["rail"], e["outcome"], e["start_bar"], e["end_bar"],
             e["knowable_bar"]) for e in read["episodes"]] == [
        ("S", "completed", 1, 1, 4),
        ("S", "completed", 5, 5, 8),
    ]
    assert episode_sequence_stats(read)["n_completed_s"] == 2


def test_unreadable_confirm_close_types_unreadable_never_failed():
    """Contract §5: the confirming close IS the verdict — when it is not
    finite the episode types UNREADABLE (profile '?'), never a printed
    'failed'. On readable data the confirm comparison cannot flip an
    outcome (the run-end bar sits outside the zone by construction), so a
    'failed' confirm was only ever reachable via NaN — a fabricated bearish
    fact that would suppress a completed-S count and veto a legitimate
    story admission."""
    bars = [
        (12.5, 11.5, 12.0),
        (12.5, 10.4, 11.0),                            # S visit
        (float("nan"), float("nan"), float("nan")),    # confirm bar unreadable
        (12.5, 11.5, 12.0),
        (12.5, 11.5, 12.1),
        (12.5, 11.5, 12.2),
    ]
    read = read_rail_episodes(_episode_frame(bars), 14.0, 10.0, 1.0)
    assert [(e["rail"], e["outcome"]) for e in read["episodes"]] == [
        ("S", "unreadable")]
    st = episode_sequence_stats(read)
    assert (st["n_completed_s"], st["profile"]) == (0, "S?")
    assert read["nan_bars"] == 1


def test_identity_unfixed_verdicts_carry_the_tilde_and_are_excluded_as_of():
    """A verdict still inside its merge horizon at the frame edge prints
    with a '~' suffix and is EXCLUDED from the as-of counts — the sentence
    can never appear to contradict the scalar columns beside it."""
    bars = [
        (12.5, 11.5, 12.0),
        (12.5, 10.4, 11.0),   # S visit
        (12.5, 11.5, 12.0),   # confirm -> completed; horizon NOT printed
        (12.5, 11.5, 12.1),   # frame ends 2 bars after the run
    ]
    read = read_rail_episodes(_episode_frame(bars), 14.0, 10.0, 1.0)
    e = read["episodes"][0]
    assert (e["outcome"], e["knowable_bar"], e["in_progress"]) == (
        "completed", None, True)
    st = episode_sequence_stats(read, as_of_bar=len(bars) - 1)
    assert st["n_completed_s"] == 0
    assert st["profile"] == "S+~"
    # The full-frame (probe) read still counts every typed outcome.
    assert episode_sequence_stats(read)["n_completed_s"] == 1


def test_episode_substrate_producer_is_as_of_at_the_window_edge():
    """The archived substrate (the producer evaluation.py actually calls)
    EXCLUDES a completed-but-identity-unfixed episode at the window edge —
    replacing the producer's as-of read with the census's full-frame
    semantics (the easy copy-paste regression) reddens here. The tape's
    shape and date anchoring are pinned in the same pass (the cell's one
    owning module)."""
    import json as _json

    from engine_alpha.structure.event_map import episode_substrate_fields

    bars = [
        (12.5, 11.5, 12.0),
        (12.5, 10.4, 11.0),   # S test A — knowable inside the window
        (12.5, 11.5, 12.0),   # A's confirm
        (12.5, 11.5, 12.0),
        (12.5, 11.5, 12.0),   # A's identity fixed here (1 + 3)
        (12.5, 10.3, 11.0),   # S test B
        (12.5, 11.5, 12.0),   # B's confirm — horizon NOT printed at the edge
        (14.2, 13.6, 14.3),   # terminal R engagement, close above R
    ]
    df = _episode_frame(bars)
    df.index = pd.date_range("2026-01-05", periods=len(bars), freq="B")
    fields = episode_substrate_fields(df, 14.0, 10.0, 1.0)
    assert fields["_event_map_completed_s"] == 1        # B excluded (as-of)
    assert fields["_event_map_terminal_posture"] == 1
    assert fields["_event_map_story_admitted"] == 0     # 1 knowable S < 2
    assert fields["_event_map_episode_profile"] == "S+ S+~ R^"
    tape = _json.loads(fields["_event_map_episodes"])
    assert [set(e) for e in tape] == [
        {"rail", "outcome", "posture", "span", "knowable"}] * 3
    assert all("-" in e["span"][0] for e in tape)   # ISO dates, never indexes
    # Full-frame semantics would have counted B: the discriminating pin.
    full = episode_sequence_stats(
        read_rail_episodes(df, 14.0, 10.0, 1.0))
    assert full["n_completed_s"] == 2


def test_episode_substrate_zone_coverage_companion():
    """The geometry companion (2026-08-10, the nan-bars sibling): the
    substrate reports what fraction of the box the two ATR-fixed touch zones
    consume — 2*tol/(R-S), raw and unclamped — so zero-by-geometry can never
    masquerade as zero-by-drift downstream. NULL exactly when the reader's
    own preconditions failed (the family's "NULL = not measured" law)."""
    from config import settings
    from engine_alpha.structure.event_map import episode_substrate_fields

    bars = [(12.5, 11.5, 12.0)] * 6
    df = _episode_frame(bars)
    df.index = pd.date_range("2026-01-05", periods=len(bars), freq="B")

    # R-S = 4 box units, ATR 1.0, tol 0.5 each side -> coverage = 1.0/4 = 0.25
    fields = episode_substrate_fields(df, 14.0, 10.0, 1.0)
    expected = 2.0 * settings.TOUCH_TOLERANCE_ATR * 1.0 / 4.0
    assert fields["_event_map_zone_coverage"] == pytest.approx(expected)

    # A LEVI-shaped box (1.45 ATR tall) reads past the unreadable floor.
    tight = episode_substrate_fields(df, 11.45, 10.0, 1.0)
    assert (tight["_event_map_zone_coverage"]
            >= settings.STORY_UNREADABLE_ZONE_COVERAGE)

    # Refused-read geometry -> NULL, never a fabricated number.
    assert episode_substrate_fields(df, 10.0, 14.0, 1.0)[
        "_event_map_zone_coverage"] is None            # R <= S
    assert episode_substrate_fields(df, 14.0, 10.0, None)[
        "_event_map_zone_coverage"] is None            # no usable ATR
    assert episode_substrate_fields(df, 14.0, 10.0, float("nan"))[
        "_event_map_zone_coverage"] is None
    # ...and the WHOLE family follows the coverage column's law (2026-08-25
    # sweep): a refused read archives NULL everywhere — fabricated zeros
    # must never masquerade as a measured-empty tape.
    for refused in (episode_substrate_fields(df, 14.0, 10.0, None),
                    episode_substrate_fields(df, 10.0, 14.0, 1.0),
                    episode_substrate_fields(df.iloc[:0], 14.0, 10.0, 1.0)):
        assert all(v is None for v in refused.values())
