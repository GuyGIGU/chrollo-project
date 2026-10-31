"""The box's life (stage 4 of the walk): when the box shown gives way, and to which pair. The first pair to become
a box is shown; another takes its place by one of his rules (``inside_a_live_trend``, ``left_for_good``, ``wraps``,
``came_back_to``, or ``out_respected`` under the election by respect). ``lives`` reads the chain day by day on what
each day knew; the why-sentence of every hand-over is a constant at the top, printed by the trail.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from engine_alpha import numbers as M
from engine_alpha.box.pairs import RESISTANCE, SUPPORT, Pair, _respects


#: Why a box is shown.
FIRST_BOX = "the first pair to become a box"


#: His GFR, Thu 16/10/2026: the sibling pair tried first (same opening anchor, earlier second) takes the place at birth.
TRIED_FIRST = "the pair tried before it became a box"


LIVE_TREND = "the box before it was anchored inside a live trend"


LEFT_FOR_GOOD = "the price left the box before it and the bars no longer came back to both its rails"


CAME_BACK = "the dip came back: the bars are back at both rails of the box it had given up"


#: His AMTB, Wed 28/10/2026: a one-bar box the bars never came back to gives way to the tighter pair they live in.
WRAPS = "the box was one bar's own high and low; the pair inside it the bars live in and come back to is the box"


#: The election by respect, Fri 30/10/2026: the pair the bars touch most is the box (behind ``RESPECT_ELECTS``).
RESPECTED = "the bars respect the pair more than the box before it: they touch its rails and it wraps them"


# --------------------------------------------------------------------------- #
# Stage 4: the box's life                                                     #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Life:
    """One box in the read's history: the pair, the day the reader began to show it and why, and — once a newer
    box took its place — the day its lines stop."""
    pair: Pair
    shown_bar: int
    why: str
    ended_bar: Optional[int] = None
    trend_end: Optional[dict] = None    # the trend end whose rise or fall swallowed the box before it
    lead: Optional[int] = None          # by how many touches it led the box before it (the election by respect)


def poke_came_back(shown: Pair, high, low, climax_bar: int, read_bar: int) -> Optional[bool]:
    """His EXPD, Sat 18/10/2026: a run past the top of a box already born is the box's own poke when the bars came
    back to both its rails within the fifteen trading days from the run's top; None until those days are all known."""
    last = int(climax_bar) + int(M.BOX_DAYS) - 1
    if int(read_bar) < last:
        return None
    days = np.arange(int(climax_bar), last + 1)
    return bool(_back_at_both(shown, high, low, int(climax_bar), days).any())


def knew_the_rails(shown: Pair, high, low) -> bool:
    """His HCA, Sat 24/10/2026: the bars knew the pair's rails before it opened — in the ``KNOWN_RAILS_DAYS`` before,
    ``KNOWN_RAILS_MIN_BARS`` highs at its resistance and lows at its support, within ``KNOWN_RAILS_AREA_RANGES``."""
    opening = int(shown.opening_bar)
    first = max(0, opening - int(M.KNOWN_RAILS_DAYS))
    near = float(M.KNOWN_RAILS_AREA_RANGES) * shown.unit
    at_r = int((np.abs(high[first:opening] - shown.R) <= near).sum())
    at_s = int((np.abs(low[first:opening] - shown.S) <= near).sum())
    return at_r >= int(M.KNOWN_RAILS_MIN_BARS) and at_s >= int(M.KNOWN_RAILS_MIN_BARS)


def poke_stayed_in(shown: Pair, high, low, climax_bar: int, read_bar: int) -> Optional[bool]:
    """His HCA, Sat 24/10/2026: a run over a pair the bars knew is its own poke when the bars came back to both rails
    within fifteen days and their middles sat inside it more often than over it; None until those days are known."""
    back = poke_came_back(shown, high, low, climax_bar, read_bar)
    if not back:
        return back
    after = slice(int(climax_bar) + 1, int(climax_bar) + int(M.BOX_DAYS))
    middle = (np.asarray(high[after], dtype=float) + np.asarray(low[after], dtype=float)) / 2.0
    inside = int(((middle >= shown.S) & (middle <= shown.R)).sum())
    return inside > int((middle > shown.R).sum())


def _run_over_a_known_pair(shown: Pair, trend: dict, high, low) -> bool:
    """A rise over a pair the bars knew (``knew_the_rails``); never a fall."""
    return trend["kind"] == "BC" and high is not None and knew_the_rails(shown, high, low)


def inside_a_live_trend(shown: Pair, new: Pair, trends, day: int, high=None, low=None,
                        known_rails: bool = True) -> Optional[dict]:
    """His anchor rule, Mon 27/07/2026: the trend end known by ``day`` whose run began before the shown pair's anchor
    and whose walk starts after it, the newer pair opening on or after that foot; None when there is none."""
    found = None
    for trend in trends:
        if trend["known_bar"] > day or trend.get("foot_bar") is None or trend["foot_bar"] > new.opening_bar:
            continue
        if (trend["kind"] == "BC") != shown.top_first:
            continue                    # a rise swallows a pair that opened on a top, a fall one on a low
        if trend["kind"] == "BC" and high is not None and shown.birth_bar is not None \
                and trend["climax_bar"] > shown.birth_bar \
                and poke_came_back(shown, high, low, trend["climax_bar"], day) is not False:
            continue                    # a run past the top of a box already born: not judged yet, or a poke
        if known_rails and _run_over_a_known_pair(shown, trend, high, low) \
                and poke_stayed_in(shown, high, low, trend["climax_bar"], day) is not False:
            continue                    # a run past the top of a pair the bars knew: not judged yet, or a poke
        if trend["start_bar"] < shown.opening_bar < trend["foot_bar"] and \
                (found is None or trend["known_bar"] < found["known_bar"]):
            found = trend               # the one known first
    return found


def _back_at_both(pair: Pair, high, low, first: int, days) -> np.ndarray:
    """Per day of ``days``: a bar was back at both rails over the last fifteen trading days, never before ``first``."""
    last = int(days[-1])
    on_r, on_s = _respects(high[first:last + 1], low[first:last + 1], pair.R, pair.S, pair.area)
    at_r, at_s = np.concatenate(([0], np.cumsum(on_r))), np.concatenate(([0], np.cumsum(on_s)))
    since = np.maximum(first, days - (int(M.BOX_DAYS) - 1))
    return (at_r[days - first + 1] > at_r[since - first]) & (at_s[days - first + 1] > at_s[since - first])


def _back_at_rail(pair: Pair, rail: str, high, low, first: int, days) -> np.ndarray:
    """Per day of ``days``: a bar was back at ONE rail over the last fifteen trading days, never before ``first``."""
    last = int(days[-1])
    on_r, on_s = _respects(high[first:last + 1], low[first:last + 1], pair.R, pair.S, pair.area)
    at = np.concatenate(([0], np.cumsum(on_r if rail == RESISTANCE else on_s)))
    since = np.maximum(first, days - (int(M.BOX_DAYS) - 1))
    return at[days - first + 1] > at[since - first]


def far_rail(new: Pair, shown: Pair) -> str:
    """The shown box's rail the price would have to cross coming back from the newer pair: its support for a pair
    above, its resistance for a pair below; "no longer come back" is read on it (his DSGX, Sat 18/10/2026)."""
    return SUPPORT if new.S >= shown.R - shown.area else RESISTANCE


def lies_beyond(new: Pair, shown: Pair) -> bool:
    """The newer pair lies beyond the shown box: its support in or above the shown resistance's area, or its
    resistance in or below the shown support's area. The one judgment the walk's take-over and the mini both ask."""
    return new.S >= shown.R - shown.area or new.R <= shown.S + shown.area


def left_for_good(shown: Pair, new: Pair, high, low, since: int, read_bar: int) -> Optional[int]:
    """His sentences 9 and 10 (his DSGX, Sat 18/10/2026): the first day from ``since`` on, ``new`` a box lying beyond
    the shown box, that the bars came back to both its rails and not to the shown box's far rail in fifteen days."""
    if new.opening_bar <= shown.opening_bar:
        return None
    if not lies_beyond(new, shown):
        return None
    first, start = new.opening_bar, max(int(since), int(new.birth_bar))
    if start > read_bar:
        return None
    days = np.arange(start, read_bar + 1)
    left = ~_back_at_rail(shown, far_rail(new, shown), high, low, first, days)
    if not left.any():
        return None
    gone = np.flatnonzero(left & _back_at_both(new, high, low, first, days))
    return int(days[gone[0]]) if len(gone) else None


def wraps(shown: Pair, new: Pair, high, low, since: int, read_bar: int) -> Optional[int]:
    """His AMTB, Wed 28/10/2026: a one-bar box gives way to a tighter pair inside it, opened while the box formed, on
    the first day the bars are back at both its rails and none since the box opened came back to the box's rails."""
    if new.opening_bar <= shown.opening_bar or new.birth_bar is None or shown.birth_bar is None:
        return None
    if int(shown.r_bar) != int(shown.s_bar):
        return None                                 # a two-bar box stands; only one bar's own range gives way
    if lies_beyond(new, shown) or int(new.opening_bar) > int(shown.birth_bar):
        return None
    if new.height >= float(M.MINI_MAX_PARENT_HEIGHT_RATIO) * shown.height:
        return None
    start = max(int(since), int(new.birth_bar))
    if start > read_bar:
        return None
    first = int(shown.opening_bar)
    on_r, on_s = _respects(high[first:read_bar + 1], low[first:read_bar + 1], shown.R, shown.S, new.area)
    for hits, anchor in ((on_r, int(shown.r_bar) - first), (on_s, int(shown.s_bar) - first)):
        hits[anchor] = False
        for step in (1, -1):                        # the bars that stay at the rail on either side of its anchor
            k = anchor + step
            while 0 <= k < len(hits) and hits[k]:
                hits[k] = False
                k += step
    at_r, at_s = np.cumsum(on_r), np.cumsum(on_s)
    days = np.arange(start, read_bar + 1)
    dead = (at_r[days - first] == 0) | (at_s[days - first] == 0)
    took = np.flatnonzero(dead & _back_at_both(new, high, low, int(new.opening_bar), days))
    return int(days[took[0]]) if len(took) else None


def came_back_to(old: Pair, shown: Pair, high, low, since: int, read_bar: int) -> Optional[int]:
    """His sentence 9, a dip that comes back late (his STGW, Fri 23/10/2026): the first day after ``since`` that the
    bars are back at both rails of the box given up and no longer come back to the shown pair's far rail."""
    first = int(since) + 1
    if first > read_bar:
        return None
    days = np.arange(first, read_bar + 1)
    left = ~_back_at_rail(shown, far_rail(old, shown), high, low, first, days)
    back = np.flatnonzero(left & _back_at_both(old, high, low, first, days))
    return int(days[back[0]]) if len(back) else None


def respect_marks(high, low, ranges, R: float, S: float) -> tuple:
    """His close-enough, Fri 30/10/2026, each bar in its own daily range: ``(on_r, on_s)``, per bar +1 when an end of
    it touches the rail (within ``RESPECT_AREA_RANGES``, closer than the other), -1 when the whole bar sits beyond."""
    area = float(M.RESPECT_AREA_RANGES) * np.asarray(ranges, dtype=float)
    high, low = np.asarray(high, dtype=float), np.asarray(low, dtype=float)
    on_r, on_s = _respects(high, low, R, S, area)
    over, under = low > R + area, high < S - area
    return on_r.astype(np.int8) - over.astype(np.int8), on_s.astype(np.int8) - under.astype(np.int8)


def respect_cum(high, low, ranges, R: float, S: float) -> np.ndarray:
    """The running sum of a pair's marks on both rails, with a leading zero: its score over bars ``a`` to ``d`` is
    ``cum[d + 1] - cum[a]``."""
    on_r, on_s = respect_marks(high, low, ranges, R, S)
    return np.concatenate(([0], np.cumsum(on_r.astype(int) + on_s.astype(int))))


def out_respected(shown: Pair, new: Pair, cum_shown, cum_new, since: int, read_bar: int) -> Optional[tuple]:
    """The election by respect, Fri 30/10/2026 (behind ``RESPECT_ELECTS``): ``(day, lead)`` for the first day from
    ``since`` on, ``new`` a box, that it leads the shown pair by ``RESPECT_MARGIN`` over ``RESPECT_WINDOW_DAYS``."""
    if new.birth_bar is None:
        return None
    start = max(int(since), int(new.birth_bar))
    if start > int(read_bar):
        return None
    window = int(M.RESPECT_WINDOW_DAYS)
    if window < 1:
        raise ValueError("the election by respect reads the last RESPECT_WINDOW_DAYS days: it must be at least 1")
    days = np.arange(start, int(read_bar) + 1)
    opens = np.maximum(0, days - (window - 1))
    own, kept = cum_new[days + 1] - cum_new[opens], cum_shown[days + 1] - cum_shown[opens]
    lead = own - kept
    # The challenger must itself reach the margin (a pair the bars never visit scores nothing and would "lead" a box
    # they ran from), and the box shown gives way only once the bars have stopped respecting it (his sentence 9).
    margin = float(M.RESPECT_MARGIN)
    won = np.flatnonzero((lead >= margin) & (own >= margin) & (kept < margin))
    return (int(days[won[0]]), int(lead[won[0]])) if len(won) else None


def _key(pair: Pair) -> tuple:
    """The order boxes are tried in: birth day, earlier opening, earlier second anchor, tighter; the feet last."""
    return (pair.birth_bar, pair.opening_bar, pair.second_bar, pair.height, pair.r_index, pair.s_index)


def lives(pairs, trends, high, low, read_bar: int, known_rails: bool = True, ranges=None) -> tuple:
    """The box's life, day by day on what each day knew: the first pair to become a box is shown, and the earliest
    hand-over (live trend, tried first, left for good, wraps, the way back; under ``RESPECT_ELECTS`` the election in
    place of the last three) moves the box on. Every box handed over stays, with the day its lines stop."""
    if M.RESPECT_ELECTS and ranges is None:
        raise ValueError("the election by respect reads each bar's own daily range: pass ranges")
    born = sorted((p for p in pairs if p.birth_bar is not None), key=_key)
    if not born:
        return ()
    elects, cums = bool(M.RESPECT_ELECTS), {}

    def cum(pair: Pair):
        if pair.feet not in cums:
            cums[pair.feet] = respect_cum(high, low, ranges, pair.R, pair.S)
        return cums[pair.feet]

    out, vetoed = [], set()
    shown, day, why, trend, lead, before = born[0], int(born[0].birth_bar), FIRST_BOX, None, None, None
    # Every hand-over moves the day forward, raises the shown box's score by the margin or vetoes one more pair, so
    # the loop ends; a chain longer than every pair on every day is a cycle, refused out loud rather than a hang.
    cap = (len(born) + 1) * (int(read_bar) + 2)
    while True:
        if len(out) > cap:
            tail = ", ".join(f"{life.pair.R:.2f}/{life.pair.S:.2f} on bar {life.shown_bar} ({life.why[:24]})"
                             for life in out[-8:])
            raise RuntimeError(f"the box's life does not end: {len(out)} hand-overs; the last: {tail}")
        best = None
        if why == LEFT_FOR_GOOD and before is not None and shown.S < before.R - before.area:
            # The shown pair lies under the box it took over from: the price had left that box downward.
            back = came_back_to(before, shown, high, low, day, read_bar)
            if back is not None:
                best = ((back, 0, ()), before, CAME_BACK, None, None)    # the empty key: before a pair of that day
        for pair in born:
            if best is not None and pair.birth_bar > best[0][0]:
                break                   # born after the best day found: no later-born pair can come before it
            if pair.opening_bar == shown.opening_bar and pair.second_bar < shown.second_bar \
                    and int(pair.birth_bar) > day:
                # The sibling tried before the shown pair (sentence 5) is a box: it takes the place on its birth.
                order = (int(pair.birth_bar), 0, _key(pair))
                if best is None or order < best[0]:
                    best = (order, pair, TRIED_FIRST, None, None)
                continue
            when = took = by = ahead = None
            if elects and pair.feet in vetoed:
                # Under the election his anchor rule is a veto, not a score: a pair it swallowed never comes back.
                continue
            if pair.opening_bar <= shown.opening_bar:
                if not elects or pair.feet == shown.feet:
                    continue            # as built, only a pair that opened later takes the place
            else:
                swallowed = inside_a_live_trend(shown, pair, trends, read_bar, high, low, known_rails)
                if swallowed is not None:
                    when, took, by = max(int(pair.birth_bar), int(swallowed["known_bar"])), LIVE_TREND, swallowed
                    if swallowed["kind"] == "BC" and (swallowed["climax_bar"] > int(shown.birth_bar) or (
                            known_rails and _run_over_a_known_pair(shown, swallowed, high, low))):
                        # a run past a born box, or a pair the bars knew, is judged on the fifteenth day from its top
                        when = max(when, int(swallowed["climax_bar"]) + int(M.BOX_DAYS) - 1)
                if not elects:
                    left = left_for_good(shown, pair, high, low, day, read_bar)
                    if left is not None and (when is None or left < when):
                        when, took, by = left, LEFT_FOR_GOOD, None
                    wrap = wraps(shown, pair, high, low, day, read_bar) if M.WRAP_TAKES_OVER else None
                    if wrap is not None and (when is None or wrap < when):
                        when, took, by = wrap, WRAPS, None
            if elects:
                won = out_respected(shown, pair, cum(shown), cum(pair), day, read_bar)
                if won is not None and (when is None or won[0] < when):
                    when, took, by, ahead = won[0], RESPECTED, None, won[1]
            if when is None:
                continue
            order = (max(when, day), 0 if ahead is None else -ahead, _key(pair))
            if best is None or order < best[0]:
                best = (order, pair, took, by, ahead)
        if best is None:
            break
        out.append(Life(shown, shown_bar=day, why=why, ended_bar=max(best[1].opening_bar, shown.second_bar),
                        trend_end=trend, lead=lead))
        if best[2] == LIVE_TREND:
            vetoed.add(shown.feet)
        before = shown
        shown, day, why, trend, lead = best[1], best[0][0], best[2], best[3], best[4]
    out.append(Life(shown, shown_bar=day, why=why, trend_end=trend, lead=lead))
    return tuple(out)
