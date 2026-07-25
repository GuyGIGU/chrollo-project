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

Causality (specs/event-map-causality-contract.md — binding):
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

Measure-only: moves no rail, gates nothing, scores nothing. Nothing on the live
scan path calls this yet — fire-path staging with its flag protocol is plan
Task 6 (PLAN-event-tape.md).
"""
from __future__ import annotations

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

    Measure-only; no live-path caller (fire-path staging is plan Task 6).
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
    ``_box_events_with_meta`` chokepoint the puzzle read uses, so the roles can
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
    bounds. Measure-only — gates nothing, scores nothing, no live-path caller
    (fire-path staging is plan Task 6).
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


def read_rail_episodes(df, R, S, atr_val) -> dict:
    """The chronological rail-episode read over ANY rail pair (doctrine:
    strategy_alpha.md "The rail-episode read"). Bar-level BY DESIGN: the
    sequence probe's separating evidence (EGBN ``S+ S+ S+ R^`` vs the
    drift-junk zeros) is a zone-visit read, and the promotion battery pins
    those counts — deriving episodes from the swing walk would change the
    measurement. Yardsticks are the engine's own (touch zone, respect buffer,
    the band-rails same-side merge); no free knobs.

    Each episode is one merged visit of a rail's touch zone, typed by outcome:

      * ``completed`` — the engagement resolves back inside: any breach beyond
        the respect buffer is reclaimed and the first close after the episode
        confirms the rail held (support reclaimed / advance rejected).
      * ``failed`` — an unreclaimed breach, or the confirming close lands
        beyond the rail.
      * ``open`` — the window ends inside the engagement: no verdict printed
        (contract §2 — never satisfies a completion predicate). An open R
        episode whose final close sits above R carries
        ``terminal_posture=True`` (the pre-breakout stance, profile ``R^``).

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
    never enter a zone (comparisons fail closed) and ``nan_bars`` makes the
    silence visible. Measure-only: moves no rail, gates nothing, scores
    nothing.
    """
    empty = {"episodes": [], "n_episodes": 0, "nan_bars": 0}
    if df is None or len(df) == 0:
        return empty
    R, S = float(R), float(S)
    if not np.isfinite(R) or not np.isfinite(S) or R - S <= 0:
        return empty
    if atr_val is None or atr_val <= 0 or not np.isfinite(atr_val):
        return empty

    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    closes = df["Close"].values.astype(float)
    nan_bars = int((~(np.isfinite(highs) & np.isfinite(lows)
                      & np.isfinite(closes))).sum())

    tol = settings.TOUCH_TOLERANCE_ATR * atr_val
    buf = settings.BOUNDARY_ATR_BUFFER * atr_val
    n = len(df)
    horizon = EPISODE_MAX_GAP_BARS + 1

    episodes = []
    for rail, visit in (("S", lows <= S + tol), ("R", highs >= R - tol)):
        for a, b in _zone_visit_runs(visit):
            seg = closes[a:b + 1]
            terminal = b >= n - 1
            posture = False
            if rail == "S":
                broke = bool(np.nanmin(seg) < S - buf)
                reclaimed = (not broke) or bool(seg[-1] >= S)
                if terminal:
                    outcome = "open"
                elif not reclaimed:
                    outcome = "failed"
                else:
                    outcome = "completed" if closes[b + 1] >= S else "failed"
            else:
                broke_up = bool(np.nanmax(seg) > R + buf)
                held = (not broke_up) or bool(seg[-1] <= R)
                if terminal:
                    outcome = "open"
                    posture = bool(seg[-1] > R)
                elif not held:
                    outcome = "failed"
                else:
                    outcome = "completed" if closes[b + 1] <= R else "failed"
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
            "nan_bars": nan_bars}


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


_EPISODE_MARK = {"completed": "+", "failed": "x", "open": "0"}


def episode_sequence_stats(read, *, as_of_bar=None) -> dict:
    """Summary statistics over a rail-episode read — the sentence and its
    counts. With ``as_of_bar`` given, completed history counts ONLY episodes
    whose ``knowable_bar`` ≤ ``as_of_bar`` (the contract's as-of rule); the
    terminal flags are right-edge reads of the frame as printed and are
    reported separately from completed history, never counted as facts.
    ``as_of_bar=None`` is the full-frame read (the probe's own semantics —
    every typed outcome counts, stamps ignored)."""
    eps = read["episodes"]
    if as_of_bar is None:
        completed = [e for e in eps if e["outcome"] == "completed"]
    else:
        completed = [e for e in eps
                     if e["outcome"] == "completed"
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
    profile = " ".join(
        f"{e['rail']}{'^' if e['terminal_posture'] else _EPISODE_MARK[e['outcome']]}"
        for e in eps)
    return {
        "n_completed_s": n_s,
        "n_completed_r": n_r,
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
