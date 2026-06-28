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
event reader (``~/.claude/plans/tingly-dazzling-gadget.md``).

Measure-first / opinion-free: it reads the zigzag the engine already builds and
adds labels — it never moves R/S, scores, or any canonical field. The pure
``label_market_structure(zigzag)`` is the testable core; ``read_market_structure
(df)`` builds the skeleton with the same order/PIP convention as
``segment_swings`` so the labels line up bar-for-bar with the rest of the engine.
"""
from __future__ import annotations

from typing import Optional

from config import settings
from core.structure.pivots import _build_zigzag, _find_pivots


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


def read_market_structure(df, *, lookback: Optional[int] = None,
                          order: Optional[int] = None) -> dict:
    """Build the swing skeleton off ``df`` and label it. Bar indices in the
    result are df-positional. Mirrors ``segment_swings`` exactly: same pivot
    order selection and the same PIP-substrate flag, so the labels line up with
    the swings the rest of the engine reads."""
    n_all = len(df)
    if n_all < 5:
        return _empty()
    if lookback is not None and 0 < lookback < n_all:
        win = df.iloc[n_all - lookback:]
    else:
        win = df
    base_off = n_all - len(win)

    try:
        highs = win["High"].values.astype(float)
        lows = win["Low"].values.astype(float)
    except (KeyError, TypeError, ValueError):
        return _empty()
    n = len(highs)

    if settings.PIP_PIVOTS_ENABLED:
        from core.structure.pip import pip_pivots
        zigzag = pip_pivots(highs, lows, dist_min=settings.PIP_PIVOTS_DIST_MIN)
    else:
        if order is None:
            order = (settings.PIVOT_ORDER_LONG if n >= settings.PIVOT_ORDER_THRESHOLD
                     else settings.PIVOT_ORDER_SHORT)
        peaks, valleys = _find_pivots(highs, lows, order)
        if not peaks or not valleys:
            return _empty()
        zigzag = _build_zigzag(peaks, valleys, highs, lows)

    # Re-base to df-positional bars before labelling.
    zigzag = [(int(base_off + b), k, p) for (b, k, p) in zigzag]
    return label_market_structure(zigzag)


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
    order-AWARE companion to ``lps._pairwise_descent_fraction`` (which is order-
    agnostic and so cannot tell a lone poke from a genuine up-turn).

    Per-bar ``kind``:
      * ``dip``        — lower-high and lower-low: the test descending into support.
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
    ``clean_dip`` (down steps dominate), else ``mixed``.
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
