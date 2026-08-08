"""Archive-wide TA-grade replay — measure puzzle quality (and the full
would-be 0-100) for archived fires whose rows predate the grade columns.

The archive's score_puzzle_quality column was born 2026-08-08; every earlier
row carries it NULL while its stored v1 score contains the points. This
instrument re-reads each archived fire POINT-IN-TIME from the price cache
(the replay-seam basis: slice to scan_date, run the ONE live eval chain) and
reports the measured puzzle + the flag-on would-be grade.

Honesty gates, in order:
  * READ-ONLY. Nothing is ever written to the archive — pre-flip rows keep
    NULL grade columns forever (the flip checklist's no-backfill contract);
    this report is a SIDECAR evidence artifact, not a backfill.
  * CONCORDANCE. The replay runs TODAY'S engine on TODAY'S cache; the archive
    spans many engine epochs and the cache's history basis drifts (repairs,
    as-traded cutover). A replayed read is joined to its archived row only
    when the replayed rails match the archived rails within RAIL_TOL — the
    same shelf, re-read. Everything else is a NAMED outcome (cache_missing /
    no_fire / eval_error / discordant), never a silent join.
  * FROZEN market scalars (the replay-seam policy): breadth/SPY shape only
    scoring, never the fire decision, so the replayed v1 Score differs from
    the stored one by the breadth delta BY DESIGN; concordance judges rails.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.ta_grade_archive_replay                    # full archive
    python -m tools.ta_grade_archive_replay --since 2026-07-01
    python -m tools.ta_grade_archive_replay --scan-date 2026-08-08
    python -m tools.ta_grade_archive_replay --limit 50         # smoke
    python -m tools.ta_grade_archive_replay --json output/ta_grade_archive_replay.json
"""
from __future__ import annotations

import argparse
import json
import time

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    from _bootstrap import configure_path, refuse_sealed_output

_PROJECT_ROOT = configure_path(backend=True)

import os

import pandas as pd

from config import settings
from engine_alpha.evaluation import EVAL_ERROR
from engine_alpha.freeze.manifest import manifest_hash

# Concordance tolerance on each rail, relative to the rail's own level. Wide
# enough to absorb cache-repair float drift, far tighter than the gap between
# two different shelves on one chart.
RAIL_TOL = 0.005


def rails_concordant(rep_r, rep_s, arc_r, arc_s, tol: float = RAIL_TOL) -> bool:
    """Same shelf, re-read? Both rails within ``tol`` of the archived level.
    Any missing/zero rail refuses (never a silent join on partial identity)."""
    vals = (rep_r, rep_s, arc_r, arc_s)
    if any(v is None for v in vals):
        return False
    if not arc_r or not arc_s:
        return False
    return (abs(rep_r - arc_r) / abs(arc_r) <= tol
            and abs(rep_s - arc_s) / abs(arc_s) <= tol)


def _ranks(keyed: list) -> dict:
    ordered = sorted(keyed, key=lambda kv: (-kv[1], kv[0]))
    return {t: i + 1 for i, (t, _v) in enumerate(ordered)}


def summarize(records: list) -> dict:
    """The machine-checkable rollup the console render and the tests share."""
    funnel: dict = {}
    epochs: dict = {}
    for r in records:
        funnel[r["outcome"]] = funnel.get(r["outcome"], 0) + 1
        e = epochs.setdefault(r["epoch"], {"n": 0, "concordant": 0})
        e["n"] += 1
        if r["outcome"] == "concordant":
            e["concordant"] += 1

    conc = [r for r in records if r["outcome"] == "concordant"]
    puzzles = sorted(r["puzzle"]["quality"] for r in conc
                     if r["puzzle"] and r["puzzle"]["quality"] is not None)
    cap = float(settings.SCORE_PUZZLE_QUALITY)
    pz = None
    if puzzles:
        pz = {
            "n": len(puzzles),
            "mean": sum(puzzles) / len(puzzles),
            "median": puzzles[len(puzzles) // 2],
            "at_zero": sum(1 for p in puzzles if p == 0.0),
            "at_cap": sum(1 for p in puzzles if p >= cap - 1e-9),
            "cap": cap,
        }

    months: dict = {}
    for r in conc:
        if r["puzzle"] and r["puzzle"]["quality"] is not None:
            m = months.setdefault(r["scan_date"][:7], [0, 0.0])
            m[0] += 1
            m[1] += r["puzzle"]["quality"]
    monthly = {k: {"n": n, "mean_puzzle": s / n}
               for k, (n, s) in sorted(months.items())}

    # Movement on the newest replayed date, puzzle now included: old-score
    # ranking vs would-be-grade ranking over that date's CONCORDANT rows.
    movement = None
    if conc:
        latest = max(r["scan_date"] for r in conc)
        day = [r for r in conc if r["scan_date"] == latest
               and r["ta_grade"] is not None and r["old"]["score"] is not None]
        if len(day) >= 2:
            old = _ranks([(r["ticker"], r["old"]["score"]) for r in day])
            new = _ranks([(r["ticker"], r["ta_grade"]) for r in day])
            deltas = sorted((abs(old[r["ticker"]] - new[r["ticker"]])
                             for r in day))
            movement = {"scan_date": latest, "n": len(day),
                        "median_abs_rank_delta": deltas[len(deltas) // 2],
                        "max_abs_rank_delta": deltas[-1]}

    return {"funnel": funnel, "epochs": epochs, "puzzle": pz,
            "monthly": monthly, "latest_date_movement": movement}


def _render(summary: dict, meta: dict) -> list[str]:
    lines = ["TA-grade archive replay — puzzle measured point-in-time, "
             "would-be grades, READ-ONLY (nothing written to the archive)"]
    lines.append(f"engine_config_version (flag-on replay): {meta['ecv']}")
    lines.append(f"population: {meta['n_rows']} archived fires "
                 f"({meta['universe']}, source={meta['source']}); "
                 f"fingerprint {meta['fingerprint']}; cache {meta['cache']}")
    f = summary["funnel"]
    total = sum(f.values()) or 1
    lines.append("")
    lines.append("outcome funnel:")
    for k in ("concordant", "discordant", "no_fire", "cache_missing",
              "eval_error"):
        if f.get(k):
            lines.append(f"  {k:<14} {f[k]:>6}  ({100.0 * f[k] / total:.1f}%)")
    lines.append("")
    lines.append("per-epoch concordance (archived engine_config_version[:8]):")
    for e, d in sorted(summary["epochs"].items(),
                       key=lambda kv: -kv[1]["n"]):
        lines.append(f"  {e:<10} n={d['n']:>5}  concordant "
                     f"{100.0 * d['concordant'] / d['n']:.1f}%")
    pz = summary["puzzle"]
    if pz:
        lines.append("")
        lines.append(
            f"puzzle_quality over {pz['n']} concordant reads: "
            f"mean {pz['mean']:.2f} / median {pz['median']:.2f} "
            f"(cap {pz['cap']:.0f}); at-zero {pz['at_zero']} "
            f"({100.0 * pz['at_zero'] / pz['n']:.0f}%), at-cap {pz['at_cap']} "
            f"({100.0 * pz['at_cap'] / pz['n']:.0f}%)")
        for m, d in summary["monthly"].items():
            lines.append(f"  {m}  n={d['n']:>5}  mean {d['mean_puzzle']:.2f}")
    mv = summary["latest_date_movement"]
    if mv:
        lines.append("")
        lines.append(
            f"v1->v2 rank movement on {mv['scan_date']} with puzzle measured "
            f"({mv['n']} concordant rows, current weights): median |dRank| "
            f"{mv['median_abs_rank_delta']}, max {mv['max_abs_rank_delta']}")
    return lines


def build_records(session, panel, *, source: str, since: str | None,
                  scan_date: str | None, limit: int | None,
                  progress_every: int = 500) -> tuple[list, dict]:
    import hashlib

    from archive_models import SetupArchive
    from core.pipeline.screener import _evaluate_ticker
    from core.pipeline.universe import default_universe_type
    from tools.replay import FROZEN_BREADTH, FROZEN_SPY_6M, flag_capture

    universe = default_universe_type()
    q = (session.query(SetupArchive)
         .filter(SetupArchive.universe_type == universe,
                 SetupArchive.source == source))
    if since:
        q = q.filter(SetupArchive.scan_date >= since)
    if scan_date:
        q = q.filter(SetupArchive.scan_date == scan_date)
    # Ticker-major order so each cached frame is extracted once.
    rows = q.order_by(SetupArchive.ticker, SetupArchive.scan_date).all()
    if limit:
        rows = rows[:limit]

    cached = set(panel.columns.get_level_values(0))
    records: list = []
    t0 = time.perf_counter()
    with flag_capture(TA_SCORE_V2=True):
        ecv = manifest_hash()
        raw = None
        raw_ticker = None
        for i, row in enumerate(rows):
            rec = {"id": row.id, "ticker": row.ticker,
                   "scan_date": row.scan_date,
                   "epoch": (row.engine_config_version or "?")[:8],
                   "old": {"score": row.score, "tier": row.tier},
                   "puzzle": None, "ta_grade": None, "ta_grade_raw": None,
                   "rails": None}
            if row.ticker not in cached:
                rec["outcome"] = "cache_missing"
                records.append(rec)
                continue
            if row.ticker != raw_ticker:
                raw = panel[row.ticker].dropna()
                raw_ticker = row.ticker
            sliced = raw.loc[:pd.Timestamp(row.scan_date)]
            result = _evaluate_ticker(row.ticker, sliced,
                                      FROZEN_SPY_6M, FROZEN_BREADTH)
            if result is None:
                rec["outcome"] = "no_fire"
            elif result is EVAL_ERROR or not isinstance(result, dict):
                rec["outcome"] = "eval_error"
            else:
                rep_r, rep_s = result.get("_R"), result.get("_S")
                rec["rails"] = {
                    "rep_r": rep_r, "rep_s": rep_s,
                    "arc_r": row.r_level, "arc_s": row.s_level,
                    "rep_base_len": result.get("Base Len"),
                    "arc_base_len": row.base_length,
                }
                sub = result.get("_sub_scores") or {}
                rec["puzzle"] = {
                    "quality": sub.get("puzzle_quality"),
                    "completeness": result.get("_puzzle_completeness"),
                    "chronology": result.get("_puzzle_chronology"),
                    "upthrust_terminal": result.get("_puzzle_upthrust_terminal"),
                }
                rec["ta_grade"] = result.get("_ta_grade")
                rec["ta_grade_raw"] = result.get("_ta_grade_raw")
                rec["outcome"] = ("concordant" if rails_concordant(
                    rep_r, rep_s, row.r_level, row.s_level) else "discordant")
            records.append(rec)
            done = i + 1
            if progress_every and done % progress_every == 0:
                rate = done / (time.perf_counter() - t0)
                print(f"  ... {done}/{len(rows)} replayed "
                      f"({rate:.1f} rows/s, ~{(len(rows) - done) / rate:.0f}s "
                      f"left)", flush=True)

    fingerprint = hashlib.sha256("|".join(
        sorted(f"{r.id}:{r.ticker}" for r in rows)).encode()).hexdigest()[:16]
    meta = {"ecv": ecv, "n_rows": len(rows), "universe": universe,
            "source": source, "fingerprint": fingerprint,
            "cache": settings.CACHE_FILENAME,
            "basis": ("point-in-time replay of TODAY'S engine on the current "
                      "cache; frozen market scalars; joins gated on rail "
                      "concordance; READ-ONLY sidecar, no backfill")}
    return records, meta


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.ta_grade_archive_replay")
    parser.add_argument("--source", default="screener")
    parser.add_argument("--since", default=None)
    parser.add_argument("--scan-date", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", default=None,
                        help="write records + summary (sealed-output guarded)")
    args = parser.parse_args(argv)

    import database

    cache_path = os.path.join(_PROJECT_ROOT, settings.CACHE_FILENAME)
    if not os.path.exists(cache_path):
        print(f"price cache not found: {cache_path}")
        return 1
    panel = pd.read_parquet(cache_path, engine=settings.PARQUET_ENGINE)

    session = database.SessionLocal()
    try:
        records, meta = build_records(
            session, panel, source=args.source, since=args.since,
            scan_date=args.scan_date, limit=args.limit)
    finally:
        session.close()

    summary = summarize(records)
    for line in _render(summary, meta):
        print(line)
    if args.json:
        path = refuse_sealed_output(args.json)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"meta": meta, "summary": summary,
                       "records": records}, f, indent=1)
        print(f"\nwrote {path} ({len(records)} records)")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
