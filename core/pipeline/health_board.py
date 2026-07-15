"""Market & Sector Health Board — a passive position-in-cycle read.

The equity-momentum firing chain fires ZERO setups on broad ETFs / indices by
design (SPY/QQQ are skipped as benchmarks; the baseline gate needs an uptrending
stock; the crash/extension filters drop fallen and broken-out members), so the
Sectors + Market and Commodities + ETFs tabs render nothing. This module is a
SEPARATE, looser read that classifies EVERY member of those universes — including
SPY/QQQ as first-class members — into exactly one position-in-cycle **state**, so
those tabs become a useful "where is this in its cycle" board.

Boundaries this module lives inside (see specs/market-sector-health-board.md and
docs/health_board_state_audit.md):

* It reads ONLY the PUBLIC ``core.structure`` API — the same box detector and
  gate-free measures the firing engine uses (``find_outer_box`` for R/S,
  ``trend_template`` / ``distance_to_52w_high_pct`` for posture / drawdown). It
  NEVER imports the firing-chain helpers (``_resolve_structure_context`` /
  ``_run_eval_chain`` / the baseline+crash+extension gates), so the
  byte-parity-locked ``us_equities`` output cannot drift.
* It ``structure``-measures and then judges; it assigns NO score / tier / trigger
  and writes NOTHING to the archive.
* Every measure is evaluated on the SAME as-of bar the box detector uses
  (``df[:-STRUCTURE_EDGE_SKIP_BARS]``, i.e. ``df[-6]``), never the live edge, so a
  member's state can never lead its own geometry — the board is an END-OF-SCAN
  read, not a real-time feed (a fresh move may take a few sessions to re-label).
* ``settings`` is read LAZILY inside functions (never at import) to respect the
  backend config-vs-cwd shadowing trap.

The seven states are a CLOSED set; their ``HealthState`` declaration order is the
decision-proximity order the frontend sorts by. ``read_structure`` is deliberately
NOT reused: it only returns a ``Structure`` when a full A→B→(C?)→D narrative WITH a
completed LPS exists, so it would collapse a good LPS-less base to "no structure" —
exactly the non-firing cohort the board exists to show.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd

log = logging.getLogger("chrollo.health_board")


class HealthState(str, Enum):
    """The closed set of position-in-cycle states, in decision-proximity order.

    Declaration order == the frontend's decision-point-first sort order: members
    AT a decision point (near a rail / just broke out) surface before dormant ones
    (trending / deep correction / no structure). The ``str`` mixin makes each
    member's value its own JSON-safe wire string (e.g. ``HealthState.NEAR_RESISTANCE
    == "near_resistance"``).
    """

    NEAR_RESISTANCE = "near_resistance"          # coiled just under the box ceiling R
    POST_BREAKOUT_MARKUP = "post_breakout_markup"  # established base, price now above R
    NEAR_SUPPORT = "near_support"                # pressed against the box floor S
    CONSOLIDATING = "consolidating"              # worked two-sided box, price inside the rails
    TRENDING = "trending"                        # clean directional move, no established base
    DEEP_CORRECTION = "deep_correction"          # fallen well below its base / near the 52w low
    NO_STRUCTURE = "no_structure"                # no readable base, nothing else actionable


# The canonical wire order — the same closed set the serve-path contract and the
# frontend sort selector mirror. One definition, referenced everywhere.
HEALTH_STATE_ORDER: tuple[str, ...] = tuple(s.value for s in HealthState)


class InsufficientHistoryError(ValueError):
    """A member fetched but carries too little history to classify (< the trend
    template's 200-bar floor on the as-of frame). Distinct from a generic read
    error so the board can surface a "can't read yet" bucket rather than silently
    dropping the member or mislabeling it ``no_structure``."""


@dataclass(frozen=True)
class MemberHealth:
    """One member's classified position-in-cycle read.

    Carries the closed-set ``state`` plus the small, scale-invariant numeric facts
    the board sorts and draws by — and deliberately NO score / tier / trigger /
    setup field (there is no "buy" read here). ``R`` / ``S`` / ``base_len`` are
    ``None`` / ``0`` for a member with no readable box, so the reused card draws
    candles with no box overlay.
    """

    state: HealthState
    # (Close - S) / (R - S) at the as-of bar, 0 = floor, 1 = ceiling; None with no box.
    box_pos: Optional[float]
    # (Close / R - 1) for a broken-out member (freshest breakouts first); None otherwise.
    breakout_extension: Optional[float]
    # Fraction below the trailing 52-week high at the as-of bar (e.g. -0.07 = 7% below).
    distance_to_high_pct: Optional[float]
    R: Optional[float]
    S: Optional[float]
    base_len: int


def classify_member(df: "pd.DataFrame") -> MemberHealth:
    """Classify a single member's daily OHLCV frame into exactly one state.

    Pure and self-contained: it prepares its own as-of frame, reads only the public
    ``core.structure`` measures, and returns one :class:`MemberHealth`. Raises
    :class:`InsufficientHistoryError` when the member is too short to read; any
    other degenerate input is routed to ``no_structure`` rather than a poisoned
    value. Never mutates the caller's frame (works on an explicit ``.copy()``).

    The precedence ladder is ONE ordered, exhaustive, non-overlapping cascade so a
    member always gets exactly one state:

      1. **deep_correction** — drawdown at/below the deep-correction floor
         (classified FIRST, before any box read; also absorbs the below-SMA200
         fallen cohort the box substrate refuses).
      2. **valid box** → one of the four box states (``post_breakout_markup`` when
         the as-of close is clearly above R; else ``near_resistance`` /
         ``near_support`` by the calibrated traversal zones; else ``consolidating``).
      3. **trending** — no box, but a clean Stage-2 moving-average stack.
      4. **no_structure** — the total fallback.
    """
    from config import settings  # lazy: config-vs-cwd shadowing trap
    from core.pipeline.downloads import _trim_to_period
    from core.structure import (
        calculate_atr,
        distance_to_52w_high_pct,
        find_outer_box,
        trend_template,
    )

    min_bars = int(settings.HEALTH_MIN_BARS)
    if df is None or len(df) < min_bars:
        raise InsufficientHistoryError(
            f"need >= {min_bars} bars, have {0 if df is None else len(df)}"
        )

    # Same trailing daily window + ATR frame the firing chain reads on (a fresh
    # .copy() so the shared panel slice is never enriched in place).
    daily_df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
    daily_df["ATR_10"] = calculate_atr(daily_df, 10)

    skip = int(settings.STRUCTURE_EDGE_SKIP_BARS)
    eval_df = daily_df.iloc[:-skip] if len(daily_df) > skip else daily_df
    # trend_template needs a full 200-bar read on the as-of frame; below that the
    # member is "can't read yet", never silently mislabeled.
    if len(eval_df) < min_bars:
        raise InsufficientHistoryError(
            f"as-of frame has {len(eval_df)} bars (< {min_bars})"
        )

    as_of_close = float(eval_df["Close"].iloc[-1])
    if not math.isfinite(as_of_close):
        return _boxless(HealthState.NO_STRUCTURE, None)

    # ATR sampled on the SAME bar (df[-6]) the box/LPS zones anchor to.
    atr_raw = float(daily_df["ATR_10"].iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET])
    atr = atr_raw if (math.isfinite(atr_raw) and atr_raw > 0) else None

    drawdown = distance_to_52w_high_pct(eval_df["High"], as_of_close)

    # 1. Deep correction — a large drawdown dominates every other read.
    deep_floor = float(settings.HEALTH_DEEP_CORRECTION_DRAWDOWN)
    if drawdown is not None and drawdown <= deep_floor:
        return _boxless(HealthState.DEEP_CORRECTION, drawdown)

    # 2. Box read. find_outer_box applies the SMA200 macro gate + the full
    #    worked-equilibrium/traversal gates internally, so a returned box is a
    #    genuinely worked two-sided range (no need to re-measure traversal here).
    box = find_outer_box(daily_df)
    base_len, R, S = int(box[0]), float(box[1]), float(box[2])
    span = R - S
    has_box = (
        base_len > 0
        and math.isfinite(R)
        and math.isfinite(S)
        and math.isfinite(span)
        and span > 0
    )
    if has_box:
        box_pos = (as_of_close - S) / span  # guarded: span > 0 and inputs finite
        touch_band = (settings.TOUCH_TOLERANCE_ATR * atr) if atr is not None else 0.0
        if as_of_close > R + touch_band:
            # Coarse "price above the established box R" (the extension comparison
            # without the veto) — the honest v1 post-breakout flag.
            return MemberHealth(
                state=HealthState.POST_BREAKOUT_MARKUP,
                box_pos=round(box_pos, 4),
                breakout_extension=(round(as_of_close / R - 1.0, 4) if R > 0 else None),
                distance_to_high_pct=_round_opt(drawdown),
                R=round(R, 2),
                S=round(S, 2),
                base_len=base_len,
            )
        if box_pos >= settings.TRAVERSAL_HIGH_ZONE:
            state = HealthState.NEAR_RESISTANCE
        elif box_pos <= settings.TRAVERSAL_LOW_ZONE:
            state = HealthState.NEAR_SUPPORT
        else:
            state = HealthState.CONSOLIDATING
        return MemberHealth(
            state=state,
            box_pos=round(box_pos, 4),
            breakout_extension=None,
            distance_to_high_pct=_round_opt(drawdown),
            R=round(R, 2),
            S=round(S, 2),
            base_len=base_len,
        )

    # 3. Trending — no readable box, but a clean Stage-2 moving-average stack
    #    (price > SMA50 > SMA150 > SMA200). Pure gate-free posture measure.
    trend = trend_template(eval_df, dist_52w_high_pct=drawdown)
    if trend.get("stage2_ma_stack_pass"):
        return _boxless(HealthState.TRENDING, drawdown)

    # 4. Total fallback.
    return _boxless(HealthState.NO_STRUCTURE, drawdown)


def _boxless(state: HealthState, drawdown: Optional[float]) -> MemberHealth:
    """A state with no readable box — R/S/base_len empty so the card draws bare
    candles (no box overlay)."""
    return MemberHealth(
        state=state,
        box_pos=None,
        breakout_extension=None,
        distance_to_high_pct=_round_opt(drawdown),
        R=None,
        S=None,
        base_len=0,
    )


def _round_opt(value: Optional[float]) -> Optional[float]:
    return round(float(value), 4) if value is not None and math.isfinite(value) else None


def classify_universe_members(
    data: "pd.DataFrame", universe
) -> tuple[dict[str, MemberHealth], list[dict]]:
    """Classify EVERY member of ``universe`` off the already-fetched ``data`` panel.

    The member set is the universe's own curated CSV list PLUS its index symbols
    (SPY/QQQ), so the benchmarks appear as first-class members even though the
    firing frame-prep deliberately excludes them. Reads only the cached panel — no
    new fetch, no ProcessPool (~15–29 members, offline; simplicity over scale).

    Each member is classified inside its OWN try/except so one unreadable member
    degrades to the ``unreadable`` list rather than tearing the whole board:

      * ``short_history``  — fetched but too little history to classify.
      * ``not_available``  — a member with no column in the panel this scan.
      * ``error``          — any other read failure (surfaced, never silent).

    Returns ``(members, unreadable)`` where ``members`` maps ticker ->
    :class:`MemberHealth` and ``unreadable`` is a list of ``{ticker, reason}``.
    """
    from core.pipeline.tickers import get_cached_tickers

    uni = _resolve(universe)
    member_list = list(
        dict.fromkeys(
            [t.upper() for t in get_cached_tickers(uni.ticker_csv)]
            + [s.upper() for s in uni.index_symbols]
        )
    )
    multi = isinstance(data.columns, pd.MultiIndex)

    members: dict[str, MemberHealth] = {}
    unreadable: list[dict] = []
    for ticker in member_list:
        try:
            if multi:
                if ticker not in data.columns.get_level_values(0):
                    unreadable.append({"ticker": ticker, "reason": "not_available"})
                    continue
                frame = data[ticker].dropna()
            else:
                frame = data.dropna()
            members[ticker] = classify_member(frame)
        except InsufficientHistoryError:
            unreadable.append({"ticker": ticker, "reason": "short_history"})
        except Exception as exc:  # noqa: BLE001 — one bad member must not tear the board
            log.warning("health-board classify failed [%s]: %s", ticker, exc)
            unreadable.append({"ticker": ticker, "reason": "error"})

    return members, unreadable


def _resolve(universe):
    """Lazy universe resolution (keeps the import off module load for the
    config-vs-cwd trap)."""
    from core.pipeline.universe import resolve_universe

    return resolve_universe(universe)
