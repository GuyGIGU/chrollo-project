"""Do tighter, cleaner bases run further? The new reader on the archived fires (Tue 13/10/2026).

His words (Tue 13/10/2026): "out of every winning stock the best were the tightest and cleanest looking, and all
calibrated stocks are what I would consider Tight ... we can send our new reader to read all of the past archives
and measure fires as well!" The measures, the outcome and the bar were written down before any table was read:
`research/evidence/base_tightness_new_reader_2026-10-13_prereg.md`. This tool computes exactly those and nothing
it could pick after looking.

For every matured episode (the screener's US-equity fires) the reader reads the episode's archived days in order,
on the cached daily bars up to each day, until it fires (the method of 12/10/2026). The six facts are read on the
parent box (the grade's box), in its own daily range dr frozen at its birth:

  height       (R - S) / dr
  quiet_bars   median daily bar in the base / median daily bar of the 60 trading days before the box opened
  dead_space   the grade's empty days / base days
  wrap         (|R - 90th pct of the base's highs| + |10th pct of its lows - S|) / dr
  tightening   mean daily bar of the last 10 trading days up to the fire day / mean daily bar of the base
  lps_depth    (highest high from the day before the LPS to its last day - lowest low of the LPS days) / dr

The base is the grade's own: the box's opening day to the day before THE SOS's push, else to the fire day (the
pre-registration's amendment, written after a smoke test and before the run). The outcome is the best gain within
40 trading days of the fire day's close. Small is tight on every fact.

Usage (repo venv, from the repo root; read-only against both inputs):
    python -m tools.research.base_tightness_new_reader --db COPY.db --cache COPY.parquet
    python -m tools.research.base_tightness_new_reader ... --json research/evidence/X.json --rows X.csv
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

try:  # works under both `python -m tools.research.base_tightness_new_reader` and a direct run
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

configure_path(backend=True)

from core.archive.episodes import SetupRow, build_episodes                        # noqa: E402
from tools.research.volume_key_points_census import _outcome                     # noqa: E402

HORIZON = 40          # trading days after the fire day, the same for every fire
TAILS = (0.25, 0.40)  # the tail the edge lives in (2026-09-08)
PRIOR_DAYS = 60       # the stock's normal bar before the box opened
LAST_DAYS = 10        # the last stretch the tightening is read on
WORKERS = 10
BOOTSTRAP_DRAWS = 2000
FACTS = ("height", "quiet_bars", "dead_space", "wrap", "tightening", "lps_depth")
REFERENCE = ("height_pct",)


# ------------------------------------------------------------------
# The facts of one fire
# ------------------------------------------------------------------
def _box_unit(frame: pd.DataFrame, box) -> float | None:
    """The box's own daily range, frozen at its birth; the 14-day daily range on its opening day when not stored."""
    if box.daily_range is not None and np.isfinite(box.daily_range) and box.daily_range > 0:
        return float(box.daily_range)
    from engine_alpha.two_eyes.daily_range import calculate_atr
    opened = int(frame.index.searchsorted(pd.Timestamp(box.opened_day)))
    atr = calculate_atr(frame.iloc[:opened + 1], 14)
    value = float(atr.iloc[-1]) if len(atr) else float("nan")
    return value if np.isfinite(value) and value > 0 else None


def base_facts(frame: pd.DataFrame, pos: int, read) -> dict:
    """The six facts of the parent box (the grade's box), read on ``frame`` up to ``pos`` (the fire day), and the
    outcome after it. The base is the grade's own: the box's opening day to the day before THE SOS's push, else to
    the fire day (the pre-registration's amendment)."""
    from engine_alpha.two_eyes.grade import ending_sos
    box = read.parent
    index = frame.index
    high, low, close = (frame[c].to_numpy(float) for c in ("High", "Low", "Close"))
    bar = high - low
    r, s = float(box.resistance.price), float(box.support.price)
    dr = _box_unit(frame, box)
    opened = int(index.searchsorted(pd.Timestamp(box.opened_day)))
    start = index.get_loc(pd.Timestamp(read.lps.start_day))
    end = index.get_loc(pd.Timestamp(read.lps.end_day))
    days = [d.date() for d in index[:pos + 1]]
    sos = ending_sos(read.events, days, opened)
    base_end = days.index(sos.first_day) - 1 if sos is not None else pos
    base = slice(opened, base_end + 1)
    base_high, base_low, base_bar = high[base], low[base], bar[base]
    prior = bar[max(0, opened - PRIOR_DAYS):opened]
    tall = r - s
    grade = read.grade
    after = high[pos + 1:pos + 1 + HORIZON]
    top = float(np.nanpercentile(base_high, 90)) if len(base_high) else float("nan")
    bottom = float(np.nanpercentile(base_low, 10)) if len(base_low) else float("nan")
    lps_top = float(np.nanmax(high[max(0, start - 1):end + 1]))
    lps_low = float(np.nanmin(low[start:end + 1]))
    return {
        "against": read.lps.read_against,
        "has_mini": read.mini is not None,
        "base_days": int(base_end - opened + 1),
        "sos_ends_base": sos is not None,
        "height": tall / dr if dr else None,
        "quiet_bars": float(np.nanmedian(base_bar) / np.nanmedian(prior)) if len(prior) >= 20 and len(base_bar) else None,
        "dead_space": grade.empty_days / grade.base_days if grade is not None and grade.base_days else None,
        "wrap": (abs(r - top) + abs(bottom - s)) / dr if dr and np.isfinite(top) and np.isfinite(bottom) else None,
        "tightening": float(np.nanmean(bar[pos - LAST_DAYS + 1:pos + 1]) / np.nanmean(base_bar))
        if len(base_bar) and pos - opened + 1 > LAST_DAYS else None,
        "lps_depth": (lps_top - lps_low) / dr if dr else None,
        "height_pct": tall / s * 100 if s > 0 else None,
        "grade_letter": None if grade is None else grade.letter,
        "adr_bars": float(np.nanmean(high[max(0, pos - 19):pos + 1] / low[max(0, pos - 19):pos + 1] - 1.0)) * 100,
        "best": float(after.max() / close[pos] - 1.0) if len(after) == HORIZON else None,
    }


def read_ticker(task) -> list:
    """One ticker's episodes: each read day by day, in order, until the reader fires."""
    from engine_alpha import two_eyes
    ticker, frame, episodes = task
    out = []
    for episode, days in episodes:
        first_state = None
        for row_id, day in days:
            pos = int(frame.index.searchsorted(pd.Timestamp(day), side="right")) - 1
            if pos < 0 or frame.index[pos] != pd.Timestamp(day):
                continue
            read = two_eyes.read(ticker, frame.iloc[:pos + 1])
            if first_state is None:
                first_state = "failed" if read.failed else read.state
            if read.fired:
                out.append({"episode": episode, "row_id": row_id, "scan_date": day, "ticker": ticker,
                            **base_facts(frame, pos, read)})
                break
        else:
            out.append({"episode": episode, "row_id": None, "first_state": first_state or "no bars"})
    return out


# ------------------------------------------------------------------
# Inputs
# ------------------------------------------------------------------
def archive_rows(db: str) -> pd.DataFrame:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(
            "SELECT * FROM setup_archive WHERE source = 'screener' AND universe_type = 'us_equities'", con)
    finally:
        con.close()


def reviews(db: str) -> dict:
    """His verdict per (ticker, scan day): 'liked' or 'passed'."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {(t, d): v for t, d, v in con.execute("SELECT ticker, scan_date, verdict FROM setup_reviews")}
    finally:
        con.close()


def tasks_from(rows: pd.DataFrame, panel: pd.DataFrame):
    """Per ticker: its frame and its matured episodes' (row id, day) lists, oldest day first."""
    rows = rows.set_index("id", drop=False)
    episodes = build_episodes(
        SetupRow(id=int(i), ticker=str(t), scan_date=str(d), setup_type=str(s), universe_type=str(u))
        for i, t, d, s, u in zip(rows["id"], rows["ticker"], rows["scan_date"], rows["setup_type"],
                                 rows["universe_type"].fillna("us_equities")))
    matured = [e for e in episodes if _outcome(rows.loc[e.canonical_id])["mfe"] is not None]
    have = set(panel.columns.get_level_values(0))
    by_ticker: dict = {}
    for n, e in enumerate(matured):
        days = sorted(((int(i), str(rows.at[i, "scan_date"])) for i in e.member_ids), key=lambda x: x[1])
        by_ticker.setdefault(e.ticker, []).append((n, days))
    tasks = []
    for ticker, eps in by_ticker.items():
        if ticker not in have:
            continue
        frame = panel[ticker][["Open", "High", "Low", "Close", "Volume"]].dropna(how="any")
        if len(frame):
            tasks.append((ticker, frame, eps))
    return matured, tasks


# ------------------------------------------------------------------
# The read against outcomes
# ------------------------------------------------------------------
def _rate(fires: pd.DataFrame, mask, col: str = "hit25") -> list:
    """[n, share of the fires under ``mask`` with ``col`` true]."""
    n = int(mask.sum())
    return [n, round(float(fires.loc[mask, col].mean()), 4) if n else None]


def _gap_ci(fires: pd.DataFrame, a, b, col: str = "hit25", seed: int = 7) -> list | None:
    """95% interval of (share under ``a`` - share under ``b``), resampling scan DAYS (one day's fires share a market)."""
    rng = np.random.default_rng(seed)
    days = fires["scan_date"].unique()
    by_a = {k: g[col].to_numpy(float) for k, g in fires[a].groupby("scan_date")}
    by_b = {k: g[col].to_numpy(float) for k, g in fires[b].groupby("scan_date")}
    gaps = []
    for _ in range(BOOTSTRAP_DRAWS):
        pick = rng.choice(days, len(days))
        x = np.concatenate([by_a[k] for k in pick if k in by_a] or [np.array([])])
        y = np.concatenate([by_b[k] for k in pick if k in by_b] or [np.array([])])
        if len(x) and len(y):
            gaps.append(x.mean() - y.mean())
    return [round(float(np.percentile(gaps, 2.5)), 4), round(float(np.percentile(gaps, 97.5)), 4)] if gaps else None


def quarters(fires: pd.DataFrame, col: str) -> pd.Series:
    """Quarter 0 (tightest) to 3 (loosest), cut inside each scan month."""
    has = fires[col].notna()
    q = pd.Series(np.nan, index=fires.index)
    q.loc[has] = fires.loc[has].groupby("month")[col].transform(
        lambda s: pd.qcut(s.rank(method="first"), 4, labels=False, duplicates="drop"))
    return q


def fact_read(fires: pd.DataFrame, col: str) -> dict:
    """The pre-registered read of one fact, and its verdict against the bar."""
    q = quarters(fires, col)
    tight, loose = q == 0, q == 3
    thirds = {t: [_rate(fires, (q == k) & (fires["third"] == t))[1] for k in range(4)] for t in (0, 1, 2)}
    months = {m: [_rate(fires, (q == k) & (fires["month"] == m))[1] for k in range(4)]
              for m in sorted(fires.loc[q.notna(), "month"].unique())}
    ci = _gap_ci(fires, tight, loose)
    thirds_with = sum(1 for v in thirds.values() if None not in (v[0], v[3]) and v[0] > v[3])
    months_with = sum(1 for v in months.values() if None not in (v[0], v[3]) and v[0] > v[3])
    a = ci is not None and ci[0] > 0
    b = thirds_with >= 2
    c = months_with > len(months) / 2
    met = "".join(name for name, ok in (("a", a), ("b", b), ("c", c)) if ok)
    verdict = "HOLDS" if met == "abc" else (f"partly ({met} of abc)" if met else "no")
    return {
        "n": int(q.notna().sum()),
        "cuts": [round(float(x), 3) for x in fires[col].dropna().quantile([0.25, 0.5, 0.75])],
        "p25": [_rate(fires, q == k) for k in range(4)],
        "p40": [_rate(fires, q == k, "hit40") for k in range(4)],
        "median_best": [round(float(fires.loc[q == k, "best"].median()), 4) if (q == k).any() else None
                        for k in range(4)],
        "tight_minus_loose_ci": ci,
        "tight_minus_loose_ci_p40": _gap_ci(fires, tight, loose, "hit40"),
        "by_adr_third": thirds,
        "by_month": months,
        "bar": {"a_interval_above_zero": a, "b_thirds_same_way": thirds_with, "c_months_same_way":
                f"{months_with} of {len(months)}"},
        "verdict": verdict,
    }


def likes_read(fires: pd.DataFrame) -> dict:
    """His liked and passed fires beside the rest: the median of each fact (description only)."""
    out = {}
    for group in ("liked", "passed", "rest"):
        sub = fires[fires["review"] == group]
        out[group] = {"n": int(len(sub)), **{col: (round(float(sub[col].median()), 3) if sub[col].notna().any()
                                                   else None) for col in FACTS + REFERENCE},
                      "p25": round(float(sub["hit25"].mean()), 3) if len(sub) else None}
    return out


def census(db: str, cache: str, rows_out: str | None = None) -> dict:
    rows = archive_rows(db)
    verdicts = reviews(db)
    panel = pd.read_parquet(cache)
    if getattr(panel.index, "tz", None) is not None:
        panel.index = panel.index.tz_localize(None)
    matured, tasks = tasks_from(rows, panel)
    with ProcessPoolExecutor(WORKERS) as pool:
        results = [r for chunk in pool.map(read_ticker, tasks, chunksize=4) for r in chunk]
    by_id = rows.set_index("id")
    fired, missed = [], Counter()
    for r in results:
        if r["row_id"] is None:
            missed[r["first_state"]] += 1
            continue
        if r["best"] is None:
            missed[f"fired with fewer than {HORIZON} trading days after it"] += 1
            continue
        row = by_id.loc[r["row_id"]]
        adr = row.get("adr_pct")
        # His verdict on any day of the episode counts for the episode's fire.
        episode_days = [str(by_id.at[i, "scan_date"]) for i in matured[r["episode"]].member_ids]
        review = next((verdicts[(r["ticker"], d)] for d in episode_days if (r["ticker"], d) in verdicts), "rest")
        fired.append({**r, "review": review,
                      "adr_pct": float(adr) if adr is not None and pd.notna(adr) else r["adr_bars"]})
    fires = pd.DataFrame(fired)
    for col in FACTS + REFERENCE + ("adr_pct", "best"):
        fires[col] = pd.to_numeric(fires[col], errors="coerce")
    fires["hit25"] = fires["best"] >= TAILS[0]
    fires["hit40"] = fires["best"] >= TAILS[1]
    fires["month"] = fires["scan_date"].str[:7]
    fires["third"] = pd.qcut(fires["adr_pct"].rank(method="first"), 3, labels=False)
    if rows_out:
        refuse_sealed_output(rows_out)
        fires.to_csv(rows_out, index=False)
    return {
        "inputs": {"db": os.path.basename(db), "cache_last_day": str(panel.index[-1].date()), "horizon": HORIZON,
                   "prereg": "research/evidence/base_tightness_new_reader_2026-10-13_prereg.md"},
        "coverage": {"matured_episodes": len(matured), "read": len(results), "fired": int(len(fires)),
                     "not_fired_by_first_state": dict(missed.most_common()),
                     "scan_days": [str(fires["scan_date"].min()), str(fires["scan_date"].max()),
                                   int(fires["scan_date"].nunique())],
                     "against": {str(k): int(v) for k, v in Counter(fires["against"]).items()}},
        "all": {"p25": _rate(fires, fires["hit25"].notna()), "p40": _rate(fires, fires["hit40"].notna(), "hit40"),
                "median_best": round(float(fires["best"].median()), 4)},
        "by_month": {m: _rate(fires, fires["month"] == m) for m in sorted(fires["month"].unique())},
        "by_adr_third": {t: _rate(fires, fires["third"] == t) for t in (0, 1, 2)},
        "facts": {col: fact_read(fires, col) for col in FACTS},
        "reference": {col: fact_read(fires, col) for col in REFERENCE},
        "likes": likes_read(fires),
    }


def _pct(x) -> str:
    return "-" if x is None else f"{x * 100:.1f}"


def _print(report: dict) -> None:
    c = report["coverage"]
    print(f"matured episodes {c['matured_episodes']} | the new reader fired on {c['fired']} | scan days {c['scan_days']}"
          f" | LPS read against {c['against']}")
    print(f"not fired, by the state on the episode's first day: {c['not_fired_by_first_state']}")
    a = report["all"]
    print(f"all fires: +25% {_pct(a['p25'][1])}% | +40% {_pct(a['p40'][1])}% | median best {_pct(a['median_best'])}%")
    print(f"by month {({m: _pct(v[1]) for m, v in report['by_month'].items()})} | by ADR third (calm, middle, jumpy) "
          f"{[_pct(report['by_adr_third'][t][1]) for t in (0, 1, 2)]}")
    for group, facts in (("PRE-REGISTERED", report["facts"]), ("REFERENCE", report["reference"])):
        for col, f in facts.items():
            print(f"\n== [{group}] {col}: {f['verdict']} (n={f['n']}, cuts {f['cuts']})")
            print(f"   +25% tight..loose: {[_pct(r[1]) for r in f['p25']]} | CI {f['tight_minus_loose_ci']}")
            print(f"   +40% tight..loose: {[_pct(r[1]) for r in f['p40']]} | CI {f['tight_minus_loose_ci_p40']}")
            print(f"   median best: {[_pct(x) for x in f['median_best']]} | bar {f['bar']}")
            for t, name in ((0, "calm"), (1, "middle"), (2, "jumpy")):
                print(f"   {name:<6} third: {[_pct(x) for x in f['by_adr_third'][t]]}")
            print(f"   by month: { {m: [_pct(x) for x in v] for m, v in f['by_month'].items()} }")
    print("\n== his Likes (medians; description only)")
    for group, g in report["likes"].items():
        print(f"   {group:<6} n={g['n']:<5} " + " ".join(f"{k}={g[k]}" for k in FACTS + REFERENCE) + f" +25%={g['p25']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", required=True, help="a COPY of the archive DB (opened read-only)")
    parser.add_argument("--cache", required=True, help="the 5-year price cache parquet (read only)")
    parser.add_argument("--json", help="write the report here (research/evidence/...)")
    parser.add_argument("--rows", help="also write one CSV row per fire here")
    args = parser.parse_args()
    report = census(args.db, args.cache, args.rows)
    _print(report)
    if args.json:
        refuse_sealed_output(args.json)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
