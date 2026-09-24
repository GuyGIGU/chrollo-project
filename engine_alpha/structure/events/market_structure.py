"""Market-structure reader — the chart in Highs & Lows.

Labels the shared swing skeleton (the ``_build_zigzag`` peaks/valleys every
other detector already uses) as Higher-High / Higher-Low / Lower-High /
Lower-Low, derives a running trend state, and marks the structural breaks:

  * BOS      (break of structure)  — a break that CONTINUES the mechanical trend:
                                     a HH in an uptrend, a LL in a downtrend.
  * reversal (mechanical flip)      — the FIRST break that flips the mechanical
                                     trend: a HH out of a downtrend, a LL out of
                                     an uptrend.

These are the raw SWING primitives. They are NOT the Wyckoff events — a single
mechanical ``reversal`` may be a spring (a LL that reclaims), the start of a
re-accumulation, or just the LPS pullback, and the operator's "CHoCH" is a
higher-level CHANGE OF REGIME (trend->equilibrium, or equilibrium->breakout)
that brackets the box. Those Wyckoff reads are derived in Layer 2 from these
primitives + the box + the HTF trend / base count — never here. Layer 0 of the
event reader (docs/strategy_alpha.md, the market-structure reader section).

Measure-first / opinion-free: it reads the zigzag the engine already builds and
adds labels — it never moves R/S, scores, or any canonical field. The pure
``label_market_structure(zigzag)`` is the testable core; ``read_market_structure
(df)`` builds the skeleton with the same ``_pivot_order`` convention as
``segment_swings``'s fallback — the macro-PIP upgrade deliberately does NOT
apply here (fine vs coarse skeleton; see the function's own docstring).
"""
from __future__ import annotations

from typing import NamedTuple, Optional

import numpy as np

from config import settings
from engine_alpha.structure.metrics.pivots import _find_pivots, _pivot_order, _swing_skeleton


def _empty() -> dict:
    return {
        "points": [],
        "events": [],
        "trend_state": "range",
        "n_points": 0,
        "last_event": None,
    }


def label_market_structure(zigzag) -> dict:
    """Label an alternating ``[(bar, 'peak'|'valley', price)]`` zigzag.

    Peaks are graded against the prior peak (HH / LH), valleys against the prior
    valley (HL / LL). A HH that takes OUT the prior swing high is a bullish break;
    a LL that takes out the prior swing low is a bearish break. A break that
    continues the trend is a ``BOS``; the first break that flips it is a
    ``reversal`` (a mechanical flip — NOT the operator's Wyckoff CHoCH; see the
    module docstring).
    An equal extreme (double top / bottom) holds the level — it is labelled with
    the trend-friendly tag but is NOT a structural break.
    """
    if not zigzag or len(zigzag) < 2:
        return _empty()

    points: list[dict] = []
    events: list[dict] = []
    prev_peak: Optional[float] = None
    prev_valley: Optional[float] = None
    trend = "range"
    last_event: Optional[dict] = None

    for bar, kind, price in zigzag:
        bar = int(bar)
        price = float(price)
        label = "first"

        if kind == "peak":
            if prev_peak is not None:
                if price > prev_peak:
                    label = "HH"
                    etype = "BOS" if trend == "up" else "reversal"
                    event = {"bar": bar, "type": etype, "direction": 1,
                             "broke": round(prev_peak, 4)}
                    events.append(event)
                    last_event = event
                    trend = "up"
                elif price < prev_peak:
                    label = "LH"
                else:
                    label = "HH"          # double top — held, no break
            prev_peak = price

        elif kind == "valley":
            if prev_valley is not None:
                if price < prev_valley:
                    label = "LL"
                    etype = "BOS" if trend == "down" else "reversal"
                    event = {"bar": bar, "type": etype, "direction": -1,
                             "broke": round(prev_valley, 4)}
                    events.append(event)
                    last_event = event
                    trend = "down"
                elif price > prev_valley:
                    label = "HL"
                else:
                    label = "HL"          # double bottom — held, no break
            prev_valley = price

        points.append({"bar": bar, "kind": kind, "price": round(price, 4),
                       "label": label, "trend": trend})

    return {
        "points": points,
        "events": events,
        "trend_state": trend,
        "n_points": len(points),
        "last_event": last_event,
    }


def read_market_structure(df, *, order: Optional[int] = None, line: Optional[bool] = None) -> dict:
    """Build the swing skeleton off ``df`` and label it. Bar indices in the
    result are df-positional. Mirrors ``segment_swings``' pivot order selection,
    so the labels line up with the swings the rest of the engine reads. The
    MACRO Phase-A read (``phase_a.macro_bridge_zigzag``) deliberately does NOT
    apply here: event labels want the fine skeleton, the Phase-A bridge wants
    the coarse one — same substrate, different zoom.

    ``line`` pins the skeleton: None follows ``TURN_LINE_TREND_ENABLED`` (build
    step 4); the Phase A climax repair passes False through
    ``trend_terminal_floor``, because the painter is build step 10's."""
    n = len(df)
    if n < 5:
        return _empty()
    try:
        highs = df["High"].values.astype(float)
        lows = df["Low"].values.astype(float)
    except (KeyError, TypeError, ValueError):
        return _empty()

    if (settings.TURN_LINE_TREND_ENABLED if line is None else line) and order is None:
        # Build step 4 (dark): the trend labels read the one turn line. The line is measured in daily ranges,
        # so a frame carrying no range column (a bare OHLC fixture, or a caller pinning an explicit order)
        # falls back to today's skeleton rather than inventing a unit.
        from engine_alpha.structure.pivots import turn_line, turn_line_floors
        floors = turn_line_floors(df, None)
        if np.any(np.isfinite(floors) & (floors > 0)):
            line = turn_line(highs, lows, floors)
            if len(line) < 2:
                return _empty()
            return label_market_structure([(int(b), k, float(p)) for (b, k, p, _) in line])

    if order is None:
        order = _pivot_order(n)
    peaks, valleys, zigzag = _swing_skeleton(highs, lows, order, _find_pivots)
    if not peaks or not valleys:
        return _empty()

    zigzag = [(int(b), k, p) for (b, k, p) in zigzag]
    return label_market_structure(zigzag)


def _pairwise_descent_fraction(values) -> float:
    """Fraction of pairwise comparisons where later values do not rise.

    The order-AGNOSTIC descent classifier — co-located with its order-AWARE
    twin ``classify_window_descent`` below: both answer "does this window
    descend?", as two labeled forms of one question (moved here from lps.py;
    body verbatim). This one stays the live LPS-window gate input."""
    n = len(values)
    if n < 2:
        return 1.0
    total_pairs = n * (n - 1) // 2
    concordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            if values[j] <= values[i]:
                concordant += 1
    return concordant / total_pairs if total_pairs > 0 else 1.0


def _median(values) -> float:
    ordered = sorted(float(v) for v in values)
    m = len(ordered)
    if m == 0:
        return 0.0
    if m % 2:
        return ordered[m // 2]
    return 0.5 * (ordered[m // 2 - 1] + ordered[m // 2])


def classify_window_descent(highs, lows, *, base_spread: Optional[float] = None,
                            atr: Optional[float] = None,
                            rising_march_frac: float = 0.6,
                            rising_march_min_steps: int = 3,
                            flat_band_frac: float = 0.5,
                            end_window: int = 3,
                            big_dip_depth_atr: Optional[float] = None) -> dict:
    """Layer-1: read a candidate LPS/Test window bar-by-bar in Highs AND Lows.

    Measure-only. Walks the window left→right and, on the SAME HH/HL/LH/LL logic
    as ``label_market_structure``, decides per bar whether it continues the dip,
    is a forgivable NOISE poke, or is a CONFIRMED up-turn that ends the test; then
    classifies the window as a whole. It GATES NOTHING — it returns magnitudes and
    a read; the caller (later, flag-gated) decides what to reject. This is the
    order-AWARE companion to ``_pairwise_descent_fraction`` above (which is order-
    agnostic and so cannot tell a lone poke from a genuine up-turn).

    Per-bar ``kind``:
      * ``dip``        — either extreme lower with neither higher (lower-high +
                         lower-low, and also lower-high/flat-low or
                         flat-high/lower-low): descending into support.
      * ``lift``       — low rises while the high holds/falls: bottoming.
      * ``noise_poke`` — the high pokes up but it is UNCONFIRMED (the low did not
                         make a higher low, or the next bar's high falls back) →
                         noise that does not break the formation.
      * ``turn``       — a CONFIRMED higher-low → higher-high that the next bar
                         carries: a real up-structure (L0's BOS-up) that ENDS the
                         test. ``confirmed_turn_bar`` is the first one.
      * ``flat``       — high and low both unchanged.

    Window ``classification``: ``rising_march`` (a SUSTAINED markup, not a test —
    mostly both-up steps with a net rising low over at least ``rising_march_min_
    steps`` steps, so a 2-bar tick-up near support is not mislabelled), ``turned``
    (a genuine VALLEY-turn: the window descended to an INTERIOR low that sits
    at/before a confirmed up-turn preceding the last bar — an all-up window with
    no descent, or an early up-blip later overrun by a new low, is not a turn),
    ``clean_dip`` (down steps >= up steps — a tie, and a window whose steps
    are all lift/noise/flat, both file here), else ``mixed``. This is an
    archived closed-set vocabulary: tightening the boundary is a measured
    change with a seam note, never a drive-by.
    ``end_shape`` is ``descending`` / ``valley`` / ``flat`` / ``mixed``.
    ``big_dip`` is returned only when ``big_dip_depth_atr`` is supplied (deep AND
    bars not tighter than the base average); otherwise ``None`` (measure-first —
    threshold set after eyeball).
    """
    highs = [float(h) for h in highs]
    lows = [float(l) for l in lows]
    n = len(highs)
    if n < 2 or len(lows) != n:
        return {
            "n": n, "steps": [], "classification": "insufficient",
            "rising_frac": 0.0, "up_steps": 0, "down_steps": 0,
            "noise_pokes": [], "confirmed_turn_bar": None,
            "end_shape": "insufficient", "depth": 0.0, "depth_frac": 0.0,
            "depth_atr": None, "median_spread": 0.0, "tighter_than_base": None,
            "rising_march": False, "big_dip": None, "window_low_idx": 0,
        }

    steps: list[dict] = []
    up_steps = down_steps = 0
    noise_pokes: list[int] = []
    confirmed_turn_bar: Optional[int] = None
    for i in range(1, n):
        dh = highs[i] - highs[i - 1]
        dl = lows[i] - lows[i - 1]
        higher_high = dh > 0
        higher_low = dl > 0
        if higher_high and higher_low:
            up_steps += 1
        elif dh <= 0 and dl < 0:
            down_steps += 1

        if higher_high:
            # Confirmed up-turn: a higher-low here AND the next bar carries the
            # high above this one. Anything else is a forgivable noise poke.
            confirmed = higher_low and (i + 1 < n) and highs[i + 1] >= highs[i]
            if confirmed:
                kind = "turn"
                if confirmed_turn_bar is None:
                    confirmed_turn_bar = i
            else:
                kind = "noise_poke"
                noise_pokes.append(i)
        elif higher_low:
            kind = "lift"
        elif dl < 0 or dh < 0:
            kind = "dip"
        else:
            kind = "flat"
        steps.append({
            "bar": i, "dh": round(dh, 4), "dl": round(dl, 4), "kind": kind,
            "over_atr": round(dh / atr, 3) if (atr and dh > 0) else 0.0,
        })

    total = n - 1
    rising_frac = up_steps / total if total else 0.0
    # A markup "march" needs SUSTAINED up-structure, not a lone up-step: a 2-bar
    # both-up shuffle (1 step, net advance ~0) is a flat base poke, not a markup.
    # Require a minimum step count so the BBN/CII/PCQ class (len-2, descent 0,
    # netAdv/box <= 0.4) is not mislabelled; OHI (4 steps, +7.8%) still qualifies.
    rising_march = bool(total >= rising_march_min_steps
                        and rising_frac >= rising_march_frac
                        and lows[-1] > lows[0])

    window_low = min(lows)
    window_low_idx = lows.index(window_low)
    high0 = highs[0]
    depth = high0 - window_low
    depth_frac = depth / high0 if high0 > 0 else 0.0
    depth_atr = (depth / atr) if (atr and atr > 0) else None

    spreads = [highs[i] - lows[i] for i in range(n)]
    median_spread = _median(spreads)
    tighter_than_base = (median_spread < float(base_spread)) if base_spread else None

    k = min(max(2, end_window), n)
    tail_lows = lows[n - k:]
    band = max(tail_lows) - min(tail_lows)
    flat_tol = (float(base_spread) * flat_band_frac) if base_spread else (depth * 0.25)
    if lows[-1] < lows[-2]:
        end_shape = "descending"
    elif band <= flat_tol:
        end_shape = "flat"
    elif window_low_idx < n - 1 and lows[-1] > window_low:
        end_shape = "valley"
    else:
        end_shape = "mixed"

    if big_dip_depth_atr is not None and depth_atr is not None:
        big_dip: Optional[bool] = bool(
            depth_atr >= float(big_dip_depth_atr) and tighter_than_base is False)
    else:
        big_dip = None

    # A confirmed up-turn only ENDS the test when it is a genuine valley-turn: the
    # window descended to an INTERIOR low (window_low_idx > 0) that sits at/before
    # the turn (no new low afterwards), with the turn before the last bar. Two
    # shapes are NOT valley-turns: an early up-blip later overrun by a new low
    # (AAON turn@bar1 then net -0.34; BTX@bar3 ends descending — low sits AFTER the
    # turn); and an all-up window with no descent at all (low at bar 0 — a short
    # markup, not a test). The raw confirmed_turn_bar still records the blip.
    turned = bool(confirmed_turn_bar is not None
                  and confirmed_turn_bar < n - 1
                  and 0 < window_low_idx <= confirmed_turn_bar)
    if rising_march:
        classification = "rising_march"
    elif turned:
        classification = "turned"
    elif down_steps >= up_steps:
        classification = "clean_dip"
    else:
        classification = "mixed"

    return {
        "n": n,
        "steps": steps,
        "classification": classification,
        "rising_frac": round(rising_frac, 3),
        "up_steps": up_steps,
        "down_steps": down_steps,
        "noise_pokes": noise_pokes,
        "confirmed_turn_bar": confirmed_turn_bar,
        "end_shape": end_shape,
        "depth": round(depth, 4),
        "depth_frac": round(depth_frac, 4),
        "depth_atr": round(depth_atr, 3) if depth_atr is not None else None,
        "median_spread": round(median_spread, 4),
        "tighter_than_base": tighter_than_base,
        "rising_march": rising_march,
        "big_dip": big_dip,
        "window_low_idx": window_low_idx,
    }


# ---------------------------------------------------------------------------
# The TREND MODEL — trends as HH/HL vs LH/LL runs, with start / climax / CHoCH.
# ---------------------------------------------------------------------------

def segment_trends(points) -> list:
    """Split a labelled HH/HL/LH/LL point stream into directional TREND segments.

    ``points`` is ``label_market_structure(...)["points"]`` (each
    ``{bar, kind, price, label, trend}``). A trend is a maximal directional run
    of the mechanical trend state:

      * it is CONFIRMED at the structural break that establishes its direction
        (``confirm_bar`` — the first HH that breaks a prior down/range = an
        uptrend's change-of-character up; the first LL that breaks a prior
        up/range = a downtrend's change-of-character down),
      * it launched off the pivot before that break (``start_bar`` — the valley
        an uptrend rallied from, the peak a downtrend fell from),
      * it TOPS at its extreme pivot (``terminal_bar`` — the highest HH of an
        uptrend / lowest LL of a downtrend: the buying/selling climax), and
      * it ENDS at the opposite structural break (``end_bar`` — the CHoCH that
        confirms the next trend), or is still running at the right edge
        (``end_bar = None``).

    ``impulse_start_bar`` is the base of the TERMINAL IMPULSE LEG — the last
    higher-low before the climax (mirror: the last lower-high before a selling
    climax) — i.e. the launch of the final push into the climax. (The automatic
    reaction is measured against the FULL leg — ``start_bar`` → climax, via
    ``elected_trend_leg_base`` — not this sub-leg.)

    Pure / measure-only: it reads the labels the substrate already assigned and
    assigns no points, moves no rails, and gates nothing. Returns one dict per
    confirmed segment, in chronological order (``[]`` when no trend is confirmed).
    """
    pts = list(points) if points else []
    n = len(pts)
    if n < 3:
        return []

    def _dir(p) -> int:
        t = p.get("trend")
        return 1 if t == "up" else (-1 if t == "down" else 0)

    # Maximal runs of a constant, non-range mechanical trend. Leading "range"
    # pivots (before the first break) belong to no confirmed trend; the trend
    # state never returns to "range" once a break has fired, so range is a
    # prefix only.
    runs: list = []
    cur = None
    run_start = None
    for idx, p in enumerate(pts):
        d = _dir(p)
        if d == 0:
            continue
        if d != cur:
            if cur is not None:
                runs.append((run_start, idx - 1, cur))
            cur = d
            run_start = idx
    if cur is not None:
        runs.append((run_start, n - 1, cur))

    segments: list = []
    for s, e, d in runs:
        want = "peak" if d > 0 else "valley"
        # The climax = the extreme pivot of the trend's own kind within the run.
        extreme_idx = None
        extreme_price = None
        for i in range(s, e + 1):
            if pts[i]["kind"] != want:
                continue
            price = float(pts[i]["price"])
            if (extreme_price is None
                    or (d > 0 and price > extreme_price)
                    or (d < 0 and price < extreme_price)):
                extreme_price = price
                extreme_idx = i
        if extreme_idx is None:            # a run with no pivot of its own kind
            continue

        launch_idx = s - 1 if s > 0 else s
        # Terminal impulse leg base = the last opposite pivot before the climax
        # (the last HL before the terminal HH / the last LH before the terminal
        # LL). Falls back to the launch pivot when the climax is the first pivot.
        opp = "valley" if d > 0 else "peak"
        impulse_idx = launch_idx
        for i in range(launch_idx, extreme_idx):
            if pts[i]["kind"] == opp:
                impulse_idx = i

        end_idx = e + 1 if e + 1 < n else None
        segments.append({
            "direction": int(d),
            "start_bar": int(pts[launch_idx]["bar"]),
            "start_price": round(float(pts[launch_idx]["price"]), 4),
            "confirm_bar": int(pts[s]["bar"]),
            "terminal_bar": int(pts[extreme_idx]["bar"]),
            "terminal_price": round(float(extreme_price), 4),
            "impulse_start_bar": int(pts[impulse_idx]["bar"]),
            "impulse_start_price": round(float(pts[impulse_idx]["price"]), 4),
            "end_bar": int(pts[end_idx]["bar"]) if end_idx is not None else None,
            "end_price": (round(float(pts[end_idx]["price"]), 4)
                         if end_idx is not None else None),
        })
    return segments


class TrendFloor(NamedTuple):
    """Per-bar covering-trend terminal: bar index, price, direction (+1/-1)."""
    bar: np.ndarray
    price: np.ndarray
    direction: np.ndarray


def trend_terminal_floor(df, *, segments=None) -> "TrendFloor":
    """Per-bar EARLIEST LEGAL BOX OPEN — the terminal pivot of the CAUSE trend.

    ``segment_trends`` already defines ``terminal_bar`` as the trend's extreme
    pivot: *the buying / selling climax*. **A base may not open before its own
    trend has printed that extreme** (operator ruling 2026-07-27, LIVN) — a box
    opening earlier is describing a still-running trend leg as an equilibrium,
    and every read anchored to it (rails, Phase C, LPS, tier) inherits the lie.

    **Overlap resolution is the load-bearing detail.** Segments overlap by one
    leg: an uptrend runs to its CHoCH, which IS the next downtrend's start. The
    EARLIER segment — the cause — wins those shared bars (first write, never
    overwritten). Letting the later one win would make a base's own automatic
    reaction (BC -> AR: the base forming) veto the box open at the very top
    where it belongs; measured 2026-07-27, that form broke 6 pinned Guided-List
    hits (AVT/CTOS/MATX/NGL/SYRE/VIK).

    Direction-blind by construction, and deliberately NOT keyed to the root's
    BC/SC kind — the root is only a scan origin, not the box's cause (LIVN's
    winning root is an SC at bar 114 while the trend that swallowed its box is
    the advance topping at 491). The cause is whichever segment actually runs
    into the candidate bar.

    Returns a ``TrendFloor`` of three ``len(df)`` arrays — the covering trend's
    terminal ``bar``, its ``price``, and its ``direction``. ``bar`` is ``-1``
    where no segment covers (no trend to still be inside of).

    **``direction`` is the live consumer.** Since the 2026-08-19 polarity
    re-key, ``bricks._cause_is_up`` reads it to decide which end of the
    lead-in the climax-terminality repair takes — that is now this array's
    ONLY caller. ``bar`` fed the trend-terminal box gate's legality test,
    which the operator RULED DELETED 2026-09-08; ``bar`` and ``price`` are
    diagnostics-only until something reads them again.

    **Do NOT rebuild a price test off these arrays — it is Tested-DEAD.**
    Refusing a box on how far the trend ran past its own rail (the removed
    ``TREND_TERMINAL_OVERSHOOT_BOX`` knob) was falsified three times: the
    operator ACCEPTS 47.9% (PXS), 82% (VIK) and 101% (MATX) of a box height
    past R — those are upthrusts inside an established base — and REJECTS LIVN
    at 20.6%. Maturity is the separator (LIVN 13 bars, PXS 53), and it needs no
    price leg to hold the case the price form was written for: CTOS (box
    R 10.20, "terminal" 10.22 = 2.7% of box height) still fires as a pinned
    Guided-List hit with the gate ON. See docs/decisions.md, Tested-DEAD.
    """
    n = 0 if df is None else len(df)
    floor = TrendFloor(np.full(max(n, 0), -1, dtype=int),
                       np.full(max(n, 0), np.nan, dtype=float),
                       np.zeros(max(n, 0), dtype=int))
    if n == 0:
        return floor
    if segments is None:
        # The Phase A climax repair kept today's skeleton until build step 10 (review finding RF-4); under the
        # climax-first walk the trend floor reads the line like everything else.
        segments = segment_trends(read_market_structure(
            df, line=(None if settings.CLIMAX_FIRST_WALK_ENABLED else False)).get("points", []))
    for seg in segments:
        end = seg["end_bar"]
        if end is None:
            # STILL RUNNING at the right edge: its "terminal" is only the
            # highest-high-so-far, an unconfirmed extreme — the trend has not
            # printed a CHoCH, so nothing proves it topped. Vetoing a box on it
            # is the very error the macro bridge's True-Root rule avoids ("the
            # right edge is now, never an AR"). VIK 2026-06 is exactly this: a
            # provisional terminal 3 bars from the edge that cost a pinned hit.
            continue
        lo = max(0, int(seg["start_bar"]))
        hi = min(n - 1, int(end))
        if lo > hi:
            continue
        unset = floor.bar[lo:hi + 1] < 0
        floor.bar[lo:hi + 1][unset] = int(seg["terminal_bar"])
        floor.price[lo:hi + 1][unset] = float(seg["terminal_price"])
        floor.direction[lo:hi + 1][unset] = int(seg["direction"])
    return floor


# The daily trend-state vocabulary (Power-Play program Task 11) — a PURE
# classification over segment_trends' own segments, never a third daily trend
# reader (HTF's `trend_state` is the declared second labeled form; this is the
# daily projection of the SAME segment substrate). Closed set; the wire copy
# lives in the frontend's TREND_STATE_LABELS registry.
TREND_STATES = ("trending", "correcting", "consolidating", "choppy")


def classify_trend_state(segments, n_bars: int) -> str:
    """One word for where the chart's right edge sits — the operator's mandate
    ("understand Trends, Chops, Corrections... and its relation to the current
    state of the graph"). PROVISIONAL rules, measure-only, no live consumer
    yet; the operator's trend-end labels (the species ruling loop) calibrate
    or re-rule them. Reads ONLY the segment dicts — no price re-read:

      * a segment RUNNING at the right edge names the state directly:
        up → ``trending``, down → ``correcting``;
      * no running segment, and the latest confirmed terminal printed within
        ``MIN_BASE_DAYS`` bars of the edge → the transition zone (the
        operator's "trend end + base open = one short zone"): after an UP
        terminal → ``correcting`` (the reaction is still forming), after a
        DOWN terminal → ``consolidating`` (the base has opened);
      * an older terminal (≥ the clock) → ``consolidating`` — the pause has
        had time to become a base;
      * no confirmed segment at all → ``choppy`` (the labeller found no
        structure to stand on).
    """
    from config import settings

    segs = list(segments or [])
    if not segs:
        return "choppy"
    running = [s for s in segs if s.get("end_bar") is None]
    if running:
        return "trending" if int(running[-1]["direction"]) == 1 else "correcting"
    last = max(segs, key=lambda s: int(s["terminal_bar"]))
    bars_since = int(n_bars) - int(last["terminal_bar"])
    if bars_since < int(settings.MIN_BASE_DAYS):
        return "correcting" if int(last["direction"]) == 1 else "consolidating"
    return "consolidating"


def measure_trend_bases(df, atr_val, elected_start_bar, elected_width) -> dict:
    """Charter measurement (TA-grade build task 8): the Minervini base COUNT
    within the current confirmed up-segment + the inter-base width ratio —
    ONE bounded box-walk producing both numbers (a second enumeration would
    silently double the only expensive new measurement). Measure-only; runs
    fires-only in the shared eval chain (unconditional since the 2026-08-22
    legacy retirement).

    Pinned semantics (pinned before code; the battery asserts each):
      * the elected base counts as ONE — the count is never zero;
      * predecessors count only INSIDE the covering confirmed up-segment; the
        walk runs on the segment-restricted sub-frame BEFORE enumeration, so
        the anchor-polarity rule holds by construction (no root is ever
        sought inside an opposite-direction trend);
      * deterministic: roots advance chronologically (search_from = climax+1)
        and a predecessor is admitted only when its start_bar is strictly
        after the previously admitted box's start_bar — the stated dedup rule
        for overlapping/nested candidates;
      * the count saturates at TREND_BASE_COUNT_CAP (Minervini counts bases
        1-4; nobody grades base 9 differently from base 12), and the walk is
        bounded by TREND_BASE_WALK_MAX_ROOTS root attempts;
      * widths compare in the SAME units — raw (R-S)/S fractions on BOTH
        sides — and the ratio is elected / most-recent-predecessor (a
        tighter current base reads < 1). The walk runs its full root budget
        even after the count saturates, so the last admission truly IS the
        most recent predecessor; a walk the budget truncated emits NO ratio
        (the real predecessor may lie beyond the truncation);
      * no predecessor → ratio None — never 1.0, never infinity;
      * the labelling refusing entirely → the WHOLE measurement is absent
        (None, None) — a fabricated count never archives.
    """
    from config import settings

    out = {"trend_base_count": None, "inter_base_width_ratio": None}
    if df is None or len(df) == 0 or elected_start_bar is None:
        return out
    try:
        points = read_market_structure(df).get("points", [])
    except Exception:
        return out
    if not points:
        return out                      # the labelling refused: absent
    start = int(elected_start_bar)
    covering = None
    for seg in segment_trends(points):
        if int(seg["direction"]) != 1:
            continue
        seg_start = int(seg["start_bar"])
        seg_end = seg["end_bar"]
        if seg_start <= start and (seg_end is None or start <= int(seg_end)):
            covering = seg              # the LATEST covering up-segment wins
    widths: list = []
    cap = int(settings.TREND_BASE_COUNT_CAP)
    # True only when the enumeration genuinely reached the segment's right
    # edge (find_root_swing returned None). The walk runs the FULL root
    # budget even after the count saturates — the ratio's contract is
    # "elected / MOST-RECENT predecessor", and the old cap break truncated
    # the RIGHT end of the enumeration, exactly where the most recent
    # predecessor lives, so saturated rows (the strongest names) archived a
    # ratio against the wrong base (2026-08-08 review, finding 8). A walk
    # the root BUDGET truncated never emits a ratio: absent, not a guess.
    # Cost: bounded by the same TREND_BASE_WALK_MAX_ROOTS the task-8 timing
    # certified (0.54 ms max/fire IS the full-budget case).
    walk_reached_right_edge = False
    if covering is not None:
        sub = df.iloc[int(covering["start_bar"]):start]
        if len(sub) >= int(settings.MIN_BASE_DAYS):
            from engine_alpha.structure.narrative import bricks  # lazy: the htf precedent
            last_admitted_start = -1
            search_from = 0
            for _ in range(int(settings.TREND_BASE_WALK_MAX_ROOTS)):
                root = bricks.find_root_swing(sub, search_from, atr_val)
                if root is None:
                    walk_reached_right_edge = True
                    break
                search_from = int(root.climax_bar) + 1
                box = bricks.validate_equilibrium(sub, root, atr_val)
                if box is None:
                    continue
                box_start = int(box.start_bar)
                s_rail = float(box.S)
                if box_start <= last_admitted_start \
                        or not np.isfinite(s_rail) or s_rail <= 0:
                    continue
                width = (float(box.R) - s_rail) / s_rail
                if not np.isfinite(width) or width <= 0:
                    continue
                widths.append(width)
                last_admitted_start = box_start
    out["trend_base_count"] = min(cap, 1 + len(widths))
    if widths and walk_reached_right_edge:
        try:
            ew = float(elected_width)
        except (TypeError, ValueError):
            ew = float("nan")
        if np.isfinite(ew) and ew > 0:
            out["inter_base_width_ratio"] = ew / widths[-1]
    return out


def elected_trend_leg_base(df, terminal_bar, direction, *,
                           order: Optional[int] = None):
    """The base of the FULL trend leg that tops at ``terminal_bar``.

    The START pivot of the elected HH/HL trend segment whose terminal (the
    buying/selling climax) sits within 3 bars of ``terminal_bar`` — i.e. the
    whole advance the climax ended: the valley a buying climax rallied from
    (``direction=+1``) / the peak a selling climax fell from (``-1``). This is the
    entire move the reaction reverses, NOT the terminal impulse sub-leg — so a
    normal reaction into the base support clears the retrace threshold in one piece
    (not split at a mid-decline pause), while a shallow wobble on the way up does not.

    Its engine consumer (``first_reaction_after``) retired 2026-09-08 with
    ``AR_FIRST_REACTION_ENABLED``; this survives because
    ``tools/research/full_package_render.py`` draws the full leg, and the climax-anchor
    program that renderer serves is still open.

    Returns ``(start_bar, start_price)`` in df positions, or ``None`` when no
    confirmed trend segment tops near the climax (the caller then falls back to the
    blind lookback extreme). Pure / measure-only.
    """
    pts = read_market_structure(df, order=order).get("points", [])
    best = None
    best_gap = None
    for s in segment_trends(pts):
        if int(s["direction"]) != int(direction):
            continue
        gap = abs(int(s["terminal_bar"]) - int(terminal_bar))
        if gap <= 3 and (best_gap is None or gap < best_gap):
            best, best_gap = s, gap
    if best is None:
        return None
    return int(best["start_bar"]), float(best["start_price"])


def _full_leg_base(df, highs, lows, terminal_bar, direction, lookback):
    """Price of the full-trend-leg base into the climax: the elected trend
    segment's start (``elected_trend_leg_base``), else the blind ``lookback``-bar
    extreme. Deep by design — the automatic reaction is measured against the whole
    advance, and a too-shallow basis is what let the reaction anchor short."""
    seg = elected_trend_leg_base(df, terminal_bar, direction)
    if seg is not None:
        return seg[1]
    lo = max(0, terminal_bar - lookback)
    if direction > 0:
        return float(np.min(lows[lo:terminal_bar + 1]))
    return float(np.max(highs[lo:terminal_bar + 1]))
