"""Orchestration tests for the chronological structure reader.

These prove the state machine + backtracking in isolation, using *fake* bricks
injected into ``read_structure``. They deliberately do NOT touch the real
detectors (those are validated separately) — the point is that the spine places
A -> B -> (C?) -> D correctly and backtracks to the next root swing when a story
fails, regardless of what the bricks are.
"""
from types import SimpleNamespace

from engine_alpha.structure.narrative import Structure, read_structure


def _root(climax, ar, R=110.0, S=100.0):
    return SimpleNamespace(climax_bar=climax, ar_bar=ar, R=R, S=S)


def _box(start, S=100.0, R=110.0, bw=0.10):
    return SimpleNamespace(S=S, R=R, start_bar=start, box_width=bw)


def _spring(tip, recovery):
    return SimpleNamespace(tip_bar=tip, recovery_bar=recovery)


def _lps(start):
    return SimpleNamespace(start_bar=start)


class _Bricks:
    """Scripted brick provider. Boxes/springs/lps are keyed so different root
    swings (climax bar) and boxes (start bar) can resolve to different results."""

    def __init__(self, roots, boxes, springs, lpss):
        self._roots = sorted(roots, key=lambda r: r.climax_bar)
        self._boxes = boxes      # climax_bar -> box | None
        self._springs = springs  # box.start_bar -> spring | None
        self._lpss = lpss        # box.start_bar -> lps | None

    def find_root_swing(self, df, search_from_bar, atr):
        for r in self._roots:                 # oldest-first
            if r.climax_bar >= search_from_bar:
                return r
        return None

    def validate_equilibrium(self, df, root, atr, trace=None):
        # ``trace`` mirrors the real brick's pair-cascade kwarg; the spine passes
        # it only when the caller is tracing (same contract as find_lps diagnose).
        return self._boxes.get(root.climax_bar)

    def find_spring(self, df, box, atr):
        return self._springs.get(box.start_bar)

    def find_lps(self, df, box, atr, *, diagnose=False):
        lps = self._lpss.get(box.start_bar)
        if diagnose:
            from collections import Counter
            return lps, (Counter() if lps is not None else Counter({"does not rest on its low": 1}))
        return lps

    def resolve_phase_a(self, df, root, box, atr):
        # Identity passthrough: these tests exercise the spine's control flow /
        # backtracking, not Phase-A locality (that is covered in test_bricks).
        return root.climax_bar, root.ar_bar

    def find_inner_box(self, df, box, atr):
        # No inner range in the orchestration fakes (inner is covered in
        # test_bricks); the spine must carry None through cleanly.
        return None


def test_narrative_happy_path_with_spring():
    bricks = _Bricks([_root(10, 20)], {10: _box(20)},
                     {20: _spring(80, 83)}, {20: _lps(85)})
    s = read_structure(df=None, atr=1.0, bricks=bricks)
    assert isinstance(s, Structure)
    assert s.terminator == "spring"
    assert s.has_spring
    assert s.climax_bar == 10 and s.ar_bar == 20
    assert s.phase_b_start_bar == 20
    assert s.phase_b_end_bar == 80          # B ends at the spring tip
    # The spring reclaim (83) is the END of Phase C, not the start of Phase D —
    # it only floors the search. With no richer right-side evidence after it, D
    # opens at the LPS (85), the mandatory fallback.
    assert s.phase_d_start_bar == 85
    assert s.phase_d_source == "lps"


def test_narrative_clean_base_no_spring_ends_at_lps():
    bricks = _Bricks([_root(10, 20)], {10: _box(20)},
                     {20: None}, {20: _lps(85)})
    s = read_structure(None, 1.0, bricks=bricks)
    assert s.terminator == "lps"
    assert not s.has_spring
    assert s.phase_b_end_bar == 85 and s.phase_d_start_bar == 85
    assert s.phase_d_source == "lps"


def test_narrative_backtracks_when_no_lps():
    # root1's box has no LPS -> not a setup -> advance to root2, which completes.
    bricks = _Bricks(
        [_root(10, 20), _root(40, 50)],
        {10: _box(20), 40: _box(50)},
        {20: None, 50: None},
        {20: None, 50: _lps(90)},           # only root2's box yields an LPS
    )
    s = read_structure(None, 1.0, bricks=bricks)
    assert s.climax_bar == 40 and s.terminator == "lps"


def test_narrative_backtracks_when_box_invalid():
    # root1 is not a worked range -> advance to root2.
    bricks = _Bricks(
        [_root(10, 20), _root(40, 50)],
        {10: None, 40: _box(50)},
        {50: None},
        {50: _lps(90)},
    )
    s = read_structure(None, 1.0, bricks=bricks)
    assert s.climax_bar == 40


def test_narrative_none_when_no_root_swing():
    assert read_structure(None, 1.0, bricks=_Bricks([], {}, {}, {})) is None


def test_narrative_none_when_story_never_completes():
    # A valid box but no LPS, and no further root swing to fall back to.
    bricks = _Bricks([_root(10, 20)], {10: _box(20)}, {20: None}, {20: None})
    assert read_structure(None, 1.0, bricks=bricks) is None


class _InnerBricks(_Bricks):
    """Scripted provider with an inner box: the walk must run the
    inner-first-then-parent Phase-D election on it."""

    def __init__(self, *args, inner, inner_lps):
        super().__init__(*args)
        self._inner = inner
        self._inner_lps = inner_lps

    def find_inner_box(self, df, box, atr):
        return self._inner

    def find_lps(self, df, box, atr, *, diagnose=False):
        if self._inner is not None and box is self._inner:
            return self._inner_lps
        return super().find_lps(df, box, atr, diagnose=diagnose)


def test_narrative_prefers_inner_lps_then_parent():
    """The walk's Phase-D election (the ONE home of the rule): take the inner
    box's LPS when it yields one (closer trigger/stop), else the parent's;
    lps_in_inner follows the winner. Migrated from the retired evaluation-side
    duplicate (select_active_lps)."""
    inner = SimpleNamespace(start_bar=60, search_start_bar=55)

    # Inner yields an LPS -> it wins; the elected brick is the inner's.
    bricks = _InnerBricks([_root(10, 20)], {10: _box(20)}, {20: None},
                          {20: _lps(85)}, inner=inner, inner_lps=_lps(88))
    s = read_structure(None, 1.0, bricks=bricks)
    assert s.lps_in_inner is True and s.lps.start_bar == 88
    assert s.inner is inner

    # Inner yields none -> the parent's LPS completes; lps_in_inner False.
    bricks = _InnerBricks([_root(10, 20)], {10: _box(20)}, {20: None},
                          {20: _lps(85)}, inner=inner, inner_lps=None)
    s = read_structure(None, 1.0, bricks=bricks)
    assert s.lps_in_inner is False and s.lps.start_bar == 85

    # No inner box at all -> parent path.
    bricks = _InnerBricks([_root(10, 20)], {10: _box(20)}, {20: None},
                          {20: _lps(85)}, inner=None, inner_lps=None)
    s = read_structure(None, 1.0, bricks=bricks)
    assert s.lps_in_inner is False and s.lps.start_bar == 85


def _full_structure(*, inner, spring):
    """A directly-built Structure with rich brick stand-ins for the view tests."""
    box = SimpleNamespace(
        S=100.0, R=110.0, start_bar=20, base_len=40, box_width=10.0,
        r_touches=4, s_touches=3, breach_days=2,
        n_full_traversals=3, traversal_density=0.15,
    )
    lps = SimpleNamespace(
        start_bar=58, length=5, offset=2, descent_frac=0.4,
        high_extension_atr=0.9, high_extension_box=0.3,
    )
    return Structure(
        climax_bar=10, ar_bar=20, R=110.0, S=100.0,
        phase_b_start_bar=20, phase_b_end_bar=50, box_width=10.0,
        box=box, inner=inner, spring=spring, lps=lps, lps_in_inner=False,
        phase_d_start_bar=58, phase_d_source="lps", phase_d_evidence={},
        terminator="spring" if spring is not None else "lps",
    )


def test_read_structure_trace_records_complete_story():
    bricks = _Bricks([_root(10, 20)], {10: _box(20)},
                     {20: _spring(80, 83)}, {20: _lps(85)})
    trace: list = []
    s = read_structure(df=None, atr=1.0, bricks=bricks, trace=trace)
    assert s is not None
    assert len(trace) == 1
    rec = trace[0]
    assert rec["outcome"] == "complete"
    assert rec["box"] is not None and rec["box"]["start_bar"] == 20
    assert rec["spring"] is not None
    assert rec["lps"] is not None and rec["lps"]["start_bar"] == 85
    assert rec["lps_rejects"] is None


def test_read_structure_trace_records_no_lps_then_backtracks():
    # root1: worked box but NO lps -> a 'no_lps' record carrying reject reasons;
    # the spine backtracks to root2, which completes.
    bricks = _Bricks(
        [_root(10, 20), _root(40, 50)],
        {10: _box(20), 40: _box(50)},
        {20: None, 50: None},
        {20: None, 50: _lps(90)},
    )
    trace: list = []
    s = read_structure(None, 1.0, bricks=bricks, trace=trace)
    assert s is not None and s.climax_bar == 40
    assert [r["outcome"] for r in trace] == ["no_lps", "complete"]
    assert trace[0]["box"] is not None            # box validated...
    assert trace[0]["lps"] is None                # ...but no LPS
    assert trace[0]["lps_rejects"]["parent"]      # and we recorded why


def test_read_structure_trace_carries_the_box_cascade():
    # The spine hands the brick a cascade list and attaches it to the root
    # record — the pair election narrating itself travels with the story.
    class _CascadeBricks(_Bricks):
        def validate_equilibrium(self, df, root, atr, trace=None):
            if trace is not None:
                trace.append({"verdict": "elected", "stage": "selection"})
            return super().validate_equilibrium(df, root, atr)

    bricks = _CascadeBricks([_root(10, 20)], {10: _box(20)},
                            {20: None}, {20: _lps(85)})
    trace: list = []
    s = read_structure(None, 1.0, bricks=bricks, trace=trace)
    assert s is not None
    assert trace[0]["box_cascade"] == [{"verdict": "elected", "stage": "selection"}]


def test_read_structure_trace_is_opt_in_noop_by_default():
    # No trace arg -> identical result, no crash (the live-path guarantee).
    bricks = _Bricks([_root(10, 20)], {10: _box(20)}, {20: None}, {20: _lps(85)})
    assert read_structure(None, 1.0, bricks=bricks) is not None


def test_read_structure_trace_carries_tape_and_role_summaries():
    """Task 10: the per-root trace records carry compact Event Map summaries —
    a ``tape`` brief once a box is elected, a ``roles`` brief on a complete
    story. With df=None (scripted bricks) both stay None; with a real frame
    and a real-shaped box they are computed."""
    import pandas as pd

    # df=None path: keys present, briefs None (nothing readable).
    bricks = _Bricks([_root(10, 20)], {10: _box(20)}, {20: None}, {20: _lps(85)})
    trace: list = []
    assert read_structure(None, 1.0, bricks=bricks, trace=trace) is not None
    assert trace[0]["tape"] is None and trace[0]["roles"] is None

    # Real-frame path: a V-shaped 24-bar frame and a box stand-in shaped like
    # the real brick (start_bar/R/S/base_len). The briefs must materialize.
    closes = [108, 107, 106, 105, 104, 103, 102, 101, 102, 103, 104, 105,
              104, 103, 102, 103, 104, 105, 106, 105, 104, 105, 106, 107]
    df = pd.DataFrame({
        "High": [c + 0.6 for c in closes],
        "Low": [c - 0.6 for c in closes],
        "Close": [float(c) for c in closes],
    })
    real_box = SimpleNamespace(S=100.0, R=110.0, start_bar=0, box_width=0.10,
                               base_len=len(df))
    lps = SimpleNamespace(start_bar=20, end_bar=23, low_bar=21,
                          swing_type="holding_shelf")
    bricks = _Bricks([_root(0, 0)], {0: real_box}, {0: None}, {0: lps})
    trace = []
    s = read_structure(df, 1.0, bricks=bricks, trace=trace)
    assert s is not None
    rec = trace[0]
    assert isinstance(rec["tape"]["n_swings"], int)
    assert rec["tape"]["pre_box_trend"] is not None
    assert rec["tape"]["box_trend"] is not None
    assert isinstance(rec["roles"]["n_labels"], int)
    assert 0 <= rec["roles"]["n_committed"] <= rec["roles"]["n_labels"]


def test_structure_views_compose_brick_fields():
    """horizontal/vertical are derived views over existing brick fields — no recompute."""
    inner = SimpleNamespace(base_len=15, box_width=4.0)
    spring = SimpleNamespace(tip_bar=50, recovery_bar=54, undercut_atr=1.8, time_loc=0.7)
    s = _full_structure(inner=inner, spring=spring)

    h = s.horizontal
    assert h["base_len"] == 40
    assert (h["r_touches"], h["s_touches"]) == (4, 3)
    assert h["full_traversals"] == 3
    assert h["traversal_density"] == 0.15
    assert h["lps_shelf_len"] == 5
    assert h["inner_base_len"] == 15
    assert h["spring_time_loc"] == 0.7

    v = s.vertical
    assert (v["R"], v["S"]) == (110.0, 100.0)
    assert v["box_height"] == 10.0
    assert v["box_height_pct"] == 10.0 / 110.0
    assert v["spring_undercut_atr"] == 1.8
    assert v["lps_descent_frac"] == 0.4
    assert v["right_side_extension_atr"] == 0.9
    assert v["inner_box_height"] == 4.0


def test_structure_views_degrade_when_no_spring_no_inner():
    """Optional bricks (Phase C spring, inner box) read as None, not a crash."""
    s = _full_structure(inner=None, spring=None)
    assert s.horizontal["inner_base_len"] is None
    assert s.horizontal["spring_time_loc"] is None
    assert s.vertical["spring_undercut_atr"] is None
    assert s.vertical["inner_box_height"] is None
