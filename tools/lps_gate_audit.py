"""Read-only LPS gate audit harness.

This tool replays the current structure reader up to Phase B, then diagnoses the
LPS/Test layer with ``detect_lps(..., diagnose=True)``. It is meant for
calibration work: which gates reject candidate windows, and what firing deltas a
small settings override would create.

Examples:
    python -m tools.lps_gate_audit --tickers NMM --as-of 2026-06-08
    python -m tools.lps_gate_audit --source screener --limit 200
    python -m tools.lps_gate_audit --source screener --limit 200 ^
        --override LPS_VOL_CONTRACTION_MAX=0.95
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from core.pipeline.evaluation import apply_baseline_filters
from core.structure import calculate_atr
from core.structure import bricks
from core.structure.lps import detect_lps

_MAX_ANCHORS = 64
_DB_PATH = ROOT / "webapp" / "backend" / "trading_journal.db"
_AUDIT_DIR = ROOT / "output" / "audits"

_LPS_CORE_MATRIX: dict[str, dict[str, Any]] = {
    "descent_gates_off": {
        "LPS_MIN_DESCENT_FRAC": 0.0,
        "LPS_MIN_HIGH_DESCENT_FRAC": 0.0,
    },
    "volume_soft": {
        "LPS_VOL_CONTRACTION_MAX": 1.10,
    },
    "spread_soft": {
        "LPS_SPREAD_MAX_PROFILE_MULT": 99.0,
        "LPS_SPREAD_EXPANSION_MAX_PROFILE": 99.0,
    },
    "terminal_low_tolerance_soft": {
        "LPS_TERMINAL_LOW_TOL_PROFILE": 1.0,
    },
    "pullback_profile_soft": {
        "LPS_PULLBACK_PROFILE_MIN": 0.0,
        "LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R": 0.0,
        "LPS_PULLBACK_PROFILE_MAX": 99.0,
    },
    "combined_adaptive_soft": {
        "LPS_SPREAD_MAX_PROFILE_MULT": 99.0,
        "LPS_SPREAD_EXPANSION_MAX_PROFILE": 99.0,
        "LPS_TERMINAL_LOW_TOL_PROFILE": 1.0,
        "LPS_PULLBACK_PROFILE_MIN": 0.0,
        "LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R": 0.0,
        "LPS_PULLBACK_PROFILE_MAX": 99.0,
    },
}


@dataclass
class AuditInput:
    ticker: str
    scan_date: Optional[str] = None
    source: Optional[str] = None
    setup_type: Optional[str] = None
    triggered: Optional[int] = None
    barrier_label: Optional[str] = None
    r_multiple_60d: Optional[float] = None


def _finite(value: Any) -> bool:
    try:
        return value is not None and np.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _parse_value(raw: str) -> Any:
    text = raw.strip()
    lower = text.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"none", "null"}:
        return None
    try:
        if "." not in text and "e" not in lower:
            return int(text)
        return float(text)
    except ValueError:
        return text


def _parse_overrides(pairs: Iterable[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"Invalid override {pair!r}; use NAME=VALUE")
        name, raw = pair.split("=", 1)
        name = name.strip()
        if not hasattr(settings, name):
            raise SystemExit(f"Unknown settings override: {name}")
        out[name] = _parse_value(raw)
    return out


@contextmanager
def _temporary_settings(overrides: dict[str, Any]):
    old = {name: getattr(settings, name) for name in overrides}
    try:
        for name, value in overrides.items():
            setattr(settings, name, value)
        yield
    finally:
        for name, value in old.items():
            setattr(settings, name, value)


def _cache_path() -> Path:
    return ROOT / settings.CACHE_FILENAME


def _load_cache() -> pd.DataFrame:
    path = _cache_path()
    if not path.exists():
        raise SystemExit(f"Market data cache not found: {path}")
    return pd.read_parquet(path)


def _normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    idx = pd.to_datetime(out.index)
    try:
        idx = idx.tz_localize(None)
    except TypeError:
        idx = idx.tz_convert(None)
    out.index = idx
    return out


def _ticker_frame(cache: pd.DataFrame, ticker: str,
                  as_of: Optional[str]) -> Optional[pd.DataFrame]:
    if isinstance(cache.columns, pd.MultiIndex):
        if ticker not in cache.columns.get_level_values(0):
            return None
        frame = cache[ticker].copy()
    else:
        frame = cache.copy()

    required = ["Open", "High", "Low", "Close", "Volume"]
    if not set(required) <= set(frame.columns):
        return None
    frame = _normalize_index(frame[required])
    frame = frame.dropna(subset=["High", "Low", "Close", "Volume"])
    if as_of:
        frame = frame.loc[frame.index <= pd.Timestamp(as_of)]
    return frame if not frame.empty else None


def _archive_inputs(args) -> list[AuditInput]:
    if not _DB_PATH.exists():
        raise SystemExit(f"Archive DB not found: {_DB_PATH}")

    clauses = []
    params: list[Any] = []
    if args.source:
        clauses.append("source = ?")
        params.append(args.source)
    if args.since:
        clauses.append("scan_date >= ?")
        params.append(args.since)
    if args.until:
        clauses.append("scan_date <= ?")
        params.append(args.until)
    if args.tickers:
        marks = ",".join("?" for _ in args.tickers)
        clauses.append(f"ticker IN ({marks})")
        params.extend([t.upper() for t in args.tickers])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit = "LIMIT ?" if args.limit else ""
    if args.limit:
        params.append(int(args.limit))

    sql = f"""
        SELECT ticker, scan_date, source, setup_type, triggered, barrier_label,
               r_multiple_60d
        FROM setup_archive
        {where}
        ORDER BY scan_date DESC, ticker ASC
        {limit}
    """
    con = sqlite3.connect(_DB_PATH)
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()

    return [
        AuditInput(
            ticker=str(r[0]).upper(),
            scan_date=r[1],
            source=r[2],
            setup_type=r[3],
            triggered=r[4],
            barrier_label=r[5],
            r_multiple_60d=r[6],
        )
        for r in rows
    ]


def _manual_inputs(args) -> list[AuditInput]:
    as_of = args.as_of
    return [AuditInput(ticker=t.upper(), scan_date=as_of) for t in args.tickers]


def _lps_context(df: pd.DataFrame, box, atr: float) -> tuple[Optional[dict], Counter]:
    work_df = df if "Spread" in df.columns else df.assign(Spread=df["High"] - df["Low"])
    base_df = work_df.iloc[int(box.start_bar):]
    if base_df.empty:
        return None, Counter({"empty_base": 1})

    threshold = max(
        float(base_df["Spread"].quantile(settings.LPS_RANGE_PERCENTILE)),
        1.2 * float(atr),
    )
    swing_complete_idx = max(int(box.r_anchor_bar), int(box.s_anchor_bar))
    result, rejects = detect_lps(
        work_df,
        work_df.iloc[-1],
        float(box.S),
        float(box.R),
        float(atr),
        threshold,
        int(box.base_len),
        swing_complete_idx,
        diagnose=True,
    )
    return result, rejects


def _top_rejects(counter: Counter, n: int = 5) -> str:
    if not counter:
        return ""
    return ", ".join(f"{k}:{v}" for k, v in counter.most_common(n))


def _outcome_bucket(item: AuditInput) -> str:
    if item.barrier_label:
        return str(item.barrier_label)
    if item.r_multiple_60d is not None:
        try:
            return "r2_win" if float(item.r_multiple_60d) >= 2.0 else "sub_2r"
        except (TypeError, ValueError):
            return "unknown"
    return "unknown"


def _prepare_frame(df_raw: pd.DataFrame) -> dict[str, Any]:
    baseline = apply_baseline_filters(df_raw)
    if baseline is None:
        return {"status": "baseline_filter", "rejects": Counter()}

    df, _yearly_return = baseline
    if len(df) < 6:
        return {"status": "insufficient_data", "rejects": Counter()}
    df = df.copy()
    df["ATR_10"] = calculate_atr(df, 10)
    df["ATR_50"] = calculate_atr(df, 50)

    atr_idx = -6 if len(df) > 5 else -1
    atr = float(df.iloc[atr_idx]["ATR_10"])
    if not _finite(atr) or atr <= 0:
        return {"status": "bad_atr", "rejects": Counter()}

    search_from = 0
    roots_seen = 0
    boxes_seen = 0
    last_box = None
    prepared_contexts: list[dict[str, Any]] = []

    for _ in range(_MAX_ANCHORS):
        root = bricks.find_root_swing(df, search_from_bar=search_from, atr=atr)
        if root is None:
            break
        roots_seen += 1
        search_from = int(root.climax_bar) + 1

        box = bricks.validate_equilibrium(df, root, atr)
        if box is None:
            continue
        boxes_seen += 1
        last_box = box

        inner = bricks.find_inner_box(df, box, atr)
        box_contexts = []
        if inner is not None:
            box_contexts.append(("inner", inner))
        box_contexts.append(("parent", box))

        for context_name, active_box in box_contexts:
            prepared_contexts.append({
                "context": context_name,
                "box": active_box,
                "roots_seen": roots_seen,
                "boxes_seen": boxes_seen,
            })

    if prepared_contexts:
        return {
            "status": "ready",
            "df": df,
            "atr": atr,
            "contexts": prepared_contexts,
            "roots_seen": roots_seen,
            "boxes_seen": boxes_seen,
            "last_box": last_box,
        }

    status = "no_lps" if boxes_seen else ("no_equilibrium" if roots_seen else "no_root")
    out = {
        "status": status,
        "roots_seen": roots_seen,
        "boxes_seen": boxes_seen,
        "rejects": Counter(),
    }
    if last_box is not None:
        out["box_start"] = int(last_box.start_bar)
        out["box_width"] = float(last_box.box_width)
    return out


def _audit_prepared(prepared: dict[str, Any]) -> dict[str, Any]:
    if prepared.get("status") != "ready":
        return prepared

    df = prepared["df"]
    atr = float(prepared["atr"])
    reject_totals: Counter = Counter()

    for context in prepared["contexts"]:
        context_name = context["context"]
        active_box = context["box"]
        result, rejects = _lps_context(df, active_box, atr)
        reject_totals.update(rejects)
        if not result:
            continue

        trigger = float(result["trigger_price"])
        current = float(df.iloc[-1]["Close"])
        distance = (trigger - current) / current if current > 0 else None
        if distance is None or distance <= 0:
            return {
                "status": "no_trigger_room",
                "context": context_name,
                "roots_seen": int(context["roots_seen"]),
                "boxes_seen": int(context["boxes_seen"]),
                "box_start": int(active_box.start_bar),
                "box_width": float(active_box.box_width),
                "lps_start": int(result["start_index"]),
                "lps_end": int(result["end_index"]),
                "trigger": trigger,
                "distance_to_trigger": distance,
                "rejects": reject_totals,
            }

        return {
            "status": "fires",
            "context": context_name,
            "roots_seen": int(context["roots_seen"]),
            "boxes_seen": int(context["boxes_seen"]),
            "box_start": int(active_box.start_bar),
            "box_width": float(active_box.box_width),
            "lps_start": int(result["start_index"]),
            "lps_end": int(result["end_index"]),
            "lps_zone": result.get("zone_type"),
            "lps_length": int(result["length"]),
            "trigger": trigger,
            "distance_to_trigger": distance,
            "rejects": reject_totals,
        }

    last_box = prepared.get("last_box")
    boxes_seen = int(prepared.get("boxes_seen", 0))
    roots_seen = int(prepared.get("roots_seen", 0))
    status = "no_lps" if boxes_seen else ("no_equilibrium" if roots_seen else "no_root")
    out = {
        "status": status,
        "roots_seen": roots_seen,
        "boxes_seen": boxes_seen,
        "rejects": reject_totals,
    }
    if last_box is not None:
        out["box_start"] = int(last_box.start_bar)
        out["box_width"] = float(last_box.box_width)
    return out


def _audit_frame(df_raw: pd.DataFrame) -> dict[str, Any]:
    return _audit_prepared(_prepare_frame(df_raw))


def _prepare_inputs(cache: pd.DataFrame, inputs: list[AuditInput]) -> list[dict[str, Any]]:
    prepared = []
    for item in inputs:
        frame = _ticker_frame(cache, item.ticker, item.scan_date)
        if frame is None:
            state = {"status": "missing_data", "rejects": Counter()}
        else:
            try:
                state = _prepare_frame(frame)
            except Exception as exc:  # noqa: BLE001 - diagnostic harness
                state = {"status": "error", "error": repr(exc), "rejects": Counter()}
        prepared.append(state)
    return prepared


def _run_variant(cache: pd.DataFrame, inputs: list[AuditInput],
                 overrides: dict[str, Any],
                 prepared: Optional[list[dict[str, Any]]] = None) -> list[dict[str, Any]]:
    rows = []
    with _temporary_settings(overrides):
        for i, item in enumerate(inputs):
            if prepared is not None:
                try:
                    state = _audit_prepared(prepared[i])
                except Exception as exc:  # noqa: BLE001 - diagnostic harness
                    state = {"status": "error", "error": repr(exc), "rejects": Counter()}
            else:
                frame = _ticker_frame(cache, item.ticker, item.scan_date)
                if frame is None:
                    state = {"status": "missing_data", "rejects": Counter()}
                else:
                    try:
                        state = _audit_frame(frame)
                    except Exception as exc:  # noqa: BLE001 - diagnostic harness
                        state = {"status": "error", "error": repr(exc), "rejects": Counter()}
            rows.append({
                "ticker": item.ticker,
                "scan_date": item.scan_date,
                "source": item.source,
                "archive_setup": item.setup_type,
                "archive_triggered": item.triggered,
                "archive_outcome": _outcome_bucket(item),
                **{k: v for k, v in state.items() if k != "rejects"},
                "top_rejects": _top_rejects(state.get("rejects", Counter())),
                "_rejects": dict(state.get("rejects", Counter())),
            })
    return rows


def _status_counts(rows: list[dict[str, Any]]) -> Counter:
    return Counter(str(r.get("status")) for r in rows)


def _reject_counts(rows: list[dict[str, Any]]) -> Counter:
    out: Counter = Counter()
    for row in rows:
        out.update(row.get("_rejects") or {})
    return out


def _print_summary(label: str, rows: list[dict[str, Any]]) -> None:
    print(f"\n{label}")
    print("-" * len(label))
    print(f"rows: {len(rows)}")
    print("statuses:", ", ".join(f"{k}:{v}" for k, v in _status_counts(rows).most_common()))
    rejects = _reject_counts(rows)
    if rejects:
        print("top rejects:", _top_rejects(rejects, 10))

    fired = [r for r in rows if r.get("status") == "fires"]
    if fired:
        outcomes = Counter(str(r.get("archive_outcome")) for r in fired)
        print("fired outcomes:", ", ".join(f"{k}:{v}" for k, v in outcomes.most_common()))


def _print_deltas(base: list[dict[str, Any]], variant: list[dict[str, Any]]) -> None:
    delta = _delta_summary(base, variant)
    recovered = delta["recovered"]
    dropped = delta["dropped"]
    changed = delta["changed"]

    print("\nDelta")
    print("-----")
    print(f"recovered: {len(recovered)}")
    print(f"dropped: {len(dropped)}")
    print(f"status_changed_nonfire: {len(changed)}")
    if recovered:
        print("recovered tickers:", ", ".join(
            f"{r['ticker']}@{r.get('scan_date')}({r.get('archive_outcome')})"
            for r in recovered[:25]
        ))
    if dropped:
        print("dropped tickers:", ", ".join(
            f"{r['ticker']}@{r.get('scan_date')}({r.get('archive_outcome')})"
            for r in dropped[:25]
        ))


def _delta_summary(base: list[dict[str, Any]], variant: list[dict[str, Any]]) -> dict[str, Any]:
    by_key_base = {(r["ticker"], r.get("scan_date")): r for r in base}
    by_key_var = {(r["ticker"], r.get("scan_date")): r for r in variant}
    recovered = []
    dropped = []
    changed = []
    for key, b in by_key_base.items():
        v = by_key_var.get(key)
        if v is None:
            continue
        b_fire = b.get("status") == "fires"
        v_fire = v.get("status") == "fires"
        if v_fire and not b_fire:
            recovered.append(v)
        elif b_fire and not v_fire:
            dropped.append(v)
        elif b.get("status") != v.get("status"):
            changed.append((b, v))
    return {"recovered": recovered, "dropped": dropped, "changed": changed}


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    public_rows = [{k: v for k, v in r.items() if k != "_rejects"} for r in rows]
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(public_rows, indent=2, default=str), encoding="utf-8")
        return
    fields = sorted({k for row in public_rows for k in row})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(public_rows)


def _markdown_summary(label: str, baseline: list[dict[str, Any]],
                      variants: dict[str, list[dict[str, Any]]]) -> str:
    lines = [f"# {label}", ""]

    def _fmt_counts(counter: Counter) -> str:
        return ", ".join(f"{k}:{v}" for k, v in counter.most_common()) or "none"

    lines += [
        "## Baseline",
        f"- rows: {len(baseline)}",
        f"- statuses: {_fmt_counts(_status_counts(baseline))}",
        f"- top rejects: {_top_rejects(_reject_counts(baseline), 10) or 'none'}",
        "",
    ]

    for name, rows in variants.items():
        delta = _delta_summary(baseline, rows)
        lines += [
            f"## {name}",
            f"- rows: {len(rows)}",
            f"- statuses: {_fmt_counts(_status_counts(rows))}",
            f"- recovered: {len(delta['recovered'])}",
            f"- dropped: {len(delta['dropped'])}",
            f"- status changed, non-fire: {len(delta['changed'])}",
            f"- top rejects: {_top_rejects(_reject_counts(rows), 10) or 'none'}",
        ]
        if delta["recovered"]:
            lines.append("- recovered tickers: " + ", ".join(
                f"{r['ticker']}@{r.get('scan_date')}" for r in delta["recovered"][:25]
            ))
        if delta["dropped"]:
            lines.append("- dropped tickers: " + ", ".join(
                f"{r['ticker']}@{r.get('scan_date')}" for r in delta["dropped"][:25]
            ))
        lines.append("")
    return "\n".join(lines)


def _run_matrix(cache: pd.DataFrame, inputs: list[AuditInput], matrix: str) -> list[dict[str, Any]]:
    if matrix != "lps-core":
        raise SystemExit(f"Unknown matrix: {matrix}")

    prepared = _prepare_inputs(cache, inputs)
    baseline = _run_variant(cache, inputs, {}, prepared)
    _print_summary("Baseline", baseline)
    all_rows = [{**r, "variant": "baseline"} for r in baseline]
    variant_rows: dict[str, list[dict[str, Any]]] = {}

    for name, overrides in _LPS_CORE_MATRIX.items():
        rows = _run_variant(cache, inputs, overrides, prepared)
        variant_rows[name] = rows
        _print_summary(f"Matrix {name}", rows)
        _print_deltas(baseline, rows)
        all_rows.extend({**r, "variant": name} for r in rows)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(_AUDIT_DIR, exist_ok=True)
    csv_path = _AUDIT_DIR / f"lps_core_{stamp}.csv"
    md_path = _AUDIT_DIR / f"lps_core_{stamp}.md"
    _write_rows(csv_path, all_rows)
    md_path.write_text(
        _markdown_summary("LPS Core Matrix", baseline, variant_rows),
        encoding="utf-8",
    )
    print(f"\nwrote: {csv_path}")
    print(f"wrote: {md_path}")
    return all_rows


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only LPS gate audit")
    parser.add_argument("--tickers", nargs="*", help="Explicit tickers to audit")
    parser.add_argument("--as-of", help="Evaluation date for explicit tickers")
    parser.add_argument("--source", help="Archive source filter, e.g. screener/seed/manual")
    parser.add_argument("--since", help="Archive scan_date lower bound")
    parser.add_argument("--until", help="Archive scan_date upper bound")
    parser.add_argument("--limit", type=int, default=200, help="Archive row limit")
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        help="Temporary settings override for a variant run, NAME=VALUE",
    )
    parser.add_argument("--out", help="Optional CSV/JSON output path for detailed rows")
    parser.add_argument("--matrix", choices=["lps-core"], help="Run a named override matrix")
    args = parser.parse_args(argv)

    cache = _load_cache()
    archive_filters = bool(args.source or args.since or args.until)
    inputs = _manual_inputs(args) if args.tickers and not archive_filters else _archive_inputs(args)
    if not inputs:
        raise SystemExit("No audit inputs found")

    if args.matrix:
        rows_to_write = _run_matrix(cache, inputs, args.matrix)
        if args.out:
            out_path = Path(args.out)
            if not out_path.is_absolute():
                out_path = ROOT / out_path
            os.makedirs(out_path.parent, exist_ok=True)
            _write_rows(out_path, rows_to_write)
            print(f"\nwrote: {out_path}")
        return 0

    overrides = _parse_overrides(args.override)
    baseline = _run_variant(cache, inputs, {})
    _print_summary("Baseline", baseline)

    rows_to_write = baseline
    if overrides:
        variant = _run_variant(cache, inputs, overrides)
        label = "Variant " + ", ".join(f"{k}={v}" for k, v in overrides.items())
        _print_summary(label, variant)
        _print_deltas(baseline, variant)
        rows_to_write = [
            {**b, "variant": "baseline"}
            for b in baseline
        ] + [
            {**v, "variant": "override"}
            for v in variant
        ]

    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        os.makedirs(out_path.parent, exist_ok=True)
        _write_rows(out_path, rows_to_write)
        print(f"\nwrote: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
