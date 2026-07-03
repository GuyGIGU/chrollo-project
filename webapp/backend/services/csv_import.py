"""Parse an IBKR Activity Statement CSV and feed it into the auto-import pipeline.

The Activity Statement is a multi-section CSV — each row is tagged with a section
name and a discriminator (Header/Data/SubTotal/Total/Notes). We only care about:

- ``Account Information`` → pulls the account number once.
- ``Trades`` (Stocks + Equity-and-Index-Options) → one row per fill.

Each parsed fill gets a synthetic ``exec_id`` of the form ``csv:<sha1[:24]>``,
deterministic over (account, symbol, time, side, qty, price). Re-uploading the
same CSV is therefore idempotent: duplicate rows are skipped, not double-counted.

Two ingest-time normalizations keep CSV rows compatible with live fills:

- **UTC times.** Statement timestamps are naive US/Eastern; live fills are stored
  as naive UTC. Statement times are converted to UTC before storage so the FIFO
  round-trip walk orders both sources on one clock.
- **Live-fill dedupe.** Live fills carry real IBKR execIds while CSV rows use
  synthetic ``csv:`` ids — the exec_id dedupe can never catch the overlap, so a
  statement covering live-connected days used to insert those fills twice. A CSV
  row that matches already-stored live fills on (account, symbol, side, qty,
  price, time window) is skipped and reported as ``matched_live``.

Trade-log construction is delegated to the existing
:func:`services.auto_import.rebuild_trade_logs_for` after all executions for a
batch are persisted, so the same FIFO round-trip walk that handles live fills
also handles bulk-imported history.
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

import models
from database import SessionLocal
from services import auto_import

log = logging.getLogger(__name__)


# Asset categories we ingest. Forex/Bonds/Futures live in their own sections in
# the same statement and aren't part of the trade-journal model.
_ALLOWED_ASSETS = {"Stocks", "Equity and Index Options"}

_EASTERN = ZoneInfo("America/New_York")

# A statement 'Order' row aggregates the partial fills of one order; live fills
# within this window of the order timestamp are candidates for the duplicate check.
_LIVE_MATCH_WINDOW = timedelta(minutes=2)
_QTY_TOL = 1e-6
_PRICE_TOL = 0.01


def _parse_dt(s: str) -> datetime:
    """IBKR statement timestamps look like ``2026-03-02, 13:14:04`` (naive Eastern)."""
    return datetime.strptime(s.strip(), "%Y-%m-%d, %H:%M:%S")


def _statement_time_to_utc(dt_eastern: datetime) -> datetime:
    """Statement times are naive US/Eastern; the executions table stores naive UTC
    (live fills arrive tz-aware UTC and are normalized the same way). Mixing the
    two skewed the FIFO walk's time ordering by 4-5 hours."""
    return dt_eastern.replace(tzinfo=_EASTERN).astimezone(timezone.utc).replace(tzinfo=None)


def _parse_float(s: str) -> float:
    if s is None or s == "":
        return 0.0
    return float(s.replace(",", ""))


def _synthesize_exec_id(account: str, symbol: str, time_iso: str, side: str, qty: float, price: float) -> str:
    sig = f"csv|{account}|{symbol}|{time_iso}|{side}|{qty:.8f}|{price:.8f}"
    return "csv:" + hashlib.sha1(sig.encode("utf-8")).hexdigest()[:24]


def parse_activity_statement(content: str) -> Dict[str, Any]:
    """Parse the CSV string into ``{account, trades: [...]}``.

    Each trade dict has: ``asset_category``, ``symbol``, ``date_time`` (raw),
    ``time`` (datetime), ``quantity`` (signed), ``price``, ``commission`` (abs),
    ``realized_pnl``, ``code``.
    """
    if content.startswith("﻿"):
        content = content[1:]

    reader = csv.reader(StringIO(content))
    rows = list(reader)

    account: Optional[str] = None
    for row in rows:
        if len(row) >= 4 and row[0] == "Account Information" and row[1] == "Data" and row[2] == "Account":
            account = row[3].strip()
            break

    trades: List[Dict[str, Any]] = []
    current_header: Optional[Dict[str, int]] = None
    parse_errors: List[str] = []

    for row in rows:
        if not row or row[0] != "Trades":
            continue
        if row[1] == "Header":
            current_header = {name: i for i, name in enumerate(row)}
            continue
        if row[1] != "Data" or current_header is None:
            continue  # SubTotal / Total / Notes
        try:
            if row[current_header["DataDiscriminator"]] != "Order":
                continue
            asset_cat = row[current_header["Asset Category"]]
            if asset_cat not in _ALLOWED_ASSETS:
                continue
            symbol = row[current_header["Symbol"]].strip()
            date_time = row[current_header["Date/Time"]].strip()
            qty_signed = _parse_float(row[current_header["Quantity"]])
            price = _parse_float(row[current_header["T. Price"]])
            commission_raw = _parse_float(row[current_header["Comm/Fee"]])
            realized = _parse_float(row[current_header["Realized P/L"]])
            code = row[current_header["Code"]].strip() if "Code" in current_header else ""
            if not symbol or not date_time or qty_signed == 0:
                continue
            trades.append({
                "asset_category": asset_cat,
                "symbol": symbol,
                "date_time": date_time,
                "time": _parse_dt(date_time),
                "quantity": qty_signed,
                "price": price,
                "commission": abs(commission_raw),
                "realized_pnl": realized,
                "code": code,
            })
        except (KeyError, ValueError) as e:
            parse_errors.append(f"row {row}: {e}")
            continue

    return {"account": account, "trades": trades, "errors": parse_errors}


def _trade_to_exec_dict(trade: Dict[str, Any], account: str) -> Dict[str, Any]:
    qty = trade["quantity"]
    side = "BUY" if qty > 0 else "SELL"
    abs_qty = abs(qty)
    sec_type = "OPT" if trade["asset_category"] == "Equity and Index Options" else "STK"
    multiplier = 100.0 if sec_type == "OPT" else 1.0
    time_dt: datetime = trade["time"]  # naive Eastern, straight from the statement
    # The synthetic id hashes the statement-local time on purpose: it must stay
    # byte-identical to ids from pre-UTC-normalization imports so re-uploads
    # keep deduping against rows already in the DB.
    exec_id = _synthesize_exec_id(account, trade["symbol"], time_dt.isoformat(), side, abs_qty, trade["price"])
    return {
        "exec_id": exec_id,
        "perm_id": None,
        "order_id": None,
        "account": account,
        "symbol": trade["symbol"],
        "sec_type": sec_type,
        "side": side,
        "quantity": abs_qty,
        "price": trade["price"],
        "multiplier": multiplier,
        "commission": trade["commission"],
        # Realized P/L only meaningful on closing legs; leave None for opens.
        "realized_pnl": trade["realized_pnl"] if trade["realized_pnl"] != 0 else None,
        "time": _statement_time_to_utc(time_dt),
        "raw_json": json.dumps({"source": "csv_import", "code": trade["code"], "raw": trade}, default=str),
    }


def _matches_live_fill(db, account: str, exec_dict: Dict[str, Any]) -> bool:
    """True if this CSV order-row duplicates fills already ingested live.

    Matches on the trade facts — same (account, symbol, side) inside a small
    time window — covering either one identical fill, or the whole order's
    partial fills (statement Order rows aggregate them: qty = total,
    T. Price = the fill VWAP).
    """
    t = exec_dict["time"]
    live = (
        db.query(models.Execution)
        .filter(models.Execution.account == account)
        .filter(models.Execution.symbol == exec_dict["symbol"])
        .filter(models.Execution.side == exec_dict["side"])
        .filter(~models.Execution.exec_id.like("csv:%"))
        .filter(models.Execution.time >= t - _LIVE_MATCH_WINDOW)
        .filter(models.Execution.time <= t + _LIVE_MATCH_WINDOW)
        .all()
    )
    if not live:
        return False
    qty, price = exec_dict["quantity"], exec_dict["price"]
    for fill in live:
        if abs(float(fill.quantity) - qty) < _QTY_TOL and abs(float(fill.price) - price) <= _PRICE_TOL:
            return True
    total_qty = sum(float(f.quantity) for f in live)
    if abs(total_qty - qty) < _QTY_TOL:
        vwap = sum(float(f.quantity) * float(f.price) for f in live) / total_qty
        if abs(vwap - price) <= _PRICE_TOL:
            return True
    return False


def import_activity_statement(content: str) -> Dict[str, Any]:
    """Parse + ingest in one shot. Returns a summary suitable for the API response.

    Idempotent on re-upload (dedupe key is the synthetic exec_id), and rows that
    duplicate fills already ingested from the live IBKR feed are skipped and
    reported as ``matched_live`` (see :func:`_matches_live_fill`).

    Rebuild policy: **every** (account, symbol) pair with executions in the DB
    gets re-derived, not just pairs that received new fills. This is the
    "uploading the latest CSV refreshes all my fills" contract — manual edits
    to ``entry_price``/``quantity``/``actions_json``/etc. on previously-imported
    trades are rolled back to IBKR's truth, while user-set ``stop_loss`` and
    ``planned_stop`` survive (the rebuild loop only fills these when empty).
    """
    parsed = parse_activity_statement(content)
    account = parsed["account"]
    if not account:
        raise ValueError("Could not locate 'Account Information' row in CSV — is this an IBKR Activity Statement?")
    trades = parsed["trades"]
    if not trades:
        return {
            "account": account,
            "imported": 0,
            "skipped": 0,
            "matched_live": 0,
            "trade_logs_rebuilt": 0,
            "parse_errors": parsed["errors"],
            "message": "No tradeable rows found in the Trades section.",
        }

    db = SessionLocal()
    try:
        imported = 0
        skipped = 0
        matched_live = 0
        affected_pairs: Set[Tuple[str, str]] = set()

        for t in trades:
            exec_dict = _trade_to_exec_dict(t, account)
            exec_id = exec_dict["exec_id"]
            existing = (
                db.query(models.Execution)
                .filter(models.Execution.exec_id == exec_id)
                .one_or_none()
            )
            if existing is not None:
                skipped += 1
                # Self-heal rows from pre-UTC-normalization imports: same
                # synthetic id, but the stored time is still naive Eastern.
                if existing.time != exec_dict["time"]:
                    existing.time = exec_dict["time"]
                continue
            if _matches_live_fill(db, account, exec_dict):
                matched_live += 1
                continue
            row = models.Execution(
                exec_id=exec_id,
                perm_id=exec_dict["perm_id"],
                order_id=exec_dict["order_id"],
                account=exec_dict["account"],
                symbol=exec_dict["symbol"],
                sec_type=exec_dict["sec_type"],
                side=exec_dict["side"],
                quantity=exec_dict["quantity"],
                price=exec_dict["price"],
                multiplier=exec_dict["multiplier"],
                commission=exec_dict["commission"],
                realized_pnl=exec_dict["realized_pnl"],
                time=exec_dict["time"],
                raw_json=exec_dict["raw_json"],
            )
            db.add(row)
            imported += 1
            affected_pairs.add((account, t["symbol"]))

        db.commit()

        # Rebuild every pair in the account, not just newly-affected ones, so a
        # CSV upload always re-derives all fills from executions. Pairs not in
        # this CSV but still in the DB still get refreshed — that's the point.
        all_pairs: Set[Tuple[str, str]] = set(
            db.query(models.Execution.account, models.Execution.symbol)
            .filter(models.Execution.account == account)
            .distinct()
            .all()
        )
        for acct, sym in all_pairs:
            try:
                auto_import.rebuild_trade_logs_for(db, acct, sym)
            except Exception:
                log.exception("Failed to rebuild trade logs for (%s, %s)", acct, sym)

        return {
            "account": account,
            "imported": imported,
            "skipped": skipped,
            "matched_live": matched_live,
            "trade_logs_rebuilt": len(all_pairs),
            "parse_errors": parsed["errors"],
            "message": (
                f"Imported {imported} new fills ({skipped} duplicates skipped, "
                f"{matched_live} matched live fills); refreshed {len(all_pairs)} symbol(s)."
            ),
        }
    finally:
        db.close()
