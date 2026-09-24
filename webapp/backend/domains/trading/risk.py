"""Single source of truth for the price-dependent open-trade risk overlay.

This is a faithful, stdlib-only Python port of the JavaScript risk math that
historically lived in ``webapp/frontend/src/features/journal/model/tradeTableUtils.js``
(``deriveTradeRow`` + ``summarizeFillLedger``). The JS is the live oracle the
trader has been reading, so this port is PARITY-FIRST: it reproduces the JS
outputs field-for-field (see ``tests/test_trade_risk.py``), with two deliberate
changes that were settled before the port:

  * The R-multiple (``rValue``) anchors 1R to ``planned_stop`` when recorded,
    else the working ``stop_loss``, else ``None`` (never fabricated). Distance to
    stop (``distToStopPct`` / ``rToStop``) and the stop-risk tone keep using the
    CURRENT working ``stop_loss`` on both sides, so they stay numerically
    identical to the JS for any trade without a separate ``planned_stop``.
  * Two new outputs: ``pnlPct`` (P&L as a percent of deployed capital) and
    ``distToStopR`` (distance to the working stop expressed in R = ``rToStop``,
    surfaced explicitly for display).

DEPENDENCY-FREE BY DESIGN. No FastAPI / SQLAlchemy / pandas / ``config`` imports
and no module-level settings reads — so it resolves identically from the backend
cwd (``webapp/backend``) and from the repo-root pytest gate, sidestepping the
config-vs-cwd shadowing trap (conventions AP-3). Output keys are camelCase to
match the existing frontend consumer contract; every numeric is coerced to a
finite float or ``None`` before return, so NaN/inf never reach the JSON layer.

The price-INDEPENDENT fill ledger (``summarize_fill_ledger``) is ported here only
because deriving open-trade risk needs it; the JS ``summarizeFillLedger`` stays
in the frontend because it also feeds the fill-SAVE write path (out of scope for
this read-only layer). The two are reconciled by the parity test, not shared.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date
from typing import Any, Dict, List, Optional

EPS = 1e-9

# --- JS numeric-idiom helpers --------------------------------------------------
# JS leans on `Number(x) || d`, `parseFloat(x) || d`, and bare truthiness where 0
# is FALSY. A literal float()/or port diverges on exactly the blank/zero boundary
# cases the trader's R and distance-to-stop depend on, so these are explicit.

_PARSEFLOAT_RE = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")


def _js_number(x: Any) -> float:
    """Mimic JS ``Number(x)``: '' / whitespace / None -> 0, junk -> NaN."""
    if x is None:
        return 0.0
    if isinstance(x, bool):
        return 1.0 if x else 0.0
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return 0.0
        try:
            return float(s)
        except ValueError:
            return math.nan
    return math.nan


def _js_parse_float(x: Any) -> float:
    """Mimic JS ``parseFloat(x)``: tolerates trailing junk ('12abc' -> 12)."""
    if isinstance(x, bool):
        return math.nan
    if isinstance(x, (int, float)):
        return float(x)
    if x is None:
        return math.nan
    m = _PARSEFLOAT_RE.match(str(x).strip())
    if not m:
        return math.nan
    try:
        return float(m.group(0))
    except ValueError:
        return math.nan


def _num_or(x: Any, default: Optional[float] = 0.0) -> Optional[float]:
    """JS ``Number(x) || default`` — 0/NaN/''/None collapse to default."""
    v = _js_number(x)
    if v == 0.0 or math.isnan(v):
        return default
    return v


def _parse_float_or(x: Any, default: float = 0.0) -> float:
    """JS ``parseFloat(x) || default``."""
    v = _js_parse_float(x)
    if v == 0.0 or math.isnan(v):
        return default
    return v


def _finite_or_none(x: Any) -> Optional[float]:
    """Coerce to a finite float, or None — NaN/inf must never reach JSON."""
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    return xf if math.isfinite(xf) else None


def _stop_value(raw: Any) -> Optional[float]:
    """Port of the JS ``stop && Number(stop) !== 0 ? Number(stop) : null`` guard:
    a stop resolves to None when its numeric value is 0 / blank / non-numeric."""
    v = _js_number(raw)
    if math.isnan(v) or v == 0.0:
        return None
    return v


# --- symbol + direction --------------------------------------------------------

_HUMAN_OPTION_RE = re.compile(r"^([A-Z.]+) (\d{1,2})([A-Z]{3})(\d{2}) [\d.]+ [CP]$")
_IBKR_LOCAL_OPTION_RE = re.compile(r"^([A-Z.]+) (\d{6})[CP]\d{8}$")
_OCC_OPTION_RE = re.compile(r"^([A-Z.]{1,6})(\d{6})[CP]\d{8}$")

# Explicit month map (not strptime %b, which is locale-dependent).
_OPTION_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def is_option_symbol(symbol: Any) -> bool:
    if not symbol:
        return False
    value = re.sub(r"\s+", " ", str(symbol).strip().upper())
    compact = re.sub(r"\s+", "", value)
    # fullmatch / anchored ^...$ — Python $ also matches before a trailing newline,
    # so the patterns use explicit ^...$ via fullmatch to avoid a stray-newline match.
    return bool(
        _HUMAN_OPTION_RE.fullmatch(value)
        or _IBKR_LOCAL_OPTION_RE.fullmatch(value)
        or _OCC_OPTION_RE.fullmatch(compact)
    )


def option_expiry(symbol: Any) -> Optional[date]:
    """Expiry date parsed from an option symbol, or ``None`` (non-options too).

    Recognizes the same three forms as ``is_option_symbol`` ("UNG 17JUL26 11 C",
    IBKR local "UNG 260717C00011000", OCC compact); an impossible calendar date
    degrades to ``None`` (unknown), never an exception.
    """
    if not symbol:
        return None
    value = re.sub(r"\s+", " ", str(symbol).strip().upper())
    compact = re.sub(r"\s+", "", value)
    try:
        m = _HUMAN_OPTION_RE.fullmatch(value)
        if m:
            month = _OPTION_MONTHS.get(m.group(3))
            return date(2000 + int(m.group(4)), month, int(m.group(2))) if month else None
        m = _IBKR_LOCAL_OPTION_RE.fullmatch(value) or _OCC_OPTION_RE.fullmatch(compact)
        if m:
            digits = m.group(2)
            return date(2000 + int(digits[:2]), int(digits[2:4]), int(digits[4:6]))
    except ValueError:
        return None
    return None


def infer_direction(trade: Dict[str, Any]) -> str:
    direction = str(trade.get("direction") or "").upper()
    if direction in ("L", "LONG"):
        return "LONG"
    if direction in ("S", "SHORT"):
        return "SHORT"
    entry = _js_number(trade.get("entry_price"))
    stop = _js_number(trade.get("stop_loss"))
    if not math.isnan(entry) and not math.isnan(stop) and stop != 0:
        return "LONG" if stop < entry else "SHORT"
    return "LONG"


def parse_actions(actions_json: Any) -> List[Dict[str, Any]]:
    """JS ``parseActions`` + a dict-element guard.

    null / malformed / non-array -> []. A valid array is kept, but non-object
    elements are dropped: SQLite ``Text`` affinity stores anything, so a
    hand-edited/imported ``actions_json`` like ``[1, 2]`` or ``["BUY"]`` would
    otherwise reach ``{**a}`` and raise out of the per-trade loop, 500-ing the
    whole endpoint. The JS ledger silently skips such cells (their numeric reads
    coerce to 0 and drop out), so filtering here preserves parity AND degrades a
    poisoned cell to "one trade ignores it" instead of a crash.
    """
    if not actions_json:
        return []
    try:
        actions = json.loads(actions_json) if isinstance(actions_json, str) else actions_json
    except (TypeError, ValueError):
        return []
    if not isinstance(actions, list):
        return []
    return [a for a in actions if isinstance(a, dict)]


def _normalize_action_side(action: Dict[str, Any], open_side: str, close_side: str) -> str:
    raw_side = str(action.get("side") or "").upper()
    raw_type = str(action.get("type") or "").upper()
    raw_role = str(action.get("role") or "").upper()
    if raw_side in ("BUY", "SELL"):
        return raw_side
    if raw_type in ("BUY", "SELL"):
        return raw_type
    if raw_type == "ENTRY" or raw_role == "ENTRY":
        return open_side
    if raw_type == "EXIT" or raw_role == "EXIT":
        return close_side
    return raw_type


# --- fill ledger (price-independent) -------------------------------------------

def summarize_fill_ledger(fills: List[Dict[str, Any]], direction: str, multiplier: float = 1.0) -> Dict[str, Any]:
    """Faithful port of JS ``summarizeFillLedger`` — an order-dependent state
    machine. The statement order (avg-cost read BEFORE the openCost/position
    decrements) and the ``<= EPS`` / ``> EPS`` comparisons are load-bearing for
    the VWAP / realized-vs-unrealized split; do not reorder or vectorize."""
    is_long = direction == "LONG"
    open_side = "BUY" if is_long else "SELL"
    close_side = "SELL" if is_long else "BUY"

    position = 0.0
    open_cost = 0.0
    open_fees = 0.0
    cycle_open_qty = 0.0
    cycle_open_cash = 0.0
    cycle_close_qty = 0.0
    cycle_close_cash = 0.0
    cycle_realized_pnl = 0.0
    cycle_opening_date: Optional[str] = None
    cycle_closing_date: Optional[str] = None
    last_cycle_open_qty = 0.0
    last_cycle_entry: Optional[float] = None
    last_cycle_opening_date: Optional[str] = None
    last_cycle_closing_date: Optional[str] = None
    realized_pnl = 0.0
    commissions = 0.0
    any_close = False

    for fill in fills:
        raw_side = str(fill.get("side") or "").upper()
        raw_type = str(fill.get("type") or "").upper()
        raw_role = str(fill.get("role") or "").upper()
        if raw_side in ("BUY", "SELL"):
            side = raw_side
        elif raw_type in ("BUY", "SELL"):
            side = raw_type
        elif raw_type == "ENTRY" or raw_role == "ENTRY":
            side = open_side
        elif raw_type == "EXIT" or raw_role == "EXIT":
            side = close_side
        else:
            side = ""
        quantity = _parse_float_or(fill.get("quantity"), 0.0)
        price = _parse_float_or(fill.get("price"), 0.0)
        fee = _parse_float_or(fill.get("fee"), 0.0)
        date = str(fill.get("date") or "")[:10]
        if quantity <= 0 or price <= 0:
            commissions += fee
            continue

        commissions += fee

        if side == open_side:
            if position <= EPS:
                position = 0.0
                open_cost = 0.0
                open_fees = 0.0
                cycle_open_qty = 0.0
                cycle_open_cash = 0.0
                cycle_close_qty = 0.0
                cycle_close_cash = 0.0
                cycle_realized_pnl = 0.0
                cycle_opening_date = None
                cycle_closing_date = None
            position += quantity
            open_cost += quantity * price * multiplier
            open_fees += fee
            cycle_open_qty += quantity
            cycle_open_cash += quantity * price * multiplier
            if date and (not cycle_opening_date or date < cycle_opening_date):
                cycle_opening_date = date
        elif side == close_side:
            closed_qty = min(quantity, position)
            cycle_close_qty += closed_qty
            cycle_close_cash += closed_qty * price * multiplier
            any_close = any_close or closed_qty > 0
            if date and (not cycle_closing_date or date > cycle_closing_date):
                cycle_closing_date = date

            if closed_qty > 0 and position > EPS:
                avg_cost = open_cost / position
                if is_long:
                    gross = (price * multiplier - avg_cost) * closed_qty
                else:
                    gross = (avg_cost - price * multiplier) * closed_qty
                open_fee_share = open_fees * (closed_qty / position)
                fill_pnl = gross - open_fee_share - fee
                realized_pnl += fill_pnl
                cycle_realized_pnl += fill_pnl
                open_fees -= open_fee_share
                open_cost -= avg_cost * closed_qty
                position -= closed_qty
            else:
                realized_pnl -= fee
                cycle_realized_pnl -= fee

            if position <= EPS:
                last_cycle_open_qty = cycle_open_qty
                last_cycle_entry = (
                    cycle_open_cash / (cycle_open_qty * multiplier) if cycle_open_qty > 0 else last_cycle_entry
                )
                last_cycle_opening_date = cycle_opening_date
                last_cycle_closing_date = cycle_closing_date
                position = 0.0
                open_cost = 0.0
                open_fees = 0.0

    current_entry = open_cost / (position * multiplier) if position > EPS else last_cycle_entry
    return {
        "anyClose": any_close,
        "commissions": commissions,
        "currentOpenFees": open_fees,
        "entryPrice": current_entry,
        "exitPrice": (cycle_close_cash / (cycle_close_qty * multiplier)) if cycle_close_qty > 0 else None,
        "openingDate": cycle_opening_date if position > EPS else last_cycle_opening_date,
        "closingDate": last_cycle_closing_date if (position <= EPS and any_close) else None,
        "openQty": position if position > EPS else last_cycle_open_qty,
        "position": position,
        "riskQty": cycle_open_qty if position > EPS else last_cycle_open_qty,
        "activeCycleRealizedPnl": cycle_realized_pnl,
        "realizedPnl": realized_pnl,
        "cycleCloseCash": cycle_close_cash,
        "cycleCloseQty": cycle_close_qty,
    }


# --- price-dependent overlay helpers -------------------------------------------

def _get_exit_price(close_cash, close_qty, live_price, live_source, multiplier, position, trade):
    if position > 0 and live_price is not None:
        return live_price, live_source
    if close_qty > 0:
        return close_cash / (close_qty * multiplier), "fills"
    if trade.get("exit_price") is not None:
        return _js_number(trade.get("exit_price")), "fills"
    return None, None


def _calculate_pnl(entry_vwap, is_long, ledger, live_price, multiplier, position, trade):
    if position > 0 and live_price is not None and entry_vwap is not None:
        if is_long:
            unrealized = (live_price - entry_vwap) * position * multiplier
        else:
            unrealized = (entry_vwap - live_price) * position * multiplier
        return ledger["activeCycleRealizedPnl"] + unrealized - ledger["currentOpenFees"]
    if position > 0:
        return ledger["activeCycleRealizedPnl"] if ledger["activeCycleRealizedPnl"] != 0 else None
    if ledger["anyClose"]:
        return ledger["realizedPnl"]
    return _js_number(trade.get("pnl")) if trade.get("pnl") is not None else None


def _get_status(close_qty, has_closed, initial_qty, pnl, position):
    if position > 0 and close_qty > 0:
        return "partial"
    if position > 0:
        return "open"
    if has_closed:
        return "win" if (pnl is not None and pnl > 0) else "loss"
    if initial_qty > 0:
        return "open"
    return "draft"


def _risk_tone_for(r_to_stop) -> Optional[str]:
    if r_to_stop is None or not math.isfinite(r_to_stop):
        return None
    if r_to_stop <= 0:
        return "breached"
    if r_to_stop <= 0.25:
        return "danger"
    if r_to_stop <= 0.5:
        return "warning"
    return None


def _finite_positive(value) -> Optional[float]:
    v = _js_number(value)
    return v if (not math.isnan(v) and math.isfinite(v) and v > 0) else None


def _build_target_ladder(current_exit, is_long, risk_distance, trade) -> List[Dict[str, Any]]:
    targets = []
    for index in (1, 2, 3, 4, 5):
        price = _finite_positive(trade.get(f"t{index}_price"))
        if price is None:
            continue
        qty = _finite_positive(trade.get(f"t{index}_qty"))
        if current_exit is not None:
            signed_distance = (price - current_exit) if is_long else (current_exit - price)
            hit = (current_exit >= price) if is_long else (current_exit <= price)
        else:
            signed_distance = None
            hit = False
        targets.append({
            "index": index,
            "label": f"T{index}",
            "price": price,
            "qty": qty,
            "hit": hit,
            "isNext": False,
            "distToTargetPct": (signed_distance / current_exit * 100)
            if (signed_distance is not None and current_exit) else None,
            "rToTarget": (signed_distance / risk_distance)
            if (signed_distance is not None and risk_distance) else None,
        })

    next_index = next((t["index"] for t in targets if not t["hit"]), None)
    for t in targets:
        t["isNext"] = t["index"] == next_index
    return targets


def _coerce_target(t: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "index": t["index"],
        "label": t["label"],
        "price": _finite_or_none(t["price"]),
        "qty": _finite_or_none(t["qty"]),
        "hit": bool(t["hit"]),
        "isNext": bool(t["isNext"]),
        "distToTargetPct": _finite_or_none(t["distToTargetPct"]),
        "rToTarget": _finite_or_none(t["rToTarget"]),
    }


# --- main entry ----------------------------------------------------------------

def derive_trade_risk(
    trade: Dict[str, Any],
    live_price: Optional[float] = None,
    live_source: Optional[str] = None,
) -> Dict[str, Any]:
    """Derive the risk overlay for one trade given a single live price.

    Mirrors the JS ``deriveTradeRow`` (where ``priceFor`` returned
    ``{price, source}``) — ``live_price=None`` degrades exactly like a missing
    quote. Output keys are camelCase to match the frontend consumer contract.
    """
    # Coerce the live price once at the boundary (the JS oracle coerces a string
    # via arithmetic; here a string/NaN/inf collapses to a usable float or None),
    # so the single-source-of-truth degrades like a missing quote regardless of
    # caller hygiene rather than raising mid-derivation.
    live_price = _finite_or_none(live_price)
    direction = infer_direction(trade)
    is_long = direction == "LONG"
    multiplier = 100.0 if is_option_symbol(trade.get("ticker")) else 1.0
    open_side = "BUY" if is_long else "SELL"
    close_side = "SELL" if is_long else "BUY"

    raw_actions = parse_actions(trade.get("actions_json"))
    actions = [
        {**a, "side": _normalize_action_side(a, open_side, close_side)} for a in raw_actions
    ]
    includes_opener = any(a["side"] == open_side for a in actions)
    initial_qty = _js_number(trade.get("quantity"))
    if math.isnan(initial_qty):
        initial_qty = 0.0
    if includes_opener:
        fallback_actions = actions
    else:
        fallback_actions = [
            {
                "side": open_side,
                "quantity": initial_qty,
                "price": _num_or(trade.get("entry_price"), 0.0),
                "fee": _num_or(trade.get("commissions"), 0.0),
                "date": trade.get("opening_date"),
            },
            *actions,
        ]
    ledger = summarize_fill_ledger(fallback_actions, direction, multiplier)

    entry_vwap = ledger["entryPrice"] if ledger["entryPrice"] is not None else _num_or(trade.get("entry_price"), None)
    position = ledger["position"]
    open_qty = ledger["openQty"]
    risk_qty = _num_or(ledger["riskQty"], None) or (open_qty if open_qty else None) or initial_qty
    total_worth = (entry_vwap * open_qty * multiplier) if (entry_vwap is not None and open_qty) else None

    current_exit, current_exit_source = _get_exit_price(
        ledger["cycleCloseCash"], ledger["cycleCloseQty"], live_price, live_source, multiplier, position, trade,
    )
    pnl = _calculate_pnl(entry_vwap, is_long, ledger, live_price, multiplier, position, trade)

    # Two stop bases: the working stop drives distance/tone (what will execute);
    # the R basis anchors 1R to planned_stop when recorded (original risk).
    working_stop = _stop_value(trade.get("stop_loss"))
    r_basis_stop = _stop_value(trade.get("planned_stop"))
    if r_basis_stop is None:
        r_basis_stop = working_stop

    stop_pct = (
        abs(entry_vwap - working_stop) / entry_vwap * 100
        if (working_stop is not None and entry_vwap is not None and entry_vwap != 0)
        else None
    )
    working_risk_distance = (
        abs(entry_vwap - working_stop) if (working_stop is not None and entry_vwap is not None) else None
    )
    r_basis_risk_distance = (
        abs(entry_vwap - r_basis_stop) if (r_basis_stop is not None and entry_vwap is not None) else None
    )

    # R-multiple of P&L: anchored to the original (planned) risk.
    r_value = (
        pnl / (r_basis_risk_distance * risk_qty * multiplier)
        if (r_basis_risk_distance and risk_qty and pnl is not None)
        else None
    )

    # Distance to the CURRENT working stop, in % and in R (price-based so it stays
    # exact on scaled-out positions). Identical to the JS for any trade without a
    # distinct planned_stop.
    dist_to_stop = (
        ((current_exit - working_stop) if is_long else (working_stop - current_exit))
        if (current_exit is not None and working_stop is not None)
        else None
    )
    dist_to_stop_pct = (
        dist_to_stop / current_exit * 100 if (dist_to_stop is not None and current_exit) else None
    )
    r_to_stop = dist_to_stop / working_risk_distance if (dist_to_stop is not None and working_risk_distance) else None
    stop_risk_tone = _risk_tone_for(r_to_stop)

    # NEW: P&L as a percent of deployed capital (pnlPct * totalWorth == pnl).
    pnl_pct = (pnl / total_worth * 100) if (pnl is not None and total_worth) else None

    target_ladder = _build_target_ladder(current_exit, is_long, r_basis_risk_distance, trade)
    next_target = next((t for t in target_ladder if t["isNext"]), None)
    dist_to_target_pct = next_target["distToTargetPct"] if next_target else None
    status = _get_status(ledger["cycleCloseQty"], ledger["anyClose"], initial_qty, pnl, position)

    if position <= 0 and ledger["closingDate"]:
        exit_date = ledger["closingDate"]
    elif position <= 0:
        exit_date = trade.get("closing_date") or None
    else:
        exit_date = None

    return {
        "distToStopPct": _finite_or_none(dist_to_stop_pct),
        "distToStopR": _finite_or_none(r_to_stop),
        "distToTargetPct": _finite_or_none(dist_to_target_pct),
        "direction": direction,
        "entryVwap": _finite_or_none(entry_vwap),
        "exitDate": exit_date,
        "isLong": is_long,
        "multiplier": multiplier,
        "nextTarget": _coerce_target(next_target) if next_target else None,
        "openQty": _finite_or_none(open_qty),
        "pnl": _finite_or_none(pnl),
        "pnlPct": _finite_or_none(pnl_pct),
        "position": _finite_or_none(position),
        "riskDistance": _finite_or_none(r_basis_risk_distance),
        "riskQty": _finite_or_none(risk_qty),
        "rValue": _finite_or_none(r_value),
        "rToStop": _finite_or_none(r_to_stop),
        "status": status,
        "stopPct": _finite_or_none(stop_pct),
        "stopRiskTone": stop_risk_tone,
        "stopVal": _finite_or_none(working_stop),
        "plannedStopVal": _finite_or_none(r_basis_stop),
        "targetLadder": [_coerce_target(t) for t in target_ladder],
        "totalExit": _finite_or_none(ledger["cycleCloseCash"]) if ledger["cycleCloseQty"] > 0 else None,
        "totalWorth": _finite_or_none(total_worth),
        "currentExit": _finite_or_none(current_exit),
        "currentExitSource": current_exit_source,
    }


def build_open_risk_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate the per-trade rows into the PortfolioStatusBar open-risk strip.

    Computed over server-derived rows only (single source of truth) — the client
    never re-sums. P&L totals over rows that actually have a value; the at-risk
    count is over rows with a breached/danger/warning tone.
    """
    open_rows = [r for r in rows if r.get("status") in ("open", "partial")]
    pnls = [r["pnl"] for r in open_rows if r.get("pnl") is not None]
    total_unrealized = sum(pnls) if pnls else None
    n_priced = sum(1 for r in open_rows if r.get("currentExit") is not None)
    breached = sum(1 for r in open_rows if r.get("stopRiskTone") == "breached")
    danger = sum(1 for r in open_rows if r.get("stopRiskTone") == "danger")
    warning = sum(1 for r in open_rows if r.get("stopRiskTone") == "warning")
    return {
        "nOpen": len(open_rows),
        "nPriced": n_priced,
        "totalUnrealizedPnl": _finite_or_none(total_unrealized),
        "nBreached": breached,
        "nDanger": danger,
        "nWarning": warning,
        "nAtRisk": breached + danger + warning,
    }
