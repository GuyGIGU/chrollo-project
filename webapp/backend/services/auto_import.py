"""Turn raw IBKR executions into TradeLog rows.

Strategy
--------
- Every fill is persisted to ``executions`` (dedupe key: ``exec_id``).
- For each (account, symbol), we run a FIFO net-position walk over that symbol's
  executions in time order. A **round-trip** opens when signed qty crosses from 0 to
  non-zero and closes when it returns to 0. Each round-trip maps to a single
  ``trade_logs`` row whose ``actions_json`` contains every leg as an ACTION entry
  compatible with the existing frontend schema.
- Writes are serialized by a single writer thread — callers drop ``ExecEvent`` dicts
  onto an in-process ``queue.Queue``. This keeps SQLAlchemy off the IBKR event loop.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

import models
from database import SessionLocal

log = logging.getLogger(__name__)

# ── Writer thread plumbing ───────────────────────────────────────
_EXEC_Q: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue(maxsize=10_000)
_writer_thread: Optional[threading.Thread] = None
_writer_stop = threading.Event()


def submit_execution(exec_dict: Dict[str, Any]) -> None:
    """Thread-safe: enqueue a raw execution dict for persistence."""
    try:
        _EXEC_Q.put_nowait(exec_dict)
    except queue.Full:
        log.warning("Execution queue full; dropping event %s", exec_dict.get("exec_id"))


def start_writer() -> None:
    global _writer_thread
    if _writer_thread and _writer_thread.is_alive():
        return
    _writer_stop.clear()
    _writer_thread = threading.Thread(
        target=_writer_loop, name="ibkr-db-writer", daemon=True
    )
    _writer_thread.start()


def stop_writer() -> None:
    _writer_stop.set()
    try:
        _EXEC_Q.put_nowait(None)  # sentinel
    except Exception:
        pass
    if _writer_thread:
        _writer_thread.join(timeout=3)


def _writer_loop() -> None:
    while not _writer_stop.is_set():
        try:
            item = _EXEC_Q.get(timeout=0.5)
        except queue.Empty:
            continue
        if item is None:
            return
        try:
            ingest_execution(item)
        except Exception:
            log.exception("Failed to ingest execution %s", item.get("exec_id"))


# ── Ingestion ────────────────────────────────────────────────────
def ingest_execution(exec_dict: Dict[str, Any]) -> None:
    """Upsert one execution and rebuild the trade log for its (account, symbol)."""
    db: Session = SessionLocal()
    try:
        exec_id = exec_dict.get("exec_id")
        if not exec_id:
            return
        existing = (
            db.query(models.Execution).filter(models.Execution.exec_id == exec_id).one_or_none()
        )
        if existing is None:
            row = models.Execution(
                exec_id=exec_id,
                perm_id=exec_dict.get("perm_id"),
                order_id=exec_dict.get("order_id"),
                account=exec_dict.get("account"),
                symbol=exec_dict.get("symbol"),
                sec_type=exec_dict.get("sec_type"),
                side=exec_dict.get("side"),
                quantity=float(exec_dict.get("quantity") or 0),
                price=float(exec_dict.get("price") or 0),
                multiplier=exec_dict.get("multiplier"),
                commission=float(exec_dict.get("commission") or 0),
                realized_pnl=exec_dict.get("realized_pnl"),
                time=exec_dict.get("time") or datetime.utcnow(),
                raw_json=exec_dict.get("raw_json"),
            )
            db.add(row)
        else:
            # Patch commission / realized if the commission report arrived later
            if exec_dict.get("commission"):
                existing.commission = float(exec_dict["commission"])
            if exec_dict.get("realized_pnl") is not None:
                existing.realized_pnl = exec_dict.get("realized_pnl")
        db.commit()

        rebuild_trade_logs_for(db, exec_dict.get("account"), exec_dict.get("symbol"))
    finally:
        db.close()


def rebuild_trade_logs_for(db: Session, account: Optional[str], symbol: Optional[str]) -> None:
    """Re-derive TradeLog rows (source='ibkr') for one (account, symbol) pair.

    Manual trades (source='manual') are never touched.
    """
    if not symbol:
        return

    rows: List[models.Execution] = (
        db.query(models.Execution)
        .filter(models.Execution.account == account)
        .filter(models.Execution.symbol == symbol)
        .order_by(models.Execution.time.asc(), models.Execution.id.asc())
        .all()
    )
    if not rows:
        return

    # Group into round-trips via FIFO net-position walk
    trips = _group_round_trips(rows)
    if not trips:
        return

    # Fetch existing ibkr-sourced trade logs for this pair keyed by opening exec_id
    existing: Dict[str, models.TradeLog] = {}
    tls = (
        db.query(models.TradeLog)
        .filter(models.TradeLog.source == "ibkr")
        .filter(models.TradeLog.ibkr_account == account)
        .filter(models.TradeLog.ticker == symbol)
        .all()
    )
    for tl in tls:
        if tl.actions_json:
            try:
                acts = json.loads(tl.actions_json)
                if acts:
                    key = acts[0].get("exec_id")
                    if key:
                        existing[key] = tl
            except Exception:
                continue

    auto_stop_tls: List[models.TradeLog] = []
    for trip in trips:
        opener_exec_id = trip["legs"][0].exec_id
        tl = existing.get(opener_exec_id)
        if tl is None:
            tl = models.TradeLog(source="ibkr", ticker=symbol, ibkr_account=account)
            db.add(tl)
        flags = _apply_trip_to_trade_log(tl, trip)
        if flags.get("auto_stop"):
            auto_stop_tls.append(tl)
        # Track new entries by opener so we can resolve IDs after flush
        existing[opener_exec_id] = tl
        # Link executions back to this trade log
        for leg in trip["legs"]:
            if leg.trade_log_id is None:
                leg.trade_log_id = tl.id  # may be None first time; fill after flush

    db.flush()
    # Resolve trade_log_id for newly-created rows (IDs now assigned after flush)
    for trip in trips:
        opener_exec_id = trip["legs"][0].exec_id
        tl = existing.get(opener_exec_id)
        if tl is None:
            continue
        for leg in trip["legs"]:
            if leg.trade_log_id != tl.id:
                leg.trade_log_id = tl.id
    # Attach the auto-stop tag to any trade where we inferred a stop. Done after
    # flush so newly-created tl rows already have IDs for the m2m link.
    for tl in auto_stop_tls:
        _ensure_and_attach_tag(db, tl, "auto-stop")
    db.commit()


def _ensure_and_attach_tag(db: Session, tl: models.TradeLog, name: str, category: str = "custom") -> None:
    """Idempotent: create the named tag if missing, attach if not already on tl."""
    tag = db.query(models.Tag).filter(models.Tag.name == name).one_or_none()
    if tag is None:
        tag = models.Tag(name=name, category=category)
        db.add(tag)
        db.flush()
    if tag not in tl.tags:
        tl.tags.append(tag)


def _find_tl_by_opener(db: Session, account: Optional[str], symbol: str, opener_exec_id: str):
    tls = (
        db.query(models.TradeLog)
        .filter(models.TradeLog.source == "ibkr")
        .filter(models.TradeLog.ibkr_account == account)
        .filter(models.TradeLog.ticker == symbol)
        .all()
    )
    for tl in tls:
        if tl.actions_json:
            try:
                acts = json.loads(tl.actions_json)
                if acts and acts[0].get("exec_id") == opener_exec_id:
                    return tl
            except Exception:
                continue
    return None


def _group_round_trips(rows: Iterable[models.Execution]) -> List[Dict[str, Any]]:
    """Walk executions; whenever signed position returns to 0, close a round-trip."""
    trips: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    net_qty = 0.0

    for r in rows:
        signed = float(r.quantity) * (1 if r.side == "BUY" else -1)

        if current is None and net_qty == 0 and signed != 0:
            current = {"direction": "L" if signed > 0 else "S", "legs": []}

        if current is not None:
            current["legs"].append(r)

        prev = net_qty
        net_qty += signed

        # Closed round-trip
        if current is not None and prev != 0 and net_qty == 0:
            trips.append(current)
            current = None
        # Flipped through zero (e.g. long 100 → sell 300 → short 200). Close the long
        # trip at the zero-crossing, start a new short trip with the residual.
        elif current is not None and prev * net_qty < 0:
            # Split the last leg at the zero crossing. For simplicity we close the current
            # trip including the whole flip leg; the next leg starts a new trip. This is
            # imperfect but rare for a discretionary trader.
            trips.append(current)
            current = {"direction": "L" if net_qty > 0 else "S", "legs": [r]}

    if current is not None:
        trips.append(current)  # still-open round-trip

    return trips


def _apply_trip_to_trade_log(tl: models.TradeLog, trip: Dict[str, Any]) -> Dict[str, Any]:
    """Populate a TradeLog from a round-trip's legs.

    Returns a flag dict (e.g. ``{"auto_stop": True}``) so the caller can run
    post-processing — currently the auto-stop tag attachment.

    Smart bits beyond a naive opener=first-leg implementation:
    - **Entry VWAP**: ``entry_price`` is the volume-weighted average of all
      opener-side legs, not just the first fill. Matters for scale-ins.
    - **Total opening qty**: ``quantity`` is the sum of opener-side qty, so a
      scaled-in 50+50+50+50 entry reports as 200, not 50.
    - **Exit VWAP**: ``exit_price`` on closed trips is the VWAP of closer-side
      legs (was the last leg's price).
    - **Auto-stop heuristic**: when a trip closes at a loss, was held under
      24h, and the user has set neither ``stop_loss`` nor ``planned_stop``,
      we infer the stop as the exit VWAP and the caller tags the trade
      ``auto-stop`` so the inferred value is distinguishable from a typed
      planned stop. Idempotent — once ``stop_loss`` is non-zero, subsequent
      rebuilds skip the inference.
    """
    legs: List[models.Execution] = trip["legs"]
    direction = trip["direction"]
    opener_side = "BUY" if direction == "L" else "SELL"
    closer_side = "SELL" if direction == "L" else "BUY"

    # Walk opener / closer legs separately to compute VWAPs and timestamps.
    opener_qty = 0.0
    opener_cost = 0.0
    opener_times: List[datetime] = []
    closer_qty = 0.0
    closer_cost = 0.0
    closer_times: List[datetime] = []
    commissions = 0.0
    mult_seen: Optional[float] = None
    for leg in legs:
        q = float(leg.quantity)
        p = float(leg.price)
        if mult_seen is None and leg.multiplier:
            mult_seen = float(leg.multiplier)
        if leg.side == opener_side:
            opener_qty += q
            opener_cost += q * p
            if isinstance(leg.time, datetime):
                opener_times.append(leg.time)
        elif leg.side == closer_side:
            closer_qty += q
            closer_cost += q * p
            if isinstance(leg.time, datetime):
                closer_times.append(leg.time)
        commissions += float(leg.commission or 0)

    mult = mult_seen if mult_seen is not None else 1.0
    entry_vwap = (opener_cost / opener_qty) if opener_qty > 0 else float(legs[0].price)
    exit_vwap = (closer_cost / closer_qty) if closer_qty > 0 else None

    opening_leg = legs[0]
    tl.direction = direction
    tl.opening_date = (
        opening_leg.time.date().isoformat() if isinstance(opening_leg.time, datetime) else str(opening_leg.time)
    )
    tl.entry_price = entry_vwap
    tl.quantity = int(round(opener_qty)) if opener_qty > 0 else int(abs(float(opening_leg.quantity)))
    tl.position_size = entry_vwap * opener_qty * mult
    tl.commissions = commissions

    # Net signed qty across all legs determines whether the trip is closed.
    net_qty = opener_qty - closer_qty  # magnitude; sign comes from direction
    tl.remaining_qty = int(round(net_qty)) if direction == "L" else -int(round(net_qty))

    # P&L from cash flow (commissions netted)
    cash = 0.0
    for leg in legs:
        leg_sign = 1 if leg.side == "BUY" else -1
        leg_mult = float(leg.multiplier) if leg.multiplier else 1.0
        cash += -float(leg.quantity) * leg_sign * float(leg.price) * leg_mult

    flags: Dict[str, Any] = {}
    if abs(net_qty) < 1e-9:
        # Closed round-trip
        tl.pnl = cash - commissions
        tl.exit_price = exit_vwap
        last_close = max(closer_times) if closer_times else None
        tl.closing_date = (
            last_close.date().isoformat() if isinstance(last_close, datetime) else None
        )

        # Auto-stop heuristic — only when truly empty and the trip was a quick loser.
        held_seconds = (
            (max(closer_times) - min(opener_times)).total_seconds()
            if opener_times and closer_times else float("inf")
        )
        already_set = bool((tl.stop_loss and tl.stop_loss > 0) or (tl.planned_stop and tl.planned_stop > 0))
        if (
            tl.pnl is not None
            and tl.pnl < 0
            and exit_vwap is not None
            and held_seconds <= 24 * 3600
            and not already_set
        ):
            tl.stop_loss = exit_vwap
            flags["auto_stop"] = True
        elif not tl.stop_loss:
            tl.stop_loss = 0.0
    else:
        tl.pnl = None
        tl.exit_price = None
        tl.closing_date = None
        if not tl.stop_loss:
            tl.stop_loss = 0.0

    # Rebuild actions_json so the frontend shows every leg
    actions: List[Dict[str, Any]] = []
    for leg in legs:
        is_opener = leg.side == opener_side
        actions.append({
            "id": leg.id,
            "exec_id": leg.exec_id,
            "type": "ENTRY" if is_opener else "EXIT",
            "date": leg.time.isoformat() if isinstance(leg.time, datetime) else str(leg.time),
            "side": leg.side,
            "quantity": float(leg.quantity),
            "price": float(leg.price),
            "fee": float(leg.commission or 0),
        })
    tl.actions_json = json.dumps(actions)

    return flags


def backfill_from_db() -> None:
    """Re-derive trade logs from every existing execution. Safe to call on startup."""
    db: Session = SessionLocal()
    try:
        pairs: List[Tuple[Optional[str], str]] = (
            db.query(models.Execution.account, models.Execution.symbol)
            .distinct()
            .all()
        )
        for account, symbol in pairs:
            rebuild_trade_logs_for(db, account, symbol)
    finally:
        db.close()
