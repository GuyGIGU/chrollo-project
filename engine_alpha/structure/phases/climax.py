"""The climax and its automatic reaction, read on the ONE turn line: point 3 of the final method, build step 10.

His words (docs/final_method_2026-09.md point 3, and Sat 19/09/2026): a run is higher highs and higher lows (the
mirror for a decline); the climax is the run's highest turn; the automatic reaction is the reaction after it; the run
has ended when the line prints its first swing that fails to continue it; and "the swings for BC and AR are needed to
be decided before the Root Swing, because said root swing can either be them, or a swing later". Point 4's
reaction-low rule fixes the reaction's anchor: the lowest low of the reaction before the first higher low (the
mirror for a selling climax), which reproduces eight of his nine non-consecutive anchor pairs to the cent.

A pure function of the line; it reads no bars, applies no number and gates nothing. ``bricks.find_root_swing``
turns each run into a root under ``CLIMAX_FIRST_WALK_ENABLED``.
"""
from __future__ import annotations

__all__ = ["runs_on_the_line"]

def _cmp(t, i):
    """Sign of turn ``i`` against the previous turn of its own kind (``i - 2`` on an alternating line)."""
    d = t[i][2] - t[i - 2][2]
    return 1 if d > 0 else (-1 if d < 0 else 0)


def _reaction(t, climax, direction):
    """The reaction after the climax, by point 4's rule: for a buying climax, walk the valleys after it; the
    reaction low is the lowest valley before the first higher low, and it is known only once that higher low has
    printed (the reaction may still be running until then; the forming turn at the edge never anchors). Mirror
    for a selling climax. Returns the reaction turn's index or None."""
    want = "valley" if direction > 0 else "peak"
    cand = None
    for j in range(climax + 1, len(t)):
        if t[j][1] != want:
            continue
        if t[j][3] is None:
            return None                                   # the forming turn at the edge decides nothing yet
        if cand is not None and (t[j][2] > t[cand][2] if direction > 0 else t[j][2] < t[cand][2]):
            return cand                                   # the first higher low (lower high) ends the reaction
        cand = j
    return None                                           # no higher low yet: the reaction is not decided


def _run(t, start, last, end, direction):
    want = "peak" if direction > 0 else "valley"
    climax = max(i for i in range(start, last + 1) if t[i][1] == want)     # the run's extreme: the last of its kind
    launch = min(i for i in range(start, last + 1) if t[i][1] != want)     # the run's launch: the first of the other kind
    reaction = _reaction(t, climax, direction)
    if reaction is None or t[reaction][3] is None:
        return None
    return {
        "kind": "BC" if direction > 0 else "SC",
        "climax_bar": t[climax][0], "climax_price": t[climax][2],
        "ar_bar": t[reaction][0], "ar_price": t[reaction][2],
        "launch_bar": t[launch][0], "launch_price": t[launch][2],
        "end_bar": t[end][0],
    }


def runs_on_the_line(turns):
    """Every run the line prints, oldest first, as ``(bar, kind, price, knowable_bar)`` turns go in: a run is at
    least two peaks and two valleys with every peak above the previous peak and every valley above the previous
    valley (the mirror for a decline), and it ends at the first swing that fails to continue it (a lower or equal
    high, a lower or equal low). Each run returns its climax (the run's extreme turn), its reaction (point 4's
    reaction-low rule), its launch (the run's first turn of the other kind) and the turn that ended it. A run whose
    reaction is not yet decided, or one still running at the right edge, is not returned: its climax is not proven.
    """
    t = [(int(b), k, float(p), know) for (b, k, p, know) in turns]
    n = len(t)
    out = []
    direction, start = 0, None
    i = 3
    while i < n:
        if direction == 0:
            first, second = _cmp(t, i - 1), _cmp(t, i)
            if first != 0 and first == second:
                direction, start = first, i - 3
            i += 1
            continue
        if _cmp(t, i) == direction:
            i += 1
            continue
        run = _run(t, start, i - 1, i, direction)         # the run [start .. i-1] ended at turn i
        if run is not None:
            out.append(run)
        direction, start = 0, None                        # the ending swing may open the opposite run
        i += 1
    return out
