"""Unit tests for the PIP (Perceptually Important Points) swing skeleton.

Pure-function contract for the substrate, plus the flag-gated MACRO Phase-A
read (``macro_bridge_zigzag``) and its ``segment_swings`` wire.
"""
import numpy as np

from config import settings
from engine_alpha.structure.phases.phase_a import macro_bridge_zigzag, pip_indices, pip_pivots, pip_skeleton


def test_pip_indices_picks_biggest_swing_first():
    # Two humps; the index-4 spike (10) dwarfs the index-1/7 bumps (3).
    P = [0, 3, 0, 0, 10, 0, 0, 3, 0]
    idx = pip_indices(P, n_points=3)
    # order = [endpoint0, endpointN-1, most-important-interior]
    assert idx[0] == 0 and idx[1] == len(P) - 1
    assert idx[2] == 4                       # the tallest deviation is chosen first


def test_pip_indices_multi_resolution_is_nested():
    P = [0, 3, 0, 1, 10, 1, 0, 6, 0, 2, 0]
    coarse = pip_indices(P, n_points=4)
    fine = pip_indices(P, n_points=7)
    # Greedy global pick is target-independent -> the coarse skeleton is an exact
    # prefix of the fine one (top-K subset of top-(K+1)).
    assert fine[:len(coarse)] == coarse
    assert set(coarse).issubset(set(fine))


def test_pip_pivots_alternate_and_snap_to_high_low():
    # P (hl2) zigzags; High = P+0.5, Low = P-0.5 so snap is observable.
    P = np.array([0.0, 5.0, 1.0, 6.0, 0.0])
    highs = P + 0.5
    lows = P - 0.5
    zz = pip_pivots(highs, lows, n_points=5)

    assert len(zz) >= 3
    kinds = [k for _, k, _ in zz]
    assert all(kinds[i] != kinds[i + 1] for i in range(len(kinds) - 1))  # strict alternation
    for bar, kind, price in zz:
        if kind == "peak":
            assert price == highs[bar]      # peaks snap to the High
        else:
            assert price == lows[bar]       # valleys snap to the Low


def test_pip_pivots_flat_series_is_empty():
    flat = np.full(20, 50.0)
    assert pip_pivots(flat, flat, n_points=10) == []


def test_pip_pivots_too_few_bars_is_empty():
    assert pip_pivots(np.array([10.0, 11.0]), np.array([9.0, 10.0]), n_points=5) == []


def test_pip_indices_dist_min_limits_selection():
    # One large swing (index 4) + tiny wiggles. A dist_min above the wiggles'
    # relative size keeps only the dominant turn, fewer than the n_points cap.
    P = [0, 0.2, 0, 0.1, 10, 0.1, 0, 0.2, 0]
    idx = pip_indices(P, n_points=8, dist_min=0.30)
    assert 4 in idx                          # the dominant turn survives
    assert len(idx) < 8                       # the floor stopped it before the cap


def test_pip_skeleton_returns_each_level():
    rng = np.linspace(0, 1, 60)
    highs = 100 + 10 * np.sin(rng * 12) + 0.5
    lows = 100 + 10 * np.sin(rng * 12) - 0.5
    import pandas as pd
    df = pd.DataFrame({"High": highs, "Low": lows})
    sk = pip_skeleton(df, levels=(5, 15, 30))
    assert set(sk.keys()) == {5, 15, 30}
    # finer levels resolve at least as many turning points as coarser ones
    assert len(sk[30]) >= len(sk[5]) >= 2


# ---------------------------------------------------------- macro bridge ----

def _markup_range_frame():
    """Markup -> AR -> worked range, with a LATE range retest poking marginally
    ABOVE the true climax (the climax thief a fine skeleton falls for).

    bars 0..39   linear markup 100 -> 140 (true climax @39)
    bars 40..45  reaction 140 -> 122     (true AR low @45)
    bars 46..99  oscillating range ~125..138
    bar  80      poke to 141 — higher than the climax, but a range event
    """
    up = np.linspace(100.0, 140.0, 40)
    drop = np.linspace(140.0, 122.0, 7)[1:]
    t = np.arange(54, dtype=float)
    rng = 131.5 + 6.5 * np.sin(t * (2 * np.pi / 18.0))
    P = np.concatenate([up, drop, rng])
    P[80] = 141.0
    return P + 0.5, P - 0.5          # highs, lows


def test_macro_bridge_stops_before_the_climax_thief():
    highs, lows = _markup_range_frame()
    zz, k = macro_bridge_zigzag(highs, lows, with_k=True)
    assert k == 4                          # confirmed at the coarsest bridge
    bars = [b for b, _, _ in zz]
    assert 39 in bars and 45 in bars       # true climax + true AR
    assert 80 not in bars                  # the thief never enters the skeleton
    peaks = [(b, p) for b, kind, p in zz if kind == "peak"]
    assert max(peaks, key=lambda t: t[1])[0] == 39   # climax = the LEFT top


def test_macro_bridge_fresh_climax_abstains():
    # Monotone wiggly rise: the extreme is the right edge, no AR has held yet.
    t = np.arange(60, dtype=float)
    P = 100.0 + t + 0.8 * np.sin(t)
    zz, k = macro_bridge_zigzag(P + 0.5, P - 0.5, with_k=True)
    assert k is None                       # no validated bridge by k_max
    assert zz == []                        # ABSTAINS -> caller uses order-N


def test_confirmed_bridge_guards_tnc_class():
    # TNC class, tested on the pure guard: a shallow old-top bridge whose leg
    # CONTAINS the crash low (AR extremity) — and, separately, whose climax is
    # later exceeded by far more than the bridge height (terminality).
    from engine_alpha.structure.phases.phase_a import _validated_bridge

    P = np.concatenate([
        np.linspace(100.0, 140.0, 11),      # bars 0..10, old top 140 @10
        np.linspace(140.0, 60.0, 11)[1:],   # bars 11..20, crash low 60 @20
        np.linspace(60.0, 86.0, 11)[1:],    # bars 21..30, range rally
        np.linspace(86.0, 61.0, 11)[1:],    # bars 31..40, range retest low @40
        np.linspace(61.0, 82.0, 11)[1:],    # bars 41..50, range rally
        np.linspace(82.0, 75.0, 10)[1:],    # bars 51..59, right-edge drift
    ])
    highs, lows = P + 0.5, P - 0.5

    # Bad bridge: old top -> the RANGE RETEST low; the crash lies inside the
    # leg, so the AR is not its own extreme -> rejected.
    bad = [(0, "valley", lows[0]), (10, "peak", highs[10]),
           (40, "valley", lows[40]), (50, "peak", highs[50])]
    assert _validated_bridge(bad, 59, highs, lows) is None

    # Honest story on the same chart: the window nets DOWN, so the SC form
    # wins — crash low (SC) -> automatic rally (AR), followed by the worked
    # 60-86 equilibrium (two-sided traversal, floor holds) -> accepted.
    ok = [(0, "valley", lows[0]), (10, "peak", highs[10]),
          (20, "valley", lows[20]), (30, "peak", highs[30])]
    assert _validated_bridge(ok, 59, highs, lows) == (2, 3)


def test_macro_bridge_needs_room_for_a_base():
    # A confirmed reaction with only a handful of bars after it is a CLAIM,
    # not a story: no equilibrium can exist in 5 bars -> abstain.
    highs, lows = _markup_range_frame()
    zz, k = macro_bridge_zigzag(highs[:51], lows[:51], with_k=True)
    assert k is None and zz == []


def test_macro_bridge_rejects_taken_out_climax():
    # ATI class: a pullback whose "climax" is decisively taken out by the
    # continuing trend right after — terminality must reject the bridge.
    up1 = np.linspace(100.0, 150.0, 40)                  # markup leg 1
    dip = np.linspace(150.0, 138.0, 5)[1:]               # small pullback
    up2 = np.linspace(138.0, 185.0, 30)[1:]              # trend continues WAY up
    P = np.concatenate([up1, dip, up2])
    zz, k = macro_bridge_zigzag(P + 0.5, P - 0.5, with_k=True)
    # The only interior bridge is 150->138, exceeded by +35 (~2.9x bridge
    # height) afterwards -> reject -> abstain (fresh-trend chart, no story).
    assert k is None and zz == []


def test_macro_bridge_downtrend_mirror_sc():
    # Vertical mirror of the markup frame: decline -> SC -> rally -> range,
    # with a late poke BELOW the SC.
    highs_u, lows_u = _markup_range_frame()
    P = 250.0 - (highs_u + lows_u) / 2.0   # mirror the hl2 path
    highs, lows = P + 0.5, P - 0.5
    zz, k = macro_bridge_zigzag(highs, lows, with_k=True)
    assert k == 4
    bars = [b for b, _, _ in zz]
    assert 39 in bars and 45 in bars and 80 not in bars
    valleys = [(b, p) for b, kind, p in zz if kind == "valley"]
    assert min(valleys, key=lambda t: t[1])[0] == 39  # SC = the LEFT bottom


def test_segment_swings_macro_wire():
    # The macro read is unconditional in segment_swings (folded 2026-07-18;
    # formerly flag PIP_MACRO_PHASE_A_ENABLED, live since 2026-07-04).
    import pandas as pd
    from engine_alpha.structure.phases.segmentation import segment_swings

    highs, lows = _markup_range_frame()
    df = pd.DataFrame({"High": highs, "Low": lows})
    seg = segment_swings(df, atr_val=2.0)
    root = seg["root_swing"]
    assert root is not None
    assert root["bc_bar"] == 39 and root["ar_bar"] == 45
