"""Archive stats, health, calibration, and equity-curve endpoints."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from archive_models import SetupArchive
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE
from database import get_db
from services import scan_status
from domains.archive.queries import _canonical_setups

router = APIRouter(tags=["archive"])


def _safe_mean(vals: list[float]) -> float:
    return round(float(np.mean(vals)), 5) if vals else 0.0


def _safe_corr(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation, NaN-safe."""
    if len(xs) < 5 or len(ys) < 5:
        return 0.0
    xs_arr = np.array(xs)
    ys_arr = np.array(ys)
    mask = ~(np.isnan(xs_arr) | np.isnan(ys_arr))
    if mask.sum() < 5:
        return 0.0
    corr = float(np.corrcoef(xs_arr[mask], ys_arr[mask])[0, 1])
    # corrcoef returns NaN when either series has zero variance (e.g. a sub-score
    # that's constant across every archived setup). NaN isn't caught by the
    # downstream `x or 0.0` idiom (NaN is truthy), so it poisons the weight
    # normalization and turns every suggested weight into null. Neutralize here.
    return round(corr, 4) if not np.isnan(corr) else 0.0


@router.get("/stats")
def archive_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Aggregate statistics for the archive."""
    # Episode-collapsed (one row per logical setup) so a base's daily re-flags
    # don't inflate counts/win-rates — consistent with the /episodes table.
    setups = _canonical_setups(db)
    total = len(setups)
    with_returns = [s for s in setups if s.fwd_return_20d is not None]

    return {
        "total_setups": total,
        "with_forward_returns": len(with_returns),
        "by_tier": _count_by(setups, "tier"),
        "by_setup_type": _count_by(setups, "setup_type"),
        "by_source": _count_by(setups, "source"),
        "by_quality": _count_by(setups, "quality_label"),
        "date_range": {
            "earliest": min((s.scan_date for s in setups), default=None),
            "latest": max((s.scan_date for s in setups), default=None),
        },
    }


def _count_by(setups: list, field: str) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for s in setups:
        val = getattr(s, field, None) or "unknown"
        counts[val] += 1
    return dict(counts)


@router.get("/health")
def archive_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Read-only continuity summary for the live research loop.

    The point of this endpoint is not to certify trades; it tells the operator
    whether Chrollo's memory is clean enough to trust for engine calibration:
    live scans are arriving, forward returns are keeping up, and curated seed
    rows are not being mistaken for unbiased evidence.
    """
    # Scope raw rows to us_equities so the row-derived signals (latest_scan_date,
    # row counts) stay in the SAME universe as the episode-derived ones below
    # (_canonical_setups defaults to us_equities). Mixing scopes let the endpoint
    # report "scans arriving" off an ETF row while "no live sample" off the empty
    # equities episodes — a self-contradicting health verdict. Calibration is
    # equities-only, so equities is the right scope for the whole endpoint.
    all_rows = db.query(SetupArchive).filter(
        SetupArchive.universe_type == DEFAULT_UNIVERSE_TYPE
    ).all()
    all_episodes = _canonical_setups(db)
    live_episodes = _canonical_setups(db, source="screener")
    live_rows = [row for row in all_rows if (row.source or "screener") == "screener"]
    latest_scan_date = max((row.scan_date for row in live_rows if row.scan_date), default=None)
    latest_run = scan_status.latest_run()

    live_with_20d = [row for row in live_episodes if row.fwd_return_20d is not None]
    live_with_60d = [row for row in live_episodes if row.fwd_return_60d is not None]
    pending_20d = [
        row for row in live_episodes
        if row.fwd_return_20d is None and _days_since_date(row.scan_date) is not None
        and _days_since_date(row.scan_date) >= 28
    ]
    pending_60d = [
        row for row in live_episodes
        if row.fwd_return_60d is None and _days_since_date(row.scan_date) is not None
        and _days_since_date(row.scan_date) >= 70
    ]

    checks = [
        _scan_date_check(latest_scan_date),
        _scan_run_check(latest_run),
        _forward_returns_check(live_episodes, pending_20d, pending_60d),
        _live_sample_check(live_episodes, live_with_20d, live_with_60d),
        _source_mix_check(all_episodes, live_episodes),
    ]
    status = _overall_health_status(checks)

    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_scan_date": latest_scan_date,
        "latest_scan_age_days": _days_since_date(latest_scan_date),
        "latest_scan_run": latest_run,
        "archive": {
            "rows": len(all_rows),
            "episodes": len(all_episodes),
            "by_source": _count_by(all_episodes, "source"),
        },
        "live": {
            "rows": len(live_rows),
            "episodes": len(live_episodes),
            "with_20d_returns": len(live_with_20d),
            "with_60d_returns": len(live_with_60d),
            "pending_20d_returns": len(pending_20d),
            "pending_60d_returns": len(pending_60d),
            "date_range": {
                "earliest": min((row.scan_date for row in live_episodes), default=None),
                "latest": max((row.scan_date for row in live_episodes), default=None),
            },
        },
        "checks": checks,
    }


def _days_since_date(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return max(0, (datetime.now(timezone.utc).date() - parsed).days)


def _hours_since_iso(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - parsed).total_seconds() / 3600.0


def _health_check(key: str, label: str, status: str, detail: str) -> Dict[str, str]:
    return {"key": key, "label": label, "status": status, "detail": detail}


def _scan_date_check(latest_scan_date: Optional[str]) -> Dict[str, str]:
    age = _days_since_date(latest_scan_date)
    if age is None:
        return _health_check("live_scan", "Live archive", "critical", "No live screener rows archived yet.")
    if age <= 3:
        return _health_check("live_scan", "Live archive", "ok", f"Latest live setup date is {latest_scan_date}.")
    if age <= 7:
        return _health_check("live_scan", "Live archive", "watch", f"Latest live setup date is {latest_scan_date} ({age}d old).")
    return _health_check("live_scan", "Live archive", "critical", f"Latest live setup date is {latest_scan_date} ({age}d old).")


def _scan_run_check(latest_run: Optional[dict]) -> Dict[str, str]:
    if not latest_run:
        return _health_check("scan_run", "Scan runner", "critical", "No scan run history recorded.")
    status = latest_run.get("status") or "unknown"
    finished_at = latest_run.get("finished_at") or latest_run.get("started_at")
    age_hours = _hours_since_iso(finished_at)
    n_setups = latest_run.get("n_setups")
    suffix = f"{n_setups} setups" if n_setups is not None else "setup count unknown"
    if status in {"failed", "stale_data"}:
        detail = latest_run.get("error") or f"Latest run ended as {status}."
        return _health_check("scan_run", "Scan runner", "critical", detail)
    if status == "running":
        return _health_check("scan_run", "Scan runner", "watch", "A scan is currently running.")
    if age_hours is not None and age_hours > 84:
        return _health_check("scan_run", "Scan runner", "watch", f"Last run finished {age_hours:.0f}h ago with {suffix}.")
    return _health_check("scan_run", "Scan runner", "ok", f"Latest run status is {status}; {suffix}.")


def _forward_returns_check(live_episodes: list, pending_20d: list, pending_60d: list) -> Dict[str, str]:
    if not live_episodes:
        return _health_check("forward_returns", "Forward returns", "watch", "No live episodes are available to mature yet.")
    if pending_20d or pending_60d:
        parts = []
        if pending_20d:
            parts.append(f"{len(pending_20d)} overdue 20d")
        if pending_60d:
            parts.append(f"{len(pending_60d)} overdue 60d")
        return _health_check("forward_returns", "Forward returns", "watch", ", ".join(parts) + ".")
    return _health_check("forward_returns", "Forward returns", "ok", "No mature live episodes are waiting on return backfill.")


def _live_sample_check(live_episodes: list, live_with_20d: list, live_with_60d: list) -> Dict[str, str]:
    n_live = len(live_episodes)
    n_20d = len(live_with_20d)
    n_60d = len(live_with_60d)
    if n_live < 30:
        return _health_check("live_sample", "Live sample", "watch", f"{n_live} live episodes; still early for calibration.")
    if n_20d < 30:
        return _health_check("live_sample", "Live sample", "watch", f"{n_20d} live episodes have 20d outcomes.")
    return _health_check("live_sample", "Live sample", "ok", f"{n_live} live episodes; {n_20d} with 20d and {n_60d} with 60d outcomes.")


def _source_mix_check(all_episodes: list, live_episodes: list) -> Dict[str, str]:
    if not all_episodes:
        return _health_check("source_mix", "Evidence mix", "watch", "Archive is empty.")
    live_share = len(live_episodes) / len(all_episodes)
    if live_share >= 0.50:
        return _health_check("source_mix", "Evidence mix", "ok", f"Live screener episodes are {live_share:.0%} of the archive.")
    return _health_check("source_mix", "Evidence mix", "watch", f"Live screener episodes are only {live_share:.0%}; curated rows may dominate analysis.")


def _overall_health_status(checks: list[dict]) -> str:
    statuses = {check["status"] for check in checks}
    if "critical" in statuses:
        return "critical"
    if "watch" in statuses:
        return "watch"
    return "ok"


@router.get("/calibration")
def calibration_data(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Calibration analytics — the engine for refining the screener.

    Returns tier performance, sub-score correlations with forward returns,
    and setup type breakdown.
    """
    # Episode-collapsed so continuation re-flags don't inflate tier win-rates /
    # expectancy — the same de-dup the /episodes table applies.
    setups = _canonical_setups(db)
    with_returns = [s for s in setups if s.fwd_return_20d is not None]

    # ── Tier Performance ─────────────────────────────────────
    tier_perf: Dict[str, Dict[str, Any]] = {}
    tier_groups: Dict[str, list] = defaultdict(list)
    for s in with_returns:
        tier_groups[s.tier].append(s)

    for tier, group in sorted(tier_groups.items()):
        returns = [s.fwd_return_20d for s in group if s.fwd_return_20d is not None]
        triggered = [s for s in group if s.triggered == 1]
        mfes = [s.mfe_20d for s in group if s.mfe_20d is not None]
        maes = [s.mae_20d for s in group if s.mae_20d is not None]
        r_mults = [s.r_multiple_20d for s in group if s.r_multiple_20d is not None]

        # Expectancy in R-multiples — single number that says
        # "this tier makes/loses N R per setup on average". The headline metric.
        wins = [r for r in r_mults if r > 0]
        losses = [r for r in r_mults if r <= 0]
        wr = (len(wins) / len(r_mults)) if r_mults else 0
        avg_win = float(np.mean(wins)) if wins else 0.0
        avg_loss = float(np.mean(losses)) if losses else 0.0   # negative
        expectancy_r = round(wr * avg_win + (1 - wr) * avg_loss, 3) if r_mults else None

        tier_perf[tier] = {
            "count": len(group),
            "avg_fwd_20d": _safe_mean(returns),
            "win_rate": round(len([r for r in returns if r > 0]) / max(len(returns), 1), 3),
            "trigger_rate": round(len(triggered) / max(len(group), 1), 3),
            "avg_mfe_20d": _safe_mean(mfes),
            "avg_mae_20d": _safe_mean(maes),
            "avg_score": _safe_mean([s.score for s in group]),
            "avg_r_multiple_20d": round(float(np.mean(r_mults)), 3) if r_mults else None,
            "expectancy_r": expectancy_r,
            "r_sample_size": len(r_mults),
            # Epoch honesty (task 14): stored tier/score mean different things
            # across an engine_config_version seam — post-flip this counts >1
            # and the tier card badges the blend instead of hiding it.
            "epochs": len({s.engine_config_version or "?" for s in group}),
        }

    # ── Sub-Score Correlations (20d + 60d) ──────────────────
    # Two horizons are reported side-by-side: 20d ≈ swing-exit window,
    # 60d ≈ position-exit window. A sub-score that predicts well at one
    # horizon but not the other is useful information for re-weighting —
    # if base_age correlates strongly at 60d but weakly at 20d, that's a
    # "long-hold edge" signal, not a swing edge.
    sub_score_fields = [
        "score_box_tightness", "score_touch_density",
        "score_atr_squeeze", "score_lps_tightness", "score_vol_contraction",
        "score_base_age",
    ]
    with_60d = [s for s in with_returns if s.fwd_return_60d is not None]
    fwd_20d_vals = [s.fwd_return_20d for s in with_returns]
    fwd_60d_vals = [s.fwd_return_60d for s in with_60d]

    sub_score_corr_20d: Dict[str, float] = {}
    sub_score_corr_60d: Dict[str, float] = {}
    for field in sub_score_fields:
        short_name = field.replace("score_", "")
        vals_20 = [getattr(s, field) or 0.0 for s in with_returns]
        vals_60 = [getattr(s, field) or 0.0 for s in with_60d]
        sub_score_corr_20d[short_name] = _safe_corr(vals_20, fwd_20d_vals)
        sub_score_corr_60d[short_name] = _safe_corr(vals_60, fwd_60d_vals)

    # ── Suggested Re-weighting ──────────────────────────────
    # Average |corr| across 20d and 60d horizons → re-normalize to preserve
    # the current total of the six caps (derived live from settings - never
    # a hand-typed number; the old "128 pts" claim had drifted from a real 117).
    # Sub-scores with negative or near-zero correlation get floored at a
    # small positive (0.02) so they're not zeroed out by a single noisy
    # archive — re-weighting is a *suggestion*, not auto-apply.
    #
    # Read the caps fresh from the root config/ files, isolated from the backend's
    # sys.path (the one loader the scheduler and scan alerts use too).
    from app.core_settings import load_core_settings
    _cfg = load_core_settings()
    current_weights = {
        "box_tightness":   _cfg.SCORE_BOX_TIGHTNESS,
        "touch_density":   _cfg.SCORE_TOUCH_DENSITY,
        "atr_squeeze":     _cfg.SCORE_ATR_SQUEEZE,
        "lps_tightness":   _cfg.SCORE_LPS_TIGHTNESS,
        "vol_contraction": _cfg.SCORE_VOL_CONTRACTION,
        "base_age":        _cfg.SCORE_BASE_AGE,
    }
    # The suggested-weights math + its adequacy gate live in
    # core.archive.analyze.suggested_weights. This router is its ONLY caller: the
    # CLI analysis flags candidate sub-scores but does not re-weight. It applies
    # the signal-edge adequacy + minority-class guard (verdicts_trustworthy) —
    # stronger than the old inline `n >= 30` check — and returns an EMPTY table on
    # a winners-only / too-thin sample rather than fitting noise. Advisory display
    # only: it never applies a weight.
    #
    # Imported lazily (like the settings load above) to keep the config-shadow
    # concern local to this handler and off the backend's import path.
    import pandas as pd

    from core.archive.analyze import suggested_weights
    _gate_df = pd.DataFrame(
        [{c.name: getattr(s, c.name) for c in SetupArchive.__table__.columns}
         for s in with_returns]
    )
    _suggestion = suggested_weights(
        _gate_df, sub_score_corr_20d, sub_score_corr_60d, current_weights)
    weights_table: List[Dict[str, Any]] = _suggestion["weights"]
    weights_basis = _suggestion["basis"]

    # Also correlate structural metrics (20d only — diagnostic, not re-weight input).
    structural_corr = {}
    for field in ["box_width", "base_length", "touches", "atr_ratio", "vol_contraction"]:
        vals = [float(getattr(s, field) or 0) for s in with_returns]
        structural_corr[f"{field}_vs_fwd20d"] = _safe_corr(vals, fwd_20d_vals)

    # ── Setup Type Breakdown ─────────────────────────────────
    type_groups: Dict[str, list] = defaultdict(list)
    for s in with_returns:
        type_groups[s.setup_type].append(s)

    type_breakdown = {}
    for stype, group in sorted(type_groups.items()):
        returns = [s.fwd_return_20d for s in group if s.fwd_return_20d is not None]
        type_breakdown[stype] = {
            "count": len(group),
            "avg_fwd_20d": _safe_mean(returns),
            "win_rate": round(len([r for r in returns if r > 0]) / max(len(returns), 1), 3),
        }

    # ── Market Context Analysis ──────────────────────────────
    spy_groups: Dict[str, list] = defaultdict(list)
    for s in with_returns:
        trend = s.spy_trend or "UNKNOWN"
        spy_groups[trend].append(s)

    market_context = {}
    for trend, group in spy_groups.items():
        returns = [s.fwd_return_20d for s in group if s.fwd_return_20d is not None]
        market_context[trend] = {
            "count": len(group),
            "avg_fwd_20d": _safe_mean(returns),
            "win_rate": round(len([r for r in returns if r > 0]) / max(len(returns), 1), 3),
        }

    return {
        "total_with_returns": len(with_returns),
        "total_with_60d_returns": len(with_60d),
        "tier_performance": tier_perf,
        "sub_score_correlations_20d": sub_score_corr_20d,
        "sub_score_correlations_60d": sub_score_corr_60d,
        "suggested_weights": weights_table,
        "weights_basis": weights_basis,
        "structural_correlations": structural_corr,
        "setup_type_breakdown": type_breakdown,
        "market_context": market_context,
    }


@router.get("/calibration/equity-curve")
def equity_curve(
    tier: Optional[str] = Query(None, description="Filter by tier; default = ALL triggered setups"),
    label: Optional[str] = Query(None, description="Filter by quality_label"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Cumulative R-multiple curve over time — 'if I'd taken every triggered
    setup matching the filter, here's the running P&L in R'.

    Sorted by trigger_date so the curve reflects realistic chronological
    deployment of capital.
    """
    # Episode-collapsed so a persisting base contributes one entry to the curve,
    # not one per day it re-flagged.
    setups = [
        s for s in _canonical_setups(db, tier=tier, quality_label=label)
        if s.triggered == 1 and s.r_multiple_20d is not None
    ]
    if not setups:
        return {"points": [], "summary": {}}

    setups.sort(key=lambda s: s.trigger_date or s.scan_date or "")

    points = []
    cum = 0.0
    for s in setups:
        cum += float(s.r_multiple_20d)
        points.append({
            "date": s.trigger_date or s.scan_date,
            "ticker": s.ticker,
            "tier": s.tier,
            "r": round(float(s.r_multiple_20d), 3),
            "cum_r": round(cum, 3),
        })

    rs = [float(s.r_multiple_20d) for s in setups]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]

    return {
        "points": points,
        "summary": {
            "total_setups": len(setups),
            "total_r": round(cum, 2),
            "win_rate": round(len(wins) / len(rs), 3) if rs else 0,
            "avg_r": round(float(np.mean(rs)), 3) if rs else 0,
            "best_r": round(float(np.max(rs)), 3) if rs else 0,
            "worst_r": round(float(np.min(rs)), 3) if rs else 0,
            "max_drawdown_r": round(_max_drawdown_r(points), 3),
        },
    }


def _max_drawdown_r(points: List[dict]) -> float:
    """Peak-to-trough drawdown of cum_r in R units."""
    if not points:
        return 0.0
    peak = points[0]["cum_r"]
    max_dd = 0.0
    for p in points:
        peak = max(peak, p["cum_r"])
        dd = peak - p["cum_r"]
        if dd > max_dd:
            max_dd = dd
    return float(max_dd)


# ── Manual Actions ───────────────────────────────────────────────
