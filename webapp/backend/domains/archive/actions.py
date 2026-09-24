"""Archive manual-add, analysis, and forward-return action endpoints."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from archive_models import SetupArchive
from database import get_db
from domains.archive.schemas import ManualSetupIn, SetupOut
from app.dependencies import require_same_app
from domains.archive.queries import archive_row_from_result
from services.scan_runner import scan_lock

router = APIRouter(tags=["archive"])

# Three levels up from routers/ reaches the project root, where core/ lives.
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


@router.post("/add-setup", response_model=SetupOut)
def add_setup_manually(payload: ManualSetupIn, db: Session = Depends(get_db)):
    """Manually add a setup to the archive.

    Downloads OHLC for the ticker, slices the DataFrame at ``scan_date`` (or
    today), runs the full screener pipeline at that date, and writes the
    resulting row with ``source="manual"``. Forward returns are computed
    immediately from the bars after ``scan_date`` (if any exist yet).

    Raises 422 if the screener doesn't fire on the given date — we want the
    structural fingerprint, so we won't store a "setup" the engine rejected.
    """
    import sys as _sys
    import os as _os
    import pandas as _pd

    # Make project root importable so we can use core/ modules.
    _root = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", "..", "..", ".."))
    if _root not in _sys.path:
        _sys.path.insert(0, _root)

    from core.archive.seed import SEED_HISTORY_DAYS, _evaluate_at_date
    from core.archive.forward_returns import FORWARD_RETURN_DOWNLOAD_DAYS, _compute_returns
    from core.pipeline.market_data.downloads import _batched_download, price_auto_adjust
    from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE
    from engine_alpha.freeze.manifest import manifest_hash
    from engine_alpha.structure.context.power_play import power_play_archive_values
    from engine_alpha.scoring.scoring import (
        sub_score_archive_values,
        ta_grade_archive_values,
    )
    from engine_alpha.structure.context.htf import htf_archive_values
    from engine_alpha.structure.events.event_map import event_map_archive_values
    from engine_alpha.structure.events.event_vocabulary import sentence_archive_values
    from engine_alpha.structure.context.strategy_read import strategy_archive_values
    from engine_alpha.structure.box.trace_export import election_trace_archive_values
    from archive_models import (
        SetupArchive,
        get_market_context,
        get_sector_etf,
        get_sector_trend,
    )

    def _download_one(symbol: str, start_date: str, end_date: str, label: str):
        # Regime rule: this path re-runs the live engine (_evaluate_at_date),
        # so its series must match the scan cache — one auto_adjust source.
        raw_frame = _batched_download(
            [symbol],
            {"start": start_date, "end": end_date, "auto_adjust": price_auto_adjust()},
            label,
        )
        if raw_frame is None or raw_frame.empty:
            return raw_frame
        if hasattr(raw_frame.columns, "nlevels") and raw_frame.columns.nlevels > 1:
            try:
                return raw_frame[symbol].dropna()
            except KeyError:
                return _pd.DataFrame()
        return raw_frame.dropna()

    ticker = (payload.ticker or "").strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")

    scan_dt = (payload.scan_date or _pd.Timestamp.today().strftime("%Y-%m-%d")).strip()
    try:
        target_ts = _pd.Timestamp(scan_dt)
    except Exception:
        raise HTTPException(status_code=400, detail=f"invalid scan_date: {scan_dt}")

    # Manual adds run the single-ticker equities pipeline, so the existence
    # check must match the widened 3-col identity key (conventions.md EC-4) —
    # a same-day ETF/sector screener row is a different identity, not a dup.
    existing = (
        db.query(SetupArchive)
        .filter_by(ticker=ticker, scan_date=scan_dt, universe_type=DEFAULT_UNIVERSE_TYPE)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"{ticker} @ {scan_dt} already in archive")

    # Download enough history for monthly HTF context; _evaluate_at_date trims
    # the daily structure read back to settings.DAILY_STRUCTURE_PERIOD.
    start = (target_ts - _pd.Timedelta(days=SEED_HISTORY_DAYS)).strftime("%Y-%m-%d")
    end = (target_ts + _pd.Timedelta(days=FORWARD_RETURN_DOWNLOAD_DAYS)).strftime("%Y-%m-%d")
    try:
        raw = _download_one(ticker, start, end, f"Manual archive {ticker}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"market-data download failed: {e}")
    if raw is None or raw.empty:
        raise HTTPException(status_code=404, detail=f"no market data found for {ticker}")
    if hasattr(raw.columns, "nlevels") and raw.columns.nlevels > 1:
        raw.columns = raw.columns.droplevel("Ticker")

    df_slice = raw[raw.index <= target_ts].dropna()
    if len(df_slice) < 200:
        raise HTTPException(status_code=422, detail=f"only {len(df_slice)} bars at {scan_dt} (need 200+)")

    result = _evaluate_at_date(df_slice)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail=f"screener did not fire on {ticker} @ {scan_dt} — no valid LPS at that date",
        )

    fwd_df = raw[raw.index > target_ts]
    hist_df = raw[raw.index <= target_ts]
    vol_50_at_scan = None
    if "Volume" in hist_df.columns and len(hist_df) >= 50:
        vs = hist_df["Volume"]
        if hasattr(vs, "columns"):
            vs = vs.iloc[:, 0]
        vol_50_at_scan = float(vs.tail(50).mean())
    fwd_returns = (
        _compute_returns(
            fwd_df, result["current_price"], result["trigger_price"],
            s_level=result.get("s_level"), vol_50_at_scan=vol_50_at_scan,
        )
        if not fwd_df.empty else {}
    )

    market_ctx = get_market_context(scan_dt)
    sector_etf = get_sector_etf(ticker)
    sector_trend = get_sector_trend(sector_etf, scan_dt) if sector_etf else None
    sub = result.get("sub_scores", {}) or {}

    # RS vs sector: stock base return − sector ETF base return, same window.
    rs_vs_sector = None
    base_start = result.get("base_date_start"); base_end = result.get("base_date_end")
    if sector_etf and base_start and base_end:
        try:
            sec_raw = _download_one(sector_etf, base_start, base_end, f"Manual archive {sector_etf}")
            if sec_raw is not None and not sec_raw.empty:
                sc = sec_raw["Close"]
                if hasattr(sc, "columns"): sc = sc.iloc[:, 0]
                if len(sc) >= 2:
                    sec_ret = (float(sc.iloc[-1]) - float(sc.iloc[0])) / float(sc.iloc[0])
                    bcs = float(result.get("base_close_start") or 0)
                    bce = float(result.get("base_close_end") or 0)
                    if bcs > 0:
                        stock_ret = (bce - bcs) / bcs
                        rs_vs_sector = round(stock_ret - sec_ret, 5)
        except Exception:
            rs_vs_sector = None

    # Special-cased columns: identity, required fields (KeyError if the eval
    # result lacks them), sub-score remaps, the three int(bool(...)) coercions,
    # market-context enrichment, and the HTF / forward-return splats. Everything
    # else is a flat result.get(col) pass-through that archive_row_from_result
    # fills by iterating SetupArchive.__table__ — so a new flat model column needs
    # no edit here.
    overrides = {
        "ticker": ticker,
        "scan_date": scan_dt,
        "universe_type": DEFAULT_UNIVERSE_TYPE,  # single-ticker manual add = equities scope (EC-4)
        "setup_type": result["setup_type"],
        "tier": result["tier"],
        "score": result["score"],
        "current_price": result["current_price"],
        "r_level": result["r_level"],
        "s_level": result["s_level"],
        "trigger_price": result["trigger_price"],
        "base_length": result["base_length"],
        "box_width": result["box_width"],
        "touches": result["touches"],
        "r_touches": result["r_touches"],
        "s_touches": result["s_touches"],
        "atr_ratio": result["atr_ratio"],
        "lps_length": result["lps_length"],
        "breach_days": result["breach_days"],
        "vol_contraction": result["vol_contraction"],
        "tightness_ratio": result["tightness_ratio"],
        # Per-term sub-score columns — the ONE registry-driven producer (task
        # 6 fold). The manual path's deliberate NULL (score_traversal_quality,
        # also frozen in _MANUAL_UNMAPPED_COLUMNS) is a DECLARED exclusion,
        # never a hand-omission.
        **sub_score_archive_values(
            sub, exclude=frozenset({"score_traversal_quality"})),
        # TA-grade family — the SAME single stamping point the live and seed
        # writers use (council review 2026-08-08, finding 1: the raw model
        # pass would bind resolve_fired_tags' Python LIST into the TEXT
        # column and skip every EC-19 closed-set refusal + the EC-2 scrub).
        **ta_grade_archive_values(result.get, prefixed=False),
        # Power-Play family — EC-30: the producer rides EVERY writer of the
        # table; the raw model pass would skip the NaN scrub, the INTEGER
        # coercions, and the pp_state closed-set refusal on exactly this
        # route (council review 2026-08-17, finding 8 — the same class the
        # TA-grade splat above was added for).
        **power_play_archive_values(result.get, prefixed=False),
        # Coercions (nullable 0/1)
        "bin_c_present": (int(bool(result.get("bin_c_present")))
                          if result.get("bin_c_present") is not None else None),
        "phase_d_inner": (int(bool(result.get("phase_d_inner")))
                          if result.get("phase_d_inner") is not None else None),
        "lps_in_inner": (int(bool(result.get("lps_in_inner")))
                         if result.get("lps_in_inner") is not None else None),
        # Market-context enrichment (computed above, not from result)
        "spy_trend": market_ctx.get("spy_trend"),
        "vix_level": market_ctx.get("vix_level"),
        "sector_etf": sector_etf,
        "sector_trend": sector_trend,
        "rs_vs_sector_pct": rs_vs_sector,
        # Provenance + curation
        "source": "manual",
        "engine_config_version": manifest_hash(),
        "quality_label": payload.quality_label,
        "notes": payload.notes,
        # HTF (higher-timeframe) context splat — seed result, unprefixed keys
        **htf_archive_values(result.get, prefixed=False),
        # Event Map tape summary — NULL when EVENT_MAP_ENABLED is off (EC-30:
        # the family producer rides EVERY writer, same shape as the seed path)
        **event_map_archive_values(result.get, prefixed=False),
        # Sentence-token family (consolidation-method Task 8) — NULL until
        # the sentence measurement flag flips (EC-30, same shape)
        **sentence_archive_values(result.get, prefixed=False),
        # Election-trace evidence — NULL when the export flag is off
        **election_trace_archive_values(result.get, prefixed=False),
        # Strategy read (held-through-correction) — NULL when dark
        **strategy_archive_values(result.get, prefixed=False),
        # Forward-return / triple-barrier outcomes computed above
        **fwd_returns,
    }
    row = SetupArchive(**archive_row_from_result(result, overrides=overrides))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


_ANALYSIS_CACHE: Dict[str, Any] = {"report": None, "ts": 0.0}


# Deliberate guard retrofit (the calibration.py posture rule): both routes below
# are reachable as CORS "simple requests" (a GET, a body-less POST) which no
# preflight stops — /analysis spawns a 120s subprocess per request and
# /update-returns holds SCAN_LOCK, whose contention makes the 18:00 scheduled
# scan skip its night's run. Only our own frontend passes the header.
@router.get("/analysis", dependencies=[Depends(require_same_app)])
def get_archive_analysis(
    source: Optional[str] = Query(None, description="Restrict to a source: screener / seed / manual"),
    refresh: bool = Query(False, description="Bypass the ~5min cache and re-run"),
):
    """Run the read-only archive analysis report (mirrors ``python -m core.archive.analyze``)
    and return it as text. Cached ~5 minutes per process unless ``refresh=true``."""
    import time as _time

    now = _time.time()
    if (
        not refresh
        and not source
        and _ANALYSIS_CACHE["report"] is not None
        and (now - _ANALYSIS_CACHE["ts"] < 300)
    ):
        return {"report": _ANALYSIS_CACHE["report"], "cached": True}

    cmd = [sys.executable, "-m", "core.archive.analyze"]
    if source:
        cmd += ["--source", source]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        result = subprocess.run(
            cmd,
            cwd=_ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            creationflags=flags,
            env=env,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=(result.stderr or "analysis failed")[-1000:])

    report = result.stdout or ""
    if not source:
        _ANALYSIS_CACHE.update({"report": report, "ts": now})
    return {"report": report, "cached": False}


@router.post("/update-returns", dependencies=[Depends(require_same_app)])
def trigger_update_returns():
    """Trigger forward return computation for all pending setups."""
    # forward_returns writes the archive DB — same one-child-at-a-time
    # guarantee as the scan jobs, taken through the SAME shape (EC-3): the
    # context manager owns the release, so no line between the acquire and
    # the work can orphan the lock (services/scan_runner.py).
    with scan_lock() as acquired:
        if not acquired:
            raise HTTPException(
                status_code=409,
                detail="another scan or data job is already running",
            )
        try:
            script = os.path.join(_ROOT_DIR, "core", "archive", "forward_returns.py")
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            result = subprocess.run(
                [sys.executable, script],
                cwd=_ROOT_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                creationflags=flags,
                env=env,
            )
            return {
                "status": "ok" if result.returncode == 0 else "error",
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-500:] if result.stderr else "",
                "returncode": result.returncode,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
