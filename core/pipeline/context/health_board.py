"""Market & Sector Health Board — a passive position-in-cycle read.

The equity-momentum firing chain fires ZERO setups on broad ETFs / indices by
design (SPY/QQQ are skipped as benchmarks; the baseline gate needs an uptrending
stock; the crash/extension filters drop fallen and broken-out members), so the
Sectors + Market and Commodities + ETFs tabs render nothing. This module is a
SEPARATE, looser read that classifies EVERY member of those universes — including
SPY/QQQ as first-class members — into exactly one position-in-cycle **state**, so
those tabs become a useful "where is this in its cycle" board.

Boundaries this module lives inside (see docs/archive/specs/market-sector-health-board.md and
docs/health_board_state_audit.md):

* It reads the member's box through the reader door (``engine_alpha.gate.read_record``:
  the frame contract, then the universe door, then the reader's parent box) and the
  shared stock measures (``engine_alpha.stock``: ``trend_template`` /
  ``distance_to_52w_high_pct`` for posture / drawdown). It never scores, so the
  ``us_equities`` output cannot drift.
* It measures and then judges; it assigns NO score / tier / trigger and writes
  NOTHING to the archive.
* Every measure is read on the last close, as the reader reads — the board is an
  END-OF-SCAN read, not a real-time feed.
* ``settings`` is read LAZILY inside functions (never at import) to respect the
  backend config-vs-cwd shadowing trap.

The seven states are a CLOSED set; their ``HealthState`` declaration order is the
decision-proximity order the frontend sorts by. A member the reader holds a box
for but reads no LPS on is still a box (``consolidating`` / ``near_*``): the
non-firing cohort is exactly what the board exists to show.
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

    Pure and self-contained: it reads the member's box through the reader door
    (``engine_alpha.gate.read_record``: the frame contract, then the universe
    door, then the reader) and the shared stock measures (``engine_alpha.stock``),
    and returns one :class:`MemberHealth`. Raises :class:`InsufficientHistoryError`
    when the member is too short to read; any other degenerate input is routed to
    ``no_structure`` rather than a poisoned value. Never mutates the caller's frame.

    The precedence ladder is ONE ordered, exhaustive, non-overlapping cascade so a
    member always gets exactly one state:

      1. **deep_correction** — drawdown at/below the deep-correction floor
         (classified FIRST, before any box read).
      2. **a box the reader holds** → one of the four box states (``post_breakout_markup``
         when the last close is more than one line area above R; else ``near_resistance``
         / ``near_support`` when the last close is within one line area —
         ``LINE_WORD_AREA_ATR`` daily ranges — of R or S; else ``consolidating``).
      3. **trending** — no box, but a clean Stage-2 moving-average stack.
      4. **no_structure** — the total fallback.
    """
    from config import settings  # lazy: config-vs-cwd shadowing trap
    from core.pipeline.market_data.downloads import _trim_to_period
    from engine_alpha import gate
    from engine_alpha import numbers as M
    from engine_alpha.chart import calculate_atr
    from engine_alpha.stock import distance_to_52w_high_pct, trend_template

    min_bars = int(settings.HEALTH_MIN_BARS)
    if df is None or len(df) < min_bars:
        raise InsufficientHistoryError(
            f"need >= {min_bars} bars, have {0 if df is None else len(df)}"
        )

    # The same trailing daily window the reader reads on (a fresh .copy() so the
    # shared panel slice is never enriched in place).
    daily_df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
    if len(daily_df) < min_bars:
        raise InsufficientHistoryError(
            f"the daily window has {len(daily_df)} bars (< {min_bars})"
        )

    as_of_close = float(daily_df["Close"].iloc[-1])
    if not math.isfinite(as_of_close):
        return _boxless(HealthState.NO_STRUCTURE, None)

    drawdown = distance_to_52w_high_pct(daily_df["High"], as_of_close)

    # 1. Deep correction — a large drawdown dominates every other read.
    deep_floor = float(settings.HEALTH_DEEP_CORRECTION_DRAWDOWN)
    if drawdown is not None and drawdown <= deep_floor:
        return _boxless(HealthState.DEEP_CORRECTION, drawdown)

    # 2. The box, through the door. None when the universe door refused the
    #    member or the reader holds no box; a read that failed is no box either.
    box = _parent_box(gate, daily_df)
    if box is not None:
        R, S = float(box.resistance.price), float(box.support.price)
        span = R - S
        box_pos = (as_of_close - S) / span
        # The line's area: the last day's range (the reader's own unit), so many
        # ranges wide. A NaN or non-positive range reads as no area.
        atr_raw = float(calculate_atr(daily_df, M.DAILY_RANGE_DAYS).iloc[-1])
        area = M.LINE_WORD_AREA_ATR * atr_raw if (math.isfinite(atr_raw) and atr_raw > 0) else 0.0
        base_len = _sessions_in(daily_df, box.opened_day, box.end_day)
        if as_of_close > R + area:
            return MemberHealth(
                state=HealthState.POST_BREAKOUT_MARKUP,
                box_pos=round(box_pos, 4),
                breakout_extension=(round(as_of_close / R - 1.0, 4) if R > 0 else None),
                distance_to_high_pct=_round_opt(drawdown),
                R=round(R, 2),
                S=round(S, 2),
                base_len=base_len,
            )
        if as_of_close >= R - area:
            state = HealthState.NEAR_RESISTANCE
        elif as_of_close <= S + area:
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
    trend = trend_template(daily_df, dist_52w_high_pct=drawdown)
    if trend.get("stage2_ma_stack_pass"):
        return _boxless(HealthState.TRENDING, drawdown)

    # 4. Total fallback.
    return _boxless(HealthState.NO_STRUCTURE, drawdown)


def _parent_box(gate, daily_df):
    """The reader's parent box for this frame, or None: the universe door refused
    the member, the reader held no box, or the read failed (a failed read is said
    by the reader's own record; the board draws no box for it)."""
    read = gate.read_record("", daily_df)
    if read is None or read.failed:
        return None
    box = read.parent
    if box is None:
        return None
    R, S = float(box.resistance.price), float(box.support.price)
    if not (math.isfinite(R) and math.isfinite(S) and R - S > 0):
        return None
    return box


def _sessions_in(df, opened_day, end_day) -> int:
    """Trading sessions from the box's first day through its last (or the frame's)."""
    start = pd.Timestamp(opened_day)
    end = pd.Timestamp(end_day) if end_day else df.index[-1]
    return int(((df.index >= start) & (df.index <= end)).sum())


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
    from core.pipeline.universe.tickers import get_cached_tickers

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
    from core.pipeline.universe.descriptor import resolve_universe

    return resolve_universe(universe)
