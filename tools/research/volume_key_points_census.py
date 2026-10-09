"""Volume at key points — the Momentum Masters volume read, measured (step 2, 2026-10-04).

The operator's selection summary (Momentum Masters, given 2026-10-02) reads volume
WITH price, at the moments that matter:

  * advancing prices on expanding volume (buying pressure), and stronger advances
    than declines inside the range (accumulation);
  * orderly pullbacks on declining volume (selling easing);
  * sharp declines on heavy volume (substantial selling: caution);
  * breakouts on above-average volume (participation, though they can still fail).

His own words on the key points (2026-09-13): "we generally want to see Low Volume
at key points Like Phase C and LPS" — and volume never gates, never earns points
(his answer 10). This study measures each line as a fact on the DAILY bars of the
base, for every matured episode of the engine's fires and for his calibration
setups (their own group, never pooled), and asks whether it separates outcomes.

Already measured and NOT repeated here (docs/decisions.md Nulls, 2026-10-03):
O'Neil's 50-day up/down volume ratio and Minervini's stage criteria 5 and 6 (whole
weeks over the advance). This reads inside the BASE and at its key points.

The facts (all from bars up to the read day; nothing after it is used):
  up_down_volume   mean volume on up days / on down days, inside the base
  up_down_size     mean up-day change / mean down-day change (absolute), inside the base
  heavy_declines   down days inside the base that fall a full average day's range or
                   more on 1.5x the 50-day volume or more
  lps_volume       the LPS pullback's mean volume / the 50-day average; the pullback
                   is his ruled window (R18, 2026-09-13): the last run of receding
                   days (a lower high or a lower low) ending on the last receding day
Read from the archive, not recomputed:
  spring_vol_z     volume at the Phase C spring (bin_c_spring_vol_z), fires only
  breakout_volume  the trigger day's volume / its 50-day average (trigger_volume_ratio)
  vol_contraction  the base's volume dry-up, the one volume term scored today

Usage (repo venv, from the repo root; read-only against both inputs):
    python -m tools.research.volume_key_points_census --db COPY.db --cache COPY.parquet
    python -m tools.research.volume_key_points_census ... --json research/evidence/X.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

try:  # works under both `python -m tools.research.volume_key_points_census` and a direct run
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

configure_path(backend=True)

from core.archive.analyze import dedup_to_episodes                  # noqa: E402
from core.archive.calibration_outcomes import load_calibration_setups  # noqa: E402

HEAVY_VOLUME = 1.5        # x the 50-day average volume
TAIL = 0.25               # the +25% best gain the edge lives in (2026-09-08)
MIN_BASE_DAYS = 5
BOOTSTRAP_DRAWS = 2000


# ------------------------------------------------------------------
# The facts
# ------------------------------------------------------------------
def receding_days(high: np.ndarray, low: np.ndarray) -> np.ndarray:
    """A receding day makes a lower high or a lower low than the day before (R18)."""
    out = np.zeros(len(high), dtype=bool)
    out[1:] = (high[1:] < high[:-1]) | (low[1:] < low[:-1])
    return out


def lps_window(high: np.ndarray, low: np.ndarray, start: int, anchor: int):
    """(first, last) positions of the last run of receding days ending on the last
    receding day at or before ``anchor``, clipped to the base; None when the base
    has no receding day."""
    rec = receding_days(high[: anchor + 1], low[: anchor + 1])
    hits = np.flatnonzero(rec[start: anchor + 1])
    if not len(hits):
        return None
    last = start + int(hits[-1])
    first = last
    while first - 1 >= start and rec[first - 1]:
        first -= 1
    return first, last


def _ratio(a: float, b: float):
    return float(a / b) if np.isfinite(a) and np.isfinite(b) and b > 0 else None


def base_volume_read(frame: pd.DataFrame, start: int, anchor: int) -> dict | None:
    """The Momentum Masters volume facts of one base, read on ``anchor``.

    ``frame`` holds daily High/Low/Close/Volume in date order; ``start`` and
    ``anchor`` are the base's first and last positions (inclusive). No bar after
    ``anchor`` is read. None when the base is too short to read.
    """
    if start < 1 or anchor - start + 1 < MIN_BASE_DAYS or anchor >= len(frame):
        return None
    high = frame["High"].to_numpy(float)
    low = frame["Low"].to_numpy(float)
    close = frame["Close"].to_numpy(float)
    volume = frame["Volume"].to_numpy(float)

    span = slice(start, anchor + 1)
    change = close[span] / close[start - 1: anchor] - 1.0
    vol = volume[span]
    up, down = change > 0, change < 0
    vol50 = np.nanmean(volume[max(0, anchor - 49): anchor + 1])
    adr = np.nanmean(high[max(0, anchor - 19): anchor + 1] / low[max(0, anchor - 19): anchor + 1] - 1.0)

    window = lps_window(high, low, start, anchor)
    lps_volume = _ratio(np.nanmean(volume[window[0]: window[1] + 1]), vol50) if window else None
    heavy = down & (-change >= adr) & (vol >= HEAVY_VOLUME * vol50)
    return {
        "up_down_volume": _ratio(np.nanmean(vol[up]) if up.any() else np.nan,
                                 np.nanmean(vol[down]) if down.any() else np.nan),
        "up_down_size": _ratio(np.nanmean(change[up]) if up.any() else np.nan,
                               np.nanmean(-change[down]) if down.any() else np.nan),
        "heavy_declines": int(heavy.sum()),
        "lps_volume": lps_volume,
        "lps_days": (window[1] - window[0] + 1) if window else None,
        "base_days": anchor - start + 1,
    }


# ------------------------------------------------------------------
# Inputs
# ------------------------------------------------------------------
def _ticker_frame(panel: pd.DataFrame, ticker: str):
    if ticker not in panel.columns.get_level_values(0):
        return None
    frame = panel[ticker][["High", "Low", "Close", "Volume"]].dropna(how="any")
    return frame if len(frame) else None


def _position(index: pd.DatetimeIndex, day, *, before: bool = False):
    """Position of the last trading day at or before ``day`` (strictly before with
    ``before``); None when the frame does not reach back that far."""
    ts = pd.Timestamp(day)
    pos = int(index.searchsorted(ts, side="left" if before else "right")) - 1
    return pos if pos >= 0 else None


def _outcome(row) -> dict:
    mfe = row.get("mfe_60d")
    if mfe is None or pd.isna(mfe):
        bars = row.get("bars_to_date")
        mfe = row.get("mfe_to_date") if bars is not None and not pd.isna(bars) and bars >= 40 else None
    label = row.get("barrier_label")
    return {
        "mfe": None if mfe is None or pd.isna(mfe) else float(mfe),
        "resolved": label in ("win", "loss"),
        "win": label == "win",
    }


def fire_rows(db: str, panel: pd.DataFrame) -> pd.DataFrame:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM setup_archive WHERE source = 'screener' AND universe_type = 'us_equities'", con)
    finally:
        con.close()
    df = dedup_to_episodes(df)
    out = []
    for _, row in df.iterrows():
        outcome = _outcome(row)
        if outcome["mfe"] is None or pd.isna(row.get("base_length")):
            continue
        frame = _ticker_frame(panel, row["ticker"])
        if frame is None:
            continue
        anchor = _position(frame.index, row["scan_date"])
        if anchor is None or frame.index[anchor] != pd.Timestamp(row["scan_date"]):
            continue
        read = base_volume_read(frame, anchor - int(row["base_length"]) + 1, anchor)
        if read is None:
            continue
        out.append({
            "ticker": row["ticker"], "scan_date": row["scan_date"], "adr_pct": row.get("adr_pct"),
            "base_length": row.get("base_length"), **read, **outcome,
            "spring_vol_z": row.get("bin_c_spring_vol_z"),
            "breakout_volume": row.get("trigger_volume_ratio"),
            "vol_contraction": row.get("vol_contraction"),
        })
    return pd.DataFrame(out)


def calibration_rows(db: str, panel: pd.DataFrame) -> pd.DataFrame:
    cal = load_calibration_setups(db)
    out = []
    for _, row in cal.iterrows():
        frame = _ticker_frame(panel, row["ticker"])
        if frame is None or pd.isna(row.get("box_start_date")):
            continue
        # The outcome's own anchor: the trading day before his trigger, else his as-of day.
        anchor_day = row.get("anchor_date")
        if anchor_day is None or pd.isna(anchor_day):
            anchor = (_position(frame.index, row["his_trigger_date"], before=True)
                      if not pd.isna(row.get("his_trigger_date")) else _position(frame.index, row["as_of_date"]))
        else:
            anchor = _position(frame.index, anchor_day)
        start = _position(frame.index, row["box_start_date"], before=True)
        if anchor is None or start is None:
            continue
        read = base_volume_read(frame, start + 1, anchor)
        if read is None:
            continue
        mfe = row.get("mfe_60d")
        if mfe is None or pd.isna(mfe):
            mfe = row.get("mfe_to_date")
        out.append({
            "ticker": row["ticker"], "label": row.get("label"), **read,
            "mfe": None if mfe is None or pd.isna(mfe) else float(mfe),
            "breakout_volume": row.get("trigger_volume_ratio"),
        })
    return pd.DataFrame(out)


# ------------------------------------------------------------------
# The read against outcomes
# ------------------------------------------------------------------
def _rates(rows: pd.DataFrame) -> dict:
    resolved = rows[rows["resolved"]]
    return {
        "n": int(len(rows)),
        "tail_rate": round(float((rows["mfe"] >= TAIL).mean()), 4) if len(rows) else None,
        "median_mfe": round(float(rows["mfe"].median()), 4) if len(rows) else None,
        "win_rate": round(float(resolved["win"].mean()), 4) if len(resolved) else None,
        "n_resolved": int(len(resolved)),
    }


def _gap_ci(low: pd.DataFrame, high: pd.DataFrame, seed: int = 7) -> list | None:
    """95% interval of (top bin tail rate - bottom bin tail rate), resampling scan
    DAYS (fires on one day share a market), not rows."""
    if low.empty or high.empty:
        return None
    rng = np.random.default_rng(seed)
    days = np.array(sorted(set(low["scan_date"]) | set(high["scan_date"])))
    lo_by = {d: g["mfe"].to_numpy() for d, g in low.groupby("scan_date")}
    hi_by = {d: g["mfe"].to_numpy() for d, g in high.groupby("scan_date")}
    gaps = []
    for _ in range(BOOTSTRAP_DRAWS):
        pick = rng.choice(days, size=len(days), replace=True)
        lo = np.concatenate([lo_by[d] for d in pick if d in lo_by] or [np.array([])])
        hi = np.concatenate([hi_by[d] for d in pick if d in hi_by] or [np.array([])])
        if len(lo) and len(hi):
            gaps.append((hi >= TAIL).mean() - (lo >= TAIL).mean())
    return [round(float(np.percentile(gaps, 2.5)), 4), round(float(np.percentile(gaps, 97.5)), 4)] if gaps else None


def quartile_read(fires: pd.DataFrame, column: str) -> dict:
    rows = fires[fires[column].notna()].copy()
    if len(rows) < 40:
        return {"n": int(len(rows)), "note": "too few rows"}
    rows["bin"] = pd.qcut(rows[column].rank(method="first"), 4, labels=False)
    bins = []
    for b, group in rows.groupby("bin"):
        bins.append({"range": [round(float(group[column].min()), 3), round(float(group[column].max()), 3)],
                     **_rates(group)})
    volatile = rows[rows["adr_pct"] >= rows["adr_pct"].quantile(2 / 3)] if rows["adr_pct"].notna().any() else rows.iloc[:0]
    volatile_bins = ([_rates(g)["tail_rate"] for _, g in volatile.groupby("bin")] if len(volatile) >= 40 else None)
    return {
        "n": int(len(rows)), "bins": bins,
        "top_minus_bottom_tail_ci": _gap_ci(rows[rows["bin"] == 0], rows[rows["bin"] == 3]),
        "volatile_third_tail_by_bin": volatile_bins,
    }


def count_read(fires: pd.DataFrame, column: str) -> dict:
    rows = fires[fires[column].notna()]
    groups = {"0": rows[rows[column] == 0], "1": rows[rows[column] == 1], "2+": rows[rows[column] >= 2]}
    return {"n": int(len(rows)), "groups": {k: _rates(g) for k, g in groups.items()},
            "two_plus_minus_none_tail_ci": _gap_ci(groups["0"], groups["2+"])}


def calibration_read(fires: pd.DataFrame, cal: pd.DataFrame, column: str) -> dict | None:
    if column not in cal or cal[column].notna().sum() == 0:
        return None
    his = cal[column].dropna().astype(float)
    pool = fires[column].dropna().astype(float)
    if column == "heavy_declines":   # a count: compare the shares at 0, 1 and 2+
        share = lambda x: [round(float((x == 0).mean()), 3), round(float((x == 1).mean()), 3),
                           round(float((x >= 2).mean()), 3)]
        return {"n": int(len(his)), "his_share_0_1_2plus": share(his), "fires_share_0_1_2plus": share(pool)}
    edges = pool.quantile([0.25, 0.5, 0.75]).to_numpy()
    in_bins = np.bincount(np.searchsorted(edges, his.to_numpy(), side="right"), minlength=4)
    return {
        "n": int(len(his)), "his_median": round(float(his.median()), 3),
        "fires_median": round(float(pool.median()), 3),
        "his_median_fire_percentile": round(float((pool < his.median()).mean()), 3),
        "his_count_by_fire_quartile": [int(x) for x in in_bins],
    }


def controlled_read(fires: pd.DataFrame, column: str, *, count: bool = False) -> dict:
    """The +25% rate by the fact's bins inside each third of volatility (ADR) and
    of base length: a fact that only stands in for one of them goes flat here."""
    rows = fires[fires[column].notna()].copy()
    rows["bin"] = (np.where(rows[column] >= 2, 2, rows[column]).astype(int) if count
                   else pd.qcut(rows[column].rank(method="first"), 4, labels=False))
    out = {}
    for control in ("adr_pct", "base_length"):
        rows["third"] = pd.qcut(pd.to_numeric(rows[control], errors="coerce").rank(method="first"), 3, labels=False)
        out[control] = {
            int(third): {int(b): [int(len(g)), round(float((g["mfe"] >= TAIL).mean()), 4)]
                         for b, g in group.groupby("bin")}
            for third, group in rows.groupby("third")
        }
    out["median_base_length_by_bin"] = {int(b): float(pd.to_numeric(g["base_length"]).median())
                                        for b, g in rows.groupby("bin")}
    return out


CONTINUOUS = ("up_down_volume", "up_down_size", "lps_volume", "spring_vol_z", "breakout_volume", "vol_contraction")


def census(db: str, cache: str) -> dict:
    panel = pd.read_parquet(cache)
    if getattr(panel.index, "tz", None) is not None:
        panel.index = panel.index.tz_localize(None)
    fires = fire_rows(db, panel)
    cal = calibration_rows(db, panel)
    for col in CONTINUOUS:
        if col in fires:
            fires[col] = pd.to_numeric(fires[col], errors="coerce")
    report = {
        "inputs": {"db": os.path.basename(db), "cache_last_day": str(panel.index[-1].date())},
        "fires": {"episodes": int(len(fires)), "all": _rates(fires)},
        "calibration": {"setups": int(len(cal)),
                        "tail_rate": round(float((cal["mfe"].dropna() >= TAIL).mean()), 4) if len(cal) else None},
        "facts": {},
    }
    for col in CONTINUOUS:
        report["facts"][col] = {"fires": quartile_read(fires, col),
                                "calibration": calibration_read(fires, cal, col)}
    report["facts"]["heavy_declines"] = {"fires": count_read(fires, "heavy_declines"),
                                         "calibration": calibration_read(fires, cal, "heavy_declines")}
    report["controls"] = {"vol_contraction": controlled_read(fires, "vol_contraction"),
                          "lps_volume": controlled_read(fires, "lps_volume"),
                          "heavy_declines": controlled_read(fires, "heavy_declines", count=True)}
    report["fires"]["scan_days"] = [str(fires["scan_date"].min()), str(fires["scan_date"].max()),
                                    int(fires["scan_date"].nunique())]
    return report


def _print(report: dict) -> None:
    f = report["fires"]["all"]
    print(f"fires: {report['fires']['episodes']} matured episodes | +25% {f['tail_rate']:.1%} | "
          f"win {f['win_rate']:.1%} of {f['n_resolved']} resolved")
    print(f"calibration: {report['calibration']['setups']} setups | +25% {report['calibration']['tail_rate']:.1%}")
    for name, fact in report["facts"].items():
        fires = fact["fires"]
        print(f"\n== {name}  (n={fires['n']})")
        if "bins" in fires:
            for b in fires["bins"]:
                win = "-" if b["win_rate"] is None else f"{b['win_rate']:.1%}"
                print(f"   {b['range'][0]:>8} .. {b['range'][1]:<8} n={b['n']:<5} +25% {b['tail_rate']:.1%}  "
                      f"win {win}  med MFE {b['median_mfe']:.1%}")
            print(f"   top-bottom +25% gap 95% CI {fires['top_minus_bottom_tail_ci']} | "
                  f"volatile third by bin {fires['volatile_third_tail_by_bin']}")
        elif "groups" in fires:
            for k, g in fires["groups"].items():
                print(f"   {k:>3}: n={g['n']:<5} +25% {g['tail_rate'] or 0:.1%}  win {g['win_rate'] or 0:.1%}")
            print(f"   2+ minus 0 +25% gap 95% CI {fires['two_plus_minus_none_tail_ci']}")
        cal = fact["calibration"]
        if cal and "his_share_0_1_2plus" in cal:
            print(f"   his setups: n={cal['n']} share at 0/1/2+ {cal['his_share_0_1_2plus']} "
                  f"vs fires {cal['fires_share_0_1_2plus']}")
        elif cal:
            print(f"   his setups: n={cal['n']} median {cal['his_median']} vs fires {cal['fires_median']} "
                  f"(fire percentile {cal['his_median_fire_percentile']:.0%}); by fire quartile {cal['his_count_by_fire_quartile']}")


def _print_controls(report: dict) -> None:
    names = {"adr_pct": ("quiet", "mid", "volatile"), "base_length": ("short", "mid", "long")}
    for fact, read in report["controls"].items():
        print(f"\n== {fact}: +25% by bin inside each third (bin: [n, rate])")
        for control, thirds in read.items():
            if control == "median_base_length_by_bin":
                print(f"   median base length by bin {thirds}")
                continue
            for third, bins in thirds.items():
                cells = "  ".join(f"{b}:{r:.1%}(n={n})" for b, (n, r) in bins.items())
                print(f"   {control:<11} {names[control][third]:<8} {cells}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", required=True, help="a COPY of the archive DB (opened read-only)")
    parser.add_argument("--cache", required=True, help="a COPY of the 5-year price cache parquet")
    parser.add_argument("--json", help="write the report here (research/evidence/...)")
    args = parser.parse_args()
    report = census(args.db, args.cache)
    _print(report)
    _print_controls(report)
    if args.json:
        refuse_sealed_output(args.json)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
