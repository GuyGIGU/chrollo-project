"""The LPS volume on the new reader's own LPS days, measured on the archived fires (Sun 11 - Mon 12/10/2026).

His words (Sun 11/10/2026): "we measure against the Bases' avg volume, so 50 day average usually"; "you could
Measure the LPS volume on all of the Archived Results. better yet set loose the new reader on them"; the
criterion is "under the avg volume", while "an Uprise in Volume in SOS is a good trait by itself, and fading
Volume by days is also a good trait". On Mon 12/10/2026, "sure" to one more fact: the quietest 2 to 5 day
stretch, the old reader's way of counting, as a plain fact that never chooses the LPS.

The 2026-10-04 census (`volume_key_points_census`) found the old reader's own LPS dry-up separating the +25%
moves and his receding-day window flat inside every volatility third. This lets the two-eyes reader loose on the
same archive: for every matured episode (the screener's US-equity fires, the census's maturity rule), the reader
reads the episode's archived days in order, on the cached daily bars up to each day, until it fires.

The outcome is one horizon for every fire: the best gain within 40 trading days of the fire day's close (the
archive's own formula). Quarters are cut inside each scan month (the months did very differently, and their
volume ran differently, so pooled quarters mix the month in), and the 95% intervals resample scan days. The facts,
each against the 50-day average volume ending on its own last day unless said:

  lps_volume      the LPS's days (the card's measure)
  swing_volume    from the day after the top of the swing the pullback belongs to (the top his sentence two
                  measures from) to the LPS's last day
  with_top        the LPS's days and the top day before them
  lps_vs_base     the LPS's days against the base's own average (the parent box's first day to the day before)
  quietest        the quietest stretch of 2 to 5 trading days ending within the 7 trading days up to the fire day
  sos_volume      the last SOS before the LPS (his good trait: loud)
  fading          every LPS day trades less than the day before it, the first against the top day (his good trait)
  old_lps_volume  the old reader's own LPS on the same day, as archived at scan time (1 - vol_contraction)
  old_today       the old reader's LPS days, recomputed on today's bars

Usage (repo venv, from the repo root; read-only against both inputs):
    python -m tools.research.lps_volume_new_reader --db COPY.db --cache COPY.parquet
    python -m tools.research.lps_volume_new_reader ... --json research/evidence/X.json --rows X.csv
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

try:  # works under both `python -m tools.research.lps_volume_new_reader` and a direct run
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

configure_path(backend=True)

from core.archive.episodes import SetupRow, build_episodes                        # noqa: E402
from tools.research.volume_key_points_census import _outcome                     # noqa: E402

UNDER = 1.0         # his criterion: "under the avg volume"
TAIL = 0.25         # the +25% best gain the edge lives in (2026-09-08)
HORIZON = 40        # trading days after the fire day, the same for every fire
WORKERS = 10
BOOTSTRAP_DRAWS = 2000
FACTS = ("lps_volume", "swing_volume", "with_top", "lps_vs_base", "quietest", "sos_volume",
         "old_lps_volume", "old_today")


# ------------------------------------------------------------------
# The facts of one fire
# ------------------------------------------------------------------
def _ratio(a: float, b: float):
    return float(a / b) if np.isfinite(a) and np.isfinite(b) and b > 0 else None


def _vs_average(volume: np.ndarray, first: int, last: int):
    """Mean volume of ``first..last`` against the 50-day average ending on ``last``."""
    return _ratio(np.nanmean(volume[first:last + 1]), np.nanmean(volume[max(0, last - 49):last + 1]))


def quietest_stretch(volume: np.ndarray, pos: int):
    """The quietest stretch of 2 to 5 trading days ending within the 7 trading days up to ``pos``."""
    ratios = [_vs_average(volume, last - days + 1, last)
              for last in range(max(1, pos - 6), pos + 1) for days in range(2, 6) if last - days + 1 >= 0]
    ratios = [r for r in ratios if r is not None]
    return min(ratios) if ratios else None


def lps_facts(frame: pd.DataFrame, pos: int, read) -> dict:
    """The volume facts of the reader's LPS, read on ``frame`` up to ``pos`` (the fire day), and the outcome after it."""
    index, volume = frame.index, frame["Volume"].to_numpy(float)
    start = index.get_loc(pd.Timestamp(read.lps.start_day))
    end = index.get_loc(pd.Timestamp(read.lps.end_day))
    base = int(index.searchsorted(pd.Timestamp(read.parent.opened_day)))
    sos = sorted((e for e in read.events if e.kind == "SOS" and e.first_day and e.last_day
                  and e.last_day < read.lps.start_day), key=lambda e: e.last_day)
    sos_volume = None
    if sos:
        sos_volume = _vs_average(volume, index.get_loc(pd.Timestamp(sos[-1].first_day)),
                                 index.get_loc(pd.Timestamp(sos[-1].last_day)))
    # The top of the swing the pullback belongs to, as the reader's LPS step names it.
    said = next((s.saying for s in read.trail if s.stage == "LPS" and "swing's top of" in s.saying), "")
    found = re.search(r"swing's top of \w{3} (\d{2}/\d{2}/\d{4})", said)
    top = index.get_loc(pd.Timestamp(dt.datetime.strptime(found.group(1), "%d/%m/%Y"))) if found else None
    high, low, close = (frame[c].to_numpy(float) for c in ("High", "Low", "Close"))
    after = high[pos + 1:pos + 1 + HORIZON]
    lps_mean = np.nanmean(volume[start:end + 1])
    return {
        "lps_volume": _vs_average(volume, start, end),
        "swing_volume": _vs_average(volume, top + 1, end) if top is not None and top < end else None,
        "swing_days": int(end - top) if top is not None and top < end else None,
        "with_top": _vs_average(volume, start - 1, end) if start >= 1 else None,
        "lps_vs_base": _ratio(lps_mean, np.nanmean(volume[base:start])) if start > base else None,
        "quietest": quietest_stretch(volume, pos),
        "sos_volume": sos_volume,
        "fading": bool(start >= 1 and all(volume[i] < volume[i - 1] for i in range(start, end + 1))),
        "lps_days": int(end - start + 1),
        "lps_start": str(read.lps.start_day),
        "lps_end": str(read.lps.end_day),
        "adr_bars": float(np.nanmean(high[max(0, pos - 19):pos + 1] / low[max(0, pos - 19):pos + 1] - 1.0)) * 100,
        "against": read.lps.read_against,
        "best": float(after.max() / close[pos] - 1.0) if len(after) == HORIZON else None,
    }


def read_ticker(task) -> list:
    """One ticker's episodes: each read day by day, in order, until the reader fires."""
    from engine_alpha import reader
    ticker, frame, episodes = task
    out = []
    for episode, days in episodes:
        first_state = None
        for row_id, day in days:
            pos = int(frame.index.searchsorted(pd.Timestamp(day), side="right")) - 1
            if pos < 0 or frame.index[pos] != pd.Timestamp(day):
                continue
            read = reader.read(ticker, frame.iloc[:pos + 1])
            if first_state is None:
                first_state = "failed" if read.failed else read.state
            if read.lps is not None:
                out.append({"episode": episode, "row_id": row_id, "scan_date": day, "ticker": ticker,
                            **lps_facts(frame, pos, read)})
                break
        else:
            out.append({"episode": episode, "row_id": None, "first_state": first_state or "no bars"})
    return out


def old_today(panel: pd.DataFrame, ticker: str, first_day, days):
    """The old reader's LPS days, recomputed on today's bars."""
    if first_day is None or days is None or pd.isna(first_day) or pd.isna(days):
        return None
    volume = panel[ticker]["Volume"].dropna()
    first = int(volume.index.searchsorted(pd.Timestamp(first_day)))
    return _vs_average(volume.to_numpy(float), first, first + int(days) - 1)


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
def _rate(fires: pd.DataFrame, mask) -> list:
    """[n, share reaching +25%] of the fires under ``mask``."""
    n = int(mask.sum())
    return [n, round(float(fires.loc[mask, "hit"].mean()), 4) if n else None]


def _gap_ci(fires: pd.DataFrame, a, b, seed: int = 7) -> list:
    """95% interval of (share under ``a`` - share under ``b``), resampling scan DAYS (one day's fires share a market)."""
    rng = np.random.default_rng(seed)
    days = fires["scan_date"].unique()
    by_a = {k: g["hit"].to_numpy() for k, g in fires[a].groupby("scan_date")}
    by_b = {k: g["hit"].to_numpy() for k, g in fires[b].groupby("scan_date")}
    gaps = []
    for _ in range(BOOTSTRAP_DRAWS):
        pick = rng.choice(days, len(days))
        x = np.concatenate([by_a[k] for k in pick if k in by_a] or [np.array([])])
        y = np.concatenate([by_b[k] for k in pick if k in by_b] or [np.array([])])
        if len(x) and len(y):
            gaps.append(x.mean() - y.mean())
    return [round(float(np.percentile(gaps, 2.5)), 4), round(float(np.percentile(gaps, 97.5)), 4)] if gaps else None


def fact_read(fires: pd.DataFrame, col: str) -> dict:
    """Quarters cut inside each scan month, quiet to loud; his criterion (under the average) beside them."""
    has = fires[col].notna()
    quarter = fires.loc[has].groupby("month")[col].transform(
        lambda s: pd.qcut(s.rank(method="first"), 4, labels=False))
    q = pd.Series(np.nan, index=fires.index)
    q.loc[has] = quarter
    under, over = has & (fires[col] < UNDER), has & (fires[col] >= UNDER)
    return {
        "n": int(has.sum()),
        "quarters": [_rate(fires, q == k) for k in range(4)],
        "quietest_minus_loudest_ci": _gap_ci(fires, q == 0, q == 3),
        "quarters_by_adr_third": {t: [_rate(fires, (q == k) & (fires["third"] == t))[1] for k in range(4)]
                                  for t in (0, 1, 2)},
        "quarters_by_month": {m: [_rate(fires, (q == k) & (fires["month"] == m))[1] for k in range(4)]
                              for m in sorted(fires.loc[has, "month"].unique())},
        "cuts": [round(float(x), 3) for x in fires.loc[has, col].quantile([0.25, 0.5, 0.75])],
        "under_average": _rate(fires, under), "over_average": _rate(fires, over),
        "under_minus_over_ci": _gap_ci(fires, under, over),
        "under_over_by_adr_third": {t: [_rate(fires, under & (fires["third"] == t)),
                                        _rate(fires, over & (fires["third"] == t))] for t in (0, 1, 2)},
    }


def census(db: str, cache: str, rows_out: str | None = None) -> dict:
    rows = archive_rows(db)
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
        adr, vc = row.get("adr_pct"), row.get("vol_contraction")
        fired.append({**r,
                      "adr_pct": float(adr) if adr is not None and pd.notna(adr) else r["adr_bars"],
                      "old_lps_volume": 1.0 - float(vc) if vc is not None and pd.notna(vc) else None,
                      "old_today": old_today(panel, r["ticker"], row.get("lps_anchor_date"), row.get("lps_length"))})
    fires = pd.DataFrame(fired)
    for col in FACTS + ("adr_pct", "best"):
        fires[col] = pd.to_numeric(fires[col], errors="coerce")
    fires["hit"] = fires["best"] >= TAIL
    fires["month"] = fires["scan_date"].str[:7]
    fires["third"] = pd.qcut(fires["adr_pct"].rank(method="first"), 3, labels=False)
    if rows_out:
        refuse_sealed_output(rows_out)
        fires.to_csv(rows_out, index=False)
    fading = fires["fading"].astype(bool)
    return {
        "inputs": {"db": os.path.basename(db), "cache_last_day": str(panel.index[-1].date()), "horizon": HORIZON},
        "coverage": {"matured_episodes": len(matured), "read": len(results), "fired": int(len(fires)),
                     "not_fired_by_first_state": dict(missed.most_common()),
                     "scan_days": [str(fires["scan_date"].min()), str(fires["scan_date"].max()),
                                   int(fires["scan_date"].nunique())]},
        "all": _rate(fires, fires["hit"].notna()),
        "by_month": {m: _rate(fires, fires["month"] == m) for m in sorted(fires["month"].unique())},
        "lps_days": {str(k): int(v) for k, v in sorted(Counter(fires["lps_days"]).items())},
        "read_against": {str(k): int(v) for k, v in Counter(fires["against"]).items()},
        "facts": {col: fact_read(fires, col) for col in FACTS},
        "fading": {"yes": _rate(fires, fading), "no": _rate(fires, ~fading),
                   "yes_minus_no_ci": _gap_ci(fires, fading, ~fading),
                   "by_adr_third": {t: [_rate(fires, fading & (fires["third"] == t)),
                                        _rate(fires, ~fading & (fires["third"] == t))] for t in (0, 1, 2)}},
    }


def _pct(x) -> str:
    return "-" if x is None else f"{x * 100:.1f}"


def _print(report: dict) -> None:
    c = report["coverage"]
    print(f"matured episodes {c['matured_episodes']} | the new reader fired on {c['fired']} | scan days {c['scan_days']}")
    print(f"not fired, by the state on the episode's first day: {c['not_fired_by_first_state']}")
    print(f"+25% within {report['inputs']['horizon']} trading days: {_pct(report['all'][1])}% | by month "
          f"{ {m: _pct(v[1]) for m, v in report['by_month'].items()} } | LPS days {report['lps_days']}")
    for col, f in report["facts"].items():
        print(f"\n== {col} (n={f['n']}, cuts {f['cuts']})")
        print(f"   quarters inside each month, quiet to loud: {[_pct(r[1]) for r in f['quarters']]} "
              f"| quietest minus loudest CI {f['quietest_minus_loudest_ci']}")
        for t, name in ((2, "jumpy"), (1, "middle"), (0, "calm")):
            print(f"   {name:<6} third: {[_pct(x) for x in f['quarters_by_adr_third'][t]]}")
        print(f"   by month: { {m: [_pct(x) for x in v] for m, v in f['quarters_by_month'].items()} }")
        print(f"   under the average {f['under_average'][0]}: {_pct(f['under_average'][1])}% | over "
              f"{f['over_average'][0]}: {_pct(f['over_average'][1])}% | under minus over CI {f['under_minus_over_ci']}")
    fd = report["fading"]
    print(f"\n== fading day by day: yes {fd['yes']} no {fd['no']} | yes minus no CI {fd['yes_minus_no_ci']}")


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
