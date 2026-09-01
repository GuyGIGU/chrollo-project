"""Shared calibrated box primitives.

The live chronological bricks and the diagnostic standalone detectors in
``consolidation`` both compose these measurement helpers.

A candidate is a Resistance-anchor / Support-anchor pair drawn from the zigzag
(``BC``/``AR`` are the Phase-A trend climax/rally — the place the search begins,
not the rails). A pair is only a REAL trading range if price respects, touches,
and zigzags through both rails CONSTANTLY with no dead space — enforced by the
``box_gates`` judges (boundary respect + worked-equilibrium occupancy +
traversal floor). Selection keeps the EARLIEST pair that passes
every constraint; if none passes, the box is rejected.
"""
from __future__ import annotations

import logging

from typing import NamedTuple

import numpy as np

from config import settings
from engine_alpha.structure.box_gates import (
    _apply_traversal_gate,
    _buffered_rails,
    _leg_record,
    _occupancy_leg_failures,
    _respect_stats,
    _validate_base_quality,
    _worked_window_end,
    leg_threshold,
)
from engine_alpha.structure.box_trace import _trace_find, _trace_pair
from engine_alpha.structure.pivots import _find_pivots, _pivot_order, _swing_skeleton


EMPTY_BOX = (0, 0, 0, 1.0, 0, 0, 0, 0, 0)

_story_log = logging.getLogger("chrollo.engine.story_pool")

__all__ = [
    "EMPTY_BOX",
    "SEEDING_LEGS",
    "backext_shared_rail",
    "collect_root_anchors",
    "collect_zigzag_candidates",
    "select_phase_b_candidate",
    "phase_b_zigzag",
]


# The seeding-refusal vocabulary (program Task 9) — the anchor seam's OWN
# closed set, never an overload of the near-miss ``failing_leg`` set. An
# age-walled pair always records ``ar_age``: the AR sits AFTER its climax, so
# a climax inside the young zone forces its AR inside it too — the AR wall is
# the one that clears LAST and the one the first-legal-look arithmetic turns
# on. (A separate ``climax_age`` leg was advertised at build time and proven
# UNREACHABLE by that same ordering — narrowed out 2026-08-17 review, Beck:
# every leg in this tuple has a committed producing case.)
SEEDING_LEGS = ("frame_short", "below_trend_sma", "ar_age")


def collect_root_anchors(eval_df: "pd.DataFrame", min_days: int,
                         seeding_trace: list | None = None,
                         ) -> list[tuple[str, int, int, float, float]]:
    """Return qualifying Phase-A climax -> reaction anchors, most-recent first.

    ``seeding_trace``: the optional refusal recorder at THIS seam (the
    near-miss recorder attaches one seam later, at pair election — seeding
    refusals were structurally invisible to it). ``None`` (the live default)
    records nothing and is byte-identical: the young zone beyond ``scan_hi``
    is only walked when a trace rides. Records are dicts with a ``leg`` from
    ``SEEDING_LEGS`` (+ ``kind``/``climax_bar``/``ar_bar`` for pair-level
    refusals), so the census and the live product answer "why didn't it
    seed" with the same words."""
    if len(eval_df) < min_days + 15:
        if seeding_trace is not None:
            seeding_trace.append({"leg": "frame_short"})
        return []

    closes = eval_df['Close'].values
    highs = eval_df['High'].values
    lows = eval_df['Low'].values
    sma200 = eval_df['Close'].rolling(settings.ROOT_TREND_SMA).mean().values
    end = len(eval_df) - 1

    if np.isnan(sma200[end]) or closes[end] <= sma200[end]:
        # The bottoming-base lane's seeding half (BOTTOMING_BASE_LANE_ENABLED,
        # dark — operator ruling 2026-08-29, MDT): the same reclaimed-50-day
        # condition as the universe door's sma200 leg, so the two layers of
        # the sma200 rule open together or not at all. The lane may open ONLY
        # the known-below leg — a NaN 200-bar mean is a trend-UNKNOWN frame,
        # not a bottoming base, and stays hard-refused (fail-closed doctrine;
        # council review 2026-08-30). Fail-closed likewise on a short frame or
        # NaN 50-bar mean; flag off is byte-identical. The HTF weekly/monthly
        # presets pin the lane OFF — the ruling and its census cover the daily
        # clock only.
        lane_admits = False
        if not np.isnan(sma200[end]) and settings.BOTTOMING_BASE_LANE_ENABLED:
            bars = settings.BOTTOMING_SMA50_BARS
            sma50_end = (float(np.mean(closes[end - bars + 1:end + 1]))
                         if end + 1 >= bars else float("nan"))
            lane_admits = bool(np.isfinite(sma50_end)
                               and closes[end] >= sma50_end)
        if not lane_admits:
            if seeding_trace is not None:
                seeding_trace.append({"leg": "below_trend_sma"})
            return []

    min_move = settings.TREND_MIN_GAIN_PCT
    min_move_bars = settings.TREND_MIN_MOVE_BARS
    prior_lookback = settings.TREND_PRIOR_LOOKBACK
    local_peak_bars = settings.LOCAL_PEAK_BARS

    scan_lo = min_move_bars + 5
    scan_hi = end - min_days
    if scan_hi <= scan_lo:
        # Defensive band guard — UNREACHABLE under current settings (the
        # 200-bar ROOT_TREND_SMA gate above refuses every frame short enough
        # to land here), but if a future settings combination ever arms it,
        # a riding trace must not go silent (2026-08-17 review, McKinney):
        # the frame cannot host a legal walk, which is what frame_short says.
        if seeding_trace is not None:
            seeding_trace.append({"leg": "frame_short"})
        return []

    anchors: list[tuple[str, int, int, float, float]] = []

    # With a trace riding, the walk ALSO covers the young zone (scan_hi, end)
    # so age-walled pairs become records instead of silence; without one the
    # range is exactly the legacy walk.
    walk_hi = (end - 1) if seeding_trace is not None else scan_hi
    for i in range(walk_hi, scan_lo - 1, -1):
        prior_start = max(0, i - prior_lookback)
        local_start = max(0, i - local_peak_bars)

        if highs[i] >= np.max(highs[local_start:i + 1]):
            prior_lows = lows[prior_start:i]
            if len(prior_lows) >= min_move_bars:
                trough_k = int(np.argmin(prior_lows))
                trough_low = float(prior_lows[trough_k])
                trough_bar = prior_start + trough_k
                if trough_low > 0 \
                        and highs[i] / trough_low - 1.0 >= min_move \
                        and (i - trough_bar) >= min_move_bars:
                    ar_thr = highs[i] * (1.0 - settings.AR_MIN_DROP_PCT)
                    ar_end = min(len(eval_df), i + settings.AR_MAX_BARS + 1)
                    ar_completed = False
                    ar_low_bar = -1
                    ar_low_val = np.inf
                    for j in range(i + 1, ar_end):
                        if closes[j] <= ar_thr:
                            ar_completed = True
                        if lows[j] < ar_low_val:
                            ar_low_val = lows[j]
                            ar_low_bar = j
                    if ar_completed and ar_low_bar != -1:
                        ar_young = (len(eval_df) - ar_low_bar) < min_days
                        if i > scan_hi or ar_young:
                            # A young climax forces a younger AR, so the AR
                            # wall is ALWAYS the binding one (SEEDING_LEGS
                            # note; 2026-08-17 review, Beck).
                            if seeding_trace is not None:
                                seeding_trace.append({
                                    "leg": "ar_age",
                                    "kind": "BC", "climax_bar": int(i),
                                    "ar_bar": int(ar_low_bar)})
                        else:
                            anchors.append(('BC', i, ar_low_bar,
                                            float(highs[i]), float(ar_low_val)))

        if lows[i] <= np.min(lows[local_start:i + 1]):
            prior_highs = highs[prior_start:i]
            if len(prior_highs) >= min_move_bars:
                peak_k = int(np.argmax(prior_highs))
                peak_high = float(prior_highs[peak_k])
                peak_bar = prior_start + peak_k
                if peak_high > 0 \
                        and 1.0 - lows[i] / peak_high >= min_move \
                        and (i - peak_bar) >= min_move_bars:
                    bounce_thr = lows[i] * (1.0 + settings.AR_MIN_DROP_PCT)
                    bounce_end = min(len(eval_df), i + settings.AR_MAX_BARS + 1)
                    bounce_completed = False
                    bounce_high_bar = -1
                    bounce_high_val = -np.inf
                    for j in range(i + 1, bounce_end):
                        if closes[j] >= bounce_thr:
                            bounce_completed = True
                        if highs[j] > bounce_high_val:
                            bounce_high_val = highs[j]
                            bounce_high_bar = j
                    if bounce_completed and bounce_high_bar != -1:
                        ar_young = (len(eval_df) - bounce_high_bar) < min_days
                        if i > scan_hi or ar_young:
                            # Same both-walls rule as the BC branch above.
                            if seeding_trace is not None:
                                seeding_trace.append({
                                    "leg": "ar_age",
                                    "kind": "SC", "climax_bar": int(i),
                                    "ar_bar": int(bounce_high_bar)})
                        else:
                            anchors.append(('SC', i, bounce_high_bar,
                                            float(bounce_high_val), float(lows[i])))

    return anchors


def _candidate_atr(eq_df, eq_highs, eq_lows, atr_override=None):
    """Return the ATR reference used for candidate boundary and quality checks."""
    if atr_override is not None and atr_override > 0 and not np.isnan(atr_override):
        return float(atr_override)

    win = settings.PHASE_B_ATR_WINDOW
    if 'ATR_10' in eq_df.columns:
        recent_atr = eq_df['ATR_10'].values[-win:] if len(eq_df) >= win else eq_df['ATR_10'].values
        atr_val = float(np.nanmedian(recent_atr))
    else:
        atr_val = (float(np.median(eq_highs[-win:] - eq_lows[-win:]))
                   if len(eq_df) >= win else float(np.median(eq_highs - eq_lows)))

    if atr_val <= 0 or np.isnan(atr_val):
        atr_val = float(np.median(eq_highs - eq_lows))
    return atr_val


def _score_candidate(box_width, r_touches, s_touches, coverage):
    """Combined quality of a (valid) candidate framing — drives "best"/debug
    selection and breaks "earliest" ties. All inputs already passed validity."""
    tightness_score = (settings.MAX_BOX_WIDTH - box_width) / settings.MAX_BOX_WIDTH
    touch_score = min(1.0, (r_touches + s_touches) / 10.0)
    coverage_score = coverage
    return 0.4 * tightness_score + 0.4 * touch_score + 0.2 * coverage_score


ELECTED_POOLS = ("strict", "rescued", "band", "story")

# The pools whose respect refusals the STRICT pass already narrated over the
# identical windows — silence there is a property of THE POOL, never of an
# occupancy replacement. A future pool reusing the one ladder with its own
# ruled judgment narrates and records its refusals normally unless it is
# named here (consolidation-method Task 5).
PRE_NARRATED_POOLS = frozenset({"story"})


class Admission(NamedTuple):
    """One ruled admission's whole visible output — the SINGLE channel the
    occupancy-judgment seam returns. ``profile`` rides the Candidate's
    ``story_profile`` slot; ``form`` and ``sentence`` are what the calling
    pool narrates and logs with, returned rather than written into the
    caller's scope."""
    profile: str                # the evidence that rides the Candidate
    form: str                   # WHICH named ruled form admitted
    sentence: "str | None"      # the episode read's own profile sentence


class Candidate(NamedTuple):
    """The ONE candidate-framing shape every pool produces and every consumer
    reads (bricks slots 11/12, box_gates slots 1/2/9/10, box_trace slots
    7/8/9, the phase_b_zigzag slice surgery). It IS a tuple — every
    positional index, slice, and unpack keeps working byte-identically —
    but the field ORDER is a cross-module contract: append-only, and
    construction happens ONLY in ``_pack_candidate``."""
    combined: float
    R: float
    S: float
    box_width: float
    r_touches: int
    s_touches: int
    total_outside: int
    r_anchor_bar: int
    s_anchor_bar: int
    cand_start: int
    # The JUDGED window length (bars from cand_start actually measured): the
    # full candidate window for strict/story framings, the trimmed worked
    # cause for rescued, the excised judged mask for band. The traversal gate
    # measures over the SAME window, so a trimmed tail can't be ignored for
    # respect/occupancy yet counted there.
    judged_len: int
    # Electing-pool provenance — closed set ELECTED_POOLS, enforced at the
    # bricks stamping point and by the archive CHECK.
    pool: str
    # The story pool's admitting sentence (None everywhere else) — a rescued
    # fire carries ITS OWN admission evidence into the archive.
    story_profile: "str | None"


def _pack_candidate(box_width, r_touches, s_touches, coverage, total_outside,
                    R_val, S_val, r_anchor_bar, s_anchor_bar, cand_start,
                    judged_len, pool, story_profile=None):
    """Score + construct — the single producer of the Candidate shape."""
    combined = _score_candidate(box_width, r_touches, s_touches, coverage)
    return Candidate(combined, R_val, S_val, box_width, r_touches, s_touches,
                     total_outside, r_anchor_bar, s_anchor_bar, cand_start,
                     judged_len, pool, story_profile)


def _build_candidate(highs, lows, sub_df, R_val, S_val, box_width,
                     r_anchor_bar, s_anchor_bar, cand_start, atr_val,
                     trace=None, rescued=False, max_width=None, pool="strict",
                     recorder=None, occupancy_judgment=None):
    """Respect + occupancy over one window; return the candidate tuple or None.

    ``highs``/``lows``/``sub_df`` describe the window the framing is JUDGED on
    (the full candidate window for a strict framing, or its trimmed worked cause
    for a rescued one). R/S/anchors/cand_start are always the framing's true
    full-base coordinates — only the measurement window narrows. ``pool`` is
    the electing pool's closed-set provenance label (strict / rescued / band /
    story — Event Map program Task 11), carried on the tuple's last slot so a
    rescued cohort stays separable all the way into the archive. ``recorder``
    is the near-miss lane's numbers-only refusal recorder (outer consultation
    seam only; None = record nothing, byte-identical).

    ``occupancy_judgment``: the story pool's ruled-admission REPLACEMENT for
    the occupancy-family judgment — the one place the pools legally diverge
    (consolidation-method Task 5: ONE ladder for every pool; the RULED form
    "replaces ONLY the occupancy-family judgment"). ``None`` = the occupancy
    family judges (strict / rescued / band). When given: called once after
    respect passes; returns an ``Admission`` record (its whole output —
    profile, form, sentence), or ``None`` for a refusal it has already
    narrated itself. The crash filter still runs — never waived.

    Narration silence belongs to the POOL, not to the judgment: a pool named
    in ``PRE_NARRATED_POOLS`` leaves its respect refusals UN-narrated and
    UN-recorded, exactly as the story pool always refused them (the strict
    pass narrated the identical windows; policy stages are never gate legs to
    the recorder). Any other pool handing in a judgment narrates normally.
    """
    stats = _respect_stats(highs, lows, R_val, S_val, atr_val)
    respected, _r_broken, _s_broken, total_outside, share = stats[:5]
    if not respected:
        if pool in PRE_NARRATED_POOLS:
            return None     # silent, like width — the strict pass narrated it
        if recorder is not None:
            leg = ("respect_share" if share < settings.MIN_BOUNDARY_RESPECT_PCT
                   else "respect_run")
            recorder.refusal(leg, pool, r_anchor_bar, s_anchor_bar, cand_start,
                             R_val, S_val, len(highs),
                             total_outside, len(highs), stats[5])
        if trace is not None:
            # Name the sub-condition that actually fired: respect fails on the
            # outside SHARE or on a too-long consecutive RUN. When the share
            # passed, the run cap is — by elimination — the killer. The run
            # maximum itself is not in hand at this seam (measured=None; the
            # lane's completion primitive fills it).
            n = len(highs)
            share_min = leg_threshold("respect_share")
            run_max = leg_threshold("respect_run")
            if share < share_min:
                detail = (f"{total_outside}/{n} bars outside the buffered rails "
                          f"(respect {share:.2f} < {share_min})")
                legs = [_leg_record("respect_share", float(share), share_min,
                                    outside=int(total_outside), n=n)]
            else:
                detail = ("an outside run exceeded MAX_CONSECUTIVE_OUTSIDE_DAYS "
                          f"{run_max} "
                          f"({total_outside}/{n} bars outside in total)")
                legs = [_leg_record("respect_run", None, run_max,
                                    outside=int(total_outside), n=n)]
            _trace_pair(trace, "rejected", "respect", detail, R_val, S_val,
                        box_width, r_anchor_bar, s_anchor_bar, cand_start, rescued,
                        legs=legs)
        return None
    if occupancy_judgment is not None:
        admission = occupancy_judgment()
        if admission is None:
            return None                 # refused — the judgment narrated it
        r_touches, s_touches, eq, _is_valid = _validate_base_quality(
            sub_df, R_val, S_val, atr_val)
        if eq is None:
            return None                 # crash filter — never waived
        _trace_pair(trace, "valid", None, None, R_val, S_val, box_width,
                    r_anchor_bar, s_anchor_bar, cand_start, rescued)
        # The judged window is the full candidate window (strict-style — no
        # trim, no excision); the admitting sentence rides the Candidate so
        # the archive records the evidence that ACTUALLY admitted the fire.
        return _pack_candidate(box_width, r_touches, s_touches, eq["coverage"],
                               total_outside, R_val, S_val, r_anchor_bar,
                               s_anchor_bar, cand_start, len(highs), pool,
                               admission.profile)
    r_touches, s_touches, eq, is_valid = _validate_base_quality(
        sub_df, R_val, S_val, atr_val, max_width=max_width,
    )
    if not is_valid:
        if recorder is not None:
            # Family verdict only — itemized margins are the deferred
            # completion's job, never pair-loop work (crash's min-low was
            # consumed inside the gate; eq None marks it).
            recorder.refusal("crash" if eq is None else "occupancy", pool,
                             r_anchor_bar, s_anchor_bar, cand_start,
                             R_val, S_val, len(highs))
        if trace is not None:
            if eq is None:
                detail = "crash filter: min Low < S x CRASH_FILTER_MULT"
                # The min-low ratio was consumed inside the gate, not returned —
                # measured=None at the seam; post-hoc completion fills it.
                legs = [_leg_record("crash", None, leg_threshold("crash"))]
            else:
                failures = _occupancy_leg_failures(eq, r_touches, s_touches)
                detail = "; ".join(msg for _rec, msg in failures)
                legs = [rec for rec, _msg in failures]
            _trace_pair(trace, "rejected", "occupancy", detail, R_val, S_val,
                        box_width, r_anchor_bar, s_anchor_bar, cand_start, rescued,
                        legs=legs)
        return None
    _trace_pair(trace, "valid", None, None, R_val, S_val, box_width,
                r_anchor_bar, s_anchor_bar, cand_start, rescued)
    # Slot semantics live on the Candidate type — this function is the ONE
    # judgment ladder every pool runs (consolidation-method Task 5), never a
    # second shape producer.
    return _pack_candidate(box_width, r_touches, s_touches, eq["coverage"],
                           total_outside, R_val, S_val, r_anchor_bar,
                           s_anchor_bar, cand_start, len(highs), pool)


def _oriented_pairs(zigzag):
    """Consecutive zigzag limbs as oriented rail pairs — the ONE enumeration
    every candidate pool shares (the strict/rescued loop, the band pool, and
    any later last-resort rung). Yields ``(R_val, S_val, r_anchor_bar,
    s_anchor_bar)`` in chronological pair order; same-kind neighbours and
    degenerate pairs (``R <= S``) are skipped — exactly the comparisons both
    former copies applied."""
    for i in range(len(zigzag) - 1):
        zi, zj = zigzag[i], zigzag[i + 1]
        if zi[1] == 'peak' and zj[1] == 'valley':
            R_val, S_val = zi[2], zj[2]
            r_anchor_bar, s_anchor_bar = zi[0], zj[0]
        elif zi[1] == 'valley' and zj[1] == 'peak':
            R_val, S_val = zj[2], zi[2]
            r_anchor_bar, s_anchor_bar = zj[0], zi[0]
        else:
            continue
        if R_val <= S_val:
            continue
        yield R_val, S_val, r_anchor_bar, s_anchor_bar


def collect_zigzag_candidates(eq_df, atr_val, min_candidate_days=0,
                              enforce_traversal=False, trace=None,
                              recorder=None, forms=None):
    """Build valid R/S candidates from consecutive zigzag limbs.

    ``trace``: optional list; when given, every pair examined is recorded with
    its verdict and (on rejection) the gate that killed it — the Root-Swing
    cascade narrating itself (see strategy_alpha.md "The explainability rule").
    ``None`` (the live default) records nothing and changes nothing. The list
    must be scoped to a single call (pass a fresh one, as
    ``validate_equilibrium`` does): the rescue bookkeeping and the traversal
    gate match records across the WHOLE list they are handed.

    ``recorder``: the near-miss lane's numbers-only refusal recorder
    (``validate_equilibrium`` passes it on the outer consultation seam;
    inner boxes and the diagnostic mirror never do). ``None`` = record
    nothing, byte-identical. Policy stages (rescue_unused / dethroned /
    story) are election policy, never gate legs — the recorder ignores them.

    ``forms``: the armed-form roster for the story pool — WHICH named ruled
    admissions may admit (``event_map.ADMISSION_FORMS`` tokens), handed down
    explicitly by the walk (consolidation-method Task 4) and asserted at that
    entry point (``bricks.validate_equilibrium``, EC-55). ``None`` (every
    caller that means the ordinary read) = the baseline roster derived from
    settings at call time by ``event_map.baseline_admission_roster`` —
    byte-identical to the pre-roster behavior by construction.
    """
    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values

    peaks_idx, valleys_idx, zigzag = _swing_skeleton(
        eq_highs, eq_lows, _pivot_order(len(eq_df)), _find_pivots)
    if not peaks_idx or not valleys_idx:
        return []
    if len(zigzag) < 2:
        return []

    # Two pools: STRICT framings pass respect + occupancy over the full window
    # (the legacy rule, byte-identical); RESCUED framings only pass once a
    # trailing SOS breakout tail is trimmed (see ``_worked_window_end``). Rescued
    # framings are used ONLY when a window yields no strict one, so an ordinary
    # in-range setup is never re-framed — the trim can only save a box that would
    # otherwise be rejected outright (NMM's break above R, then a rest on it).
    strict, rescued = [], []
    for R_val, S_val, r_anchor_bar, s_anchor_bar in _oriented_pairs(zigzag):
        box_width = (R_val - S_val) / S_val
        if box_width > settings.MAX_BOX_WIDTH:
            if recorder is not None:
                cs = min(r_anchor_bar, s_anchor_bar)
                recorder.refusal("width", "strict", r_anchor_bar, s_anchor_bar,
                                 cs, R_val, S_val, len(eq_highs) - cs,
                                 box_width, settings.MAX_BOX_WIDTH)
            # Narration guarded whole: an unguarded call evaluated its f-string
            # argument on every trace=None live rejection (Task 1 leak fix).
            if trace is not None:
                width_max = leg_threshold("width")
                _trace_pair(trace, "rejected", "width",
                            f"box_width {box_width:.3f} > MAX_BOX_WIDTH {width_max}",
                            R_val, S_val, box_width, r_anchor_bar, s_anchor_bar,
                            min(r_anchor_bar, s_anchor_bar),
                            legs=[_leg_record("width", float(box_width), width_max)])
            continue

        cand_start = min(r_anchor_bar, s_anchor_bar)
        cand_eq_df = eq_df.iloc[cand_start:]
        if len(cand_eq_df) < min_candidate_days:
            if recorder is not None:
                recorder.refusal("window", "strict", r_anchor_bar, s_anchor_bar,
                                 cand_start, R_val, S_val, len(cand_eq_df),
                                 len(cand_eq_df), min_candidate_days)
            if trace is not None:
                _trace_pair(trace, "rejected", "window",
                            f"window {len(cand_eq_df)} < min_candidate_days {min_candidate_days}",
                            R_val, S_val, box_width, r_anchor_bar, s_anchor_bar,
                            cand_start,
                            legs=[_leg_record("window", len(cand_eq_df),
                                              min_candidate_days)])
            continue

        cand_highs = eq_highs[cand_start:]
        cand_lows = eq_lows[cand_start:]
        tup = _build_candidate(cand_highs, cand_lows, cand_eq_df, R_val, S_val,
                               box_width, r_anchor_bar, s_anchor_bar, cand_start,
                               atr_val, trace=trace, recorder=recorder)
        if tup is not None:
            strict.append(tup)
            continue

        # Rescue the break-above-R-then-rest case: the worked cause is a clean range, only the
        # already-broken-out right side tripped the gates. Outer Phase-B only, and
        # only while price is still BACKING UP to the box (not extended away from
        # it): an old range price has since blown past is stale, not a setup — the
        # same extension semantics the firing filter uses, applied here so a stale
        # rescued box can't pre-empt the ticker's real recent box in backtracking.
        if enforce_traversal:
            work_end = _worked_window_end(cand_highs, cand_lows, R_val, S_val, atr_val)
            last_close = float(cand_eq_df['Close'].iloc[-1])
            if work_end < len(cand_highs) \
                    and last_close <= R_val * settings.EXTENSION_FILTER_MULT:
                tup = _build_candidate(
                    cand_highs[:work_end], cand_lows[:work_end],
                    cand_eq_df.iloc[:work_end], R_val, S_val, box_width,
                    r_anchor_bar, s_anchor_bar, cand_start, atr_val,
                    trace=trace, rescued=True, pool="rescued",
                    recorder=recorder,
                )
                if tup is not None:
                    rescued.append(tup)

        # NOTE (gap-breach Task 4, 2026-07-24): a COMMIT-TAIL rescue — the
        # dual of the SOS trim, re-judging a failing framing on its window
        # minus a bounded terminal floor-holding pullback tail — was built
        # and REJECTED here. No cap (5/8/12/15 bars) restores the EGBN/YPF
        # right-edge elections it targeted: their collapses are structural
        # (EGBN's two-week above-R shelf residence = rail-PLACEMENT;
        # YPF's 19-bar base + occupancy), not bounded-tail artifacts, and a
        # trim long enough to matter re-elects stale windows (the rejected
        # 13b arbitration lesson). Cause-commitment stays open only via a
        # genuinely cross-frame mechanism (the measure-only election-
        # stability probe is the instrument), never via window trims.

    pool = strict if strict else rescued
    # NOTE (solve-the-engine task 13b, 2026-07-16): a rescued-pool
    # ARBITRATION lever (let a fully-valid rescued framing that predates
    # every strict candidate compete) was built and REJECTED here — on the
    # sealed corpus it kills VIK's pinned hit (the admitted early framing
    # wins earliest-of-valid, then fails to complete an LPS, and an
    # elect-then-fail kills the whole root), and no clean currency rule
    # separates that case from the MOV framing it was meant to save — the
    # reverted shelf-R lesson at election scope. Do not re-attempt without
    # new corpus evidence; MOV's fire is already covered by the
    # holding-shelf form.

    # DARK (ELECTION_DETHRONE_ENABLED — solve-the-engine task 13a): a
    # rescue-propped framing whose buffered R the tape has left FULLY behind
    # for the trailing ELECTION_DETHRONE_SESSIONS sessions has stopped being
    # the operative structure (MATX: stale spring boxes blind the fresh
    # shelf). Dethroned only IN FAVOR OF a later valid framing — never into
    # an emptier read. One trailing pass over the already-loaded window;
    # pure function of the frame, no cross-session state.
    if settings.ELECTION_DETHRONE_ENABLED and len(pool) > 1:
        buf = settings.BOUNDARY_ATR_BUFFER * atr_val
        k = settings.ELECTION_DETHRONE_SESSIONS
        rescued_ids = {id(c) for c in rescued}
        stale = [c for c in pool
                 if id(c) in rescued_ids and len(eq_lows) >= k
                 and bool((eq_lows[-k:] > c[1] + buf).all())]
        if stale:
            survivor_starts = [c[9] for c in pool if id(c) not in {id(s) for s in stale}]
            dropped = [c for c in stale
                       if any(s > c[9] for s in survivor_starts)]
            if dropped:
                dropped_ids = {id(c) for c in dropped}
                pool = [c for c in pool if id(c) not in dropped_ids]
                if trace is not None:
                    for cand in dropped:
                        rec = _trace_find(trace, cand)
                        if rec is not None:
                            rec["verdict"] = "rejected"
                            rec["stage"] = "dethroned"
                            rec["detail"] = (
                                f"rescue-propped pair fully above R+buffer for "
                                f"the last {k} sessions; a later valid framing "
                                f"is the operative structure")

    # LAST-RESORT worked-band pool (BAND_RAILS_ENABLED, dark; outer Phase B
    # only): consulted ONLY when both extreme-anchored pools are empty, so an
    # an ordinary election can never move WITHIN THIS ROOT'S WINDOW. (Scope
    # caveat, measured 2026-07-27: the guard is per-ROOT, but read_structure walks
    # roots oldest-first and returns the FIRST that completes — so a last-resort box
    # on an EARLY root can end the walk before a later root's ordinary box is ever
    # reached. Live instances: CMPR band-elects at root-early (payload agrees), AMCX
    # story-elects likewise. This is pre-existing design shared with the rescued pool,
    # NOT a story/band regression; do not "fix" it with a two-pass walk — measured,
    # that reverses CMPR's operator-accepted band election.)
    # Rails at the max-dwell close band;
    # qualified excursions (reclaim/fail-back + hold) are excised from the
    # judged window; every gate below runs UNCHANGED on the judged bars.
    if not pool and enforce_traversal and settings.BAND_RAILS_ENABLED:
        pool = _band_rail_candidates(eq_df, eq_highs, eq_lows, zigzag, atr_val,
                                     trace=trace, recorder=recorder)

    # LAST-RESORT story pool (STORY_POOL_ENABLED, dark; outer Phase B only):
    # consulted ONLY when the extreme-anchored pools AND the band pool are all
    # empty, so an an ordinary election can never move WITHIN THIS ROOT'S WINDOW. (Scope
    # caveat, measured 2026-07-27: the guard is per-ROOT, but read_structure walks
    # roots oldest-first and returns the FIRST that completes — so a last-resort box
    # on an EARLY root can end the walk before a later root's ordinary box is ever
    # reached. Live instances: CMPR band-elects at root-early (payload agrees), AMCX
    # story-elects likewise. This is pre-existing design shared with the rescued pool,
    # NOT a story/band regression; do not "fix" it with a two-pass walk — measured,
    # that reverses CMPR's operator-accepted band election.)
    # The RULED narrative form
    # (operator ruling 2026-07-25 — strategy_alpha.md "The rail-episode read")
    # replaces only the occupancy-family judgment; width/window/respect/crash
    # run unchanged here and the traversal gate below judges the returned pool.
    if not pool and enforce_traversal and settings.STORY_POOL_ENABLED:
        pool = _story_pool_candidates(eq_df, eq_highs, eq_lows, zigzag, atr_val,
                                      min_candidate_days, trace=trace,
                                      forms=forms)

    if trace is not None and strict and rescued:
        for rec in trace:
            if rec["verdict"] == "valid" and rec["rescued"]:
                rec["verdict"] = "rejected"
                rec["stage"] = "rescue_unused"
                rec["detail"] = "strict framings exist; the rescued pool is discarded"
    return _apply_traversal_gate(eq_df, pool, atr_val, enforce_traversal,
                                 trace=trace, recorder=recorder)


def _band_rail_candidates(eq_df, eq_highs, eq_lows, zigzag, atr_val, trace=None,
                          recorder=None):
    """Build the deep-event candidate pool for a window (possibly empty).

    Re-judges the SAME chronological zigzag pairs the strict pool enumerated —
    the operator's rail rule ("anchor R/S from the swings in chronological
    order, wick to wick") — with each pair's qualified excursion events excised
    from the judged window (``rail_qualification.qualify_pair_events``: every
    band-leaving span must reclaim/fail-back and HOLD, and at least one deep
    below-rail event must exist, or the pair is refused). Judged windows run
    the unchanged ``_build_candidate`` gates — the SOS-trim narrowed-
    measurement convention — except that a pair carrying a qualified deep
    event may measure up to ``BAND_MAX_BOX_WIDTH`` wick-to-wick (the class
    allowance; it exists only when the event does).
    """
    from engine_alpha.structure.rail_qualification import qualify_pair_events

    pool = []
    for R_val, S_val, r_anchor_bar, s_anchor_bar in _oriented_pairs(zigzag):
        box_width = (R_val - S_val) / S_val
        if box_width > settings.BAND_MAX_BOX_WIDTH:
            continue

        cand_start = min(r_anchor_bar, s_anchor_bar)
        read = qualify_pair_events(eq_df.iloc[cand_start:], S_val, R_val, atr_val)
        if read is None:
            continue
        mask = read["judged"]
        tup = _build_candidate(
            eq_highs[cand_start:][mask], eq_lows[cand_start:][mask],
            eq_df.iloc[cand_start:][mask], R_val, S_val, box_width,
            r_anchor_bar, s_anchor_bar, cand_start, atr_val,
            trace=trace, rescued=True, max_width=settings.BAND_MAX_BOX_WIDTH,
            pool="band", recorder=recorder,
        )
        if tup is None:
            continue
        if trace is not None:
            rec = _trace_find(trace, tup)
            if rec is not None:
                rec["detail"] = (f"chronological pair with {len(read['excursions'])} "
                                 "qualified excursion event(s) excised from the "
                                 "judged window")
        pool.append(tup)
    return pool


def _story_pool_candidates(eq_df, eq_highs, eq_lows, zigzag, atr_val,
                           min_candidate_days, trace=None, forms=None):
    """Build the story-rescue candidate pool for a window (possibly empty).

    The RULED narrative form (operator ruling 2026-07-25 — strategy_alpha.md
    "The rail-episode read"; ``event_map.story_admission``) replaces ONLY the
    occupancy-family judgment: a pair whose AS-OF episode read shows the
    ruled sentence (>= 2 completed support tests + terminal resistance
    posture + no terminal support drift) carries its worked-cause evidence in
    chronological ORDER instead of in dwell shares — the EGBN class, which
    the drift-junk twins (zero completed episodes) can never counterfeit.

    Every other law runs unchanged: the standard width cap (NO band-style
    allowance), the window floor, boundary respect (the junk defense), the
    crash filter, and the traversal gate on the returned pool (measured
    requirement: order alone does not carry the junk occupancy deaths —
    traversal kills 30 of 69). Respect, the admission slot, the crash filter
    and the pack all run through the ONE shared ladder
    (``_build_candidate``, the admission handed in as the occupancy-family
    replacement — consolidation-method Task 5), so a gate change lands in one
    place for every pool. Trace narration covers the story-stage judgment
    only; width/window/respect verdicts for these same pairs were already
    narrated by the strict pass over the identical windows.
    """
    from engine_alpha.structure.event_map import (
        ADMISSION_FORM_RESISTANCE_CONTRACTION, ADMISSION_FORM_S_TEST,
        ADMISSION_FORM_S_TEST_BAR_POSTURE,
        baseline_admission_roster, episode_sequence_stats, frame_r_engaged,
        frame_terminal_posture, read_rail_episodes_arrays,
        resistance_contraction_admission, resistance_contraction_label,
        story_admission, story_admission_bar_posture)

    # Cost shape (Task 12 profile, reordered per Council Review 2026-07-26):
    # the branch is reached by MOST windows in a scan (38/55 fixture tickers;
    # ~69 consultations x ~44 pairs on a busy evaluation — root backtracking
    # multiplies it), so the judgment runs cheapest-first: width -> O(1)
    # posture prefilter -> window floor -> boundary respect (pure numpy, and
    # the gate that actually kills the stale far-below-market pairs the
    # posture prefilter cannot) -> episode read (array views, no DataFrame
    # slice) -> ruled admission -> crash. Pure conjunction throughout: the
    # pool's content is order-independent.
    tol = settings.TOUCH_TOLERANCE_ATR * atr_val
    n_win = len(eq_df)
    last_high = eq_highs[-1] if len(eq_highs) else float("nan")
    _closes = eq_df['Close'].values
    _last_close = float(_closes[-1]) if len(_closes) else float("nan")
    # WHICH ruled forms may admit — the armed-form roster (consolidation-
    # method Task 4). ``None`` = the baseline roster, derived from settings
    # at call time by the ONE derivation, so the species lane (which arms
    # the contraction form under its declared preset via window_override)
    # and the instruments' flag_capture keep working unchanged. A caller
    # meaning anything else — today the contraction rescue's escalated
    # walk — hands the roster down explicitly; there is no other way to
    # arm a form here. Such a roster ARRIVES asserted (EC-55): the walk's
    # entry point, ``bricks.validate_equilibrium``, checks it against the
    # declared vocabulary on every read that carries one. Asserting HERE
    # instead made the check data-dependent — this branch is reached only
    # when every ordinary pool came back empty, so a typo raised on some
    # tickers and passed on others.
    if forms is None:
        forms = baseline_admission_roster()
    s_test_form = ADMISSION_FORM_S_TEST in forms
    species_form = ADMISSION_FORM_RESISTANCE_CONTRACTION in forms
    bar_form = ADMISSION_FORM_S_TEST_BAR_POSTURE in forms
    pool = []
    for R_val, S_val, r_anchor_bar, s_anchor_bar in _oriented_pairs(zigzag):
        box_width = (R_val - S_val) / S_val
        if box_width > settings.MAX_BOX_WIDTH:
            continue
        # O(1) EXACT necessary condition of an ARMED form's terminal leg —
        # each roster form contributes its own leg through shared event_map
        # predicates (the S-test form's posture via frame_terminal_posture;
        # the contraction form's AND the bar-posture variant's engagement
        # half via frame_r_engaged — engagement IS the variant's terminal
        # leg), so the prefilter and the reader's terminal reads cannot
        # drift apart. Refusing here (silently, like width) skips everything
        # below for most pairs; NaN fails closed.
        if not (s_test_form
                and frame_terminal_posture(last_high, _last_close, R_val, tol)) \
                and not ((species_form or bar_form)
                         and frame_r_engaged(last_high, R_val, tol)):
            continue
        cand_start = min(r_anchor_bar, s_anchor_bar)
        judged_len = n_win - cand_start
        if judged_len < min_candidate_days:
            continue
        cand_highs = eq_highs[cand_start:]
        cand_lows = eq_lows[cand_start:]
        admitted = None

        def _ruled_admission():
            """The occupancy-family REPLACEMENT — the ruled admission over the
            episode read, handed to the ONE shared ladder. WHICH named ruled
            form admitted (EC-18: each form has ONE implementation, both in
            event_map). S-tests first — the settled live form always wins the
            record when both read. Returns ONE ``Admission`` record — the
            admitting profile (the shelf form NAMES itself in it; the S-test
            form's record is the bare profile, exactly as before) plus the
            form and sentence this loop narrates with — or None having
            narrated the refusal. The record is bound here as well because
            the loop needs it AFTER the ladder returns; it is the same object
            the seam returned, never a second set of outputs."""
            nonlocal admitted
            read = read_rail_episodes_arrays(cand_highs, cand_lows,
                                             _closes[cand_start:],
                                             R_val, S_val, atr_val)
            stats = episode_sequence_stats(read, as_of_bar=judged_len - 1)
            if s_test_form and story_admission(stats):
                admitted_form = "ruled form"      # the S-test form's frozen label
            elif bar_form and story_admission_bar_posture(stats):
                # The bar-basis ceiling-leg variant (Task 7, dark): the
                # record names the behavior — the right edge ENGAGED at the
                # rail by the bar, s-test story intact. Operator-signed
                # 2026-09-01 (signing-sheet row W3); it freezes for good at
                # this lane's flip, and is dark until then.
                admitted_form = "engaged at resistance"
            elif species_form and resistance_contraction_admission(stats):
                # The record names the BEHAVIOR seen, from the measured posture
                # (operator naming ruling 2026-08-18): "contracting above
                # resistance" (close above the rail — the post-breakout stance)
                # or "contracting at resistance" (pressing from below).
                admitted_form = resistance_contraction_label(stats)
            else:
                _story_log.debug(
                    "story pool refused pair R=%.4f S=%.4f start=%d: %s",
                    R_val, S_val, cand_start, stats["profile"] or "no episodes")
                _trace_pair(trace, "rejected", "story",
                            f"ruled form not read: {stats['profile'] or 'no episodes'}",
                            R_val, S_val, box_width, r_anchor_bar, s_anchor_bar,
                            cand_start, rescued=True)
                return None
            profile = stats["profile"]
            if admitted_form != "ruled form":
                profile = f"{admitted_form} | {profile or 'no episodes'}"
            admitted = Admission(profile, admitted_form, stats["profile"])
            return admitted

        tup = _build_candidate(
            cand_highs, cand_lows, eq_df.iloc[cand_start:], R_val, S_val,
            box_width, r_anchor_bar, s_anchor_bar, cand_start, atr_val,
            trace=trace, rescued=True, pool="story",
            occupancy_judgment=_ruled_admission)
        if tup is None:
            continue
        if trace is not None:
            rec = _trace_find(trace, tup)
            if rec is not None:
                rec["detail"] = (f"story-admitted ({admitted.form}): "
                                 f"{admitted.sentence}")
        _story_log.debug(
            "story pool admitted pair R=%.4f S=%.4f start=%d profile=%r",
            R_val, S_val, cand_start, admitted.sentence)
        pool.append(tup)
    return pool


def select_phase_b_candidate(valid_candidates, select):
    """Pick one framing from the valid set.

    Every candidate here already passed the worked-equilibrium validity rule, so
    "earliest" is simply the earliest-starting valid range (longest Wyckoff
    cause), ties broken by higher combined quality. This is the user's "earliest
    OF the ones that qualify" — there is no longer a best-vs-earliest tension or
    a reach-quality floor, because a sparse/dead-space framing can no longer be
    valid in the first place. "best" stays for diagnostics.
    """
    if select == "earliest":
        return min(valid_candidates, key=lambda x: (x[9], -x[0]))
    return max(valid_candidates, key=lambda x: x[0])


def backext_shared_rail(eq_df, R_val, S_val, cand_start, atr_val):
    """Shared-rail back-extension of an ELECTED framing's start (gap #3).

    Candidate starts are pinned to their anchor pair (``cand_start =
    min(r_anchor, s_anchor)``), so the earliest-valid election can never reach
    an earlier start its own gates would bless (AGCO: the dissection proved
    the elected rails valid from 03-25, but the anchor pair proposes only
    04-02). Walk the elected start LEFT to the
    EARLIEST zigzag pivot that re-touches an elected rail within touch
    tolerance (peak ~ R or valley ~ S) with every intervening bar inside the
    buffered band [S - buf, R + buf]. On AGCO that lands on the 03-30
    S-touching valley — 3 bars shy of full validity, because the 03-25 peak
    never re-touches R. Anchoring the extension to a rail re-touch is what
    separates worked cause from drift (a descent leg or mid-band chop never
    qualifies, however band-conforming).

    POST-election refinement: rails, the respect/occupancy verdicts and the
    election itself are untouched, and the extended span is conforming-by-
    construction so boundary respect can only improve. But the start moves,
    so every read anchored to it re-measures: the base-window suite
    (base-age, traversal, contractions, support slope, dwell, touch-volume,
    bar compression), the spring / inner-box / LPS windows, bin evidence,
    the event story. Returns the (possibly unchanged) window-relative start.
    """
    if cand_start <= 0:
        return cand_start
    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values
    _, _, zigzag = _swing_skeleton(eq_highs, eq_lows, _pivot_order(len(eq_df)),
                                   _find_pivots)
    tol = settings.TOUCH_TOLERANCE_ATR * atr_val
    r_ceiling, s_floor = _buffered_rails(R_val, S_val, atr_val)
    for bar, kind, price in zigzag:                     # oldest pivot first
        if bar >= cand_start:
            break
        touches_rail = (abs(price - R_val) <= tol if kind == 'peak'
                        else abs(price - S_val) <= tol)
        if not touches_rail:
            continue
        if float(eq_highs[bar:cand_start].max()) <= r_ceiling \
                and float(eq_lows[bar:cand_start].min()) >= s_floor:
            return int(bar)
    return cand_start


def _debug_candidates(valid_candidates, base_length):
    return [
        {
            "cand_start": int(c[9]),
            "base_len": int(base_length - c[9]),
            "box_width": round(float(c[3]), 4),
            "r_touches": int(c[4]),
            "s_touches": int(c[5]),
            "combined": round(float(c[0]), 4),
            "R": round(float(c[1]), 4),
            "S": round(float(c[2]), 4),
        }
        for c in sorted(valid_candidates, key=lambda x: x[9])
    ]


def _rebase_selected_candidate(candidate, base_length):
    # Trailing *_ absorbs the judged-window length (slot 10), which is internal to
    # candidate selection / the traversal gate and not part of the rebased box.
    _, best_R, best_S, best_bw, best_rt, best_st, best_breach, \
        best_r_bar, best_s_bar, best_cand_start, *_ = candidate

    effective_base_length = base_length - best_cand_start
    new_r_anchor = best_r_bar - best_cand_start
    new_s_anchor = best_s_bar - best_cand_start
    return (effective_base_length, best_R, best_S, best_bw, best_rt, best_st,
            best_breach, new_r_anchor, new_s_anchor)


def phase_b_zigzag(eval_df, start_idx, base_length, atr_override=None,
                   select="earliest"):
    """Shared Phase B: zigzag S/R anchoring over eval_df.iloc[start_idx:]."""
    eq_df = eval_df.iloc[start_idx:]
    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values

    atr_val = _candidate_atr(eq_df, eq_highs, eq_lows, atr_override)
    valid_candidates = collect_zigzag_candidates(
        eq_df, atr_val, enforce_traversal=True)

    if not valid_candidates:
        return [] if select == "debug" else EMPTY_BOX

    if select == "debug":
        return _debug_candidates(valid_candidates, base_length)

    selected = select_phase_b_candidate(valid_candidates, select)
    # The diagnostic mirror applies the same shared-rail back-extension as
    # the live reader (bricks.validate_equilibrium — unconditional in both
    # since the 2026-07-18 fold; the old flag was deleted in that rotation),
    # so detect_boxes-based tools frame the SAME box as production. No-op
    # when nothing extends.
    ext_start = backext_shared_rail(eq_df, selected[1], selected[2],
                                    int(selected[9]), atr_val)
    if ext_start != selected[9]:
        selected = selected[:9] + (int(ext_start),) + selected[10:]
    return _rebase_selected_candidate(selected, base_length)
