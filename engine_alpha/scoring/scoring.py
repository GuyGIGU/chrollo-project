"""
The Scoring Engine — "what makes a stock pop".

This is the opinion layer. The Structure Engine hands it a pile of *measured
facts* about a setup (how tight the box is, how many touches, how the volume
dried up, how far below the 52-week high, how broad the market tape is, the
VCP contraction footprint, ...). This module turns those facts into points.

Every knob lives in ``config/settings.py`` (the SCORE_* and tier constants),
so tuning the strategy means editing numbers there — never touching the
measurement code. ``score_setup`` returns the total plus each sub-score so the
archive can later tell us which ingredients actually predicted winners.
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from config import settings


def _clamp(value: float, cap: float) -> float:
    """Clamp ``value`` into ``[0, cap]``. Used consistently across the scorer."""
    return max(0.0, min(cap, value))


def _ramp(value: Optional[float], zero_at: float, full_at: float, cap: float) -> float:
    """Linear ramp: 0 at/below ``zero_at``, ``cap`` at/above ``full_at``, proportional
    in between. The single shape shared by the uptrend / RS / 52w-high / breadth
    bonuses — each rewards a measurement that scales between a zero point and a
    saturation point. ``None`` (a missing measurement, e.g. no 52w history) → 0."""
    # Degenerate / inverted band (a misconfigured operator knob where the CLEAN and
    # MESSY anchors collapse or cross): return the polarity-safe neutral 0.0 rather
    # than divide by zero. 0.0 (not cap) is correct — callers that INVERT this ramp
    # (``1.0 - _ramp(...)``) then read full credit, and additive-bonus callers read
    # "no bonus". Guarded BEFORE the value check so an equal/inverted band can't
    # reach the divide. Dead code for every shipped anchor (all full_at > zero_at).
    if full_at <= zero_at:
        return 0.0
    if value is None or value <= zero_at:
        return 0.0
    progress = min(1.0, (value - zero_at) / (full_at - zero_at))
    return progress * cap


def _candle_readability(bar_compression: Optional[dict]) -> float:
    """Self-referential bar-texture readability in ``[CANDLE_GRADE_FLOOR, 1.0]``.

    1.0 = the base's bars are quiet/orderly vs its OWN box and ATR; the floor =
    choppy wide bars. Built ONLY from the already-guarded ``measure_bar_compression``
    scalars (median spread/box, median spread/ATR, tight-bar %) — each already
    normalized by the base's own box / ATR, so this NEVER applies a global/absolute
    bar-width threshold (a high-ADR but orderly mover is read against its own
    volatility). The two spread ratios are missing (``None``) together on a
    degenerate/flat base — that case returns neutral 1.0 (absent texture data never
    silently demotes a setup); a present-but-0.0 ``tight_bar_pct`` is a real
    "no tight bars" signal and is kept. Multiplicative grade: can only preserve or
    discount, never inflate (grades-not-vetoes)."""
    if not isinstance(bar_compression, dict):
        return 1.0
    msb = bar_compression.get("median_spread_pct_box")
    msa = bar_compression.get("median_spread_atr")
    tbp = bar_compression.get("tight_bar_pct")
    # The spread ratios are None together on a degenerate base -> neutral full credit.
    if msb is None or msa is None or pd.isna(msb) or pd.isna(msa):
        return 1.0
    grades = [
        # spread/box and spread/ATR: lower is cleaner -> invert the up-ramp.
        1.0 - _ramp(msb, settings.CANDLE_SPREAD_BOX_CLEAN,
                    settings.CANDLE_SPREAD_BOX_MESSY, 1.0),
        1.0 - _ramp(msa, settings.CANDLE_SPREAD_ATR_CLEAN,
                    settings.CANDLE_SPREAD_ATR_MESSY, 1.0),
    ]
    if tbp is not None and not pd.isna(tbp):
        # tight-bar %: higher is cleaner (a real 0.0 ramps to zero credit here).
        grades.append(_ramp(tbp, settings.CANDLE_TIGHTBAR_MESSY,
                            settings.CANDLE_TIGHTBAR_CLEAN, 1.0))
    composite = sum(grades) / len(grades)
    floor = settings.CANDLE_GRADE_FLOOR
    return floor + (1.0 - floor) * composite


def _puzzle_quality(narrative: Optional[dict]) -> float:
    """The L2 assembled Wyckoff puzzle as a single ``[0, 1]`` composite — the more
    high-quality pieces present in bullish order, the higher it reads.

    Built from the E2 ``assemble_box_narrative`` DESCRIPTIVE grades only:
    ``completeness`` (0..4 distinct canonical pieces: spring / SOS / LPS / held-test)
    and ``chronology`` (intact / partial / absent). These are CORRELATED — an
    ``intact`` chronology is structurally impossible without the full spine — so they
    fold into ONE composite, never two independent terms (which would double-count the
    full-puzzle case). Neutral ``0.0`` on a missing/``None`` (flag-off) or malformed
    narrative (absence never demotes a setup below its geometry merits). Monotonic:
    non-decreasing in completeness, and intact >= partial >= absent at equal
    completeness. A pure bonus grade — the caller clamps it into ``[0, cap]``."""
    if not isinstance(narrative, dict):
        return 0.0
    try:
        completeness = int(narrative.get("completeness", 0) or 0)
    except (TypeError, ValueError):
        return 0.0                       # non-numeric completeness -> neutral
    completeness = min(4, max(0, completeness))   # self-enforce the [0,1] bound here,
    #                                               not only via the caller's clamp
    chrono_factor = {
        "intact": 1.0,
        "partial": settings.PUZZLE_CHRONO_PARTIAL,
        "absent": 0.0,
    }.get(narrative.get("chronology", "absent"), 0.0)
    return (settings.PUZZLE_W_COMPLETENESS * (completeness / 4.0)
            + settings.PUZZLE_W_CHRONOLOGY * chrono_factor)


def score_setup(box_width: float, r_touches: int, s_touches: int,
                res_avg: float, sup_avg: float, base_df: pd.DataFrame,
                atr_ratio: float, tightness_ratio: float,
                vol_contraction: float, base_len: int,
                yearly_return: float, excess_return: float = 0.0,
                dist_52w_high_pct: Optional[float] = None,
                breadth_pct: Optional[float] = None,
                contraction_quality: float = 0.0,
                support_quality: float = 0.0,
                adr_quality: float = 0.0,
                adr_value: float = 0.0,
                traversal_density: float = 0.0,
                max_swing_frac: float = 1.0,
                dwell_asymmetry: float = 0.0,
                has_spring: bool = False,
                bar_compression: Optional[dict] = None,
                narrative: Optional[dict] = None) -> dict:
    """
    Calculate a composite quality score from structural metrics.

    Returns a dict with the total score and each sub-score component,
    enabling downstream regression analysis in the setup archive.

    excess_return: stock 6m return − SPY 6m return. Drives the soft RS bonus.
    dist_52w_high_pct: negative number (e.g. -0.07 = 7% below 52w high) used
    to award the 52w-high proximity bonus.
    breadth_pct: % of universe with Close > SMA_50 on scan_date. Same value
    across every setup in a run; rewards setups forming in a broad tape.
    traversal_density / max_swing_frac / dwell_asymmetry: box-relative swing facts
    (measure_equilibrium + measure_dwell_balance) grading genuine two-sided rail-working
    vs dead space; drives the traversal-quality term that replaced oscillation.
    """
    touches = r_touches + s_touches

    # Box tightness — flat linear scale, removing exponential penalty for wider boxes.
    # When TIGHTNESS_ADR_AWARE, the width is measured in ADR units rather than absolute %:
    # a genuine VCP coil is tight vs the stock's OWN daily range, whereas the absolute grade
    # rewards flat low-ADR drifts as "coils" (corr(box_tightness, ADR) = -0.73). box_width is
    # (R-S)/S, so *100 -> %, /adr_value -> ADR-widths. A box wider than MAX_BOX_WIDTH_ADR ADRs
    # earns no tightness (the _clamp floors the negative ratio at 0). The absolute MAX_BOX_WIDTH
    # validity gate upstream is unchanged — this only re-bases the SCORE.
    if settings.TIGHTNESS_ADR_AWARE and adr_value and adr_value > 0:
        box_width_adr = (box_width * 100.0) / adr_value
        box_tightness_ratio = ((settings.MAX_BOX_WIDTH_ADR - box_width_adr)
                               / settings.MAX_BOX_WIDTH_ADR)
    else:
        box_tightness_ratio = (settings.MAX_BOX_WIDTH - box_width) / settings.MAX_BOX_WIDTH
    # Candle-spread readability: discount tightness for a base whose interior bars are
    # choppy vs its OWN box/ATR, preserve it for a quiet base (self-referential — never an
    # absolute bar-width threshold). Multiplicative in [floor, 1] (grades-not-vetoes);
    # missing texture grades neutral 1.0, leaving box_tightness_ratio untouched.
    box_tightness_ratio *= _candle_readability(bar_compression)
    s_box = _clamp(box_tightness_ratio * settings.SCORE_BOX_TIGHTNESS,
                    settings.SCORE_BOX_TIGHTNESS)

    # Touch density
    base_touch_max = settings.SCORE_TOUCH_DENSITY - settings.TOUCH_BONUS_POINTS
    touch_score = _clamp(touches * 2.0, base_touch_max)
    if (r_touches >= settings.TOUCH_BONUS_INDIVIDUAL and s_touches >= settings.TOUCH_BONUS_INDIVIDUAL) \
       or (touches >= settings.TOUCH_BONUS_TOTAL):
        touch_score += settings.TOUCH_BONUS_POINTS
    s_touch = touch_score

    # Traversal quality — does the chop genuinely WORK BOTH RAILS, or hang off one?
    # Graded reward on rail-to-rail density (true round-trips per significant swing),
    # docked for one-sided dwell (lower-vs-upper-third residence asymmetry) and a
    # single oversized limb (max_swing_frac > 1 = a one-off spike defining a rail).
    # Replaces the retired, rail-blind oscillation term. The dock can only erode the
    # reward toward 0 — it is never negative, so a dead-space box simply earns
    # nothing here rather than being penalized below its other merits.
    density_reward = _clamp(
        (traversal_density / settings.TRAVERSAL_QUALITY_DENSITY_FULL) * settings.SCORE_TRAVERSAL_QUALITY,
        settings.SCORE_TRAVERSAL_QUALITY,
    )
    # A single limb dwarfing the box is a dead-space spike ONLY in a wide box with
    # no spring. In a tight box overshoot is inevitable (any real swing dwarfs the
    # tiny range, e.g. PRA), and a confirmed spring's undercut is a bullish leg, not
    # dead space — exempt the overshoot in both; the dwell-asymmetry tell remains.
    overshoot = (0.0 if (box_width <= settings.BASE_AGE_DEADSPACE_WIDTH or has_spring)
                 else max(0.0, max_swing_frac - 1.0))
    dead_space = overshoot + dwell_asymmetry
    dead_space_penalty = _clamp(dead_space * settings.TRAVERSAL_QUALITY_DWELL_PENALTY,
                                settings.TRAVERSAL_QUALITY_DWELL_PENALTY)
    s_traversal = max(0.0, density_reward - dead_space_penalty)

    # ATR squeeze
    s_atr = _clamp((1.0 - atr_ratio) * settings.SCORE_ATR_SQUEEZE,
                    settings.SCORE_ATR_SQUEEZE)

    # LPS candle tightness
    s_lps = _clamp((1 - tightness_ratio) * (settings.SCORE_LPS_TIGHTNESS * 2),
                    settings.SCORE_LPS_TIGHTNESS)

    # Volume contraction
    s_vol = _clamp(vol_contraction * (settings.SCORE_VOL_CONTRACTION * 2),
                    settings.SCORE_VOL_CONTRACTION)

    # Base age — Wyckoff "cause" reward. Sqrt-scaled so very long bases still
    # earn incremental credit past the saturation point without dominating the
    # total: a 30d base earns ~50% of cap, a 60d base ~71%, a 120d base 100%.
    s_age = 0.0
    if base_len > settings.MIN_BASE_DAYS:
        age_factor = math.sqrt(base_len / settings.BASE_AGE_CAP_DAYS)
        s_age = _clamp(age_factor * settings.SCORE_BASE_AGE, settings.SCORE_BASE_AGE)
        # Dead-space dock: "cause" only counts if a long base actually worked
        # rail-to-rail. A WIDE base with low traversal density is dead space, not
        # cause, so scale its age credit by the density shortfall. Tight boxes are
        # exempt (low density there is a small-box / spring artifact, e.g. PRA) —
        # so only gate once box_width clears BASE_AGE_DEADSPACE_WIDTH.
        if (box_width > settings.BASE_AGE_DEADSPACE_WIDTH
                and traversal_density < settings.TRAVERSAL_QUALITY_DENSITY_FULL):
            s_age *= _clamp(traversal_density / settings.TRAVERSAL_QUALITY_DENSITY_FULL, 1.0)

    # Strong-uptrend bonus — re-accumulation in an established uptrend breaks out
    # more reliably than the same structure on a flat YoY chart. Ramp MIN→MAX return.
    s_uptrend = _ramp(yearly_return, settings.MIN_STRONG_YEARLY_RETURN,
                      settings.MAX_STRONG_YEARLY_RETURN, settings.SCORE_UPTREND_BONUS)

    # Soft RS bonus — additive points for outperforming SPY over 6 months. No
    # filter, just leadership reward; ramps from 0 up to RS_MAX_EXCESS_RETURN.
    s_rs = _ramp(excess_return, 0.0, settings.RS_MAX_EXCESS_RETURN, settings.SCORE_RS_BONUS)

    # 52-week high proximity — bases near recent highs hold breakouts more
    # reliably. Ramp ZERO→FULL pct; null distance (no history) contributes zero.
    s_high = _ramp(dist_52w_high_pct, settings.HIGH_PROXIMITY_ZERO_PCT,
                   settings.HIGH_PROXIMITY_FULL_PCT, settings.SCORE_52W_HIGH_PROXIMITY)

    # Market-breadth bonus — ramp on % of universe above SMA_50. Same value for
    # every setup in a run; rewards a friendly tape regardless of the ticker.
    s_breadth = _ramp(breadth_pct, settings.BREADTH_ZERO_PCT,
                      settings.BREADTH_FULL_PCT, settings.SCORE_BREADTH_BONUS)

    # VCP progressive-contraction footprint — the *process* of tightening
    # (count + progressive-shrink + tight final contraction), as opposed to
    # box_tightness/atr_squeeze which only see static tightness. quality is
    # already a [0,1] composite from measure_contractions().
    s_contraction = _clamp(contraction_quality * settings.SCORE_CONTRACTION,
                           settings.SCORE_CONTRACTION)

    # Ascending support / higher lows — rewards a base whose swing lows are
    # stair-stepping up (rising demand). Bonus-only; flat/sagging floor = 0.
    s_ascending = _clamp(support_quality * settings.SCORE_ASCENDING_SUPPORT,
                         settings.SCORE_ASCENDING_SUPPORT)

    # ADR% absolute volatility — rewards stocks that move enough each day to
    # be worth trading. Bonus-only; quiet names simply earn zero here.
    s_adr = _clamp(adr_quality * settings.SCORE_ADR, settings.SCORE_ADR)

    # Puzzle-quality bonus (E3) — the L2 assembled Wyckoff puzzle as an additive,
    # bonus-only term. A missing/None/malformed narrative grades a neutral 0.0
    # (the containment lives in _puzzle_quality). Grades-not-vetoes: >=0 and
    # clamped to the cap, it can only raise a score.
    s_puzzle = _clamp(_puzzle_quality(narrative) * settings.SCORE_PUZZLE_QUALITY,
                      settings.SCORE_PUZZLE_QUALITY)

    total = round(s_box + s_touch + s_traversal + s_atr + s_lps + s_vol + s_age
                  + s_uptrend + s_rs + s_high + s_breadth + s_contraction
                  + s_ascending + s_adr + s_puzzle, 1)

    result = {
        'total': total,
        'box_tightness': round(s_box, 2),
        'touch_density': round(s_touch, 2),
        'traversal_quality': round(s_traversal, 2),
        'atr_squeeze': round(s_atr, 2),
        'lps_tightness': round(s_lps, 2),
        'vol_contraction': round(s_vol, 2),
        'base_age': round(s_age, 2),
        'uptrend_bonus': round(s_uptrend, 2),
        'rs_bonus': round(s_rs, 2),
        'high_proximity': round(s_high, 2),
        'breadth_bonus': round(s_breadth, 2),
        'contraction': round(s_contraction, 2),
        'ascending_support': round(s_ascending, 2),
        'adr': round(s_adr, 2),
        'puzzle_quality': round(s_puzzle, 2),
    }
    return result


def _finite(value, fallback: float = 0.0) -> float:
    """NaN/None/inf quarantine at the term boundary: a non-finite or missing
    input reads as its neutral ``fallback`` BEFORE anything is summed — one
    unguarded NaN would poison grade, chapters, and every downstream column."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return fallback
    return v if math.isfinite(v) else fallback


def _story_points(event_map: Optional[dict]) -> dict:
    """The story terms' points from the archived as-of Event-Map scalars.

    Three-state input discipline (the grade's law for story inputs):
      * missing family (map never ran / pre-flip rows)      -> ABSENT: every
        story term contributes neutral 0.0 against the FIXED divisor.
      * explicit zeros (measured-and-empty)                 -> EVIDENCE: the
        junk separator IS zero — the ramps read 0 and grade low.
      * all-zero counts with >= STORY_UNREADABLE_NAN_BARS unreadable bars
        -> ABSENT: zero-by-unreadable must never masquerade as zero-by-drift
        (the whole row routes to absent, stance included).
    Consumes the named scalars ONLY — never the episode tape, never the
    profile sentence (the archived counts already exclude in-progress and
    identity-unfixed episodes on the one as-of basis; a recount downstream
    would be lookahead by re-derivation). The right-edge stance (terminal
    posture) is its own term and is never added into completed-event facts."""
    absent = {"story_s_tests": 0.0, "story_r_rejections": 0.0,
              "story_alternations": 0.0, "story_terminal_posture": 0.0}
    if not isinstance(event_map, dict):
        return absent
    s = event_map.get("event_map_completed_s")
    r = event_map.get("event_map_completed_r")
    alt = event_map.get("event_map_alternations")
    posture = event_map.get("event_map_terminal_posture")
    if s is None and r is None and alt is None and posture is None:
        return absent
    s, r, alt = _finite(s), _finite(r), _finite(alt)
    nan_bars = _finite(event_map.get("event_map_episode_nan_bars"))
    if (s == 0 and r == 0 and alt == 0
            and nan_bars >= settings.STORY_UNREADABLE_NAN_BARS):
        return absent
    tests_full = float(settings.STORY_COMPLETED_TESTS_FULL)
    return {
        "story_s_tests": _ramp(s, 0.0, tests_full,
                               settings.SCORE_STORY_S_TESTS),
        "story_r_rejections": _ramp(r, 0.0, tests_full,
                                    settings.SCORE_STORY_R_REJECTIONS),
        "story_alternations": _ramp(alt, 0.0,
                                    float(settings.STORY_ALTERNATIONS_FULL),
                                    settings.SCORE_STORY_ALTERNATIONS),
        "story_terminal_posture": (
            float(settings.SCORE_STORY_TERMINAL_POSTURE)
            if _finite(posture) == 1.0 else 0.0),
    }


def _ta_v2_terms(*, has_spring: bool = False,
                 event_map: Optional[dict] = None) -> dict:
    """Promoted graded terms that feed the v2 grade only (never the legacy
    total). Each is bounded [0, cap], present-mask neutral (a missing/false
    input contributes 0.0 and never demotes below the geometry merits),
    grades-not-vetoes. FULL precision — nothing rounds before the sum."""
    terms = {
        # Phase-C spring: the undercut+reclaim at the base floor. Binary
        # promotion (has_spring already flows through both eval twins);
        # shape-only — SCORE_SPRING stays 0 until the operator's A/B.
        'spring': float(settings.SCORE_SPRING) if has_spring else 0.0,
    }
    terms.update(_story_points(event_map))
    return terms


def _ta_grade_warnings(event_map: Optional[dict]) -> dict:
    """{warning_id: factor} — the resolved warning discounts. Only warnings
    whose input is PRESENT and firing are emitted; a missing input emits no
    entry, so its factor is 1.0 EXACTLY, by absence. Factors are floored
    multiplicative discounts on the bounded 0-100 (grades-not-vetoes: a
    warning discounts, never vetoes). terminal_drift is the first registered
    warning — neutral 1.0 until the operator's A/B assigns its cost."""
    if not isinstance(event_map, dict):
        return {}
    out = {}
    drift = event_map.get("event_map_terminal_drift")
    if drift is not None and _finite(drift) == 1.0:
        out["terminal_drift"] = float(settings.TA_WARN_TERMINAL_DRIFT)
    return out


def compose_ta_grade(sub_scores: dict, *, has_spring: bool = False,
                     event_map: Optional[dict] = None) -> dict:
    """The Technical Analysis Grade — ONE fixed-divisor affine sum, displayed
    as story chapters (operator rulings 2026-08-06; build task 4).

        points[t]     the term's value: v1 terms from ``sub_scores``, promoted
                      v2 terms (spring + story) computed here; each
                      NaN-quarantined, absent -> neutral 0.0
        ta_grade_raw  Σ points over the emitted ta-layer terms
        chapters[c]   Σ points of c's terms × 100 / structural_cap_sum()
        pre           clamp(ta_grade_raw × 100 / structural_cap_sum(), 0, 100)
        ta_grade      pre × max(TA_GRADE_WARNING_FLOOR, Π warning factors)

    Chapters are a DISPLAY PARTITION of the one sum: the subtotals sum exactly
    to the pre-warning grade, and there is NO per-chapter divisor, floor, or
    clamp — any of those recreates the tested-DEAD present-cap denominator one
    level down. Absence is neutral against the FIXED divisor (a row missing an
    input grades against the same denominator as a full row). Warnings
    multiply on the bounded 0-100; a missing warning reads exactly 1.0. FULL
    precision throughout — rounding is display-only, at the wire. Called from
    the ONE shared eval chain (``_score_eval_context``) so live, seed, and
    manual rows are byte-identical by construction."""
    from engine_alpha.scoring import taxonomy
    v2 = _ta_v2_terms(has_spring=has_spring, event_map=event_map)
    chapters = {ch: 0.0 for ch in taxonomy.CHAPTER_ORDER}
    raw = 0.0
    for term in taxonomy.ta_layer_terms():
        pts = v2[term.key] if term.key in v2 else _finite(sub_scores.get(term.key))
        chapters[term.chapter] += pts
        raw += pts
    cap_sum = taxonomy.structural_cap_sum()
    scale = 0.0 if cap_sum <= 0 else 100.0 / cap_sum
    pre = max(0.0, min(100.0, raw * scale))
    warnings = _ta_grade_warnings(event_map)
    factor = 1.0
    for f in warnings.values():
        factor *= f
    if warnings:
        factor = max(float(settings.TA_GRADE_WARNING_FLOOR), factor)
    out = {
        'ta_grade_raw': raw,
        'ta_grade': pre * factor,
        'ta_grade_chapters': {ch: chapters[ch] * scale
                              for ch in taxonomy.CHAPTER_ORDER},
        'ta_grade_warnings': warnings,
    }
    out.update(v2)
    return out


def calculate_tier(score: float, box_width: Optional[float] = None) -> str:
    """Map a numeric score to a letter tier grade.

    ``box_width`` (optional) applies the S-tier width cap: a base wider than
    ``S_MAX_BOX_WIDTH`` cannot be S no matter how high it scores — a wide range,
    however long or well-touched, is not an elite setup. It still earns A on
    merit. Callers that don't have a width on hand omit it (no cap applied).
    """
    if score >= settings.TIER_S:
        tier = 'S'
    elif score >= settings.TIER_A:
        tier = 'A'
    elif score >= settings.TIER_B:
        tier = 'B'
    elif score >= settings.TIER_C:
        tier = 'C'
    else:
        tier = 'D'

    if tier == 'S' and box_width is not None and box_width > settings.S_MAX_BOX_WIDTH:
        tier = 'A'
    return tier
