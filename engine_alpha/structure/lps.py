"""LPS / spring detection - the Last-Point-of-Support finder.

Pure measurement + classification over an already-detected consolidation box.
The detector returns facts about the active setup LPS/Test; scoring and the
pipeline decide what those facts are worth.
"""
from __future__ import annotations

from collections import Counter
from typing import Optional, Union

import numpy as np
import pandas as pd

from config import settings
from engine_alpha.structure.market_structure import _pairwise_descent_fraction


_TIGHT_BOX_WIDTH = 0.10


def _finite(value) -> bool:
    try:
        return value is not None and np.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _zone_tolerance(sup_avg: float, res_avg: float, atr_val: float) -> float:
    """Tolerance around the active box used by the LPS zone gate.

    RULING (2026-07-24, gap-breach Task 2): this is a genuinely DIFFERENT
    concept from rail respect and is kept apart on purpose. Respect asks
    "does this bar stay inside the box envelope?" and is owned by the ONE
    per-bar classification in ``box_gates._rail_outside_masks``; zone
    tolerance asks "which zone (INSIDE / OVERSHOOT_R / UNDERCUT_S) does the
    shelf's terminal level belong to?" — an event-LOCATION typing band, with
    its own tight-box widening rescue. They share the ATR yardstick, not the
    question; do not fold them.
    """
    box_height = res_avg - sup_avg
    bw = box_height / sup_avg if sup_avg > 0 else 0.0
    if bw < _TIGHT_BOX_WIDTH:
        return max(settings.LPS_ZONE_ATR_MULT * atr_val, 0.5 * box_height)
    return settings.LPS_ZONE_ATR_MULT * atr_val


def _date_at(df: pd.DataFrame, idx: int) -> Optional[str]:
    if idx < 0 or idx >= len(df):
        return None
    try:
        return str(df.index[idx])[:10]
    except (IndexError, TypeError, ValueError):
        return None


def _spread_decline_quality(tight_spread: float, prev_spread: float,
                            profile_unit: float) -> float:
    """Reward a narrowing final bar without rejecting an otherwise tight LPS."""
    if profile_unit <= 0:
        return 1.0
    if tight_spread <= prev_spread:
        return 1.0
    widening = tight_spread - prev_spread
    return max(0.0, 1.0 - (widening / profile_unit))


def _profile_unit(base_range_threshold: float, box_height: float) -> Optional[float]:
    if not _finite(base_range_threshold) or float(base_range_threshold) <= 0:
        return None
    if not _finite(box_height) or float(box_height) <= 0:
        return None
    return max(
        float(base_range_threshold),
        settings.LPS_PROFILE_BOX_FRACTION_FLOOR * float(box_height),
    )


def _spread_series(frame: pd.DataFrame) -> pd.Series:
    if "Spread" in frame.columns:
        return frame["Spread"].astype(float)
    return frame["High"].astype(float) - frame["Low"].astype(float)


def _box_position(price: float, sup_avg: float, box_height: float) -> float:
    if box_height <= 0:
        return 1.0
    return (float(price) - float(sup_avg)) / float(box_height)


def _clean_downswing(length: int, low_descent_frac: float, high_descent_frac: float,
                     box_width: float) -> bool:
    return (
        length >= 3
        and low_descent_frac == 1.0
        and high_descent_frac == 1.0
        and box_width <= _TIGHT_BOX_WIDTH
    )


def _swing_type(zone_type: str, rising_support_shelf: bool, buec_shelf: bool,
                clean_downswing: bool, holding_shelf: bool = False) -> str:
    if zone_type == "UNDERCUT_S":
        return "undercut_rebound"
    if holding_shelf:
        return "holding_shelf"
    if rising_support_shelf:
        return "rising_support_shelf"
    if buec_shelf:
        return "buec_shelf"
    if clean_downswing:
        return "clean_downswing"
    return "terminal_valley"


# ─────────────────────────────────────────────────────────────────────────────
# The two completion forms (docs/lps_final_structure_canon_2026-07-10.md).
#
# ``detect_lps_candidates`` is form-agnostic machinery (window enumeration,
# zone typing, tightness/volume gates, trigger derivation, reject counting);
# the pure judgments below are what makes a window an LPS:
#   * pullback-and-rest — rests on its terminal low (or earns the
#     rising-support-shelf rescue) with a zone-deep pullback and a volume
#     dry-up (``_pullback_rest_low_verdict`` + ``_pullback_rest_depth_ok``);
#   * holding shelf (``_holding_shelf_verdict``, flag-gated dark) — a
#     geometry-only sibling judgment consulted at the same seams, never a
#     second detector.
# ─────────────────────────────────────────────────────────────────────────────
def _pullback_rest_low_verdict(
    last_low: float,
    window_low: float,
    terminal_low_tolerance: float,
    length: int,
    window_range_pct_box: float,
    sup_avg: float,
    box_height: float,
    first_close: float,
    end_close: float,
) -> tuple[str, bool]:
    """Terminal-rest judgment: does the window rest on its low?

    Returns ``(verdict, rescued)`` — verdict is ``"pass"`` / ``"does not rest
    on its low"`` / ``"markup leg, not a shelf"`` (plain-language reject slugs,
    Purity task 13); ``rescued`` is True when the rising-support-shelf
    exception accepts an early low (the caller re-anchors to the window low).
    """
    if last_low <= window_low + terminal_low_tolerance:
        return "pass", False
    shelf_low_pos = _box_position(window_low, sup_avg, box_height)
    # A compact rising shelf can print its real support test early,
    # then tighten upward. Keep the terminal-low rule for ordinary
    # reactions; this exception is only for a multi-bar inside-box
    # shelf whose low is still in the support side of the box.
    rising_support_shelf = (
        length >= 4
        and window_low >= sup_avg
        and window_range_pct_box <= settings.LPS_MAX_WINDOW_BOX_RANGE
        and shelf_low_pos <= settings.TRAVERSAL_LOW_ZONE
    )
    # Reaction-not-markup gate (live at LPS_RESCUE_MAX_ADVANCE_BOX =
    # 0.21). A genuine ascending-support coil is GRADUAL; reject a
    # rescued shelf that is really a steep markup leg whose low merely
    # launched from support (OHI-class). Re-anchors to a shorter
    # terminal test if one exists, else drops. None = disabled.
    if rising_support_shelf and settings.LPS_RESCUE_MAX_ADVANCE_BOX is not None:
        net_advance_box = (end_close - first_close) / box_height
        if net_advance_box > settings.LPS_RESCUE_MAX_ADVANCE_BOX:
            return "markup leg, not a shelf", False
    if not rising_support_shelf:
        return "does not rest on its low", False
    return "pass", True


def _depth_in_base_envelope(pullback_profile: float, min_pullback: float) -> bool:
    """Is the dig inside the BASE depth envelope? One judgment shared by both
    LPS completion forms (pullback-and-rest passes its zone-escalated floor,
    the holding shelf passes the plain floor). The chained comparison is the
    NaN route (NaN -> False) — keep the form; the MAX is read at call time so
    settings overrides propagate."""
    return min_pullback <= pullback_profile <= settings.LPS_PULLBACK_PROFILE_MAX


def _vol_dry_refused(avg_pullback_vol: float, vol_50_at_lps: float,
                     ceiling: float) -> bool:
    """Reject-on-True: the pullback's volume did NOT dry up against the Vol_50
    baseline at the given ceiling — ONE gate asked at two positions (the
    LPS_VOL_CONTRACTION_MAX ask, then the hard ceiling-1.0 ask after the
    post-window checks). Keep the reject-on-True direction: a NaN avg routes
    to False (pass) by design; the volume-baseline-invalid refusal upstream owns the
    broken-denominator case."""
    return avg_pullback_vol >= vol_50_at_lps * ceiling


def _pullback_rest_depth_ok(
    pullback_profile: float,
    zone_type: str,
    end_close: float,
    res_avg: float,
    box_height: float,
    length: int,
    support_low: float,
) -> tuple[bool, bool]:
    """Pullback-depth judgment: is the reaction deep enough for its zone?

    Returns ``(ok, buec_shelf)``. An OVERSHOOT_R window normally owes the
    stricter overshoot floor; the LPS-above-R / resistance-shelf exception accepts a
    longer shallow shelf holding just above R.
    """
    min_pullback = settings.LPS_PULLBACK_PROFILE_MIN
    buec_shelf = False
    if zone_type == "OVERSHOOT_R":
        close_extension_box = _box_position(end_close, res_avg, box_height)
        # LPS-above-R / resistance-shelf behavior: a longer shelf holding just
        # above R can be a valid shallow LPS. Keep the stricter overshoot
        # floor when price has already lifted away from R or when the
        # pullback is nearly a normal overshoot reaction.
        buec_shelf = (
            length >= 5
            and support_low >= res_avg
            and close_extension_box <= settings.LPS_INSIDE_HIGH_EXTENSION_BOX_MAX
            and pullback_profile <= (
                settings.LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R
                - 2 * settings.LPS_TERMINAL_LOW_TOL_PROFILE
            )
        )
        if not buec_shelf:
            min_pullback = settings.LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R
    ok = _depth_in_base_envelope(pullback_profile, min_pullback)
    return ok, buec_shelf


def _holding_shelf_verdict(
    length: int,
    low_descent_frac: float,
    support_low: float,
    sup_avg: float,
    box_height: float,
    pullback_profile: float,
) -> bool:
    """The holding-shelf completion form — the SECOND of the two sanctioned LPS
    shapes (Wyckoff: the back-up is "a simple pullback or a new TR at a higher
    level"; docs/lps_final_structure_canon_2026-07-10.md), judged on GEOMETRY
    ONLY. Consulted where the pullback-and-rest form rejects at its depth or
    volume-dry-up judgments; every machinery gate still binds.

    A shelf is a short flat-or-descending rest holding HIGH in the structure:
    monotone non-rising lows (the operator's "LPS = peak that goes down"; any
    rising low is the canon's wedging failure — the strictest reading, loosened
    only against future marked evidence), at least ``LPS_SHELF_LENGTH_MIN``
    bars, its low at/above the box midpoint (the canon position test: flat
    finals are sanctioned only high in the structure; flat-and-LOW is the named
    failure geometry), and a dig inside the BASE depth envelope — the overshoot
    escalation and the volume dry-up are the pullback form's judgments, not the
    shelf's. Monotone lows imply the terminal-rest verdict already passed, so
    this form never needs the rest seam.
    """
    if length < settings.LPS_SHELF_LENGTH_MIN:
        return False
    if low_descent_frac < 1.0:
        return False
    if _box_position(support_low, sup_avg, box_height) < settings.LPS_SHELF_MIN_LOW_POS_BOX:
        return False
    return _depth_in_base_envelope(pullback_profile, settings.LPS_PULLBACK_PROFILE_MIN)


def _public_candidate(candidate: dict, df: pd.DataFrame) -> dict:
    out = {k: v for k, v in candidate.items() if k != "_quality"}
    start = int(out["start_index"])
    end = int(out["end_index"])
    out["start_date"] = _date_at(df, start)
    out["end_date"] = _date_at(df, end - 1)
    if "lps_anchor_bar" in out:
        out["lps_anchor_date"] = _date_at(df, int(out["lps_anchor_bar"]))
    if "lps_low_bar" in out:
        out["lps_low_date"] = _date_at(df, int(out["lps_low_bar"]))
    return out


def detect_lps_candidates(
    df: pd.DataFrame,
    latest: pd.Series,
    sup_avg: float,
    res_avg: float,
    atr_val: float,
    base_range_threshold: float,
    base_len: int,
    swing_complete_idx: int,
    offset_max: Optional[int] = None,
    diagnose: bool = False,
    start_floor_bar: Optional[int] = None,
) -> tuple[list[dict], Counter]:
    """Collect every valid LPS/Test footprint before active-setup election.

    This is the detector layer only: it applies the LPS geometry/volume/spread
    gates and returns electable candidate dicts plus diagnostic reject counters.
    The candidate dicts keep ``_quality`` as the selector weight; consumers should
    use ``select_active_lps_candidate`` (or the compatibility wrapper
    ``detect_lps``) rather than scoring/archive this private field directly.

    ``start_floor_bar`` is the chronology floor the caller already resolved (the
    narrative passes the spring tip — cause before effect, Phase C -> Phase D).
    ``None`` = no floor, the measure-only default; the staircase
    (``detect_lps_tests``) keeps its own right-half rule and never passes one.
    """
    candidates: list[dict] = []
    rejects: Counter = Counter()
    n = len(df)
    scan_offset_max = settings.LPS_SCAN_OFFSET_MAX if offset_max is None else offset_max

    box_height = float(res_avg) - float(sup_avg)
    if box_height <= 0:
        if diagnose:
            rejects["box height invalid"] += 1
        return candidates, rejects

    profile_unit = _profile_unit(base_range_threshold, box_height)
    if profile_unit is None:
        if diagnose:
            rejects["profile unit invalid"] += 1
        return candidates, rejects

    # The zone gate is built on the ATR yardstick: a NaN ATR made zone_tol
    # NaN, both zone bounds NaN, and the hard zone gate then passed EVERY
    # low (NaN comparisons are False) — typing arbitrarily deep undercuts
    # as rebounds. Refuse loudly instead, mirroring the guards above.
    if not _finite(atr_val) or float(atr_val) <= 0:
        if diagnose:
            rejects["atr invalid"] += 1
        return candidates, rejects

    zone_tol = _zone_tolerance(sup_avg, res_avg, atr_val)
    r_ceiling = res_avg + zone_tol
    s_floor = sup_avg - zone_tol
    box_width = box_height / sup_avg if sup_avg > 0 else 1.0

    # LPS must land inside the base + reaction window. Without this guard,
    # raising scan depth could match an LPS that pre-dates the box entirely.
    max_window = base_len + settings.AR_MAX_BARS

    for offset in range(0, max(0, int(scan_offset_max))):
        end = n - offset
        eval_idx = end - 1

        # The LPS must sit after the swing that established both R and S.
        if eval_idx <= swing_complete_idx:
            if diagnose:
                rejects["before the R/S swing completed"] += 1
            continue

        for length in range(settings.LPS_LENGTH_MIN, settings.LPS_LENGTH_MAX + 1):
            start = end - length
            if start < 0:
                if diagnose:
                    rejects["window starts before the frame"] += 1
                continue
            # Cause before effect: the LAST point of support cannot predate the
            # spring that conducts the turn. Opening ON the floor bar is legal —
            # that is the sanctioned undercut_rebound form, the window resting on
            # the spring low itself.
            if start_floor_bar is not None and start < int(start_floor_bar):
                if diagnose:
                    rejects["window opens before the spring"] += 1
                continue
            if offset + length > max_window:
                if diagnose:
                    rejects["window overruns the base + reaction"] += 1
                continue

            pullback_period = df.iloc[start:end]
            first_lps = pullback_period.iloc[0]
            end_lps = pullback_period.iloc[-1]

            high_vals = pullback_period["High"].values.astype(float)
            low_vals = pullback_period["Low"].values.astype(float)
            spreads = _spread_series(pullback_period)

            first_high = float(first_lps["High"])
            last_low = float(end_lps["Low"])
            last_high = float(end_lps["High"])
            window_high = float(np.nanmax(high_vals))
            window_low = float(np.nanmin(low_vals))
            window_low_rel = int(np.nanargmin(low_vals))
            low_index = end - 1
            support_low = last_low
            trigger_price = last_high

            if first_high <= 0:
                if diagnose:
                    rejects["first high invalid"] += 1
                continue

            # A support test should be a reaction into support, not a rising
            # sequence that happens to contain one acceptable low.
            low_descent_frac = _pairwise_descent_fraction(low_vals)
            if low_descent_frac < settings.LPS_MIN_DESCENT_FRAC:
                if diagnose:
                    rejects["lows march up, not a reaction"] += 1
                continue

            high_descent_frac = _pairwise_descent_fraction(high_vals)
            if high_descent_frac < settings.LPS_MIN_HIGH_DESCENT_FRAC:
                if diagnose:
                    rejects["highs march up, not a reaction"] += 1
                continue

            terminal_low_tolerance = settings.LPS_TERMINAL_LOW_TOL_PROFILE * profile_unit
            window_range_pct_box = (window_high - window_low) / box_height
            low_verdict, rising_support_shelf = _pullback_rest_low_verdict(
                last_low,
                window_low,
                terminal_low_tolerance,
                length,
                window_range_pct_box,
                sup_avg,
                box_height,
                float(first_lps["Close"]),
                float(end_lps["Close"]),
            )
            if low_verdict != "pass":
                if diagnose:
                    rejects[low_verdict] += 1
                continue
            if rising_support_shelf:
                support_low = window_low
                low_index = start + window_low_rel

            # Zone gate: the elected LPS low must sit in one of the valid
            # support zones.
            if support_low < s_floor or support_low > r_ceiling:
                if diagnose:
                    rejects["low outside the support zones"] += 1
                continue
            if support_low < sup_avg:
                zone_type = "UNDERCUT_S"
            elif support_low > res_avg:
                zone_type = "OVERSHOOT_R"
            else:
                zone_type = "INSIDE"

            # Behavior gate: the candidate window should localize the support
            # test. If it spans most of the active box, it is a broad reaction
            # region, not a usable LPS footprint.
            clean_downswing = _clean_downswing(
                length,
                low_descent_frac,
                high_descent_frac,
                box_width,
            )
            # Rescope (LPS_OVERSHOOT_WINDOW_ATR_ENABLED, live 2026-07-16): a
            # breakout throwback resting ABOVE R is localized against the
            # stock's own daily ranges when the box is narrow — box height is
            # the wrong yardstick above the box. Gate-only: the archived
            # window_range_pct_box measure is unchanged. Non-finite ATR
            # refuses the rescoped path (falls back to the raw gate).
            # A throwback above R claims the cause below is COMPLETE, so the
            # rescope only engages on a MATURED cause (>= 2x MIN_BASE_DAYS —
            # the same floor a terminal shakeout needs in rail_qualification):
            # operator-ruled 2026-07-17 on BBVA ("just incomplete", 20-bar
            # minimum base, 2 traversals) vs CTOS (50-bar cause, 10
            # traversals, his own mark). Immature causes fall back to the raw
            # gate, which is the pre-flip path that already rejected them.
            window_gate_ratio = window_range_pct_box
            if (
                settings.LPS_OVERSHOOT_WINDOW_ATR_ENABLED
                and zone_type == "OVERSHOOT_R"
                and base_len >= 2 * settings.MIN_BASE_DAYS
                and atr_val is not None
                and np.isfinite(float(atr_val))
                and float(atr_val) > 0
            ):
                window_gate_ratio = (window_high - window_low) / max(
                    box_height,
                    settings.LPS_OVERSHOOT_WINDOW_ATR_MULT * float(atr_val),
                )
            if window_gate_ratio > settings.LPS_MAX_WINDOW_BOX_RANGE:
                # A clean pullback swing is allowed to cover more vertical range:
                # chart-wise it is one anchor high -> final low test, not broad
                # multi-direction chop occupying the whole box.
                if not clean_downswing:
                    if diagnose:
                        rejects["window spans the box"] += 1
                    continue

            # INSIDE means the low is back inside the old box. If the same
            # window first launched far above R, the chosen block is usually a
            # late pullback/off-structure reaction rather than LPS-above-R behavior.
            high_extension = max(0.0, window_high - res_avg)
            high_extension_box = high_extension / box_height
            high_extension_atr = (
                high_extension / float(atr_val)
                if atr_val is not None and float(atr_val) > 0
                else 0.0
            )
            if (
                zone_type == "INSIDE"
                and high_extension_box > settings.LPS_INSIDE_HIGH_EXTENSION_BOX_MAX
                and high_extension_atr > settings.LPS_INSIDE_HIGH_EXTENSION_ATR_MAX
            ):
                if diagnose:
                    rejects["window launched above resistance"] += 1
                continue

            pullback_profile = (first_high - support_low) / profile_unit
            depth_ok, buec_shelf = _pullback_rest_depth_ok(
                pullback_profile,
                zone_type,
                float(end_lps["Close"]),
                res_avg,
                box_height,
                length,
                support_low,
            )
            # Second completion form (flag-gated dark): judged once per window;
            # sanctions a window ONLY where the pullback form rejects below, so
            # a fully-passing pullback window keeps its pullback attribution.
            # When consulted-and-refused, the diagnose counters tag BOTH forms:
            # the pullback's keyed reason plus one flat-hold-form-refused tick.
            shelf_consulted = settings.LPS_HOLDING_SHELF_ENABLED
            holding_shelf = shelf_consulted and _holding_shelf_verdict(
                length, low_descent_frac, support_low, sup_avg,
                box_height, pullback_profile,
            )
            shelf_saved = False
            if not depth_ok:
                if not holding_shelf:
                    if diagnose:
                        rejects[f"pullback depth out of range ({pullback_profile:.2f})"] += 1
                        if shelf_consulted:
                            rejects["flat-hold form refused"] += 1
                    continue
                shelf_saved = True

            spread_max_allowed = profile_unit * settings.LPS_SPREAD_MAX_PROFILE_MULT
            max_spread = float(spreads.max())
            if max_spread > spread_max_allowed:
                if diagnose:
                    rejects["bar spread too wide"] += 1
                continue

            tight_spread = float(spreads.iloc[-1])
            spread_expansion = 0.0
            spread_decline_quality = 1.0
            if length >= 2:
                prev_spread = float(spreads.iloc[-2])
                spread_expansion = max(0.0, tight_spread - prev_spread)
                max_expansion = profile_unit * settings.LPS_SPREAD_EXPANSION_MAX_PROFILE
                if spread_expansion > max_expansion:
                    if diagnose:
                        rejects["final bar spread expands"] += 1
                    continue
                if settings.LPS_SPREAD_MUST_DECLINE:
                    spread_decline_quality = _spread_decline_quality(
                        tight_spread,
                        prev_spread,
                        profile_unit,
                    )

            vol_50_at_lps = float(df.iloc[eval_idx]["Vol_50"])
            # Non-finite refusal guard (threshold-move companion, 2026-07-17):
            # a NaN Vol_50 makes BOTH ratio comparisons below silently False —
            # the dry-up gate would "pass" on missing data and a NaN
            # vol_contraction would flow into quality/archive. Data-integrity
            # refusal: neither completion form may ride a broken denominator.
            if not np.isfinite(vol_50_at_lps) or vol_50_at_lps <= 0:
                if diagnose:
                    rejects["volume baseline invalid"] += 1
                continue
            avg_pullback_vol = pullback_period["Volume"].mean()
            if _vol_dry_refused(avg_pullback_vol, vol_50_at_lps,
                                settings.LPS_VOL_CONTRACTION_MAX):
                # The dry-up is the pullback form's judgment; the shelf form is
                # geometry-only (grades-not-vetoes: volume never gates it).
                if not holding_shelf:
                    if diagnose:
                        rejects["volume not drying up"] += 1
                        if shelf_consulted:
                            rejects["flat-hold form refused"] += 1
                    continue
                shelf_saved = True

            if latest["Close"] < (support_low * settings.LPS_HOLD_TOLERANCE):
                if diagnose:
                    rejects["support hold broken"] += 1
                continue

            # Bars after the LPS evaluation bar must hold above the elected LPS
            # low and stay profile-tight, or the "LPS" has become another down-leg.
            if offset > 0:
                post_lps = df.iloc[end:n]
                if post_lps["Low"].min() < support_low * settings.LPS_HOLD_TOLERANCE:
                    if diagnose:
                        rejects["low broken after the LPS"] += 1
                    continue
                if _spread_series(post_lps).max() > spread_max_allowed:
                    if diagnose:
                        rejects["spread widens after the LPS"] += 1
                    continue

            vol_contraction = (vol_50_at_lps - avg_pullback_vol) / vol_50_at_lps
            # Same gate at the hard ceiling: vol_contraction <= 0 is exactly
            # avg >= vol50 * 1.0 (vol50 > 0 is guaranteed by the refusal above).
            if _vol_dry_refused(avg_pullback_vol, vol_50_at_lps, 1.0):
                if not holding_shelf:
                    if diagnose:
                        rejects["pullback volume above baseline"] += 1
                        if shelf_consulted:
                            rejects["flat-hold form refused"] += 1
                    continue
                shelf_saved = True
            tightness_ratio = tight_spread / profile_unit
            if shelf_saved:
                # Volume-free quality: the shelf form never rewards or punishes
                # volume; only within-form qualities are ever compared (the
                # election ties break on the integer form rank first).
                quality = (
                    max(0.0, 1 - tightness_ratio)
                    * low_descent_frac
                    * high_descent_frac
                    * spread_decline_quality
                )
            else:
                quality = (
                    vol_contraction
                    * max(0.0, 1 - tightness_ratio)
                    * low_descent_frac
                    * high_descent_frac
                    * spread_decline_quality
                )

            setup_type = "REBOUND" if zone_type == "UNDERCUT_S" else "LPS"
            swing_depth = first_high - support_low
            candidates.append({
                "length": int(length),
                "offset": int(offset),
                "start_index": int(start),
                "end_index": int(end),
                "low_index": int(low_index),
                "lps_anchor_bar": int(start),
                "lps_low_bar": int(low_index),
                "low": support_low,
                "high": window_high,
                "trigger_price": trigger_price,
                "vol_contraction": float(vol_contraction),
                "tightness_ratio": float(tightness_ratio),
                "setup_type": setup_type,
                "zone_type": zone_type,
                "descent_frac": float(low_descent_frac),
                "high_descent_frac": float(high_descent_frac),
                "spread_decline_quality": float(spread_decline_quality),
                "window_range_pct_box": float(window_range_pct_box),
                "high_extension_box": float(high_extension_box),
                "high_extension_atr": float(high_extension_atr),
                "swing_type": _swing_type(
                    zone_type,
                    rising_support_shelf,
                    buec_shelf,
                    clean_downswing,
                    shelf_saved,
                ),
                "lps_swing_depth_pct": float(swing_depth / first_high),
                "lps_swing_depth_atr": (
                    float(swing_depth / float(atr_val))
                    if atr_val is not None and float(atr_val) > 0
                    else 0.0
                ),
                "lps_swing_depth_box": float(swing_depth / box_height),
                "profile_unit": float(profile_unit),
                "profile_unit_pct": float(profile_unit / first_high),
                "pullback_profile": float(pullback_profile),
                "terminal_low_tolerance": float(terminal_low_tolerance),
                "spread_expansion_profile": float(spread_expansion / profile_unit),
                "first_high": float(first_high),
                "last_low": float(last_low),
                "window_high": float(window_high),
                "window_low": float(window_low),
                "_quality": float(quality),
            })

    return candidates, rejects


def _form_rank(candidate: dict) -> int:
    """Cross-form election precedence: the established pullback-and-rest form
    outranks the holding shelf whenever the integer keys tie, so float quality
    is only ever compared WITHIN a form (deterministic cross-form election —
    causality contract §4). Flag-off every candidate ranks 1: the key ordering
    is byte-identical to the pre-shelf election."""
    return 0 if candidate.get("swing_type") == "holding_shelf" else 1


def select_active_lps_candidate(candidates: list[dict], latest: pd.Series) -> Optional[dict]:
    """Pick the latest actionable setup LPS from already-valid candidates."""
    try:
        current_price = float(latest["Close"])
    except (KeyError, TypeError, ValueError):
        return None

    actionable = [
        c for c in candidates
        if current_price < float(c["trigger_price"])
    ]
    if not actionable:
        return None

    best = max(
        actionable,
        key=lambda c: (
            int(c["end_index"]),
            int(c["low_index"]),
            _form_rank(c),
            int(c["length"]),
            float(c["_quality"]),
        ),
    )

    # If the elected slice is part of a single clean reaction into the same
    # terminal low, report the whole pullback instead of a shorter sub-slice.
    # Same-form only: widening must never flip the elected completion form.
    same_terminal_low = [
        c for c in actionable
        if c["low_index"] == best["low_index"]
        and c["end_index"] == best["end_index"]
        and _form_rank(c) == _form_rank(best)
    ]
    clean_reactions = [
        c for c in same_terminal_low
        if c["descent_frac"] == 1.0 and c["high_descent_frac"] == 1.0
    ]
    if clean_reactions:
        best = max(clean_reactions, key=lambda c: (int(c["length"]), float(c["_quality"])))
    return best


def detect_lps(
    df: pd.DataFrame,
    latest: pd.Series,
    sup_avg: float,
    res_avg: float,
    atr_val: float,
    base_range_threshold: float,
    base_len: int,
    swing_complete_idx: int,
    diagnose: bool = False,
    start_floor_bar: Optional[int] = None,
) -> Union[Optional[dict], tuple[Optional[dict], Counter]]:
    """Elect the single active setup LPS/Test.

    Public signature remains compatible. Internally this first collects every
    valid LPS/Test footprint, then elects the latest actionable terminal-low
    candidate. ``diagnose=True`` returns rejection counters for audit harnesses.
    ``start_floor_bar`` is the caller's chronology floor (see
    ``detect_lps_candidates``); ``None`` keeps the pre-floor election exactly.
    """
    candidates, rejects = detect_lps_candidates(
        df,
        latest,
        sup_avg,
        res_avg,
        atr_val,
        base_range_threshold,
        base_len,
        swing_complete_idx,
        diagnose=diagnose,
        start_floor_bar=start_floor_bar,
    )
    if not candidates:
        return (None, rejects) if diagnose else None

    best_candidate = select_active_lps_candidate(candidates, latest)
    if best_candidate is None:
        if diagnose:
            rejects["no actionable candidate"] += len(candidates)
        return (None, rejects) if diagnose else None

    best = _public_candidate(best_candidate, df)
    return (best, rejects) if diagnose else best


def detect_lps_tests(
    df: pd.DataFrame,
    latest: pd.Series,
    sup_avg: float,
    res_avg: float,
    atr_val: float,
    base_range_threshold: float,
    base_len: int,
    swing_complete_idx: int,
    max_tests: int = 8,
) -> list[dict]:
    """Enumerate non-overlapping support-test evidence across the base.

    Measure-only, and not a setup elector. It shares candidate geometry with
    ``detect_lps`` but selects differently on purpose: this keeps the visible
    support-test staircase, while ``detect_lps`` returns the one active setup
    LPS that owns the trigger.
    """
    max_window = base_len + settings.AR_MAX_BARS
    offset_max = max(0, max_window - settings.LPS_LENGTH_MIN + 1)
    candidates, _ = detect_lps_candidates(
        df,
        latest,
        sup_avg,
        res_avg,
        atr_val,
        base_range_threshold,
        base_len,
        swing_complete_idx,
        offset_max,
        diagnose=False,
    )
    if not candidates:
        return []

    selected = []
    used_spans: list[tuple[int, int]] = []
    for candidate in sorted(candidates, key=lambda c: c["_quality"], reverse=True):
        start = int(candidate["start_index"])
        end = int(candidate["end_index"])
        overlaps = any(start < used_end and end > used_start for used_start, used_end in used_spans)
        if overlaps:
            continue
        selected.append(candidate)
        used_spans.append((start, end))
        if len(selected) >= max_tests:
            break

    selected.sort(key=lambda c: c["start_index"])
    return [_public_candidate(candidate, df) for candidate in selected]


def lps_range_threshold(base_df: pd.DataFrame, atr_val: float) -> float:
    """The LPS window-sizing threshold: ``max(p-quantile spread, 1.2 * ATR)``.

    Folded out of the live (evaluation) + seed eval paths so the LPS footprint
    sizing can never silently diverge between them. Falls back to High-Low when
    the frame has no precomputed ``Spread`` column (via ``_spread_series``).
    """
    return max(
        float(_spread_series(base_df).quantile(settings.LPS_RANGE_PERCENTILE)),
        1.2 * float(atr_val),
    )
