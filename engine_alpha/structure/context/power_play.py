"""The Power-Play species archive family (program Task 7) — books of record.

The species lane (program Task 8) watches pole-qualified young bases the
default read cannot see yet (docs/power_play_program_2026-08.md; operator
ruling `c029555`). This module owns the family's declaration, its ONE
writer-facing extraction, the lane's ONE fields builder, and the shared
episode mechanics — never gates, never scores, dark until the operator's
flip. The lane ORCHESTRATION (``species_watch``, the wire vocabulary) lives
with the composed twin in ``engine_alpha.evaluation`` — structure measures,
the lane coordinates (2026-08-17 review, Fowler).

NULL discipline (the family's whole point):

* **NULL means "never evaluated"** — the lane was off, or the ticker never
  pole-qualified. Every pre-lane row reads NULL honestly.
* **"Watched but refused" is its own CLOSED-SET state** (``pp_state``):
  ``refused_clock`` (the wall itself — first legal look after breakout),
  ``refused_occupancy`` / ``refused_story`` (the cascade watched and said no,
  naming the leg), ``admitted_dark`` (the species read elected; the flag is
  dark so nothing fires). Enforced three ways (EC-19): the fresh-DB CHECK on
  the model, the write-time refusal HERE (the single stamping point), and the
  archive-layer test.
* **Candidate facts are paired writes** (EC-23): ``pp_state`` never lands
  without ``pp_clock``; the shelf quantization lands as a whole
  (numerator AND denominator) or not at all.
* **Short-shelf measurements carry raw integer counts** — on an 8-12 bar
  window a fraction hides its denominator; ``pp_lower_third_bars`` /
  ``pp_shelf_bars`` archive the thirds-occupancy as the counts themselves.
* **The zone-collision companion**: rail zones are ATR-fixed and the species
  ATR reaches back into the explosive leg, so the S+R touch zones can exceed
  the shelf's own height (the LEVI collision, squared). ``pp_zone_coverage``
  (2·tol/(R−S), raw, unclamped) rides with every zone-based read, and
  ``pp_zone_collided`` makes a collided 0.00 distinguishable from a measured
  0.00 — the pair lands together or not at all.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine_alpha.structure.events.displacement import (
    atr10_before,
    first_close_beyond,
    running_argmin,
)

__all__ = [
    "POWER_PLAY_COLUMN_SQL",
    "PP_STATES",
    "first_legal_look",
    "power_play_archive_values",
    "power_play_fields",
    "ticker_episodes",
]

# Owning declaration (the EVENT_MAP_COLUMN_SQL precedent): names, SQL types,
# extraction live HERE; all writers splat the one extraction (EC-30); the ORM
# model declares matching nullable columns as MODEL-ONLY adds (AP-7).
POWER_PLAY_COLUMN_SQL: dict[str, str] = {
    "pp_state": "TEXT",              # closed set PP_STATES; NULL = never evaluated
    "pp_clock": "INTEGER",           # the reading clock in effect (paired with state)
    "pp_climax_date": "TEXT",        # episode identity: the pole peak (ISO date)
    "pp_ar_date": "TEXT",            # episode identity: the AR low (ISO date)
    "pp_pole_gain": "FLOAT",         # best <=pole-window gain into the climax
    "pp_shelf_start_date": "TEXT",   # the watched shelf span (ISO dates)
    "pp_shelf_end_date": "TEXT",
    "pp_shelf_bars": "INTEGER",      # thirds-occupancy raw DENOMINATOR
    "pp_lower_third_bars": "INTEGER",  # thirds-occupancy raw NUMERATOR
    "pp_zone_coverage": "FLOAT",     # 2*tol/(R-S), raw, unclamped
    "pp_zone_collided": "INTEGER",   # 0/1 validity companion (lands WITH coverage)
}

# The closed set. Widening it moves CHECK + the stamping refusal below + the
# producing tests together (EC-19/EC-22) — never one of the three alone.
PP_STATES = ("refused_clock", "refused_occupancy", "refused_story",
             "admitted_dark")


def power_play_fields(state, clock, *, climax_date=None, ar_date=None,
                      pole_gain=None, shelf_start_date=None,
                      shelf_end_date=None, shelf_bars=None,
                      lower_third_bars=None, zone_coverage=None,
                      zone_collided=None) -> dict:
    """The lane's ONE write path: the ``_pp_*``-prefixed result fields for one
    watched ticker. ``state=None`` returns the empty dict — the whole family
    stays NULL (never evaluated). Every affirmative branch pairs its facts
    (EC-23): a state requires its clock; the thirds quantization is
    numerator+denominator or neither; the collision companion rides with the
    coverage it qualifies. A half-pair raises — a contradiction must fail the
    write, never land."""
    if state is None:
        return {}
    if state not in PP_STATES:
        raise ValueError(
            f"unknown pp_state {state!r} — the closed set is {'/'.join(PP_STATES)}")
    if clock is None:
        raise ValueError("pp_state without pp_clock — the pair writes as one unit")
    if (shelf_bars is None) != (lower_third_bars is None):
        raise ValueError("thirds quantization is numerator+denominator or neither")
    if (zone_coverage is None) != (zone_collided is None):
        raise ValueError("zone_coverage and zone_collided land together")
    return {
        "_pp_state": str(state),
        "_pp_clock": int(clock),
        "_pp_climax_date": climax_date,
        "_pp_ar_date": ar_date,
        "_pp_pole_gain": pole_gain,
        "_pp_shelf_start_date": shelf_start_date,
        "_pp_shelf_end_date": shelf_end_date,
        "_pp_shelf_bars": shelf_bars,
        "_pp_lower_third_bars": lower_third_bars,
        "_pp_zone_coverage": zone_coverage,
        "_pp_zone_collided": zone_collided,
    }


# ── The species episode mechanics (ONE implementation — EC-18) ──────────────
# The census (tools/research/power_play_census.py) and the live lane
# (evaluation.species_watch) share these; neither re-implements the
# enumeration or the wall arithmetic.

PEAK_DEDUP_BARS = 10


def ticker_episodes(ticker, df, pole_gain, pole_window):
    """Pole-qualified (climax, AR) episodes for ONE frame, with the
    collector's own mechanics: trailing local-max peak; AR = the argmin low
    within ``AR_MAX_BARS`` whose close confirmed >= ``AR_MIN_DROP_PCT``;
    deterministic left-to-right dedup. Moved here verbatim from the census
    (program Task 8) so the instrument and the lane can never drift."""
    from config import settings

    n = len(df)
    if n < pole_window + 20:
        return []
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)

    low_roll = pd.Series(lows).rolling(pole_window, min_periods=5).min().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        gain = np.where(low_roll > 0, highs / low_roll - 1.0, 0.0)
    # The collector's local-max test spans the bar itself + LOCAL_PEAK_BARS
    # preceding bars (see collect_root_anchors: highs[local_start:i+1]) — a
    # trailing rolling window of that span + 1, DERIVED so a retune moves
    # both reads together (2026-08-17 review, McKinney).
    peak_span = int(settings.LOCAL_PEAK_BARS) + 1
    peak_roll = pd.Series(highs).rolling(peak_span, min_periods=1).max().to_numpy()
    is_peak = (highs >= peak_roll) & (gain >= pole_gain)

    ar_max = int(settings.AR_MAX_BARS)
    ar_drop = float(settings.AR_MIN_DROP_PCT)
    raw = []
    for i in np.flatnonzero(is_peak):
        j0, j1 = i + 1, min(n, i + 1 + ar_max)
        if j0 >= j1:
            continue                       # frame ends at the peak: no AR yet
        if closes[j0:j1].min() > highs[i] * (1.0 - ar_drop):
            continue                       # reaction never confirmed (mid-pole bar)
        ar = j0 + int(np.argmin(lows[j0:j1]))
        raw.append({"peak": int(i), "ar": int(ar),
                    "peak_high": float(highs[i]),
                    "gain": round(float(gain[i]), 3),
                    "depth": round(float((highs[i] - lows[ar]) / highs[i]), 3)})

    kept = []
    for ep in raw:                          # deterministic left-to-right dedup
        if kept and ep["ar"] == kept[-1]["ar"]:
            if ep["peak_high"] > kept[-1]["peak_high"]:
                kept[-1] = ep
            continue
        if kept and (ep["peak"] - kept[-1]["peak"]) < PEAK_DEDUP_BARS:
            if ep["peak_high"] >= kept[-1]["peak_high"]:
                kept[-1] = ep
            continue
        kept.append(ep)

    idx = df.index
    # The breakout wall: an episode is RESOLVED at the first close beyond
    # the pole peak — plus the departure yardstick when the dark knob is on
    # (POWER_PLAY_BREAKOUT_DEPARTURE_ATR × ATR10 over the ten bars BEFORE
    # the crossing): a close hugging the peak is base-building, not a
    # resolution (the drift-up misfile; operator S1 rulings 2026-08-18).
    # 0.0 keeps the close-above-peak arithmetic byte-identical. The wall
    # arithmetic itself now lives in the displacement seam (story-chain
    # Task 5) — extracted verbatim, this call delegates; a NaN yardstick at
    # the frame head fails closed there (unresolved), unreachable in
    # practice because the pole screen needs >= pole_window bars.
    departure = float(getattr(settings, "POWER_PLAY_BREAKOUT_DEPARTURE_ATR", 0.0))
    wall_lift = (atr10_before(highs, lows, closes) * departure
                 if departure > 0.0 else None)
    for ep in kept:
        ep["breakout"] = first_close_beyond(
            closes, ep["peak_high"], ep["ar"] + 1, lift=wall_lift)
        ep["ticker"] = ticker
        ep["climax_date"] = str(idx[ep["peak"]].date())
        ep["ar_date"] = str(idx[ep["ar"]].date())
        ep["breakout_date"] = (str(idx[ep["breakout"]].date())
                               if ep["breakout"] is not None else None)
    return kept


def first_legal_look(ep, clock, df):
    """The first as-of POSITION (raw frame) where the anchor is seedable —
    the collector's AR-age and climax-age walls solved for the as-of, against
    the reaction the walk could actually SEE on that day.

    THE INVARIANT: a walk standing on session ``p`` never reads the reaction
    past bar ``p - skip``. The collector anchors on the edge-TRIMMED frame
    (``eval_df = df[:-STRUCTURE_EDGE_SKIP_BARS]``), so the newest ``skip``
    sessions are reserve — they exist, but no anchor may be built on them.
    Every prefix fact tested at ``p`` is therefore read at ``p - skip``,
    clamped to the reaction window's last bar: whether a confirming close has
    printed, and where the reaction low stands.

    The episode's recorded AR is the hindsight-final argmin over the full
    reaction window; the walk sees the RUNNING argmin of the bars outside the
    reserve, so when the reaction low deepens late the lane clears the AR-age
    wall at an earlier, shallower AR and watches sooner than the final-AR
    closed form admits (2026-08-17 review, McKinney). Reading that prefix at
    ``p`` instead of ``p - skip`` biased both ways — a confirming close
    printing inside the reserve watched up to ``skip`` sessions EARLY, a low
    deepening inside the reserve watched LATE (2026-08-20 review, finding 3).

    The terminal bound is the day the WHOLE reaction window has cleared the
    reserve: there the visible reaction IS the episode's own AR and its
    confirming close, so the final-AR closed form satisfies itself. That day
    is part of the bound — a confirmation printing late in the reaction is
    not walk-visible at the AR-age wall alone. The answer may sit at or past
    ``len(df)`` (pending: not yet watchable)."""
    from config import settings

    skip = int(settings.STRUCTURE_EDGE_SKIP_BARS)
    n = len(df)
    peak = int(ep["peak"])
    floor_p = peak + clock + skip                      # the climax-age wall
    j0 = peak + 1
    j1 = min(n, peak + 1 + int(settings.AR_MAX_BARS))
    if j1 <= j0:
        return max(int(ep["ar"]) + clock + skip - 1, floor_p)
    lows = df["Low"].to_numpy(dtype=float)[j0:j1]
    closes = df["Close"].to_numpy(dtype=float)[j0:j1]
    thr = float(ep["peak_high"]) * (1.0 - float(settings.AR_MIN_DROP_PCT))

    # Prefix state of the reaction window: the running argmin + whether a
    # confirming close has printed yet, per bar — indexed by the bar the walk
    # is READING (p - skip), never by the as-of it is standing on. Through
    # the displacement seam's own primitive (ONE prefix-argmin law, EC-3);
    # run_ar carries df-absolute positions, hence the + j0 rebase.
    run_ar = running_argmin(lows) + j0
    confirmed = np.logical_or.accumulate(closes <= thr)

    # The walk terminates at the first day BOTH walls are satisfiable on
    # walk-visible evidence: the reaction window fully out of the reserve
    # (``j1 - 1 + skip``, where the visible AR is the episode's own and its
    # confirming close has printed) and the two age walls cleared.
    final_wall = max(int(ep["ar"]) + clock + skip - 1, floor_p, j1 - 1 + skip)
    p = max(floor_p, j0 + skip)
    while p < final_wall:
        k = min(p - skip, j1 - 1) - j0
        if k >= 0 and confirmed[k] and p >= int(run_ar[k]) + clock + skip - 1:
            return p
        p += 1
    return final_wall


def power_play_archive_values(get, *, prefixed: bool) -> dict:
    """Row -> {column: value} (live prefixed / seed unprefixed; NaN-scrubbed,
    INTEGER coerced — the family contract). The write-time closed-set refusal
    lives HERE, the single stamping point: SQLite's ADD COLUMN path cannot
    retrofit the fresh-DB CHECK onto the live table, so an illegal state must
    die in the producer, loudly, on every writer (EC-19/EC-30)."""
    out = {}
    for col, sql_type in POWER_PLAY_COLUMN_SQL.items():
        value = get(("_" + col) if prefixed else col)
        if value is not None:
            try:
                if pd.isna(value):
                    value = None
            except (TypeError, ValueError):
                pass
        if value is not None and sql_type == "INTEGER":
            value = int(value)
        out[col] = value
    state = out["pp_state"]
    if state is not None and state not in PP_STATES:
        raise ValueError(
            f"unknown pp_state {state!r} — the closed set is {'/'.join(PP_STATES)}")
    # The family's PAIR laws hold at the one layer EVERY writer rides
    # (EC-23; 2026-08-17 review, Leach): the lane's fields builder enforces
    # them upstream, but the seed and manual shapes reach this extraction
    # directly — a half-pair contradiction must die here, not land.
    if state is not None and out["pp_clock"] is None:
        raise ValueError("pp_state without pp_clock — the pair writes as one unit")
    if (out["pp_shelf_bars"] is None) != (out["pp_lower_third_bars"] is None):
        raise ValueError("thirds quantization is numerator+denominator or neither")
    if (out["pp_zone_coverage"] is None) != (out["pp_zone_collided"] is None):
        raise ValueError("pp_zone_coverage and pp_zone_collided land together")
    return out
