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

import numpy as np

from config import settings
from engine_alpha.structure.pivots import _find_pivots, _pivot_order, _swing_skeleton


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
    result are df-positional. Mirrors ``segment_swings``' pivot order selection,
    so the labels line up with the swings the rest of the engine reads. The
    MACRO Phase-A read (``phase_a.macro_bridge_zigzag``) deliberately does NOT
    apply here: event labels want the fine skeleton, the Phase-A bridge wants
    the coarse one — same substrate, different zoom."""
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

    if order is None:
        order = _pivot_order(n)
    peaks, valleys, zigzag = _swing_skeleton(highs, lows, order, _find_pivots)
    if not peaks or not valleys:
        return _empty()

    # Re-base to df-positional bars before labelling.
    zigzag = [(int(base_off + b), k, p) for (b, k, p) in zigzag]
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
    ``elected_trend_leg_base`` — not this sub-leg; see ``first_reaction_after``.)

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


def elected_trend_leg_base(df, terminal_bar, direction, *, tol: int = 3,
                           order: Optional[int] = None):
    """The base of the FULL trend leg that tops at ``terminal_bar``.

    The START pivot of the elected HH/HL trend segment whose terminal (the
    buying/selling climax) sits within ``tol`` bars of ``terminal_bar`` — i.e. the
    whole advance the climax ended: the valley a buying climax rallied from
    (``direction=+1``) / the peak a selling climax fell from (``-1``). This is the
    entire move the reaction reverses, NOT the terminal impulse sub-leg — so a
    normal reaction into the base support clears the retrace threshold in one piece
    (not split at a mid-decline pause), while a shallow wobble on the way up does
    not (see ``first_reaction_after``).

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
        if gap <= tol and (best_gap is None or gap < best_gap):
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


def first_reaction_after(df, terminal_bar, *, direction, atr,
                         retrace_frac, up_leg_lookback,
                         bounce_atr_mult, bounce_drop_frac,
                         end_bar: Optional[int] = None):
    """The AUTOMATIC REACTION extreme after a trend's terminal swing.

    Phase-A election, form 3 of 3 (bar-level AR refinement, CLIMAX-GIVEN —
    it never elects the climax); forms 1 and 2 are
    ``segmentation._find_root_swing`` and ``phase_a._validated_bridge``.

    Derived from the HH/HL trend model: the terminal swing (a buying-climax peak
    for ``direction=+1``, a selling-climax valley for ``-1``) tops the trend, and
    the automatic reaction is the FIRST continuous counter-move off it. The
    reaction is the running extreme that only "counts" once it retraces
    ``retrace_frac`` of the trend's FULL leg — the whole advance the climax ended,
    from the elected trend segment's start (``_full_leg_base``), NOT the terminal
    impulse sub-leg — and it is closed at the first BIG confirmed bounce off that
    extreme: a counter-rally of >= ``max(bounce_atr_mult*ATR, bounce_drop_frac*
    drop)`` (mirror: a give-back for a selling climax). The full-leg basis plus the
    big-bounce close are what stop it over-tightening at a mid-decline pause: a
    genuine reaction runs to the support that anchors the base, and a shallow poke
    on the way up neither clears the retrace nor produces a big bounce (the
    operator's dated reading, 2026-07-05).

    Returns the reaction extreme bar (a low for +1, a high for -1) in
    ``(terminal_bar, end_bar]`` (``end_bar`` defaults to the last bar), or
    ``None`` when no counter-move reaches the retrace threshold inside the window
    (a one-way run that only stops at the base edge). Measure-only: it reads the
    reaction, it does not decide what to draw — the overlay caller owns the
    tighten-only / span contract.
    """
    if df is None or not ({"High", "Low"} <= set(df.columns)):
        return None
    try:
        atr = float(atr)
    except (TypeError, ValueError):
        return None
    if not (atr > 0) or not np.isfinite(atr):
        return None
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    n = len(highs)
    terminal_bar = int(terminal_bar)
    last = n - 1 if end_bar is None else min(int(end_bar), n - 1)
    if not (0 <= terminal_bar < last):
        return None
    lookback = int(up_leg_lookback)
    retrace = float(retrace_frac)
    b_mult = float(bounce_atr_mult)
    b_frac = float(bounce_drop_frac)

    if direction > 0:
        peak = highs[terminal_bar]
        up_leg = peak - _full_leg_base(df, highs, lows, terminal_bar, 1, lookback)
        if up_leg <= 0:
            return None
        threshold = peak - retrace * up_leg
        run_low, run_low_bar, reached = peak, terminal_bar, False
        for b in range(terminal_bar + 1, last + 1):
            if lows[b] < run_low:
                run_low, run_low_bar = lows[b], b
            if run_low <= threshold:
                reached = True
            if reached:
                bounce = max(b_mult * atr, b_frac * (peak - run_low))
                if highs[b] >= run_low + bounce:        # first BIG confirmed bounce
                    break
        return run_low_bar if (reached and terminal_bar < run_low_bar <= last) else None

    trough = lows[terminal_bar]
    dn_leg = _full_leg_base(df, highs, lows, terminal_bar, -1, lookback) - trough
    if dn_leg <= 0:
        return None
    threshold = trough + retrace * dn_leg
    run_hi, run_hi_bar, reached = trough, terminal_bar, False
    for b in range(terminal_bar + 1, last + 1):
        if highs[b] > run_hi:
            run_hi, run_hi_bar = highs[b], b
        if run_hi >= threshold:
            reached = True
        if reached:
            give_back = max(b_mult * atr, b_frac * (run_hi - trough))
            if lows[b] <= run_hi - give_back:           # first BIG confirmed give-back
                break
    return run_hi_bar if (reached and terminal_bar < run_hi_bar <= last) else None
