"""Point-in-time backtest backfill — replay the frozen engine across history.

Runs the SAME numeric chain the live screener uses (``_evaluate_at_date`` ->
``_run_eval_chain``, byte-identical to live by construction) over a WEEKLY date
grid across the FULL cache universe (2021-2026), writing every fire to a
**scratch** sqlite archive. Forward returns / MFE / R / triple-barrier labels are
computed OFFLINE from the same 5-year cache, so entry and outcome share one
as-traded price basis. Each fire is stamped with the prevailing SPY regime at its
scan date so the edge can be segmented bull / bear / correction.

This is the missing piece that lets the standalone-edge harness
(``tools.research.backtest_engine``) read a REGIME-SPANNING cohort instead of a single
bull market. See ``docs/backtest_methodology.md`` for the why.

SAFETY (D5): never writes the live ``trading_journal.db``. The ``--db`` path is
explicit and refused if it resolves anywhere near the production archive.

Usage:
    python -m tools.research.backtest_backfill --db output/backtest_archive.db
    python -m tools.research.backtest_backfill --db out.db --cadence monthly --start 2022-01-01
    python -m tools.research.backtest_backfill --db out.db --limit 50   # smoke test on 50 tickers

Offline: reads the local parquet cache, never the network.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional

import numpy as np
import pandas as pd

try:  # works under both `python -m tools.research.backtest_backfill` and `python tools/research/backtest_backfill.py`
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

_PROJECT_ROOT = configure_path()
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.append(_BACKEND_DIR)

from config import settings
from core.archive.forward_returns import (
    FORWARD_RETURN_HORIZON_BARS,
    _cap_forward_window,
    _compute_returns,
    _spy_window_return,
)
from core.archive.seed import _evaluate_at_date, _close_series, _ticker_frame
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("chrollo.backtest_backfill")

# Minimum bars the engine needs for a daily structure read (mirrors seed.py's
# per-offset floor). ~200 trading days ≈ 10 months, so the earliest fireable grid
# date sits ~10 months after the cache start.
MIN_BARS = 200
SPY_SYMBOL = "SPY"

# Worker-global read-only shares (populated by _init_worker via ProcessPool
# initializer so the 123 MB cache is loaded ONCE per worker, not pickled per task).
_W_CACHE: Optional[pd.DataFrame] = None
_W_SPY_FRAME: Optional[pd.DataFrame] = None
_W_SPY_CLOSE: Optional[pd.Series] = None
_W_GRID: list[pd.Timestamp] = []
_W_SPY6: dict[pd.Timestamp, float] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Grid + SPY context (parent process)
# ─────────────────────────────────────────────────────────────────────────────
def build_date_grid(index: pd.DatetimeIndex, cadence: str,
                    start: Optional[str], end: Optional[str]) -> list[pd.Timestamp]:
    """Trading-day grid: for each cadence period pick the LAST cache session in it.

    Weekly -> last session each ISO week (the Friday-or-earlier close); monthly ->
    last session each month; biweekly -> every other weekly point. Anchored to real
    cache sessions so ``frame.index <= T`` always lands on a bar the engine saw.
    """
    idx = index.sort_values().unique()
    idx = pd.DatetimeIndex(idx)
    if start:
        idx = idx[idx >= pd.Timestamp(start)]
    if end:
        idx = idx[idx <= pd.Timestamp(end)]
    if len(idx) == 0:
        return []
    s = pd.Series(idx, index=idx)
    if cadence == "monthly":
        picks = s.groupby([idx.year, idx.month]).last()
    elif cadence in ("weekly", "biweekly"):
        iso = idx.isocalendar()
        picks = s.groupby([iso.year.values, iso.week.values]).last()
    else:
        raise ValueError(f"unknown cadence {cadence!r} (weekly|biweekly|monthly)")
    grid = sorted(pd.Timestamp(x) for x in picks.values)
    if cadence == "biweekly":
        grid = grid[::2]
    return grid


def spy_6m_map(spy_close: pd.Series, grid: list[pd.Timestamp]) -> dict:
    """SPY 6-month (RS_LOOKBACK_BARS) trailing return as-of each grid date."""
    out: dict[pd.Timestamp, float] = {}
    if spy_close is None:
        return {t: 0.0 for t in grid}
    lb = settings.RS_LOOKBACK_BARS
    for t in grid:
        s = spy_close[spy_close.index <= t]
        out[t] = float(s.iloc[-1] / s.iloc[-lb - 1] - 1.0) if len(s) > lb else 0.0
    return out


def spy_trend_map(spy_close: pd.Series, grid: list[pd.Timestamp]) -> dict:
    """Coarse SPY regime label as-of each grid date, from the 200-DMA and its slope.

    'uptrend'   : SPY > 200-DMA and the 200-DMA is rising (1-month lookback)
    'downtrend' : SPY < 200-DMA and the 200-DMA is falling
    'neutral'   : anything in between (chop / transition)

    This is the segmentation axis for the regime-conditioned edge read — it is a
    REPORTING tag, never fed to the engine (which reads only the ticker frame).
    """
    out: dict[pd.Timestamp, str] = {}
    if spy_close is None:
        return {t: "unknown" for t in grid}
    sma200 = spy_close.rolling(200).mean()
    for t in grid:
        c = spy_close[spy_close.index <= t]
        m = sma200[sma200.index <= t]
        if len(c) < 221 or pd.isna(m.iloc[-1]):
            out[t] = "unknown"
            continue
        price = float(c.iloc[-1])
        ma_now = float(m.iloc[-1])
        ma_1m = float(m.iloc[-21])
        rising = ma_now > ma_1m
        if price > ma_now and rising:
            out[t] = "uptrend"
        elif price < ma_now and not rising:
            out[t] = "downtrend"
        else:
            out[t] = "neutral"
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Worker: evaluate one ticker across the whole grid
# ─────────────────────────────────────────────────────────────────────────────
def _init_worker(cache_path: str, parquet_engine: str,
                 grid: list, spy6: dict) -> None:
    """ProcessPool initializer — load the cache once per worker; stash shares."""
    global _W_CACHE, _W_SPY_FRAME, _W_SPY_CLOSE, _W_GRID, _W_SPY6
    data = pd.read_parquet(cache_path, engine=parquet_engine)
    if hasattr(data.index, "tz") and data.index.tz is not None:
        data.index = data.index.tz_localize(None)
    _W_CACHE = data
    _W_SPY_FRAME = _ticker_frame(data, SPY_SYMBOL)
    _W_SPY_CLOSE = _close_series(data, SPY_SYMBOL)
    _W_GRID = list(grid)
    _W_SPY6 = dict(spy6)


def _eval_ticker_grid(ticker: str) -> list[dict]:
    """Replay the engine on ``ticker`` at every grid date; return fire payloads.

    Each payload = {scan_date, result, fwd_returns} where ``result`` is the
    seed-shaped canonical evaluation dict and ``fwd_returns`` are the offline
    outcomes over the cache's forward bars. The parent assembles DB rows from these
    (keeps the worker DB-free / purely numeric)."""
    if _W_CACHE is None:
        return []
    try:
        frame = _ticker_frame(_W_CACHE, ticker)
    except (KeyError, AttributeError):
        return []
    if frame.empty or "Close" not in frame:
        return []

    fires: list[dict] = []
    for t in _W_GRID:
        df_slice = frame[frame.index <= t]
        if len(df_slice) < MIN_BARS:
            continue
        result = _evaluate_at_date(df_slice, spy_6m_return=_W_SPY6.get(t, 0.0))
        if result is None:
            continue

        # Offline forward returns from the cache's post-scan bars (same as seed.py).
        fwd_df = frame[frame.index > t]
        fwd_returns: dict = {}
        if not fwd_df.empty:
            hist = frame[frame.index <= t]
            vol_50 = None
            if "Volume" in hist.columns and len(hist) >= 50:
                vs = hist["Volume"]
                vs = vs.iloc[:, 0] if hasattr(vs, "columns") else vs
                vol_50 = float(vs.tail(50).mean())
            capped = _cap_forward_window(fwd_df)
            fwd_end = capped.index[-1] if capped is not None and not capped.empty else None
            spy_win = _spy_window_return(_W_SPY_FRAME, t, fwd_end)
            fwd_returns = _compute_returns(
                fwd_df, result["current_price"], result.get("trigger_price"),
                s_level=result.get("s_level"), vol_50_at_scan=vol_50,
                spy_window_return=spy_win,
            )
        fires.append({
            "scan_date": t.strftime("%Y-%m-%d"),
            "result": result,
            "fwd_returns": fwd_returns,
        })
    return fires


# ─────────────────────────────────────────────────────────────────────────────
# Row assembly + scratch-DB write (parent)
# ─────────────────────────────────────────────────────────────────────────────
def _assemble_row(ticker: str, payload: dict, spy_trend: Optional[str],
                  engine_config_version: str) -> dict:
    """Build a SetupArchive kwargs dict from one fire payload.

    Mirrors ``core.archive.seed.seed_archive``'s override block, but stamped
    source='screener' (the UNBIASED standalone-edge basis) and tagged with the
    replay-date SPY regime. Reuses ``archive_row_from_result`` (the model-driven
    mapper) verbatim so populated columns match the live/seed path.
    """
    from domains.archive.queries import archive_row_from_result
    from engine_alpha.structure.context.htf import htf_archive_values

    r = payload["result"]
    sub = r.get("sub_scores", {}) or {}

    def _flag(key):
        v = r.get(key)
        return int(bool(v)) if v is not None else None

    overrides = dict(
        ticker=ticker,
        scan_date=payload["scan_date"],
        universe_type=DEFAULT_UNIVERSE_TYPE,
        setup_type=r["setup_type"],
        tier=r["tier"],
        score=r["score"],
        current_price=r["current_price"],
        r_level=r["r_level"],
        s_level=r["s_level"],
        trigger_price=r["trigger_price"],
        base_length=r["base_length"],
        box_width=r["box_width"],
        touches=r["touches"],
        r_touches=r["r_touches"],
        s_touches=r["s_touches"],
        atr_ratio=r["atr_ratio"],
        lps_length=r["lps_length"],
        breach_days=r["breach_days"],
        vol_contraction=r["vol_contraction"],
        tightness_ratio=r["tightness_ratio"],
        score_box_tightness=sub.get("box_tightness"),
        score_touch_density=sub.get("touch_density"),
        score_traversal_quality=sub.get("traversal_quality"),
        score_atr_squeeze=sub.get("atr_squeeze"),
        score_lps_tightness=sub.get("lps_tightness"),
        score_vol_contraction=sub.get("vol_contraction"),
        score_base_age=sub.get("base_age"),
        score_uptrend_bonus=sub.get("uptrend_bonus"),
        score_rs_bonus=sub.get("rs_bonus"),
        score_high_proximity=sub.get("high_proximity"),
        score_breadth_bonus=sub.get("breadth_bonus"),
        score_contraction=sub.get("contraction"),
        score_ascending_support=sub.get("ascending_support"),
        score_adr=sub.get("adr"),
        bin_c_present=_flag("bin_c_present"),
        stage2_ma_stack_pass=_flag("stage2_ma_stack_pass"),
        stage2_trend_pass=_flag("stage2_trend_pass"),
        phase_d_inner=_flag("phase_d_inner"),
        lps_in_inner=_flag("lps_in_inner"),
        bars_since_bc=r.get("bars_since_BC"),
        descent_length=r.get("descent_length"),
        excess_return_6m=r.get("excess_return_6m"),
        trav_last_support_frac=r.get("trav_last_support_frac"),
        trav_coil_floor_pos=r.get("trav_coil_floor_pos"),
        stage2_ma200_slope_1m_pct=r.get("stage2_ma200_slope_1m_pct"),
        stage2_52w_low_pct=r.get("stage2_52w_low_pct"),
        stage2_trend_pass_count=r.get("stage2_trend_pass_count"),
        # Regime tag (replay-date SPY state) — the segmentation axis.
        spy_trend=spy_trend,
        engine_config_version=engine_config_version,
        source="screener",   # UNBIASED basis (NOT 'seed' — no winners-gallery bias)
        quality_label=None,
        **htf_archive_values(r.get, prefixed=False),
        **payload["fwd_returns"],
    )
    return archive_row_from_result(r, overrides=overrides)


def _assert_scratch_db(db_path: str) -> str:
    """Refuse to write anywhere near the live production archive (D5).

    The shared sealed-output guard runs FIRST (EC-14; sealed knowledge lives in
    one place, EC-3); this tool's own live-archive refusals bite behind it."""
    abspath = os.path.abspath(refuse_sealed_output(db_path))
    base = os.path.basename(abspath).lower()
    live = os.path.abspath(os.path.join(_BACKEND_DIR, "trading_journal.db"))
    if abspath == live or base == "trading_journal.db":
        raise SystemExit(
            f"REFUSED: '{abspath}' is (or is named like) the live archive. "
            "The backfill only writes a scratch DB — pick another path."
        )
    if os.path.normpath(_BACKEND_DIR) in os.path.normpath(os.path.dirname(abspath)):
        raise SystemExit(
            f"REFUSED: '{abspath}' is under the backend dir (live-DB territory). "
            "Write the scratch DB elsewhere (e.g. output/backtest_archive.db)."
        )
    return abspath


def _open_scratch_db(db_path: str):
    from sqlalchemy.orm import sessionmaker
    from archive_models import SetupArchive
    from database import make_sqlite_engine
    from core.archive.forward_returns import _ensure_model_columns

    engine = make_sqlite_engine(db_path)
    SetupArchive.metadata.create_all(bind=engine)
    _ensure_model_columns(engine)
    # Progress table so a resumed run skips tickers already fully processed
    # (fired OR not) — can't infer "done, no fires" from the archive alone.
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS backfill_progress "
            "(ticker TEXT PRIMARY KEY, n_fires INTEGER)"
        ))
    Session = sessionmaker(bind=engine, autoflush=False)
    return engine, Session


def _done_tickers(engine) -> set:
    from sqlalchemy import text
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT ticker FROM backfill_progress")).fetchall()
    return {row[0] for row in rows}


def run_backfill(db_path: str, cadence: str = "weekly",
                 start: Optional[str] = None, end: Optional[str] = None,
                 limit: Optional[int] = None, workers: Optional[int] = None,
                 resume: bool = True) -> int:
    """Replay the engine over the grid and write fires to the scratch archive."""
    db_path = _assert_scratch_db(db_path)
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    log.info(f"Loading cache {settings.CACHE_FILENAME} ...")
    data = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    if hasattr(data.index, "tz") and data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    grid = build_date_grid(data.index, cadence, start, end)
    if not grid:
        raise SystemExit("empty date grid — check --start/--end vs the cache range.")
    spy_close = _close_series(data, SPY_SYMBOL)
    spy6 = spy_6m_map(spy_close, grid)
    trend = spy_trend_map(spy_close, grid)
    log.info(f"Grid: {len(grid)} {cadence} dates {grid[0].date()} -> {grid[-1].date()} "
             f"| regimes {pd.Series(trend).value_counts().to_dict()}")

    all_tickers = sorted(
        t for t in set(data.columns.get_level_values(0)) if t != SPY_SYMBOL
    )
    if limit:
        all_tickers = all_tickers[:limit]

    engine, Session = _open_scratch_db(db_path)
    from engine_alpha.freeze.manifest import manifest_hash
    ecv = manifest_hash()

    done = _done_tickers(engine) if resume else set()
    todo = [t for t in all_tickers if t not in done]
    log.info(f"Tickers: {len(all_tickers)} total, {len(done)} already done, "
             f"{len(todo)} to process. Scratch DB: {db_path}")
    if not todo:
        log.info("Nothing to do (all tickers processed).")
        return 0

    from archive_models import SetupArchive
    from sqlalchemy import text
    n_workers = workers or max(1, (os.cpu_count() or 4) - 1)
    total_fires = 0
    processed = 0

    with ProcessPoolExecutor(
        max_workers=n_workers, initializer=_init_worker,
        initargs=(settings.CACHE_FILENAME, settings.PARQUET_ENGINE, grid, spy6),
    ) as ex:
        futures = {ex.submit(_eval_ticker_grid, t): t for t in todo}
        session = Session()
        for fut in as_completed(futures):
            ticker = futures[fut]
            try:
                fires = fut.result()
            except Exception as exc:  # a bad ticker frame must not kill the run
                log.warning(f"  {ticker}: worker error {type(exc).__name__}: {exc}")
                fires = []
            for payload in fires:
                row = _assemble_row(ticker, payload, trend.get(
                    pd.Timestamp(payload["scan_date"]), "unknown"), ecv)
                session.add(SetupArchive(**row))
            session.execute(
                text("INSERT OR REPLACE INTO backfill_progress(ticker, n_fires) "
                     "VALUES (:t, :n)"), {"t": ticker, "n": len(fires)})
            session.commit()
            total_fires += len(fires)
            processed += 1
            if processed % 100 == 0 or processed == len(todo):
                log.info(f"  {processed}/{len(todo)} tickers | {total_fires} fires so far")
        session.close()

    log.info(f"Backfill complete: {total_fires} fires from {len(todo)} tickers "
             f"over {len(grid)} dates -> {db_path}")
    return total_fires


def main() -> None:
    ap = argparse.ArgumentParser(description="Point-in-time backtest backfill (scratch DB).")
    ap.add_argument("--db", required=True, help="scratch sqlite path (NOT the live DB)")
    ap.add_argument("--cadence", default="weekly", choices=["weekly", "biweekly", "monthly"])
    ap.add_argument("--start", default=None, help="grid start (YYYY-MM-DD); default = cache start")
    ap.add_argument("--end", default=None, help="grid end (YYYY-MM-DD); default = cache end")
    ap.add_argument("--limit", type=int, default=None, help="cap universe to first N tickers (smoke test)")
    ap.add_argument("--workers", type=int, default=None, help="worker processes (default cpu-1)")
    ap.add_argument("--no-resume", action="store_true", help="ignore existing progress, reprocess all")
    args = ap.parse_args()
    run_backfill(
        db_path=args.db, cadence=args.cadence, start=args.start, end=args.end,
        limit=args.limit, workers=args.workers, resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
