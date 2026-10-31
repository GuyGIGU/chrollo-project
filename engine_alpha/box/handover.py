"""The box's life (stage 4 of the walk): when the box shown gives way, and to which pair. The first pair to become
a box is shown; a later box takes its place when the shown one was anchored inside a live trend
(``inside_a_live_trend``), when the price left it for good (``left_for_good``), when a tighter pair inside a
one-bar box is the one the bars live in (``wraps``), when a dip came back (``came_back_to``) or, under the election
by respect, when the bars respect it more (``out_respected``). ``lives`` reads the chain day by day on what each day
knew; every hand-over is a sentence of his, named by the constants at the top.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from engine_alpha import numbers as M
from engine_alpha.box.pairs import RESISTANCE, SUPPORT, Pair, _respects


#: Why a box is shown.
FIRST_BOX = "the first pair to become a box"


#: His GFR (Thu 16/10/2026): a pair off the SAME opening anchor with an EARLIER second anchor — the climax and its
#: reaction before the pair one swing to its right — was tried first (sentence 5) and takes the place the day it is
#: a box. A pair that opened on another anchor never comes back this way (the Tested-DEAD rows of 2026-10-01).
TRIED_FIRST = "the pair tried before it became a box"


LIVE_TREND = "the box before it was anchored inside a live trend"


LEFT_FOR_GOOD = "the price left the box before it and the bars no longer came back to both its rails"


CAME_BACK = "the dip came back: the bars are back at both rails of the box it had given up"


#: His AMTB (Wed 28/10/2026) and his word of Thu 29/10/2026, *"we simply must increase the reading accuracy of our Reader
#: to match better with the ranges of the actual price action"*: a box the bars never came back to at one of its rails
#: does not wrap them; the tighter pair inside it that they do come back to is the box (``wraps``).
WRAPS = "the box was one bar's own high and low; the pair inside it the bars live in and come back to is the box"


#: His direction of Fri 30/10/2026 (*"Still on High/LOW values only but with out being hung on extremes"*): the box is
#: the pair the bars respect most, judged by touches in each bar's own range (``out_respected``; behind ``RESPECT_ELECTS``).
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
    """His EXPD (Sat 18/10/2026), sentences 8 and 9 on a run past the top of a box ALREADY born: it is the box's
    own poke when, within the fifteen trading days from the run's top, the bars came back to both rails of the
    box; then the rise did not go on and the box stands. None while those fifteen days are not all known: the
    judgment is made once, on their last day, so a reader on any day tells the same history."""
    last = int(climax_bar) + int(M.BOX_DAYS) - 1
    if int(read_bar) < last:
        return None
    days = np.arange(int(climax_bar), last + 1)
    return bool(_back_at_both(shown, high, low, int(climax_bar), days).any())


def knew_the_rails(shown: Pair, high, low) -> bool:
    """His HCA (Sat 24/10/2026): *"an earlier pair that provides a tighter box leading to more context overall"*.
    The pair is not new: in the ``KNOWN_RAILS_DAYS`` trading days before it opened, the bars' highs were at its
    resistance and their lows at its support, at least ``KNOWN_RAILS_MIN_BARS`` of each, within a quarter of its
    daily range (``KNOWN_RAILS_AREA_RANGES``). Known on the day it opens, so every reader tells the same."""
    opening = int(shown.opening_bar)
    first = max(0, opening - int(M.KNOWN_RAILS_DAYS))
    near = float(M.KNOWN_RAILS_AREA_RANGES) * shown.unit
    at_r = int((np.abs(high[first:opening] - shown.R) <= near).sum())
    at_s = int((np.abs(low[first:opening] - shown.S) <= near).sum())
    return at_r >= int(M.KNOWN_RAILS_MIN_BARS) and at_s >= int(M.KNOWN_RAILS_MIN_BARS)


def poke_stayed_in(shown: Pair, high, low, climax_bar: int, read_bar: int) -> Optional[bool]:
    """His HCA (Sat 24/10/2026): a run over the top of a pair the bars knew is the pair's own poke when, within the
    fifteen trading days from the run's top, the bars came back to both its rails (``poke_came_back``) and the
    middles of the bars after the top sat inside the box more often than over it — the price lived in the box, not
    above it (his MSGS, where he drew the run's pair, is the other way round). Read on highs and lows: the middle
    of a bar, never its close. None while those fifteen days are not all known."""
    back = poke_came_back(shown, high, low, climax_bar, read_bar)
    if not back:
        return back
    after = slice(int(climax_bar) + 1, int(climax_bar) + int(M.BOX_DAYS))
    middle = (np.asarray(high[after], dtype=float) + np.asarray(low[after], dtype=float)) / 2.0
    inside = int(((middle >= shown.S) & (middle <= shown.R)).sum())
    return inside > int((middle > shown.R).sum())


def _run_over_a_known_pair(shown: Pair, trend: dict, high, low) -> bool:
    """A rise over a pair the bars knew (``knew_the_rails``): judged on the fifteenth day from its top
    (``poke_stayed_in``). A rise that swallows the pair topped after its second anchor without asking (its first
    foot is after the pair opened, and no bar between the pair's two anchors is over its top: sentence 5); one that
    topped after the pair was a box meets his EXPD test first, which asks less. Never a fall: the mirror is his
    WTS's Tested-DEAD row."""
    return trend["kind"] == "BC" and high is not None and knew_the_rails(shown, high, low)


def inside_a_live_trend(shown: Pair, new: Pair, trends, day: int, high=None, low=None,
                        known_rails: bool = True) -> Optional[dict]:
    """The shown pair opened on a top inside a rise that had not ended (on a low inside a fall): a trend end
    known by ``day`` whose run began before that anchor and whose walk starts after it, the newer pair opening
    on or after that first foot. His anchor rule — *"We can't start the anchor from the opposite direction of
    the trend if we are still inside that trend"*. With the bars given, a rise whose climax printed AFTER the
    shown pair was a box swallows it only once the fifteen trading days from that climax are known and the bars
    did not come back to both its rails in them (``poke_came_back``; his EXPD, Sat 18/10/2026): a poke that came
    back is the box's own. The mirror for a fall is not built: on his WTS the base he drew came after such a
    fall, and the hand-over to the fall's end is what reaches it. And a rise that topped after the shown pair's
    second anchor but BEFORE it was a box swallows a pair the bars knew before it opened only once those fifteen
    days are known and the price did not stay in it (``poke_stayed_in``; his HCA, Sat 24/10/2026); not asked with
    ``known_rails`` off (the mini's walk: inside the parent every inner pair's rails are levels the bars knew).
    Returns that trend end, or None."""
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
    """For each day of ``days``: over the last fifteen trading days, never before ``first``, a bar was back at
    the pair's resistance and one at its support."""
    last = int(days[-1])
    on_r, on_s = _respects(high[first:last + 1], low[first:last + 1], pair.R, pair.S, pair.area)
    at_r, at_s = np.concatenate(([0], np.cumsum(on_r))), np.concatenate(([0], np.cumsum(on_s)))
    since = np.maximum(first, days - (int(M.BOX_DAYS) - 1))
    return (at_r[days - first + 1] > at_r[since - first]) & (at_s[days - first + 1] > at_s[since - first])


def _back_at_rail(pair: Pair, rail: str, high, low, first: int, days) -> np.ndarray:
    """For each day of ``days``: over the last fifteen trading days, never before ``first``, a bar was back at
    ONE rail of the pair, its resistance or its support."""
    last = int(days[-1])
    on_r, on_s = _respects(high[first:last + 1], low[first:last + 1], pair.R, pair.S, pair.area)
    at = np.concatenate(([0], np.cumsum(on_r if rail == RESISTANCE else on_s)))
    since = np.maximum(first, days - (int(M.BOX_DAYS) - 1))
    return at[days - first + 1] > at[since - first]


def far_rail(new: Pair, shown: Pair) -> str:
    """The shown box's rail the price would have to cross to come back from the newer pair: its support when the
    newer pair lies above the box, its resistance when it lies below. "No longer come back to the old ones" is
    read on it (his DSGX, Sat 18/10/2026): a box is left upward when the bars stop coming back to its support, and
    downward when they stop coming back to its resistance — never downward while they still sit on its top."""
    return SUPPORT if new.S >= shown.R - shown.area else RESISTANCE


def lies_beyond(new: Pair, shown: Pair) -> bool:
    """The position half of his sentences 9 and 10: the newer pair lies BEYOND the shown box — its support in
    or above the shown resistance's area, or its resistance in or below the shown support's area. A pair that
    does not is inside or across the box: its own leg, a poke, a dip or a mini. The ONE judgment: the walk's
    take-over and the mini's home both ask it (council review 2026-10-09, finding 13)."""
    return new.S >= shown.R - shown.area or new.R <= shown.S + shown.area


def left_for_good(shown: Pair, new: Pair, high, low, since: int, read_bar: int) -> Optional[int]:
    """His sentences 9 and 10, judged on every day: the newer box lies beyond the shown one — its support in or
    above the shown resistance's area, or its resistance in or below the shown support's area — and *"the bars
    now hang on the newer rails and no longer come back to the old ones"*, both halves: over the last fifteen
    trading days, never before the newer pair opened, the bars came back to both rails of the newer pair and not
    to the shown box's far rail (``far_rail``: its support for a pair above, its resistance for a pair below).
    The first such day from ``since`` on, never before the newer pair is a box; None when there is none by the
    read day. A pair inside or across the shown box is its own leg, a poke, a dip or a mini, and never takes its
    place; nor does a pair the bars have left (his MTLS: the pair of the July run, a box by the rule on a day the
    price was already back under it). Until his DSGX (Sat 18/10/2026) the old box counted as left when the bars
    missed EITHER of its rails: a spring that touched a lower pair's rails had the box left downward fifteen days
    after its last day at the support, while the bars sat on the box's resistance and the price over its top."""
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
    """His AMTB (Wed 28/10/2026: the reader boxed the climax bar's own high and low, 30.60 / 28.41, over bars that
    lived between 29.67 and 28.54) and his word of Thu 29/10/2026 that the box must wrap the actual price action.
    Of a box that is ONE bar's own high and low (sentence 3; his TOP and CYRX too): its unit is that one wide bar's
    range, so every bar inside it "respects" its rails, and the pair the bars then live in, measured in a normal
    range, is the honest reading (a two-bar box — a climax and its reaction, his SILC — keeps its place, however
    tight the pairs inside it: his eye draws it). A newer pair INSIDE or ACROSS the shown box, meaningfully tighter
    than it (under his mini bar, 80% of its
    height, his ruling of 21/10/2026: a pair covering substantially the same range is the same box, his SILC), that
    opened while the shown pair was still forming
    (on or before the day it became a box: the same formation's own anchors, never a leg of the right side, which
    is the mini's business, his DSGX) takes its place on the first day from ``since`` on, never before it is a box,
    on which the bars have come back to both its rails over the last fifteen trading days while NO bar since the
    shown box OPENED has come back to one of the shown box's rails. A come-back is a bar at the rail after the bars
    had left it: the anchor bar and the bars on either side of it that stay at that rail are the root swing's own
    (the bars that fell from his AMTB's climax, or TOP's, through the top's area on their way down to the reaction).
    Come back is read within half the NEWER pair's daily range of the rail: his respect, in the honest unit (a one-bar
    climax's own range is so wide that every bar under its top "respects" it). None when there is none by the read
    day. Behind ``WRAP_TAKES_OVER`` (the walk's switches, Wed 28/10/2026)."""
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
    """His sentence 9 for a dip that comes back late — *"Once a box, it stays a box through dips under support
    ... that come back"*: the first day after ``since`` (the day the box was given up) on which the bars since
    that day, and of the last fifteen trading days, have come back to both its rails AND no longer come back to
    the shown pair's far rail (``far_rail``: its support, the box given up lying above it). The way back is a
    hand-over, judged as every hand-over is, by both halves of his sentence 10 (his STGW, Fri 23/10/2026: the
    breakout of Tue 13/10 ran through the pair of early August above his box, and that one run gave the old pair
    the box's place back while the bars rested on the box's top). None when there is none by the read day. A bar
    at a rail on or before ``since`` is not the price coming back."""
    first = int(since) + 1
    if first > read_bar:
        return None
    days = np.arange(first, read_bar + 1)
    left = ~_back_at_rail(shown, far_rail(old, shown), high, low, first, days)
    back = np.flatnonzero(left & _back_at_both(old, high, low, first, days))
    return int(days[back[0]]) if len(back) else None


def respect_marks(high, low, ranges, R: float, S: float) -> tuple:
    """His close-enough (Fri 30/10/2026), each bar in its OWN daily range: ``(on_r, on_s)``, for every bar +1 when an
    end of it sits within ``RESPECT_AREA_RANGES`` of that rail and closer to it than to the other (a touch: resting,
    stopping short or poking out slightly, his "whenever they are slightly poking out or not does not matter one
    bit"), -1 when the whole bar sits beyond the rail by more than that (a bar the pair does not wrap: the one
    judgment ``state.side`` makes of the right edge), 0 for a bar inside the box or short of the rail."""
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
    """The election by respect (Fri 30/10/2026; behind ``RESPECT_ELECTS``): the first day from ``since`` on, never
    before ``new`` is a box, on which ``new`` leads the shown pair by ``RESPECT_MARGIN`` touches over the last
    ``RESPECT_WINDOW_DAYS`` trading days: ``(day, lead)``, or None by the read day. ONE window for every pair, the
    same days for all: a window that started at each pair's own opening made the lead non-transitive, so three pairs
    could each beat the next round the ring on one day and the chain never moved on (measured Fri 30/10/2026 on his
    SILC and ANRO). The margin is the incumbent's: on equality, and short of it,
    the box shown stands, and the challenger's own score must reach the margin as well: a pair the bars never
    visit does not out-respect a box they have run away from. Both pairs are scored over the SAME days, each bar in its own range, so neither buys respect
    with a wide unit of its own (the one-bar box, his AMTB). A pair that opened earlier may win this way: the box
    given up wins its place back when the bars come back to it (his STGW), an earlier tighter pair when they live in
    it (his HCA)."""
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
    # The challenger must itself be respected, not merely untouched: a box the price has run away from scores
    # under zero (every bar wholly beyond it counts against it), and a pair the bars never visit scores nothing,
    # which would "lead" it. So its own score must reach the margin too. And the box shown gives way only once
    # the bars have STOPPED respecting it (its own score under the margin): his sentence 9, a box stays a box
    # while the bars come back to it, whatever tighter pair they also touch inside it. Measured without this
    # clause on his 51 (Fri 30/10/2026): the fires held (42 of 51) but his box to the cent fell from 28 to 5-10,
    # a tighter inner pair taking the place on some twenty of his drawings.
    margin = float(M.RESPECT_MARGIN)
    won = np.flatnonzero((lead >= margin) & (own >= margin) & (kept < margin))
    return (int(days[won[0]]), int(lead[won[0]])) if len(won) else None


def _key(pair: Pair) -> tuple:
    """The order boxes are tried in: the day the pair became a box, then the earlier opening, then the earlier
    second anchor, then the tighter; the feet last, so equal pairs never tie."""
    return (pair.birth_bar, pair.opening_bar, pair.second_bar, pair.height, pair.r_index, pair.s_index)


def lives(pairs, trends, high, low, read_bar: int, known_rails: bool = True, ranges=None) -> tuple:
    """The box's life, read day by day on what each day knew. The first pair to become a box is shown. A pair
    that is a box takes its place when the shown pair was anchored inside a live trend (``inside_a_live_trend``:
    judged once that trend end is known) or on the first day the price has left it for good (``left_for_good``).
    Each of those goes to a pair that opened later. One hand-over goes back: when the price had left a box
    DOWNWARD and a lower pair took its place, the box takes its place back on the first day the bars are back at
    both its rails and no longer come back to the lower pair's support (``came_back_to``) — a dip that came
    back. And one goes to a SIBLING: a pair off the shown
    pair's own opening anchor with an earlier second anchor — the climax and its reaction, before the pair one
    swing to its right — was tried first (sentence 5), and takes the place on the day it becomes a box
    (``TRIED_FIRST``; his GFR, Thu 16/10/2026: *"the AR ended where I marked it ... the entire wave going down
    is already 2 swings and it's not part of the AR"*). And one goes INSIDE a box that is one bar's own high and
    low: a meaningfully tighter pair inside or across it, opened while it was still forming, takes its place on the
    first day the bars have come back to both its rails while none since the box opened has come back to one of
    the box's rails, read in the tighter pair's own range (``wraps``; his AMTB, Wed 28/10/2026: the box must wrap
    the bars). Every box handed over
    stays, with the day its lines stop; the last one stands. Under ``RESPECT_ELECTS`` (Fri 30/10/2026) the
    left-for-good, way-back and wraps hand-overs are not asked: a pair that is a box, whenever it opened, takes the
    shown box's place on the first day the bars respect it more by the margin (``out_respected``, each bar in its
    own daily range, ``ranges``); the live-trend and tried-first hand-overs stay."""
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
    # The loop ends: every hand-over moves the day forward, or on one day raises the score of the box shown by the
    # margin (the election: one window for all, so it cannot cycle), or vetoes one more pair (the live-trend kind).
    # A chain longer than every pair could be handed over on every day is a cycle: refused out loud, never a hang
    # (the read then counts as a crash, which is what a reader that cannot finish must say).
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
                # Under the election a pair that gave way because it was anchored inside a live trend never comes
                # back: his anchor rule is a veto, not a score (else the two hand-overs ping-pong on one day and the
                # chain never moves on: measured on his SILC, Fri 30/10/2026).
                continue
            if pair.opening_bar <= shown.opening_bar:
                if not elects or pair.feet == shown.feet:
                    continue            # as built, only a pair that opened later takes the place
            else:
                # The day this pair would take the shown box's place: the day a trend end that swallowed the shown
                # pair was known (never before the pair is a box), or the first day the price has left for good.
                swallowed = inside_a_live_trend(shown, pair, trends, read_bar, high, low, known_rails)
                if swallowed is not None:
                    when, took, by = max(int(pair.birth_bar), int(swallowed["known_bar"])), LIVE_TREND, swallowed
                    if swallowed["kind"] == "BC" and (swallowed["climax_bar"] > int(shown.birth_bar) or (
                            known_rails and _run_over_a_known_pair(shown, swallowed, high, low))):
                        # A run past the top of a box already born, or of a pair the bars knew, is judged on the last
                        # of the fifteen days from its top (``poke_came_back``, ``poke_stayed_in``, by then known):
                        # the rise takes the place no sooner.
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
