"""Calibration-setup outcomes: his drawn setups measured like archived fires.

Operator ruling 2026-10-03: *"treat calibrated setups as archived ones as well!
since they are essentially modeled archived setups made for studying high quality
structures that our engine needs to master!"*

Two halves:
  * ``update_calibration_outcomes`` is a maturation pass beside the fires' and
    the near-miss lane's. It measures each calibration setup (a ``box`` mark) with
    the fires' own outcome function (``forward_returns._compute_returns``), the same
    batched download, SPY baseline and price-scale guard, and writes
    ``calibration_outcomes``. Never ``setup_archive``: his setups were chosen for
    quality, so every study reads them as their own group.
  * ``load_calibration_setups`` is the read-only loader every study shares.

The outcome clock starts on the trading day BEFORE his trigger, the fire-day
analog (the LPS complete, the trigger set); a mark with no trigger starts on its
as-of bar. His rails were stored on the price scale he drew them on, and
``anchor_close`` is that scale's as-of close, which the scale guard reads.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

_PROJECT_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.append(_BACKEND_DIR)

from core.archive.db_path import archive_db_path
from core.archive.outcomes import HORIZON_BARS

log = logging.getLogger("chrollo.archive.calibration")

SOURCE = "calibration"   # the group name every study reports them under
_HISTORY_DAYS = 100      # calendar days before the anchor: the 50-day volume average
_IDENTITY = {"mark_id", "ticker", "mark_revision", "computed_at"}
_MARKS_SQL = (
    "SELECT id, ticker, as_of_date, support, trigger_date, trigger_price, "
    "anchor_close, revision FROM calibration_marks "
    "WHERE verdict = 'box' AND support IS NOT NULL"
)


def _col(frame: pd.DataFrame, name: str) -> pd.Series:
    col = frame[name]
    return col.iloc[:, 0] if hasattr(col, "columns") else col


def outcome_anchor(index: pd.Index, mark: dict) -> Optional[tuple]:
    """The outcome clock's start as ``(bar, basis)``: the last bar BEFORE his
    trigger day, or (no trigger) the last bar on or before his as-of day.
    ``None`` when the frame holds no such bar."""
    if mark.get("trigger_date"):
        before = index[index < pd.Timestamp(mark["trigger_date"])]
        return (before[-1], "trigger") if len(before) else None
    on = index[index <= pd.Timestamp(mark["as_of_date"])]
    return (on[-1], "as_of") if len(on) else None


def measure_mark(df: pd.DataFrame, mark: dict,
                 spy_df: Optional[pd.DataFrame] = None) -> Optional[dict]:
    """One mark's outcome values, measured exactly like a fire, or ``None`` when
    the frame cannot place it (no anchor bar, no as-of bar, no forward bars)."""
    from core.archive.forward_returns import (
        _SCALE_DEPENDENT_NULLS,
        _cap_forward_window,
        _compute_returns,
        _price_scale_factor,
        _rescaled,
        _spy_window_return,
    )

    if df is None or df.empty:
        return None
    anchor = outcome_anchor(df.index, mark)
    as_of_bars = df.index[df.index <= pd.Timestamp(mark["as_of_date"])]
    if anchor is None or not len(as_of_bars):
        return None
    anchor_ts, basis = anchor
    closes = _col(df, "Close")
    # His trigger and support sit on the scale he drew them on; the as-of close he
    # saw places them on the freshly downloaded one (None = unknowable scale).
    scale = _price_scale_factor(float(closes.loc[as_of_bars[-1]]), mark.get("anchor_close"))
    entry_close = float(closes.loc[anchor_ts])
    fwd = df[df.index > anchor_ts]
    if fwd.empty:
        return None
    history = df[df.index <= anchor_ts]
    vol_50 = None
    if "Volume" in history.columns and len(history) >= 50:
        vol_50 = float(_col(history, "Volume").tail(50).mean())
    capped = _cap_forward_window(fwd)
    spy_ret = _spy_window_return(spy_df, anchor_ts, capped.index[-1])
    trigger = _rescaled(mark.get("trigger_price"), scale)
    s_level = _rescaled(mark.get("support"), scale)
    returns = _compute_returns(fwd, entry_close, trigger, s_level=s_level,
                               vol_50_at_scan=vol_50, spy_window_return=spy_ret)
    if not returns:
        return None
    if scale is None:
        returns.update(_SCALE_DEPENDENT_NULLS)
    return {"anchor_date": str(anchor_ts)[:10], "anchor_basis": basis,
            "entry_close": round(entry_close, 4), "trigger_price": trigger,
            "s_level": s_level, **returns}


def needs_measure(mark: dict, outcome, force: bool = False) -> bool:
    """Measure a mark with no outcome yet, one redrawn since (a new revision), or
    one still inside the 60-bar window."""
    if force or outcome is None:
        return True
    if outcome.mark_revision != mark["revision"]:
        return True
    return outcome.bars_to_date is None or outcome.bars_to_date < HORIZON_BARS


def _ensure_table(engine) -> None:
    """Create-on-fresh plus the ADD-only model diff, so the standalone maturation
    job (no backend boot) still lands every column (the near-miss pattern)."""
    from sqlalchemy import inspect, text

    from archive_models import CalibrationOutcome

    CalibrationOutcome.__table__.create(bind=engine, checkfirst=True)
    existing = {c["name"] for c in inspect(engine).get_columns("calibration_outcomes")}
    with engine.begin() as conn:
        for column in CalibrationOutcome.__table__.columns:
            if column.primary_key or column.name in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE calibration_outcomes ADD COLUMN "
                                  f"{column.name} {column.type}"))
            except Exception as exc:
                message = str(exc).lower()
                if "duplicate column" in message or "already exists" in message:
                    continue
                raise


def _read_marks(engine) -> list[dict]:
    from sqlalchemy import inspect, text

    if "calibration_marks" not in inspect(engine).get_table_names():
        return []
    with engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(text(_MARKS_SQL))]


def _download(marks: list[dict]):
    """One batched download (+ SPY) spanning every mark's history and window."""
    from core.archive.forward_returns import FORWARD_RETURN_DOWNLOAD_DAYS, SPY_TICKER
    from core.pipeline.market_data.downloads import _batched_download, price_auto_adjust

    days = [pd.Timestamp(d) for m in marks
            for d in (m["as_of_date"], m.get("trigger_date")) if d]
    start = min(days) - pd.Timedelta(days=_HISTORY_DAYS)
    end = min(pd.Timestamp.now() + pd.Timedelta(days=2),
              max(days) + pd.Timedelta(days=FORWARD_RETURN_DOWNLOAD_DAYS))
    tickers = list(dict.fromkeys([*(m["ticker"] for m in marks), SPY_TICKER]))
    return _batched_download(
        tickers,
        {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"),
         "auto_adjust": price_auto_adjust()},
        "Calibration outcomes",
    )


def update_calibration_outcomes(force: bool = False) -> int:
    """Fill or refresh the outcome of every calibration setup that needs it, and
    drop the outcome of a mark that was deleted or is no longer a box. Returns
    the number of setups measured."""
    from sqlalchemy.orm import sessionmaker

    from archive_models import CalibrationOutcome
    from core.archive.forward_returns import SPY_TICKER, _ticker_frame
    from database import make_sqlite_engine

    engine = make_sqlite_engine(archive_db_path())
    _ensure_table(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        marks = _read_marks(engine)
        existing = {row.mark_id: row for row in session.query(CalibrationOutcome).all()}
        live = {m["id"] for m in marks}
        for mark_id, row in existing.items():
            if mark_id not in live:
                session.delete(row)
        todo = [m for m in marks if needs_measure(m, existing.get(m["id"]), force)]
        if not todo:
            session.commit()
            log.info("No calibration setups need outcome updates.")
            return 0

        log.info("Measuring outcomes for %d calibration setup(s)...", len(todo))
        raw = _download(todo)
        try:
            spy_df = _ticker_frame(raw, SPY_TICKER)
        except (KeyError, AttributeError):
            spy_df = pd.DataFrame()
        outcome_keys = [c.name for c in CalibrationOutcome.__table__.columns
                        if c.name not in _IDENTITY]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        measured = 0
        for mark in todo:
            try:
                df = _ticker_frame(raw, mark["ticker"])
            except (KeyError, AttributeError):
                df = pd.DataFrame()
            values = measure_mark(df, mark, spy_df)
            if values is None:
                log.warning("  %s (mark %s): no prices to measure from, left as is.",
                            mark["ticker"], mark["id"])
                continue
            row = existing.get(mark["id"]) or CalibrationOutcome(mark_id=mark["id"])
            for key in outcome_keys:          # every column, so nothing stale survives
                setattr(row, key, values.get(key))
            row.ticker = mark["ticker"]
            row.mark_revision = mark["revision"]
            row.computed_at = now
            session.add(row)
            measured += 1
        session.commit()
        log.info("Measured outcomes for %d calibration setup(s).", measured)
        return measured
    finally:
        session.close()


# Every mark column a study or the screen reads, renamed where an outcome
# column shares the name (the outcome's trigger_date is the day the trigger was
# CROSSED; his is the day he marked the buy).
_SETUP_SQL = """
SELECT m.id AS mark_id, m.ticker, m.as_of_date, m.label, m.box_start_date,
       m.resistance, m.support, m.trigger_date AS his_trigger_date,
       m.trigger_price AS his_trigger_price, o.*
FROM calibration_marks m
LEFT JOIN calibration_outcomes o ON o.mark_id = m.id
WHERE m.verdict = 'box'
"""


def load_calibration_setups(db_path: Optional[str] = None) -> pd.DataFrame:
    """Every calibration setup with its outcome (NaN until measured), read-only,
    tagged ``source = 'calibration'``. Empty when either table is missing."""
    path = db_path or archive_db_path()
    if not os.path.exists(path):
        return pd.DataFrame()
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not {"calibration_marks", "calibration_outcomes"} <= tables:
            return pd.DataFrame()
        df = pd.read_sql_query(_SETUP_SQL, con)
    finally:
        con.close()
    # o.* repeats mark_id and ticker; keep the marks' own (first) copies.
    df = df.loc[:, ~df.columns.duplicated()].copy()
    df["source"] = SOURCE
    return df
