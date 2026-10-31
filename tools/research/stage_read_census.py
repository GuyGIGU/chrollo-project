"""Where the archive's fires sat in the stock's life cycle, and how they did (the stage read, Fri 16/10/2026).

The stage read (``engine_alpha/stock.py``: Minervini's four stages on the weekly chart, and the week the
current stage-2 advance began) is display and archive only. Its one open question is his: whether stage-1 and
stage-3 fires should leave Alpha's board (his theory: stage 1 is dead money, no buying; the stage-3 range carries
his X). This census gives him the numbers for it, read-only against a COPY of the archive and the price cache:

* every episode of the screener's US-equity fires (``core.archive.episodes``), read on its FIRST day, the day it
  first showed, with the stage read on the cached daily bars up to that day (at most the cache's five years, as
  the scan reads them);
* the outcome of a matured one: the best gain within 40 trading days of that day's close (the 2026-10-13
  tightness study's), +25% and +40% the tail the edge lives in; split by the stock's volatility third (its
  average daily range over the last 20 days), because the third decides the tail;
* the live reader's own fires since the flip (scan days from 12/10/2026), by stage, no outcome yet;
* his calibration setups, read on the trading day before his trigger, as their own group (his ruling of
  2026-10-03), and his five leaders on the cache's last day.

Not pre-registered: a scratch version of the same read was looked at before this tool was written, and the
tool reproduces it. Usage (repo venv, from the repo root):
    python -m tools.research.stage_read_census --db COPY.db --cache COPY.parquet [--json research/evidence/X.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

try:  # works under both `python -m tools.research.stage_read_census` and a direct run
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

configure_path()

from core.archive.episodes import SetupRow, build_episodes        # noqa: E402
from engine_alpha.stock import read_stage                    # noqa: E402

HORIZON = 40                    # trading days after the fire day, the tightness study's
TAILS = (0.25, 0.40)
FLIP_FIRST_SCAN = "2026-10-12"  # the first nightly scan the new reader read (the flip, Sat 10/10/2026)
LEADERS = ("SNOW", "FROG", "HNGE", "ANET", "DDI")
WORKERS = 10
BOOTSTRAP_DRAWS = 2000
STAGES = (1, 2, 3, 4)


def _frame(panel: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    if ticker not in set(panel.columns.get_level_values(0)):
        return None
    frame = panel[ticker][["Open", "High", "Low", "Close", "Volume"]].dropna(how="any")
    return frame if len(frame) else None


def read_day(frame: pd.DataFrame, day: str) -> dict | None:
    """The stage read on ``frame`` up to ``day`` and what followed: None when the day is not a bar of the frame."""
    pos = int(frame.index.searchsorted(pd.Timestamp(day), side="right")) - 1
    if pos < 0 or frame.index[pos] != pd.Timestamp(day):
        return None
    high, low, close = (frame[c].to_numpy(float) for c in ("High", "Low", "Close"))
    after = high[pos + 1:pos + 1 + HORIZON]
    return {**read_stage(frame.iloc[:pos + 1]),
            "adr": float(np.nanmean(high[max(0, pos - 19):pos + 1] / low[max(0, pos - 19):pos + 1] - 1.0)) * 100,
            "best": float(after.max() / close[pos] - 1.0) if len(after) == HORIZON else None}


def read_ticker(task) -> list:
    ticker, frame, days = task
    out = []
    for key, day in days:
        read = read_day(frame, day)
        out.append({"key": key, "ticker": ticker, "day": day, **(read or {"missing": True})})
    return out


# ------------------------------------------------------------------
# Inputs
# ------------------------------------------------------------------
def episodes(db: str) -> list:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = pd.read_sql_query("SELECT id, ticker, scan_date, setup_type, universe_type FROM setup_archive "
                                 "WHERE source = 'screener' AND universe_type = 'us_equities'", con)
    finally:
        con.close()
    return build_episodes(
        SetupRow(id=int(i), ticker=str(t), scan_date=str(d), setup_type=str(s), universe_type=str(u))
        for i, t, d, s, u in zip(rows["id"], rows["ticker"], rows["scan_date"], rows["setup_type"],
                                 rows["universe_type"]))


def calibration_days(db: str, panel: pd.DataFrame) -> list:
    """His drawn setups: (ticker, the trading day before his trigger), as the outcome job reads them."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        marks = con.execute("SELECT ticker, COALESCE(trigger_date, as_of_date) FROM calibration_marks").fetchall()
    finally:
        con.close()
    out = []
    for ticker, trigger in marks:
        frame = _frame(panel, ticker)
        if frame is None or not trigger:
            out.append((ticker, None))
            continue
        pos = int(frame.index.searchsorted(pd.Timestamp(trigger))) - 1
        out.append((ticker, frame.index[pos].date().isoformat() if pos >= 0 else None))
    return out


# ------------------------------------------------------------------
# The read
# ------------------------------------------------------------------
def _rate(rows: pd.DataFrame, mask, col: str = "hit25") -> list:
    n = int(mask.sum())
    return [n, round(float(rows.loc[mask, col].mean()), 4) if n else None]


def _gap_ci(rows: pd.DataFrame, a, b, col: str = "hit25", seed: int = 7) -> list | None:
    """95% interval of (share under ``a`` - share under ``b``), resampling scan DAYS (one day's fires share a
    market), as the tightness study does."""
    rng = np.random.default_rng(seed)
    days = rows["day"].unique()
    by_a = {k: g[col].to_numpy(float) for k, g in rows[a].groupby("day")}
    by_b = {k: g[col].to_numpy(float) for k, g in rows[b].groupby("day")}
    gaps = []
    for _ in range(BOOTSTRAP_DRAWS):
        pick = rng.choice(days, len(days))
        x = np.concatenate([by_a[k] for k in pick if k in by_a] or [np.array([])])
        y = np.concatenate([by_b[k] for k in pick if k in by_b] or [np.array([])])
        if len(x) and len(y):
            gaps.append(x.mean() - y.mean())
    return [round(float(np.percentile(gaps, 2.5)), 4), round(float(np.percentile(gaps, 97.5)), 4)] if gaps else None


def _stage_table(rows: pd.DataFrame) -> dict:
    return {str(s): {"p25": _rate(rows, rows["cycle_stage"] == s), "p40": _rate(rows, rows["cycle_stage"] == s, "hit40"),
                     "median_best": (round(float(rows.loc[rows["cycle_stage"] == s, "best"].median()), 4)
                                     if (rows["cycle_stage"] == s).any() else None)}
            for s in STAGES}


def census(db: str, cache: str) -> dict:
    panel = pd.read_parquet(cache)
    if getattr(panel.index, "tz", None) is not None:
        panel.index = panel.index.tz_localize(None)
    eps = episodes(db)
    by_ticker: dict = {}
    for n, e in enumerate(eps):
        by_ticker.setdefault(e.ticker, []).append((n, e.first_seen))
    tasks = [(t, f, days) for t, days in by_ticker.items() if (f := _frame(panel, t)) is not None]
    with ProcessPoolExecutor(WORKERS) as pool:
        reads = [r for chunk in pool.map(read_ticker, tasks, chunksize=8) for r in chunk]
    rows = pd.DataFrame([r for r in reads if not r.get("missing")])
    rows["matured"] = rows["best"].notna()
    matured = rows[rows["matured"]].copy()
    matured["hit25"] = matured["best"] >= TAILS[0]
    matured["hit40"] = matured["best"] >= TAILS[1]
    matured["third"] = pd.qcut(matured["adr"].rank(method="first"), 3, labels=False)
    matured["month"] = matured["day"].str[:7]
    one, two = matured["cycle_stage"] == 1, matured["cycle_stage"] == 2

    live = rows[rows["day"] >= FLIP_FIRST_SCAN]
    marks = [(t, d, read_day(_frame(panel, t), d) if d else None) for t, d in calibration_days(db, panel)]
    leaders = {}
    for t in LEADERS:
        frame = _frame(panel, t)
        leaders[t] = None if frame is None else read_stage(frame)
    stage_counts = lambda df: {str(k): int(v) for k, v in Counter(df["cycle_stage"].fillna(0).astype(int)).items()}
    return {
        "inputs": {"db": os.path.basename(db), "cache_last_day": str(panel.index[-1].date()), "horizon": HORIZON},
        "coverage": {"episodes": len(eps), "read": int(len(rows)),
                     "not_read": int(sum(1 for r in reads if r.get("missing"))),
                     "matured": int(len(matured)),
                     "first_days": [str(rows["day"].min()), str(rows["day"].max())],
                     "stage_counts_all": stage_counts(rows), "stage_counts_matured": stage_counts(matured),
                     "advance_not_in_view_stage2": int(((rows["cycle_stage"] == 2)
                                                         & rows["advance_start"].isna()).sum())},
        "outcome_by_stage": _stage_table(matured),
        "outcome_by_stage_in_adr_thirds": {str(t): _stage_table(matured[matured["third"] == t]) for t in (0, 1, 2)},
        "adr_third_cuts": [round(float(x), 2) for x in matured["adr"].quantile([1 / 3, 2 / 3])],
        "stage2_minus_stage1": {
            "p25_ci": _gap_ci(matured, two, one), "p40_ci": _gap_ci(matured, two, one, "hit40"),
            "p25_ci_in_thirds": {str(t): _gap_ci(matured, two & (matured["third"] == t), one & (matured["third"] == t))
                                 for t in (0, 1, 2)}},
        "stage_share_by_month": {m: stage_counts(matured[matured["month"] == m])
                                 for m in sorted(matured["month"].unique())},
        "advance_weeks_stage2_quartiles": [round(float(x), 1) for x in
                                           matured.loc[two, "advance_weeks"].dropna().quantile([.25, .5, .75])],
        "live_since_flip": {"episodes": int(len(live)), "stage_counts": stage_counts(live),
                            "by_stage": {str(s): sorted(live.loc[live["cycle_stage"] == s, "ticker"].tolist())
                                         for s in (1, 3, 4)}},
        "calibration_setups": [{"ticker": t, "day": d, **({k: r.get(k) for k in ("cycle_stage", "advance_start",
                                                                                 "advance_weeks")} if r else {})}
                               for t, d, r in marks],
        "leaders_on_the_last_day": leaders,
    }


def _pct(x) -> str:
    return "-" if x is None else f"{x * 100:.1f}"


def _print(report: dict) -> None:
    c = report["coverage"]
    print(f"episodes {c['episodes']}, read {c['read']}, matured {c['matured']} (first days {c['first_days']})")
    print(f"stages, all episodes {c['stage_counts_all']}; matured {c['stage_counts_matured']}")
    print("\nshare reaching +25% / +40% in 40 trading days, by stage (n, %):")
    for s, v in report["outcome_by_stage"].items():
        print(f"  stage {s}: n {v['p25'][0]:5d}  +25% {_pct(v['p25'][1]):>5}  +40% {_pct(v['p40'][1]):>5}"
              f"  median best {_pct(v['median_best'])}")
    print(f"\nby volatility third (cuts {report['adr_third_cuts']} % average daily range):")
    for t, table in report["outcome_by_stage_in_adr_thirds"].items():
        cells = "  ".join(f"stage {s} {v['p25'][0]}/{_pct(v['p25'][1])}" for s, v in table.items())
        print(f"  third {t}: {cells}")
    gap = report["stage2_minus_stage1"]
    print(f"\nstage 2 minus stage 1, +25%: 95% CI {gap['p25_ci']}; in thirds {gap['p25_ci_in_thirds']}")
    live = report["live_since_flip"]
    print(f"\nlive since the flip: {live['episodes']} episodes, stages {live['stage_counts']}")
    for s, names in live["by_stage"].items():
        print(f"  stage {s}: {', '.join(names) if names else '-'}")
    marks = Counter(m.get("cycle_stage") for m in report["calibration_setups"])
    print(f"\nhis calibration setups by stage: {dict(marks)}")
    print(f"his five leaders: {report['leaders_on_the_last_day']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", required=True, help="a COPY of the archive DB (opened read-only)")
    parser.add_argument("--cache", required=True, help="the 5-year price cache parquet (read only)")
    parser.add_argument("--json", help="write the report here (research/evidence/...)")
    args = parser.parse_args()
    report = census(args.db, args.cache)
    _print(report)
    if args.json:
        refuse_sealed_output(args.json)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
