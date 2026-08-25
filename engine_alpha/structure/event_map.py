"""Event Map — the mechanical swing layer (whole-frame, measure-only).

Widens the ONE calibrated swing skeleton (the L2 staircase's order-1 pivots +
amplitude collapse) from the elected box's window to the WHOLE evaluation frame,
so the engine can read the pre-box trend and the box story on one substrate. It
stands up no second skeleton: ONE bar-level pivot walk runs per frame, and each
windowed view — the pre-box segment, the in-box staircase — is that walk's
pivots filtered to its window and fed through the SAME staircase machinery
(``box_events._staircase_from_pivots``).

The in-box view is byte-identical to ``read_box_staircase`` by construction:
an order-1 pivot at frame bar ``a`` with ``start < a < n-1`` satisfies exactly
the comparisons the windowed walk applies at base bar ``a - start`` (asserted by
tests and the Task-4 capture battery). The widening is therefore additive —
pre-box swings appear, including a pivot at the box-start bar itself (which the
windowed walk's order margin masked); nothing inside the box moves.

The two views are stitched, not re-collapsed: alternation and collapse state
reset at the box-start seam (the price of keeping the in-box slice identical to
the elected staircase), and each view's HH/HL/LH/LL labels start fresh at its
own first swing. Consumers reading across the seam treat it as a boundary
(causality contract §4: interval/seam conventions are stated, never implicit).

Causality (docs/archive/specs/event-map-causality-contract.md — binding):
  * every swing carries ``describes_bar`` (its pivot bar) and ``knowable_bar`` —
    the first bar at whose close the swing was irreversibly committed: the bar
    that pivot-confirms the first opposite extreme whose counter-move off this
    swing reaches the collapse threshold ``min_amp``. Before that, a
    same-direction exceedance would have absorbed the swing (the collapse's
    forward merge), so commitment is refused (conservatively, on an equal
    extreme too) and the swing is ``in_progress``.
  * ``in_progress`` (``knowable_bar`` None) covers the right-edge swing whose
    committing reversal has not printed AND a window-edge extreme superseded
    outside its window. In-progress never satisfies a downstream predicate.
  * stamps are frame-causal, not window-causal: a pre-box swing may be committed
    by in-box bars — that is real chronology, not lookahead.
  * the frame's first swing is ``edge_uncertain`` — whether a more extreme swing
    preceded it depends on bars left of the live two-year trim (contract §3).

NaN policy (contract §5): highs/lows are coerced to float once at entry;
non-finite bars are counted in ``nan_bars`` and can never pivot (every pivot
comparison against NaN is False — the walk fails closed, and the count makes the
silence visible).

Measure-only: moves no rail, gates nothing, scores nothing. LIVE on the fire
path since 2026-07-25 (``EVENT_MAP_ENABLED``, Event Map program Task 13):
firing setups compute the tape + roles + the rail-episode substrate and
archive them as the ``event_map_*`` column family; the story-rescue pool
(``STORY_POOL_ENABLED``, LIVE since 2026-07-26 — the 26→28 ratchet reseal)
consults ``read_rail_episodes`` + ``story_admission`` at the election
cascade's last-resort rung.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from config import settings
from engine_alpha.structure.box_events import (
    _EVENT_HOLD_MIN_BARS,
    _box_events_with_meta,
    _staircase_empty,
    _staircase_from_pivots,
)
from engine_alpha.structure.pivots import _find_pivots


def _empty_map() -> dict:
    return {
        "swings": [], "n_swings": 0,
        "pre_box": {"n_swings": 0, "trend_state": "range"},
        "box": {"n_swings": 0, "trend_state": "range",
                "counts": {"HH": 0, "HL": 0, "LH": 0, "LL": 0},
                "rail_to_rail": False, "is_zigzag": False},
        "start_bar": 0, "n_bars": 0, "nan_bars": 0,
    }


def _stamp_causality(swings, highs, lows, min_amp):
    """Dual bar stamps (contract §1–§2), in place.

    A swing is committed at the bar that pivot-confirms the first opposite
    extreme lying ``min_amp`` beyond it: for a peak, the first valley-form bar
    ``v`` (``lows[v] <= lows[v-1]`` and ``lows[v] < lows[v+1]``) with
    ``lows[v] <= peak - min_amp`` — knowable at ``v + 1``, the bar that confirms
    the pivot. A same-direction extreme at/above the swing's price before that
    point means the collapse would have absorbed it: commitment is refused and
    the swing stays ``in_progress``. Comparisons run on the raw arrays the walk
    itself read — no re-derived floats (contract §4).
    """
    n = len(highs)
    for s in swings:
        bar = int(s["bar"])
        s["describes_bar"] = bar
        know = None
        if s["kind"] == "peak":
            top = highs[bar]
            for v in range(bar + 1, n - 1):
                if highs[v] >= top:
                    break                      # extreme migrated before committing
                if (lows[v] <= top - min_amp
                        and lows[v] <= lows[v - 1] and lows[v] < lows[v + 1]):
                    know = v + 1
                    break
        else:
            bot = lows[bar]
            for v in range(bar + 1, n - 1):
                if lows[v] <= bot:
                    break                      # extreme migrated before committing
                if (highs[v] >= bot + min_amp
                        and highs[v] >= highs[v - 1] and highs[v] > highs[v + 1]):
                    know = v + 1
                    break
        s["knowable_bar"] = know
        s["in_progress"] = know is None
    if swings:
        swings[0]["edge_uncertain"] = True


def read_swing_map(df, box, atr_val, *, noise_frac=None) -> dict:
    """The whole-frame mechanical swing map around an elected equilibrium box.

    One order-1 pivot walk over the full frame, sliced into two windowed views
    through the shared staircase machinery:

      * ``region == "box"`` — the in-box staircase, byte-identical to
        ``read_box_staircase(df.iloc[box.start_bar:], R, S, atr_val)`` (bars
        re-based to df-absolute; the tape adds only ``region`` + the causality
        stamps).
      * ``region == "pre_box"`` — the same machinery over the pivots left of the
        box start (bar ``start`` itself included: its right context exists in
        the full frame), df-absolute, annotated against the SAME elected rails
        so the trend's position relative to the box is readable.

    Returns (safe empty shape on a degenerate frame/box):
        swings     chronological, df-absolute; each ``{bar, kind, price, label,
                   box_pos, zone, rail_event, region, describes_bar,
                   knowable_bar, in_progress}`` (+ ``edge_uncertain`` on the
                   frame's first swing)
        n_swings   total swings across both regions
        pre_box    {n_swings, trend_state} of the pre-box view
        box        {n_swings, trend_state, counts, rail_to_rail, is_zigzag} —
                   the staircase's own summary, verbatim
        start_bar / n_bars / nan_bars

    Measure-only; live on the fire path since 2026-07-25 (EVENT_MAP_ENABLED).
    """
    if df is None or len(df) == 0 or box is None:
        return _empty_map()
    R, S = float(box.R), float(box.S)
    height = R - S
    if height <= 0 or atr_val is None or atr_val <= 0 or not np.isfinite(atr_val):
        return _empty_map()
    start = int(box.start_bar)
    n = len(df)
    if start < 0 or start >= n:
        return _empty_map()

    # Coerce ONCE at entry (contract §5); count unreadable bars loudly.
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    nan_bars = int((~(np.isfinite(highs) & np.isfinite(lows))).sum())

    min_amp = (noise_frac if noise_frac is not None
               else settings.TRAVERSAL_NOISE_FRAC) * height

    # THE one bar-level swing walk for the whole frame.
    peaks, valleys = _find_pivots(highs, lows, 1) if n >= 3 else ([], [])

    # In-box view: full-frame pivots right of the box start, re-based and run
    # through the same machinery the box staircase uses.
    box_view = _staircase_from_pivots(
        [p - start for p in peaks if p >= start + 1],
        [v - start for v in valleys if v >= start + 1],
        highs[start:], lows[start:], R, S, atr_val, min_amp,
    ) if len(highs) - start >= 3 else _staircase_empty()

    # Pre-box view: pivots at/left of the box start, same machinery, absolute bars.
    pre_view = _staircase_from_pivots(
        [p for p in peaks if p <= start],
        [v for v in valleys if v <= start],
        highs, lows, R, S, atr_val, min_amp,
    )

    swings = [{**s, "region": "pre_box"} for s in pre_view["swings"]]
    swings += [{**s, "bar": int(s["bar"]) + start, "region": "box"}
               for s in box_view["swings"]]
    _stamp_causality(swings, highs, lows, min_amp)

    return {
        "swings": swings,
        "n_swings": len(swings),
        "pre_box": {"n_swings": pre_view["n_swings"],
                    "trend_state": pre_view["trend_state"]},
        "box": {"n_swings": box_view["n_swings"],
                "trend_state": box_view["trend_state"],
                "counts": box_view["counts"],
                "rail_to_rail": box_view["rail_to_rail"],
                "is_zigzag": box_view["is_zigzag"]},
        "start_bar": start,
        "n_bars": n,
        "nan_bars": nan_bars,
    }


# ---------------------------------------------------------------------------
# The recovery view — the post-shakeout chapter (story-chain program Task 7)
# ---------------------------------------------------------------------------

# Provisional yardsticks (module constants while the lane is dark and the
# attribute unserialized; they move to config/settings.py + the frozen
# manifest with the archive family — program Task 8). The BANDS are the
# operator's own vocabulary (decisions.md 2026-08-23 story-chain row); the
# numeric edges are v1 first-cuts the census re-bands OFFLINE against the
# archived raw values — which is why every raw operand rides the result.
RECOVERY_MIN_FRAC = 0.5       # regained less of the undercut than this = "none"
RECOVERY_TOL_ATR = 1.0        # the destination band seam, in ATRs
RECOVERY_STAIRCASE_MAX_TESTS = 3   # more committed tests than this reads new_base

# The closed sets — engine-internal, provisional pending the naming ruling.
RECOVERY_CHARACTERS = ("one_swing", "staircase", "new_base", "none")
RECOVERY_DESTINATIONS = ("back_inside", "sitting_below", "at_the_bottom")


def _empty_recovery() -> dict:
    return {"character": None, "destination": None, "shakeout_low": None,
            "shakeout_low_bar": None, "recovery_high": None,
            "recovery_high_bar": None, "recovery_frac": None,
            "n_intervening_valleys": None, "last_close": None,
            "window": None, "nan_bars": 0}


def read_recovery_view(df, parent_r, parent_s, undercut_bar, atr_val, *,
                       noise_frac=None, pivots=None) -> dict:
    """The post-shakeout recovery read against a FROZEN parent's rails.

    The operator's law (2026-08-23): the shakeout's depth never disqualifies —
    "what happens next though is what's truly important, how does it recover?
    if at all" — and THAT is the cue to hunt for tightening. This view answers
    the two closed-set questions on his own vocabulary:

      character    one_swing / staircase / new_base / none — how it recovered
                   off the shakeout low: directly, ladder-with-tests, by
                   building a fresh range, or not at all.
      destination  back_inside / sitting_below / at_the_bottom — where the
                   read edge stands relative to the old floor.

    Stated conventions (contract §4 — never implicit): the shakeout low is
    the PREFIX minimum of the skip-trimmed window after ``undercut_bar``
    (as-of true; a low deepening inside the edge reserve does not exist yet —
    EC-45); intervening tests are COMMITTED valleys only (the causality
    stamps; in-progress never counts) strictly between the low and the
    recovery high; band edges are inclusive at the lower seam
    (``close == shakeout_low + tol`` is still at_the_bottom, ``close ==
    parent_s`` is back inside). Swings come from THE one pivot walk
    (``_find_pivots`` order 1; pass ``pivots=(peaks, valleys)`` to reuse a
    walk the caller already ran — never a second skeleton) with the swing
    map's own amplitude yardstick (``noise_frac`` × parent height).

    Pure measurement over the frame — a pure function of the truncated frame,
    so replay-at-T equals live-at-T by construction. Returns the empty shape
    (all-None) on degenerate inputs — refused, never fabricated.
    """
    if df is None or len(df) == 0:
        return _empty_recovery()
    height = float(parent_r) - float(parent_s)
    if (height <= 0 or atr_val is None or atr_val <= 0
            or not np.isfinite(atr_val)):
        return _empty_recovery()
    n = len(df)
    skip = int(settings.STRUCTURE_EDGE_SKIP_BARS)
    eval_end = n - skip if n > skip else n
    u = int(undercut_bar)
    if u < 0 or u + 3 >= eval_end:
        return _empty_recovery()

    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    closes = df["Close"].values.astype(float)
    nan_bars = int((~(np.isfinite(highs[u:eval_end])
                      & np.isfinite(lows[u:eval_end])
                      & np.isfinite(closes[u:eval_end]))).sum())

    low_rel = int(np.argmin(lows[u:eval_end]))
    low_bar = u + low_rel
    shakeout_low = float(lows[low_bar])
    depth = float(parent_s) - shakeout_low
    if depth <= 0 or not np.isfinite(depth):
        return _empty_recovery()               # never undercut the floor

    seg0 = low_bar + 1
    if seg0 >= eval_end:
        return _empty_recovery()               # the low IS the read edge
    peak_rel = int(np.argmax(highs[seg0:eval_end]))
    peak_bar = seg0 + peak_rel
    recovery_high = float(highs[peak_bar])
    if not np.isfinite(recovery_high):
        return _empty_recovery()               # unreadable recovery: refuse
    recovery_frac = (recovery_high - shakeout_low) / depth
    last_close = float(closes[eval_end - 1])
    if not np.isfinite(last_close):
        return _empty_recovery()               # unreadable read edge: refuse

    # Committed tests between the low and the recovery high, from THE walk.
    if pivots is None:
        pivots = _find_pivots(highs, lows, 1) if n >= 3 else ([], [])
    peaks, valleys = pivots
    min_amp = (noise_frac if noise_frac is not None
               else settings.TRAVERSAL_NOISE_FRAC) * height
    swings = sorted(
        [{"bar": int(p), "kind": "peak"} for p in peaks
         if low_bar < int(p) < peak_bar]
        + [{"bar": int(v), "kind": "valley"} for v in valleys
           if low_bar < int(v) < peak_bar],
        key=lambda s: s["bar"])
    _stamp_causality(swings, highs, lows, min_amp)
    n_tests = sum(1 for s in swings
                  if s["kind"] == "valley" and not s["in_progress"])

    if recovery_frac < RECOVERY_MIN_FRAC:
        character = "none"
    elif n_tests == 0:
        character = "one_swing"
    elif n_tests <= RECOVERY_STAIRCASE_MAX_TESTS:
        character = "staircase"
    else:
        character = "new_base"

    tol = RECOVERY_TOL_ATR * float(atr_val)
    if last_close >= float(parent_s):
        destination = "back_inside"
    elif last_close <= shakeout_low + tol:
        destination = "at_the_bottom"
    else:
        destination = "sitting_below"

    return {
        "character": character,
        "destination": destination,
        "shakeout_low": shakeout_low,
        "shakeout_low_bar": int(low_bar),
        "recovery_high": recovery_high,
        "recovery_high_bar": int(peak_bar),
        "recovery_frac": round(float(recovery_frac), 4),
        "n_intervening_valleys": int(n_tests),
        "last_close": last_close,
        "window": [int(u), int(eval_end)],
        "nan_bars": nan_bars,
    }


# ---------------------------------------------------------------------------
# The narrative-role layer — stamped role labels over the ELECTED bricks
# ---------------------------------------------------------------------------

def _first_bar_at_or_below(lows, after_bar, level):
    """First bar strictly after ``after_bar`` whose low reaches ``level``.
    NaN lows fail the comparison and are skipped (contract §5)."""
    for t in range(int(after_bar) + 1, len(lows)):
        if lows[t] <= level:
            return t
    return None


def _wave_closure_bar(top_abs, peak_price, lows, low_zone_price, high_zone_peaks):
    """The bar at which a resistance wave's IDENTITY became fixed.

    The wave grouper keeps extending a wave while later high-zone reaches are
    higher-highs with no drop to the support low-zone in between — so an emitted
    wave (this frame's read) is only irrevocable once one of its two closers
    printed: a low-zone drop after the top, or the COMMITMENT of the first
    non-higher high-zone peak after it (compared on the staircase's emitted
    rounded prices, per contract §4). A higher subsequent peak needs no case of
    its own: it can only coexist with this wave when a drop came first. Returns
    None while the wave is still extendable (identity provisional).
    """
    drop = _first_bar_at_or_below(lows, top_abs, low_zone_price)
    reach = None
    for s in high_zone_peaks:
        if int(s["bar"]) > int(top_abs) and float(s["price"]) <= float(peak_price):
            reach = s["knowable_bar"]      # None while that peak is uncommitted
            break
    candidates = [c for c in (drop, reach) if c is not None]
    return min(candidates) if candidates else None


def read_role_labels(df, box, atr_val, *, spring, lps):
    """Narrative-role labels over the elected bricks + the mechanical map.

    ``spring`` and ``lps`` are the engine's ELECTED bricks (``structure.spring``
    / ``structure.lps``) and are REQUIRED: an injected ``None`` means "the
    engine elected no such piece" and is honored — this layer never re-detects
    (the EC-3 cycle-escape trap). The event zones come from the same
    ``_box_events_with_meta`` chokepoint the story read uses, so the roles can
    never desync from the L2 story.

    Every label carries the contract stamps (§1–§2):

      * ``resolution`` — the measurer's own tri-state (held / failed /
        in_progress; the spring's hold window and the elected LPS are given
        theirs here from the same mechanics that confirmed them).
      * ``knowable_bar`` — the first bar at whose close BOTH the verdict and the
        label's identity were irreversible: a failed wave at its low-zone drop
        bar; a held wave/test at the last bar of its printed hold window
        (`_EVENT_HOLD_MIN_BARS` — the measurers' own horizon), and never before
        the wave stops being extendable (``_wave_closure_bar``) or the
        anchoring swing commits (the mechanical layer's stamp); a spring at the
        end of its fully-printed ``BIN_C_HOLD_BARS`` reclaim-hold window; the
        elected LPS at the frame end (its "still holding" verdict consumed
        every printed bar).
      * ``in_progress`` — True when ``knowable_bar`` is None. Stricter than
        ``resolution`` alone: a hold can be confirmed while the wave is still
        extendable, and such a label is honest only once both are settled.
      * ``election_dependent`` — True for spring/LPS: their PRESENCE tracks
        this frame's election, so truncation batteries treat them as
        frame-scoped rather than truncation-stable.

    Bars are df-absolute; ``describes`` spans use the assembler's emitted zone
    bounds. Measure-only — gates nothing, scores nothing; live on the fire
    path since 2026-07-25 (EVENT_MAP_ENABLED).
    """
    empty = {"labels": [], "n_labels": 0}
    events, _v_bar, _base_n, _has_valley = _box_events_with_meta(
        df, box, atr_val, spring=spring, lps=lps)
    if not events:
        return empty

    tape = read_swing_map(df, box, atr_val)
    start = int(box.start_bar)
    lows = df["Low"].values.astype(float)
    n = len(lows)
    height = float(box.R) - float(box.S)
    low_zone_price = float(box.S) + settings.TRAVERSAL_LOW_ZONE * height
    hold_bars = _EVENT_HOLD_MIN_BARS
    box_swings = [s for s in tape["swings"] if s["region"] == "box"]
    high_zone_peaks = [s for s in box_swings
                       if s["kind"] == "peak" and s["zone"] == "high"]

    labels = []
    for e in events:
        role = e["type"]
        resolution = e.get("resolution")
        election_dependent = False
        know = None

        if e.get("rail") == "R" and "peak_bar" in e:
            # Resistance wave: verdict from its terminal outcome, identity from
            # the wave closer — knowable only when both printed.
            top_abs = start + int(e["peak_bar"])
            if resolution == "failed":
                verdict = _first_bar_at_or_below(lows, top_abs, low_zone_price)
            elif resolution == "held":
                verdict = top_abs + hold_bars
            else:
                verdict = None
            closure = _wave_closure_bar(top_abs, e["peak_price"], lows,
                                        low_zone_price, high_zone_peaks)
            if verdict is not None and closure is not None:
                know = max(verdict, closure)

        elif "valley_bar" in e:
            # Support test: verdict from its printed hold window, identity from
            # the anchoring valley's mechanical commitment.
            valley_abs = start + int(e["valley_bar"])
            if resolution == "failed":
                # Mirror the measurer's STRICT breakdown comparison exactly.
                breach_buf = settings.BOUNDARY_ATR_BUFFER * float(atr_val)
                level = float(e["valley_price"]) - breach_buf
                verdict = next(
                    (t for t in range(valley_abs + 1,
                                      min(n, valley_abs + 1 + hold_bars))
                     if lows[t] < level),
                    None)
            elif resolution == "held":
                verdict = valley_abs + hold_bars
            else:
                verdict = None
            anchor = next((s for s in box_swings
                           if s["kind"] == "valley" and int(s["bar"]) == valley_abs),
                          None)
            commit = anchor["knowable_bar"] if anchor is not None else None
            if verdict is not None and commit is not None:
                know = max(verdict, commit)

        elif role == "spring":
            # Elected Phase-C brick: confirmed by its reclaim-hold window; a
            # window running past the last printed bar is in_progress (§2).
            election_dependent = True
            hold_end = int(spring.recovery_bar) + int(settings.BIN_C_HOLD_BARS)
            if hold_end <= n - 1:
                resolution, know = "held", hold_end
            else:
                resolution = "in_progress"

        elif role == "lps":
            # Elected Phase-D brick: "still holding" is a right-edge verdict
            # that consumed every printed bar — knowable at the frame end, and
            # re-issued by each frame's own election.
            election_dependent = True
            resolution, know = "held", n - 1

        labels.append({
            "role": role,
            "rail": e.get("rail"),
            "phase": e.get("phase"),
            "describes": [start + int(e["zone_start"]), start + int(e["zone_end"])],
            "anchor_bar": start + int(e["anchor_bar"]),
            "resolution": resolution,
            "knowable_bar": know,
            "in_progress": know is None,
            "election_dependent": election_dependent,
        })

    return {"labels": labels, "n_labels": len(labels)}


# ---------------------------------------------------------------------------
# The rail-episode read — layer 3 (chronological completion over a rail pair)
# ---------------------------------------------------------------------------

EPISODE_MAX_GAP_BARS = 2    # inside-run merge horizon (band-rails same-side convention)
EPISODE_DRIFT_MIN_BARS = 3  # an open terminal S episode at least this long = drift


def _zone_visit_runs(mask, max_gap=EPISODE_MAX_GAP_BARS):
    """Merged True runs as inclusive ``(start, end)`` pairs; visits separated
    by ``<= max_gap`` inside bars merge into one run."""
    idx = np.flatnonzero(mask)
    if len(idx) == 0:
        return []
    runs = []
    a = prev = int(idx[0])
    for i in idx[1:]:
        i = int(i)
        if i - prev <= max_gap + 1:
            prev = i
        else:
            runs.append((a, prev))
            a = prev = i
    runs.append((a, prev))
    return runs


def frame_r_engaged(last_high, R, tol) -> bool:
    """The ENGAGEMENT half of the terminal read as a frame-level fact: the
    frame's last bar inside the R touch zone (the extreme-proximity "hang",
    close anywhere). THE single expression of that leg — the resistance-
    contraction form's O(1) prefilter and the posture predicate below both resolve here,
    so a re-ruled engagement zone moves every consumer at once (NaN fails
    closed)."""
    return bool(last_high >= R - tol)


def frame_terminal_posture(last_high, last_close, R, tol) -> bool:
    """The ruled form's POSTURE leg as a frame-level fact: the frame's last
    bar engages the R touch zone AND closes above R (the pre-breakout stance,
    profile ``R^``). Composes ``frame_r_engaged`` — this is THE single
    expression of the posture leg: the episode reader's terminal-R assignment
    and the story pool's O(1) prefilter both resolve here, so they cannot
    drift apart (NaN fails closed on both comparisons)."""
    return frame_r_engaged(last_high, R, tol) and bool(last_close > R)


def read_rail_episodes(df, R, S, atr_val) -> dict:
    """The chronological rail-episode read over ANY rail pair (doctrine:
    strategy_alpha.md "The rail-episode read"). Bar-level BY DESIGN: the
    sequence probe's separating evidence (EGBN ``S+ S+ S+ R^`` vs the
    drift-junk zeros) is a zone-visit read, and the promotion battery pins
    those counts — deriving episodes from the swing walk would change the
    measurement.

    Yardsticks: zone entry uses the engine's touch convention on WICK
    extremes (low/high vs rail ± ``TOUCH_TOLERANCE_ATR``); breach-beyond-
    buffer and reclaim are read on CLOSES — a deliberate, stated divergence
    from the respect gate's extreme-basis buffer (a deep intrabar flush that
    closes back inside is a worked test to this read, a breach to respect).
    ``EPISODE_DRIFT_MIN_BARS`` (3) is this layer's own drift floor. The
    promotion counts were pinned on exactly these bases — do NOT "align"
    them with the respect yardsticks later; that is a re-measurement and a
    new archive seam.

    Each episode is one merged visit of a rail's touch zone, typed by outcome:

      * ``completed`` — the engagement resolves back inside: any close-basis
        breach beyond the buffer is reclaimed and the first close after the
        episode confirms the rail held (support reclaimed / advance rejected).
      * ``failed`` — an unreclaimed breach, or the confirming close lands
        beyond the rail.
      * ``unreadable`` — a verdict-relevant close (the confirming close, or
        the run's last close when a breach needs a reclaim read) is not
        finite: no verdict printed on unreadable bars (contract §5 — the
        choice between rejected and unreadable is explicit, never silent).
      * ``open`` — the window ends inside the engagement: no verdict printed
        (contract §2 — never satisfies a completion predicate). An open R
        episode satisfying ``frame_terminal_posture`` carries
        ``terminal_posture=True``.

    Causality (contract §1–§2): the verdict prints at the first close after
    the episode, but the episode's IDENTITY is only irreversible once the
    merge horizon has printed clean — a later zone visit within
    ``EPISODE_MAX_GAP_BARS`` would have merged into it. So ``knowable_bar`` =
    ``end_bar + EPISODE_MAX_GAP_BARS + 1`` when that bar exists; an episode
    still inside its merge horizon at the frame edge (terminal episodes
    included) is ``in_progress``.

    Chronological order is by ``(end_bar, start_bar)`` with S-rail episodes
    before R-rail episodes on full ties — a pinned, deterministic rule.

    NaN policy (contract §5): arrays are coerced once at entry; a NaN bar can
    never enter a zone (comparisons fail closed), an unreadable bar inside an
    engagement carries NO breach evidence (a breach that never printed is not
    asserted), and ``nan_bars`` plus the ``unreadable`` outcome make the
    silence visible. Measure-only: moves no rail, gates nothing, scores
    nothing.
    """
    if df is None or len(df) == 0:
        return {"episodes": [], "n_episodes": 0, "nan_bars": 0, "n_bars": 0}
    return read_rail_episodes_arrays(
        df["High"].values, df["Low"].values, df["Close"].values,
        R, S, atr_val)


def read_rail_episodes_arrays(highs, lows, closes, R, S, atr_val) -> dict:
    """Array-level core of ``read_rail_episodes`` — same read, same dict.
    Exists so per-pair callers (the story pool consults this on ~44 pairs ×
    ~69 consultations per busy evaluation) can pass numpy suffix VIEWS of
    arrays they already hold instead of constructing a DataFrame slice per
    pair; ``np.asarray(dtype=float)`` is copy-free on float64 input."""
    n = int(len(closes))
    empty = {"episodes": [], "n_episodes": 0, "nan_bars": 0, "n_bars": n}
    if n == 0:
        return empty
    R, S = float(R), float(S)
    if not np.isfinite(R) or not np.isfinite(S) or R - S <= 0:
        return empty
    if atr_val is None or atr_val <= 0 or not np.isfinite(atr_val):
        return empty

    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    closes = np.asarray(closes, dtype=float)
    nan_bars = int((~(np.isfinite(highs) & np.isfinite(lows)
                      & np.isfinite(closes))).sum())

    tol = settings.TOUCH_TOLERANCE_ATR * atr_val
    buf = settings.BOUNDARY_ATR_BUFFER * atr_val
    horizon = EPISODE_MAX_GAP_BARS + 1

    episodes = []
    for rail, visit in (("S", lows <= S + tol), ("R", highs >= R - tol)):
        for a, b in _zone_visit_runs(visit):
            seg = closes[a:b + 1]
            terminal = b >= n - 1
            posture = False
            if terminal:
                outcome = "open"
                if rail == "R":
                    posture = frame_terminal_posture(highs[b], closes[b],
                                                     R, tol)
            elif rail == "S":
                broke = bool(np.nanmin(seg) < S - buf)
                if broke and not np.isfinite(seg[-1]):
                    outcome = "unreadable"      # reclaim read unreadable
                elif broke and seg[-1] < S:
                    outcome = "failed"          # unreclaimed breach
                elif not np.isfinite(closes[b + 1]):
                    outcome = "unreadable"      # confirming close unreadable
                else:
                    outcome = ("completed" if closes[b + 1] >= S
                               else "failed")
            else:
                broke_up = bool(np.nanmax(seg) > R + buf)
                if broke_up and not np.isfinite(seg[-1]):
                    outcome = "unreadable"
                elif broke_up and seg[-1] > R:
                    outcome = "failed"          # unheld upside break
                elif not np.isfinite(closes[b + 1]):
                    outcome = "unreadable"
                else:
                    outcome = ("completed" if closes[b + 1] <= R
                               else "failed")
            know = b + horizon if (b + horizon <= n - 1 and not terminal) else None
            episodes.append({
                "rail": rail,
                "outcome": outcome,
                "start_bar": int(a),
                "end_bar": int(b),
                "n_bars": int(b - a + 1),
                "describes": [int(a), int(b)],
                "knowable_bar": know,
                "in_progress": know is None,
                "terminal_posture": posture,
            })
    # Stable sort: construction order is all-S then all-R, so a full (end,
    # start) tie deterministically keeps S before R.
    episodes.sort(key=lambda e: (e["end_bar"], e["start_bar"]))
    return {"episodes": episodes, "n_episodes": len(episodes),
            "nan_bars": nan_bars, "n_bars": n}


def story_admission(stats) -> bool:
    """The RULED story-pool admission form — operator ruling 2026-07-25,
    Option A of the census menu (canonical spec: strategy_alpha.md, "The
    rail-episode read"; the truth-table pin in test_event_map.py is the
    drift check). A judgment, deliberately OUTSIDE the factual reader: a
    re-ruling replaces THIS function (a new archive seam + a census re-run),
    never the measurement. Consumes an AS-OF stats dict — the caller is
    responsible for passing decision-day stats (contract §1)."""
    return (stats["n_completed_s"] >= 2
            and stats["terminal_r_posture"]
            and not stats["terminal_s_drift"])


def resistance_contraction_admission(stats) -> bool:
    """The SECOND named ruled form — the Power-Play species' contraction at
    resistance (program docs/power_play_program_2026-08.md Task 6; species
    ruling `c029555`; NAMED by operator ruling 2026-08-18 — the record says
    the behavior it saw, never an invented umbrella word: "is it price
    action that contracts above Resistance after breaking out? then say
    that"; the support-side sibling — contracting ON support after a
    shakeout recovery — is the LPS and keeps its own name/path).

    A young continuation base after an explosive leg contracts at or above
    resistance: its story is the HOLD, not completed support tests — S-poor
    BY VIRTUE, so the S-test form above can never read it. The form asks
    the same episode vocabulary three questions: the floor never FAILED,
    the frame is not bleeding on the floor, and the right edge is ENGAGED
    at the ceiling (an open R episode; a terminal ``R^`` posture bar
    produces the same open episode, so the post-breakout stance is covered
    by construction). WHICH behavior admitted is spoken by
    ``resistance_contraction_label`` below.

    Unification (operator ruling 2026-08-23, decisions.md story-chain row):
    the EVENT beneath this judgment is the ONE mini-consolidation event —
    the shelf at the ceiling is the inner-box mechanism at
    ``position="at_ceiling"`` (``inner_box.mini_consolidation_position``),
    not a species of its own. This function stays exactly what it is: the
    species lane's ruled ADMISSION over episode facts. It never elects
    geometry (the WCC 2.2x-wider-box catch is why), and a re-ruling
    replaces the judgment, never the measurement.

    PROVISIONAL until the operator's ruling sheets calibrate it (program
    Task 4). Dark: consulted only under ``POWER_PLAY_STORY_FORM_ENABLED``,
    which the species lane toggles around its own election — never the
    paying read. One implementation (EC-18): instruments delegate here.
    Rail comparisons upstream are the episode reader's ATR zones (never
    float equality), and same-bar ties keep the pinned (end_bar, start_bar,
    S-before-R) order — on an 8-bar window, a spring, an S-test and a
    reclaim can legally share a session."""
    return (stats["n_failed_s"] == 0
            and not stats["terminal_s_drift"]
            and stats["terminal_r_engagement"])


def resistance_contraction_label(stats) -> str:
    """The admitted behavior's NAME, derived from the measured posture —
    the ONE naming implementation (the admission's EC-18 sibling; operator
    ruling 2026-08-18). ``terminal_r_posture`` (last bar closes ABOVE the
    rail) = the post-breakout stance; engagement without posture = pressing
    the rail from below."""
    return ("contracting above resistance" if stats["terminal_r_posture"]
            else "contracting at resistance")


_EPISODE_MARK = {"completed": "+", "failed": "x", "open": "0",
                 "unreadable": "?"}


def _profile_mark(e) -> str:
    """One episode's profile token. ``^`` = terminal posture; ``+``/``x`` =
    completed/failed; ``0`` = open; ``?`` = unreadable verdict. A verdict
    whose IDENTITY is not yet fixed (non-terminal, merge horizon still open
    at the frame edge) carries a ``~`` suffix so the sentence can never
    appear to contradict the as-of scalar counts, which rightly exclude it."""
    mark = "^" if e["terminal_posture"] else _EPISODE_MARK[e["outcome"]]
    if e["in_progress"] and e["outcome"] != "open":
        mark += "~"
    return f"{e['rail']}{mark}"


def episode_sequence_stats(read, *, as_of_bar=None) -> dict:
    """Summary statistics over a rail-episode read — the sentence and its
    counts. With ``as_of_bar`` given, completed history counts ONLY episodes
    whose ``knowable_bar`` ≤ ``as_of_bar`` (the contract's as-of rule); the
    terminal flags and the profile are right-edge reads of the frame as
    printed and are reported separately from completed history, never
    counted as facts. Because they read the PHYSICAL frame edge, an
    ``as_of_bar`` below that edge is REFUSED loudly — deriving decision-day
    terminal state from a longer frame is a contract-§1 lookahead; truncate
    the frame at the decision bar instead (an ``as_of_bar`` at or beyond the
    edge is legal: the frame simply ends at or before the decision day).
    ``as_of_bar=None`` is the full-frame read (the probe's own semantics —
    every typed outcome counts, stamps ignored)."""
    eps = read["episodes"]
    if as_of_bar is None:
        completed = [e for e in eps if e["outcome"] == "completed"]
        failed_s = [e for e in eps
                    if e["outcome"] == "failed" and e["rail"] == "S"]
    else:
        if as_of_bar < read["n_bars"] - 1:
            raise ValueError(
                f"as_of_bar {as_of_bar} is below the frame edge "
                f"{read['n_bars'] - 1}: terminal flags/profile are right-edge "
                "reads — pass the frame truncated at the decision bar "
                "(contract §1)")
        completed = [e for e in eps
                     if e["outcome"] == "completed"
                     and e["knowable_bar"] is not None
                     and e["knowable_bar"] <= as_of_bar]
        failed_s = [e for e in eps
                    if e["outcome"] == "failed" and e["rail"] == "S"
                    and e["knowable_bar"] is not None
                    and e["knowable_bar"] <= as_of_bar]
    n_s = sum(1 for e in completed if e["rail"] == "S")
    n_r = sum(1 for e in completed if e["rail"] == "R")
    alternations = sum(1 for x, y in zip(completed, completed[1:])
                       if x["rail"] != y["rail"])
    s_eps = [e for e in eps if e["rail"] == "S"]
    drift = bool(
        s_eps and s_eps[-1]["outcome"] == "open"
        and s_eps[-1]["n_bars"] >= EPISODE_DRIFT_MIN_BARS)
    posture = any(e["terminal_posture"] for e in eps)
    profile = " ".join(_profile_mark(e) for e in eps)
    return {
        "n_completed_s": n_s,
        "n_completed_r": n_r,
        # The shelf form's legs (program Task 6; additive keys, measure-only):
        # knowable failed-S count under the same as-of discipline as completed,
        # and the right-edge engagement read ("open" is assigned ONLY to
        # terminal episodes, so any open R episode IS the frame-edge hang).
        "n_failed_s": len(failed_s),
        "terminal_r_engagement": any(
            e["rail"] == "R" and e["outcome"] == "open" for e in eps),
        "alternations": alternations,
        "terminal_s_drift": drift,
        "terminal_r_posture": posture,
        "profile": profile,
        "n_episodes": len(eps),
    }


# ── Archive column family: the tape summary ──────────────────────────────────
# Owning declaration for the Event Map archive columns (the HTF precedent —
# engine_alpha.structure.htf): names, SQL types, and row-value extraction live HERE;
# the live writer and seed both splat ``event_map_archive_values``. The ORM
# model (webapp/backend/archive_models.SetupArchive) declares matching nullable
# columns as MODEL-ONLY adds (the engine_config_version precedent): deliberately
# NOT hand-listed in the writer's _NEW_COLUMNS or startup._MIGRATIONS — the
# boot-time model-diff auto-migration and the writer's model-derived pass ADD
# them. Later families (shelf-LPS form, Last-Supper wave typing) extend this
# dict in their own tasks. NULL means "not measured" (flag off, pre-Event-Map
# rows), never zero.
EVENT_MAP_COLUMN_SQL: dict[str, str] = {
    "event_map_n_swings": "INTEGER",       # committed + in-progress swings, whole frame
    "event_map_pre_box_trend": "TEXT",     # pre-box view trend_state
    "event_map_n_labels": "INTEGER",       # role labels over the elected bricks
    "event_map_n_committed": "INTEGER",    # labels whose verdict was knowable at scan close
    # Rail-episode substrate (Event Map program Task 10) — the sequence
    # statistics a later TA-score calibration may grade: typed scalars only,
    # one value per column, designed in ONE pass. The compact episode tape is
    # the single audit/display artifact (time anchors, never bar indexes).
    # NULL = not measured (flag off / pre-flip rows) or refused (unreadable
    # geometry — bad ATR / non-positive rails); measured-and-empty stores
    # explicit ZEROS — the junk separator IS zero — with the readability
    # companion so zero-by-unreadable-bars can never masquerade as
    # zero-by-drift.
    "event_map_completed_s": "INTEGER",       # completed support tests (as-of)
    "event_map_completed_r": "INTEGER",       # completed resistance rejections (as-of)
    "event_map_alternations": "INTEGER",      # rail changes across completed episodes
    "event_map_terminal_posture": "INTEGER",  # 0/1 window ends engaging R, close above R
    "event_map_terminal_drift": "INTEGER",    # 0/1 open S episode at the edge >= drift floor
    "event_map_story_admitted": "INTEGER",    # 0/1 the RULED form's read (ruling 2026-07-25)
    "event_map_episode_nan_bars": "INTEGER",  # readability companion for the zeros
    # The GEOMETRY companion (2026-08-10, the nan-bars sibling): the fraction
    # of box height the two ATR-fixed touch zones consume, 2*tol/(R-S). Above
    # ~0.5 the neutral middle is thinner than an average bar and distinct
    # tests merge into one unresolved visit (LEVI: 0.69 coverage, one R
    # episode spanning the whole base, all-zero counts on a clean base) — so
    # zero-by-geometry can never masquerade as zero-by-drift. Raw and
    # unclamped (>1.0 = the zones overlap); the floor lives in
    # settings.STORY_UNREADABLE_ZONE_COVERAGE, never here.
    "event_map_zone_coverage": "REAL",
    "event_map_episode_profile": "TEXT",      # the sentence, e.g. "S+ S+ S+ R^"
    "event_map_episodes": "TEXT",             # compact JSON tape (rail/outcome/span/knowable dates)
}


def episode_substrate_fields(win_df, R, S, atr_val) -> dict:
    """The archived rail-episode substrate for ONE elected window (Task 10)
    — the producer lives HERE beside ``EVENT_MAP_COLUMN_SQL`` so the family's
    names, SQL types, row extraction AND the tape cell's shape have a single
    owning module; the per-episode tape keys (rail / outcome / posture /
    span / knowable, date-anchored) are pinned by the serializer guards in
    tests/test_event_map.py.

    BASIS NOTE: this is the ELECTED-geometry read (elected window, zone ATR)
    — a DIFFERENT basis from the story pool's admission read (candidate
    window, candidate ATR), and the two may legally disagree: YPF fires
    story-elected while this read's ``event_map_story_admitted`` is 0. The
    evidence that admitted a story fire travels separately in
    ``story_admission_profile``; this column family is the substrate a later
    TA-score calibration grades, never the admission record.

    As-of discipline (contract §1): the read is taken at the window's own
    edge — episodes still inside their merge horizon are excluded from the
    completed counts (and marked ``~`` in the sentence). Explicit zeros are
    evidence; NULL means the producer never ran OR refused to read
    (unreadable geometry — a refused read must not archive zeros that
    masquerade as a measured-empty tape)."""
    # The reader's own preconditions: positive rail height, usable ATR. On a
    # refused read NULL is the only honest value for the WHOLE family — the
    # coverage column always kept this law; the counts used to archive
    # fabricated zeros beside it (2026-08-25 sweep).
    height = float(R) - float(S)
    readable_geometry = (np.isfinite(height) and height > 0
                         and atr_val is not None and np.isfinite(atr_val)
                         and atr_val > 0)
    if not readable_geometry or win_df is None or len(win_df) == 0:
        return {col: None for col in (
            "_event_map_completed_s", "_event_map_completed_r",
            "_event_map_alternations", "_event_map_terminal_posture",
            "_event_map_terminal_drift", "_event_map_story_admitted",
            "_event_map_episode_nan_bars", "_event_map_zone_coverage",
            "_event_map_episode_profile", "_event_map_episodes")}
    epi = read_rail_episodes(win_df, float(R), float(S), atr_val)
    stats = episode_sequence_stats(epi, as_of_bar=len(win_df) - 1)
    # The geometry companion: how much of the box the two touch zones consume.
    coverage = 2.0 * settings.TOUCH_TOLERANCE_ATR * float(atr_val) / height
    dates = win_df.index
    tape = json.dumps([
        {"rail": e["rail"], "outcome": e["outcome"],
         "posture": bool(e["terminal_posture"]),
         "span": [str(dates[e["start_bar"]].date()),
                  str(dates[e["end_bar"]].date())],
         "knowable": (str(dates[e["knowable_bar"]].date())
                      if e["knowable_bar"] is not None else None)}
        for e in epi["episodes"]], separators=(",", ":"))
    return {
        "_event_map_completed_s": int(stats["n_completed_s"]),
        "_event_map_completed_r": int(stats["n_completed_r"]),
        "_event_map_alternations": int(stats["alternations"]),
        "_event_map_terminal_posture": int(stats["terminal_r_posture"]),
        "_event_map_terminal_drift": int(stats["terminal_s_drift"]),
        "_event_map_story_admitted": int(story_admission(stats)),
        "_event_map_episode_nan_bars": int(epi["nan_bars"]),
        "_event_map_zone_coverage": coverage,
        "_event_map_episode_profile": stats["profile"],
        "_event_map_episodes": tape,
    }


def event_map_archive_values(get, *, prefixed: bool) -> dict:
    """Map a result row to the {column: value} archive dict. ``get`` is the
    row's ``.get``; the LIVE result carries ``_``-prefixed keys
    (``prefixed=True``), the SEED result does not. Cells are NaN-scrubbed at
    the pandas boundary (EC-2) and INTEGER cells coerced to plain int — which
    also lands future boolean fields on the 0/1-or-NULL convention. A missing
    or scrubbed cell stays None (NULL = "not measured")."""
    out = {}
    for col, sql_type in EVENT_MAP_COLUMN_SQL.items():
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


def narrative_chart_fields(get) -> dict:
    """The payload projection of the same family — the THIRD consumer of the
    one extraction both archive writers splat (never a re-declared field
    list), keyed by the archive column names so the archived cell and the
    served field can be asserted value-identical per fire.

    Only the tape cell changes shape at this boundary: the archive stores
    JSON text, the wire carries it parsed once here (structure, never a
    string each consumer re-parses). An unparseable cell degrades that one
    field to ``None`` while the family's scalars stay measured — so
    "tape unreadable" (scalars present, tape None) can never masquerade as
    "not measured" (the whole family None). The frontend renders the two
    distinctly; it never re-derives counts from the tape (the sentence and
    its counts share one as-of basis upstream)."""
    out = event_map_archive_values(get, prefixed=True)
    tape = out.get("event_map_episodes")
    if tape is not None:
        try:
            out["event_map_episodes"] = json.loads(tape)
        except (TypeError, ValueError):
            out["event_map_episodes"] = None
    return out
