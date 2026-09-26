"""Bar-by-bar scaled-exit trade simulator (pure, deterministic).

The fixed-horizon CAR/abnormal reads measure PASSIVE hold — which understates a
momentum strategy that harvests the excursion. This module simulates the ACTUAL
exit discipline: enter at the signal, risk to a stop (1R), and scale out at a
ladder of R-multiple targets, letting the rest run to a horizon cap.

  realized_r = sum over exited tranches of (fraction * R-at-exit)

where R = (entry - stop) in price terms and r_of(price) = (price - entry) / R.
A full stop with no target hit = -1R. A trade that fills the whole 3R/6R/8R
ladder (0.5/0.25/0.25) = 0.5*3 + 0.25*6 + 0.25*8 = +5.0R.

Conventions (conservative unless noted):
  * Entry bar (i=0): targets may fill (price ran up post-signal) but the STOP is
    NOT checked — the bar's low may predate entry. Stop monitoring starts bar 1.
  * Within a later bar: the STOP is checked BEFORE targets (worst-case ordering).
  * Gaps: a gap-down through the stop fills at the OPEN (worse than the stop); a
    gap-up through a target fills at the OPEN (better than the target).
  * stop_mode='breakeven' raises the stop to entry once the FIRST target fills
    (the "risk-free the trade" trail). 'fixed' keeps the initial stop throughout.
  * Any unsold fraction at the horizon (or the last available bar) exits at that
    bar's close.

Pure: arrays in, dict out. No I/O, no price-panel knowledge.
"""
from __future__ import annotations

from typing import Optional, Sequence

# The operator's ladder: (R-multiple target, fraction of the ORIGINAL position).
DEFAULT_LADDER: tuple[tuple[float, float], ...] = ((3.0, 0.5), (6.0, 0.25), (8.0, 0.25))
DEFAULT_MAX_BARS = 60


def simulate_scaled_exit(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    entry: float,
    stop: float,
    ladder: Sequence[tuple[float, float]] = DEFAULT_LADDER,
    stop_mode: str = "fixed",
    max_bars: int = DEFAULT_MAX_BARS,
    trail_r: Optional[float] = None,
) -> Optional[dict]:
    """Simulate one trade's scaled exit over a forward OHLC path.

    ``trail_r`` (optional): once ALL fixed ladder targets have filled, any leftover
    fraction (the "runner") rides a trailing stop ``trail_r`` R below the running
    high-water mark (ratcheting up, floored at the current hard stop) instead of
    dumping at a fixed target — the way you let a winner run without a cap. The
    trail uses the PRIOR bars' high-water (no intrabar look-ahead). ``None`` keeps
    the pure fixed-ladder behaviour (leftover rides to the horizon close).

    Returns None on a degenerate setup (stop at/above entry, or no bars). Otherwise
    a dict: realized_r, realized_ret (fraction), sold (fraction closed), reason
    ('targets' | 'stop' | 'gap_stop' | 'breakeven_stop' | 'trail_stop' | 'horizon'),
    bars_held, targets_hit (list of R-mults that filled), max_r (best r_of(high)).
    """
    n = min(len(opens), len(highs), len(lows), len(closes), max_bars)
    R = entry - stop
    if R <= 0 or n == 0 or entry <= 0:
        return None
    ladder = sorted(ladder, key=lambda x: x[0])

    def r_of(price: float) -> float:
        return (price - entry) / R

    sold = 0.0
    realized_r = 0.0
    cur_stop = stop
    ti = 0
    targets_hit: list[float] = []
    reason = "horizon"
    bars_held = 0
    hw_r = 0.0   # high-water in R from bars STRICTLY BEFORE the current one

    for i in range(n):
        o, h, l, c = float(opens[i]), float(highs[i]), float(lows[i]), float(closes[i])
        bars_held = i + 1

        # Runner = the leftover fraction after every fixed target has filled; it
        # trails only once the fixed ladder is exhausted. eff_stop uses the PRIOR
        # bars' high-water (hw_r is updated AFTER this check), so no look-ahead.
        runner_active = trail_r is not None and ti >= len(ladder) and sold < 0.999
        eff_stop = cur_stop
        if runner_active:
            eff_stop = max(cur_stop, entry + (hw_r - trail_r) * R)

        # --- STOP first (skipped on the entry bar; conservative ordering after) ---
        if i > 0:
            if o <= eff_stop:  # gap down through the stop -> fill at the open
                realized_r += (1.0 - sold) * r_of(o)
                sold = 1.0
                reason = "trail_stop" if runner_active else "gap_stop"
                break
            if l <= eff_stop:
                realized_r += (1.0 - sold) * r_of(eff_stop)
                sold = 1.0
                reason = ("trail_stop" if runner_active
                          else "breakeven_stop" if cur_stop >= entry else "stop")
                break

        # High-water AFTER the stop check (so the trail lags by one bar).
        if h > 0:
            hw_r = max(hw_r, r_of(h))

        # --- TARGETS (ascending); fill at the open on a gap-up through the target ---
        while ti < len(ladder):
            rm, frac = ladder[ti]
            tgt = entry + rm * R
            if h >= tgt:
                fill = o if o >= tgt else tgt
                realized_r += frac * r_of(fill)
                sold += frac
                targets_hit.append(rm)
                ti += 1
                if stop_mode == "breakeven" and cur_stop < entry:
                    cur_stop = entry
            else:
                break
        if sold >= 0.999:
            reason = "targets"
            break

    # Remainder exits at the last bar's close.
    if sold < 0.999:
        last_close = float(closes[n - 1])
        realized_r += (1.0 - sold) * r_of(last_close)
        sold = 1.0

    return {
        "realized_r": realized_r,
        "realized_ret": realized_r * (R / entry),   # R-units -> return fraction
        "sold": 1.0,
        "reason": reason,
        "bars_held": bars_held,
        "targets_hit": targets_hit,
        "max_r": hw_r,
    }


def parse_ladder(spec: str) -> list[tuple[float, float]]:
    """Parse a '3:0.5,6:0.25,8:0.25' ladder spec into [(r, frac), ...].

    Fractions must sum to <= 1.0 (any shortfall rides to the horizon). Raises
    ValueError on a malformed spec or fractions summing above 1.
    """
    out: list[tuple[float, float]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        r_s, f_s = part.split(":")
        out.append((float(r_s), float(f_s)))
    total = sum(f for _, f in out)
    if total > 1.0 + 1e-9:
        raise ValueError(f"ladder fractions sum to {total} > 1.0")
    return out
