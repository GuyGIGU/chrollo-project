"""Frozen-config manifest — the hashable identity of the engine's constants.

The engine's computed output is a pure function of (market data, engine
constants, detector code). This module canonicalises the *constants* half: an
EXPLICIT allow-list of every value in ``config.settings`` that can move a
detector decision (which setups fire, how they score/rank, where the phase
boundaries land), gathered into a sorted dict whose sha256 is the engine config
version. An archived signal stamped with that hash can later be traced to the
exact config that produced it, and a freeze + backtest can assert the config
hasn't silently drifted.

Design rules (deliberate, audited):

  * The allow-list is HAND-CURATED, not a ``dir(settings)`` sweep. That is the
    whole point: it draws the line between "engine identity" (in) and "ops
    noise" (out — data source, cache, fetch tuning, rate-limit, quarantine,
    scheduler, dashboard, regime observability, ARCHIVE_LIVE_SCANS) so that an
    ops tweak never churns the engine version, and so the contract is auditable.
  * Settings are read LAZILY inside the function (import in-body), never at
    module import. The backend runs with cwd=webapp/backend which shadows the
    repo-root ``config`` package; a module-level import would risk binding the
    wrong module at import time. (See project_config_collision.)
  * A listed key that has VANISHED from settings raises ``KeyError`` — the
    contract cannot silently rot when a constant is renamed/removed. New
    settings are simply absent from the manifest until added to the allow-list
    on purpose.

Pure, read-only. No engine math, no I/O beyond the CLI's stdout.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

# ─────────────────────────────────────────────────────────────────────────────
# ENGINE-RELEVANT CONSTANTS (the manifest allow-list).
#
# Every name here is a setting that can change a detector decision. Grouped to
# mirror config/settings.py sections for auditability. To add a constant to the
# frozen contract, add its name here (and accept the new hash + re-baseline).
# ─────────────────────────────────────────────────────────────────────────────
ENGINE_SETTINGS_KEYS: tuple[str, ...] = (
    # Phase 0 — price-series regime (every read's provenance)
    "DATA_DIVIDEND_ADJUSTED",
    # Phase 1 — universe baseline filters
    "MIN_PRICE",
    "MIN_VOLUME_50D",
    "MIN_YEARLY_RETURN",
    # Phase 2 — consolidation base parameters
    "MIN_BASE_DAYS",
    "MAX_BOX_WIDTH",
    "CRASH_FILTER_MULT",
    "EXTENSION_FILTER_MULT",
    "PIVOT_ORDER_SHORT",
    "PIVOT_ORDER_LONG",
    "PIVOT_ORDER_THRESHOLD",
    "PIP_MACRO_K_MAX",
    "PIP_MACRO_MAX_POST_EXCESS",
    "PIP_MACRO_MIN_BASE_BARS",
    "PIP_MACRO_EQ_FLOOR_FRAC",
    "PIP_MACRO_EQ_OSC_FRAC",
    # Climax terminality on the calibrated resolve_phase_a paths (2026-07-19 —
    # a mid-trend pause may not paint as the climax; re-anchors the Phase-A
    # overlay + bin_a/bars_since_BC/descent_length diagnostics, never a rail)
    "PHASE_A_CLIMAX_TERMINALITY_EXCESS",
    # First-reaction AR anchor (Phase-A overlay; default-off flip must bump the
    # version from day one — a flip re-anchors the drawn AR on 19/140 fires)
    "AR_FIRST_REACTION_ENABLED",
    "AR_RETRACE_FRAC",
    "AR_UP_LEG_LOOKBACK",
    "AR_BOUNCE_ATR_MULT",
    "AR_BOUNCE_DROP_FRAC",
    # Cause-before-effect election precondition (2026-07-20 — a box may not be
    # elected over a live trend that never matured a cause; the MIDD class).
    # Default-off; listed BEFORE any read so the flip bumps engine_config_version
    # from day one (a name that starts abstaining stops archiving its rows).
    "CAUSE_BEFORE_EFFECT_VETO_ENABLED",
    # Third leg of that veto (loose-LPS-shelf threshold); read on the eval path
    # by cause_maturity, so it must bump engine_config_version like any weight.
    "CAUSE_LPS_LOOSE_MAX",
    # Dynamic recursive S/R scanning (Phase B)
    "BOUNDARY_ATR_BUFFER",
    "MAX_CONSECUTIVE_OUTSIDE_DAYS",
    "MIN_BOUNDARY_RESPECT_PCT",
    "TOUCH_TOLERANCE_ATR",
    # Worked-equilibrium validity (Phase B)
    "EQ_MIN_TOUCHES_PER_RAIL",
    "EQ_MIN_TOUCH_THIRDS",
    "EQ_MIN_HALF_DWELL",
    "EQ_MAX_MID_DWELL",
    "EQ_MIN_COVERAGE",
    "EQ_COVERAGE_BINS",
    "EQ_COVERAGE_MIN_FRAC",
    # Limb-traversal read (Phase B)
    "TRAVERSAL_NOISE_FRAC",
    "TRAVERSAL_FULL_FRAC",
    "TRAVERSAL_LOW_ZONE",
    "TRAVERSAL_HIGH_ZONE",
    "TRAVERSAL_MIN",
    "TRAVERSAL_MIN_DENSITY",
    # Descent-tail gate
    "DESCENT_TAIL_LSF_MAX",
    "DESCENT_TAIL_CFP_MIN",
    # SOS breakout trim
    "SOS_TRIM_MIN_RUN",
    "SOS_TRIM_MIN_PREFIX_FRAC",
    # Box-start shared-rail back-extension (Phase B)
    # SOS event detection (box_events.read_box_events -> puzzle completeness)
    "SOS_NEAR_R_MAX_BOX",
    "SOS_HOLD_MAX_RANGE_BOX",
    # Markup-leg qualification (Phase A)
    "TREND_MIN_GAIN_PCT",
    "TREND_MIN_MOVE_BARS",
    "TREND_PRIOR_LOOKBACK",
    "LOCAL_PEAK_BARS",
    "ROOT_TREND_SMA",
    "PHASE_B_ATR_WINDOW",
    "AR_MIN_DROP_PCT",
    "AR_MAX_BARS",
    # Phase 3 — LPS & breakout detection
    "LPS_MIN_DESCENT_FRAC",
    "LPS_MIN_HIGH_DESCENT_FRAC",
    "LPS_MAX_WINDOW_BOX_RANGE",
    "LPS_OVERSHOOT_WINDOW_ATR_ENABLED",
    "LPS_OVERSHOOT_WINDOW_ATR_MULT",
    "LPS_RESCUE_MAX_ADVANCE_BOX",
    "LPS_INSIDE_HIGH_EXTENSION_BOX_MAX",
    "LPS_INSIDE_HIGH_EXTENSION_ATR_MAX",
    "LPS_SCAN_OFFSET_MAX",
    "LPS_LENGTH_MIN",
    "LPS_LENGTH_MAX",
    "LPS_HOLD_TOLERANCE",
    "LPS_PROFILE_BOX_FRACTION_FLOOR",
    "LPS_PULLBACK_PROFILE_MIN",
    "LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R",
    "LPS_PULLBACK_PROFILE_MAX",
    "LPS_TERMINAL_LOW_TOL_PROFILE",
    "LPS_SPREAD_MAX_PROFILE_MULT",
    "LPS_SPREAD_EXPANSION_MAX_PROFILE",
    # Holding-shelf completion form (Event Map Task 8, flag-gated dark)
    "LPS_HOLDING_SHELF_ENABLED",
    "LPS_SHELF_LENGTH_MIN",
    "LPS_SHELF_MIN_LOW_POS_BOX",
    # Deep-excursion pair events (Event Map Task 11, dark)
    "BAND_RAILS_ENABLED",
    "BAND_MAX_BOX_WIDTH",
    "BAND_EVENT_MIN_BARS",
    "BAND_EVENT_MAX_DEPTH_ATR",
    "BAND_EVENT_MAX_BARS",
    # Election surgery (solve-the-engine task 13, dark)
    "ELECTION_DETHRONE_ENABLED",
    "ELECTION_DETHRONE_SESSIONS",
    "LPS_DRAW_MIN_DESCENT_FRAC",
    "LPS_ZONE_ATR_MULT",
    # Phase-C bin measurement
    "BIN_C_UNDERCUT_ATR_MIN",
    "BIN_C_UNDERCUT_ATR_MAX",
    "BIN_C_UNDERCUT_BOX_MAX",
    "BIN_C_RECOVERY_BARS_MAX",
    "BIN_C_LINGER_BARS_MAX",
    "BIN_C_HOLD_BARS",
    "BIN_C_HOLD_TOL_ATR",
    "BIN_C_SIGNIF_UNDERCUT_ATR",
    "BIN_C_MIN_LINGER_BARS",
    "BIN_C_LATE_BOX_FRACTION",
    # Phase B->D divider (V-tip)
    "PHASE_D_VTIP_LATE_FRACTION",
    "PHASE_D_VTIP_RECOVERY_BARS",
    # Spread rules
    "LPS_RANGE_PERCENTILE",
    "LPS_SPREAD_MUST_DECLINE",
    "LPS_VOL_CONTRACTION_MAX",
    # Shared structural-frame constants
    "STRUCTURE_EDGE_SKIP_BARS",
    "STRUCTURE_ATR_SAMPLE_OFFSET",
    "INNER_SEARCH_FRACTION",
    "INNER_TIGHTNESS_RATIO",
    "INNER_MIN_DAYS",
    # Phase 4 — scoring & ranking: tiers
    "TIER_S",
    "TIER_A",
    "TIER_B",
    "TIER_C",
    "S_MAX_BOX_WIDTH",
    # Scoring component caps + calibration
    "SCORE_BASE_AGE",
    "BASE_AGE_CAP_DAYS",
    "BASE_AGE_DEADSPACE_WIDTH",
    "SCORE_TOUCH_DENSITY",
    "SCORE_VOL_CONTRACTION",
    "SCORE_LPS_TIGHTNESS",
    "SCORE_BOX_TIGHTNESS",
    "SCORE_ATR_SQUEEZE",
    "TIGHTNESS_ADR_AWARE",
    "MAX_BOX_WIDTH_ADR",
    # Candle-spread readability grade (box_tightness multiplier, flag-gated)
    "CANDLE_GRADE_FLOOR",
    "CANDLE_SPREAD_BOX_CLEAN",
    "CANDLE_SPREAD_BOX_MESSY",
    "CANDLE_SPREAD_ATR_CLEAN",
    "CANDLE_SPREAD_ATR_MESSY",
    "CANDLE_TIGHTBAR_CLEAN",
    "CANDLE_TIGHTBAR_MESSY",
    # Technical Analysis Score v2 master flag (specs/ta-score-rework.md).
    # Listed BEFORE the scorer reads it: it is a committed engine flag whose
    # flip must bump engine_config_version from day one — the completeness scan
    # only forces names once a read lands, which would have left a window where
    # flipping it changed output without rotating the hash.
    "TA_SCORE_V2",
    # Lane-C advisory/enrichment flags + tuning knobs (deferred to engine-β;
    # default-off + byte-identical off, read via _flag()/getattr on the advisory
    # path). Pre-registered like TA_SCORE_V2 so the β consumption wave that wires
    # them into score/archive rotates engine_config_version from day one — and so a
    # lookback/lag tweak that changes an archived advisory value cannot slip the
    # hash. The tuning knobs are read one import-hop out (rs_line / sector_ranking /
    # metrics), now covered by the manifest-completeness scan. (SECTOR_RANKING_ETFS
    # is the ranked symbol SET, ops-excluded like INDEX_SYMBOLS — see below.)
    "FUNDAMENTALS_ENABLED",
    "FUNDAMENTALS_EARNINGS_HISTORY_LIMIT",
    "FUNDAMENTALS_FILING_LAG_DAYS",
    "RS_LINE_ENABLED",
    "RS_LINE_NEW_HIGH_LOOKBACK",
    "SECTOR_RANKING_ENABLED",
    "SECTOR_RANKING_LOOKBACKS",
    "RS_RATING_LOOKBACK",
    # E3 puzzle-quality graded sub-score (additive bonus term, flag-gated)
    "SCORE_PUZZLE_QUALITY",
    "PUZZLE_W_COMPLETENESS",
    "PUZZLE_W_CHRONOLOGY",
    "PUZZLE_CHRONO_PARTIAL",
    # Event Map fire-path staging (measure-only diagnostics, flag-gated dark)
    "EVENT_MAP_ENABLED",
    # Election stability probe (measure-only diagnostics, flag-gated dark)
    "ELECTION_STABILITY_ENABLED",
    "ELECTION_STABILITY_LOOKBACK",
    "SCORE_TRAVERSAL_QUALITY",
    "TRAVERSAL_QUALITY_DENSITY_FULL",
    "TRAVERSAL_QUALITY_DWELL_PENALTY",
    "MIN_STRONG_YEARLY_RETURN",
    "MAX_STRONG_YEARLY_RETURN",
    "SCORE_UPTREND_BONUS",
    "SCORE_RS_BONUS",
    "RS_LOOKBACK_BARS",
    "RS_MAX_EXCESS_RETURN",
    "SCORE_52W_HIGH_PROXIMITY",
    "HIGH_PROXIMITY_FULL_PCT",
    "HIGH_PROXIMITY_ZERO_PCT",
    "SCORE_BREADTH_BONUS",
    "BREADTH_FULL_PCT",
    "BREADTH_ZERO_PCT",
    "SCORE_CONTRACTION",
    "CONTRACTION_IDEAL_MIN",
    "CONTRACTION_IDEAL_MAX",
    "CONTRACTION_FINAL_TIGHT_PCT",
    "CONTRACTION_FINAL_LOOSE_PCT",
    "SCORE_ASCENDING_SUPPORT",
    "ASCENDING_SUPPORT_FULL_SLOPE",
    "ADR_WINDOW",
    "SCORE_ADR",
    "ADR_FULL_PCT",
    "TOUCH_BONUS_INDIVIDUAL",
    "TOUCH_BONUS_TOTAL",
    "TOUCH_BONUS_POINTS",
    # HTF structure context (same engine on resampled bars)
    "HTF_CONTEXT_ENABLED",
    "DAILY_STRUCTURE_PERIOD",
    "HTF_STAGE_MA",
    "HTF_STAGE_MA_SLOPE_BARS",
    "HTF_WEEKLY_WINDOWS",
    "HTF_MONTHLY_WINDOWS",
)

# ─────────────────────────────────────────────────────────────────────────────
# DELIBERATELY EXCLUDED (ops / observability knobs).
#
# Documented for auditability only — NOT used by collect_manifest. These move
# how data is fetched/cached/scheduled or are pure observability, never a
# detector decision. Changing one must NOT churn the engine version.
#   data source / cache:  MARKET_DATA_PROVIDER, CACHE_FILENAME, PARQUET_*,
#                         DOWNLOAD_PERIOD, TICKER_* admission/skiplist, ...
#   archiving:            ARCHIVE_LIVE_SCANS
#   fetch tuning:         TTL_*, FULL_REFRESH_*, INCREMENTAL_*, *_REPAIR_*,
#                         MARKET_DATA_MIN_LATEST_COVERAGE, SPLIT_PROBE_*
#   rate limit / quarantine:  YAHOO_RATE_LIMIT_*, YAHOO_DOWNLOAD_WORKERS,
#                         QUARANTINE_*
#   market-context fetch: SPY_SYMBOL, INDEX_SYMBOLS, SECTOR_RANKING_ETFS,
#                         MARKET_CONTEXT_TTL_*
#   regime observability: REGIME_* (state is observability-only, not a gate)
#   dashboard:            DASHBOARD_*
#   scheduler / alerts:   SCAN_SCHEDULE_*, FORWARD_RETURNS_MIN_AGE_DAYS,
#                         ALERT_*
# ─────────────────────────────────────────────────────────────────────────────


def _canonical(value: Any) -> Any:
    """Coerce a settings value into a JSON-canonical form.

    Tuples/lists -> list; dicts -> dict with sorted keys is handled by
    json.dumps(sort_keys=True), so we only need to make containers JSON-native.
    Scalars (int/float/bool/str/None) pass through unchanged.
    """
    if isinstance(value, tuple):
        return [_canonical(v) for v in value]
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    return value


def collect_manifest() -> Dict[str, Any]:
    """Return the canonical engine-config manifest (a plain dict).

    Reads ``config.settings`` lazily and pulls exactly ``ENGINE_SETTINGS_KEYS``.
    Raises ``KeyError`` if any listed key is missing from settings — the frozen
    contract must not silently rot when a constant is renamed or removed.
    """
    from config import settings

    manifest: Dict[str, Any] = {}
    missing: list[str] = []
    for key in ENGINE_SETTINGS_KEYS:
        if not hasattr(settings, key):
            missing.append(key)
            continue
        manifest[key] = _canonical(getattr(settings, key))
    if missing:
        raise KeyError(
            "frozen-config manifest references settings that no longer exist: "
            + ", ".join(sorted(missing))
            + " — update core/freeze/manifest.ENGINE_SETTINGS_KEYS deliberately "
            "(a rename/removal changes the engine contract)."
        )
    return manifest


def manifest_json() -> str:
    """Canonical JSON serialization of the manifest (sorted keys, stable)."""
    return json.dumps(collect_manifest(), sort_keys=True, separators=(",", ":"))


def manifest_hash() -> str:
    """sha256 hex digest of the canonical manifest — the engine config version."""
    return hashlib.sha256(manifest_json().encode("utf-8")).hexdigest()


def _main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m engine_alpha.freeze.manifest",
        description="Print the frozen engine-config manifest or its hash.",
    )
    parser.add_argument(
        "--hash",
        action="store_true",
        help="print only the sha256 manifest hash (the engine config version)",
    )
    args = parser.parse_args(argv)

    if args.hash:
        print(manifest_hash())
    else:
        print(json.dumps(collect_manifest(), sort_keys=True, indent=2))
        print(f"\n# engine_config_version (sha256): {manifest_hash()}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_main(sys.argv[1:]))
