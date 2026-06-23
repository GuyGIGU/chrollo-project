"""Parse an IBKR Activity Statement CSV and feed it into the auto-import pipeline.

The Activity Statement is a multi-section CSV — each row is tagged with a section
name and a discriminator (Header/Data/SubTotal/Total/Notes). We only care about:

- ``Account Information`` → pulls the account number once.
- ``Trades`` (Stocks + Equity-and-Index-Options) → one row per fill.

Each parsed fill gets a synthetic ``exec_id`` of the form ``csv:<sha1[:24]>``,
deterministic over (account, symbol, time, side, qty, price). Re-uploading the
same CSV is therefore idempotent: duplicate rows are skipped, not double-counted.

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
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional, Set, Tuple

import models
from database import SessionLocal
from services import auto_import
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

log = logging.getLogger(__name__)


# Asset categories we ingest. Forex/Bonds/Futures live in their own sections in
# the same statement and aren't part of the trade-journal model.
_ALLOWED_ASSETS = {"Stocks", "Equity and Index Options"}


def _parse_dt(s: str) -> datetime:
    """IBKR statement timestamps look like ``2026-03-02, 13:14:04`` (Eastern Time)."""
    return datetime.strptime(s.strip(), "%Y-%m-%d, %H:%M:%S")


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
    time_dt: datetime = trade["time"]
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
        "time": time_dt,
        "raw_json": json.dumps({"source": "csv_import", "code": trade["code"], "raw": trade}, default=str),
    }


def import_activity_statement(content: str) -> Dict[str, Any]:
    """Parse + ingest in one shot. Returns a summary suitable for the API response.

    Idempotent on re-upload (dedupe key is the synthetic exec_id).

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
            "trade_logs_rebuilt": 0,
            "parse_errors": parsed["errors"],
            "message": "No tradeable rows found in the Trades section.",
        }

    db = SessionLocal()
    try:
        imported = 0
        skipped = 0
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

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("Duplicate execution encountered during CSV import") from exc
        except SQLAlchemyError:
            db.rollback()
            log.exception("Failed to persist CSV executions")
            raise

        # Rebuild every pair in the account, not just newly-affected ones, so a
        # CSV upload always re-derives all fills from executions. Pairs not in
        # this CSV but still in the DB still get refreshed — that's the point.
        all_pairs: Set[Tuple[str, str]] = set(
            db.query(models.Execution.account, models.Execution.symbol)
            .filter(models.Execution.account == account)
            .distinct()
            .all()
        )
        rebuild_errors: List[Dict[str, str]] = []
        for acct, sym in all_pairs:
            try:
                auto_import.rebuild_trade_logs_for(db, acct, sym)
            except Exception as exc:
                db.rollback()
                log.exception("Failed to rebuild trade logs for (%s, %s)", acct, sym)
                rebuild_errors.append({
                    "account": acct or "",
                    "symbol": sym or "",
                    "error": str(exc),
                })

        rebuilt = len(all_pairs) - len(rebuild_errors)
        message = f"Imported {imported} new fills ({skipped} duplicates skipped); refreshed {rebuilt} symbol(s)."
        if rebuild_errors:
            message += f" {len(rebuild_errors)} symbol(s) need attention."

        return {
            "account": account,
            "imported": imported,
            "skipped": skipped,
            "trade_logs_rebuilt": rebuilt,
            "trade_logs_failed": len(rebuild_errors),
            "rebuild_errors": rebuild_errors[:10],
            "parse_errors": parsed["errors"],
            "message": message,
        }
    finally:
        db.close()
