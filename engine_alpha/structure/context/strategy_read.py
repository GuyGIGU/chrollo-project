"""The strategy read (Surface the Read Task 13) — held-through-correction,
measure-first.

The operator's concordance target has two halves: Tactics (the base's own
geometry — the surfaces the narrative block already serves) and STRATEGY —
where this base sits in the larger campaign: how deep the correction cut into
the advance that preceded it, and whether the base floor held the ground the
automatic reaction claimed. This module measures that and judges NOTHING:

- ``strategy_correction_depth_pct`` — how far the elected base's floor (S)
  sits below the resolved climax bar's high, as a fraction of that high. The
  raw "how much was surrendered" number — SIGNED: negative means the floor
  holds ABOVE the climax bar's high (the recovery-above-climax shape a
  selling-climax root produces — ALB is the live example). The sign carries
  the campaign shape; no add-time expectation is imposed on it.
- ``strategy_floor_above_ar`` — 0/1: the base floor held AT or ABOVE the
  automatic reaction's low (the correction's first claimed ground was never
  undercut by the base).

Both are archived raw on every fire (NULL = never measured), never gate,
never score; a ruled judgment over them is a LATER calibration against the
live archive, not an add-time threshold (measure-first doctrine). Flag-gated
``STRATEGY_READ_ENABLED`` (dark) with the full EC-8 protocol.
"""
from __future__ import annotations

import logging
import math

import pandas as pd

__all__ = [
    "STRATEGY_COLUMN_SQL",
    "strategy_archive_values",
    "strategy_read_fields",
]

_log = logging.getLogger("chrollo.strategy_read")

# Owning declaration (the EVENT_MAP_COLUMN_SQL precedent): names, SQL types,
# extraction live HERE; both archive writers splat the one extraction; the ORM
# model declares matching nullable columns as MODEL-ONLY adds.
STRATEGY_COLUMN_SQL: dict[str, str] = {
    "strategy_correction_depth_pct": "FLOAT",   # (climax high − S) / climax high
    "strategy_floor_above_ar": "INTEGER",       # 0/1: S >= the AR bar's low
}


def strategy_read_fields(df, structure) -> dict:
    """The two raw strategy measures for ONE fired evaluation, ``_``-prefixed
    for the live result row. Reads only facts the walk already resolved
    (climax/AR bars, the elected S) — no new detection, no re-election.

    Degrade contract (council review 2026-08-05, finding 3): the family is
    all-or-nothing — a NaN bar at the climax or AR (a reachable reality;
    ``event_map_episode_nan_bars`` exists because of them) returns the empty
    dict, ONE honest NULL family. It must never archive a half-measured pair:
    ``floor >= nan`` is False, so an unguarded NaN AR low would fabricate the
    measured fact "the base floor undercut the AR" (0) while the depth went
    NULL. And a lookup failure logs LOUDLY (EC-20 containment shape) — these
    inputs cannot legitimately be absent on a fire, so silence would record a
    broken measure as "never measured", indistinguishable from pre-flip rows.
    """
    try:
        climax_high = float(df["High"].iloc[int(structure.climax_bar)])
        ar_low = float(df["Low"].iloc[int(structure.ar_bar)])
        floor = float(structure.S)
    except (KeyError, IndexError, TypeError, ValueError):
        _log.error("strategy read failed on a FIRE — resolved facts missing "
                   "(climax_bar/ar_bar/S); archiving NULL, but this is a "
                   "defect, not an unmeasured row", exc_info=True)
        return {}
    if not all(math.isfinite(v) for v in (climax_high, ar_low, floor)):
        return {}
    if not climax_high > 0:
        return {}
    return {
        "_strategy_correction_depth_pct": (climax_high - floor) / climax_high,
        "_strategy_floor_above_ar": int(floor >= ar_low),
    }


def strategy_archive_values(get, *, prefixed: bool) -> dict:
    """Row -> {column: value} (live prefixed / seed unprefixed; NaN-scrubbed,
    INTEGER coerced — the family contract)."""
    out = {}
    for col, sql_type in STRATEGY_COLUMN_SQL.items():
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
    return out
