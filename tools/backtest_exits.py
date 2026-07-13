"""Scaled-exit backtest — run a profit-target ladder over the archived fires.

Answers the question the fixed-horizon reads cannot: if you enter each fire at the
signal, stop at the base (1R), and SCALE OUT at a ladder of R-multiple targets,
what is the realized-R expectancy — and does it beat passively holding? This is
the read that matches how the setups are actually traded.

Default ladder: 50% out at +3R, 25% at +6R, 25% at +8R (the operator's rule).
Two stop policies are reported side by side:
  * fixed     — the initial stop (base) holds for the whole remainder.
  * breakeven — after the first target fills, the stop moves to entry (risk-free).

Entry = the signal close (`current_price`); stop = ``s_level * 0.97`` (the base +
the engine's LPS_HOLD_TOLERANCE buffer) so 1R is the SAME risk unit the archive's
barrier / r_multiple stats use. Forward OHLC comes from the local cache (offline).

Read-only, offline. Never writes the archive.

Usage:
    python -m tools.backtest_exits --db output/backtest_weekly.db
    python -m tools.backtest_exits --db out.db --ladder "3:0.5,6:0.25,8:0.25"
    python -m tools.backtest_exits --db out.db --json out/exits.json
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Optional

import numpy as np
import pandas as pd

try:
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path()

from core.backtest import exit_sim
from core.backtest.loader import DEFAULT_DB_PATH, load_episodes
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE

STOP_MULT = 0.97   # LPS_HOLD_TOLERANCE — matches core.archive.forward_returns
SPY_SYMBOL = "SPY"
_LINES: list[str] = []


def emit(s: str = "") -> None:
    _LINES.append(s)


def _pct(v, nd: int = 1) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    return f"{v * 100:+.{nd}f}%"


def _f(v, nd: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    return f"{v:+.{nd}f}"


def _ohlc(panel: pd.DataFrame, ticker: str):
    try:
        sub = panel[ticker] if isinstance(panel.columns, pd.MultiIndex) else panel
    except KeyError:
        return None
    need = ("Open", "High", "Low", "Close")
    if not all(c in sub for c in need):
        return None
    out = sub[list(need)].dropna()
    return out if not out.empty else None


def _spy_return(spy_close: Optional[pd.Series], entry_ts, bars_held: int) -> Optional[float]:
    """SPY close-to-close return over the same holding window (entry -> +bars_held)."""
    if spy_close is None:
        return None
    on = spy_close.index <= entry_ts
    if not on.any():
        return None
    base = float(spy_close.loc[spy_close.index[on][-1]])
    fwd = spy_close[spy_close.index > entry_ts]
    if fwd.empty or base <= 0:
        return None
    j = min(bars_held, len(fwd)) - 1
    return float(fwd.iloc[j] / base - 1.0)


def run_exits(db_path: Optional[str], cache_path: Optional[str],
              ladder: list[tuple[float, float]], max_bars: int = 60,
              trail_r: Optional[float] = None,
              json_path: Optional[str] = None) -> dict:
    from config import settings

    _LINES.clear()
    df = load_episodes(db_path=db_path, source="screener",
                       universe_type=DEFAULT_UNIVERSE_TYPE)
    cpath = cache_path or settings.CACHE_FILENAME
    panel = pd.read_parquet(cpath, engine=settings.PARQUET_ENGINE)
    if hasattr(panel.index, "tz") and panel.index.tz is not None:
        panel.index = panel.index.tz_localize(None)
    spy_close = None
    sp = _ohlc(panel, SPY_SYMBOL)
    if sp is not None:
        spy_close = sp["Close"]

    sold_frac = sum(f for _, f in ladder)
    ladder_str = ", ".join(f"{int(f*100)}%@{r:g}R" for r, f in ladder)
    runner = 1.0 - sold_frac
    if runner > 1e-9:
        ladder_str += (f", {int(round(runner*100))}% trail {trail_r:g}R" if trail_r
                       else f", {int(round(runner*100))}% ride-to-horizon")
    emit("=" * 72)
    emit("  CHROLLO SCALED-EXIT BACKTEST")
    emit("=" * 72)
    emit(f"DB: {db_path or DEFAULT_DB_PATH}  (read-only)")
    emit(f"Ladder: {ladder_str}   entry=signal close   stop=base x{STOP_MULT} (1R)")
    emit(f"Horizon cap: {max_bars} bars   episodes (source='screener'): {len(df)}")

    # Simulate every fire under both stop policies.
    rows_fixed: list[dict] = []
    rows_be: list[dict] = []
    skipped = 0
    ohlc_cache: dict[str, Optional[pd.DataFrame]] = {}
    for r in df.itertuples(index=False):
        ticker = getattr(r, "ticker", None)
        scan_date = getattr(r, "scan_date", None)
        s_level = getattr(r, "s_level", None)
        if ticker is None or scan_date is None or s_level is None:
            skipped += 1
            continue
        if ticker not in ohlc_cache:
            ohlc_cache[ticker] = _ohlc(panel, str(ticker))
        o = ohlc_cache[ticker]
        if o is None:
            skipped += 1
            continue
        ts = pd.Timestamp(scan_date)
        on = o.index <= ts
        if not on.any():
            skipped += 1
            continue
        entry_ts = o.index[on][-1]
        entry = float(o["Close"].loc[entry_ts])
        try:
            stop = float(s_level) * STOP_MULT
        except (TypeError, ValueError):
            skipped += 1
            continue
        fwd = o[o.index > entry_ts]
        if fwd.empty or entry <= stop:
            skipped += 1
            continue
        opens = fwd["Open"].to_numpy(float)
        highs = fwd["High"].to_numpy(float)
        lows = fwd["Low"].to_numpy(float)
        closes = fwd["Close"].to_numpy(float)
        tier = getattr(r, "tier", None)
        regime = getattr(r, "spy_trend", None)
        for mode, bucket in (("fixed", rows_fixed), ("breakeven", rows_be)):
            sim = exit_sim.simulate_scaled_exit(
                opens, highs, lows, closes, entry, stop,
                ladder=ladder, stop_mode=mode, max_bars=max_bars, trail_r=trail_r)
            if sim is None:
                continue
            spy_ret = _spy_return(spy_close, entry_ts, sim["bars_held"])
            bucket.append({
                "tier": tier, "regime": regime,
                "realized_r": sim["realized_r"], "realized_ret": sim["realized_ret"],
                "reason": sim["reason"], "bars_held": sim["bars_held"],
                "n_targets": len(sim["targets_hit"]), "max_r": sim["max_r"],
                "abnormal": (sim["realized_ret"] - spy_ret) if spy_ret is not None else None,
            })

    for mode, rows in (("FIXED stop (base held throughout)", rows_fixed),
                       ("BREAKEVEN stop (raised to entry after 1st target)", rows_be)):
        _emit_report(mode, pd.DataFrame(rows))
    emit("")
    emit(f"[skipped {skipped} episodes lacking s_level / forward data]")

    report = "\n".join(_LINES)
    try:
        print(report)
    except UnicodeEncodeError:
        import sys
        sys.stdout.buffer.write(report.encode("utf-8", "replace") + b"\n")

    structured = {
        "ladder": ladder, "max_bars": max_bars, "n_episodes": len(df), "skipped": skipped,
        "fixed": _cohort_stats(pd.DataFrame(rows_fixed)),
        "breakeven": _cohort_stats(pd.DataFrame(rows_be)),
        "fixed_by_tier": _by(pd.DataFrame(rows_fixed), "tier"),
        "fixed_by_regime": _by(pd.DataFrame(rows_fixed), "regime"),
        "breakeven_by_tier": _by(pd.DataFrame(rows_be), "tier"),
        "breakeven_by_regime": _by(pd.DataFrame(rows_be), "regime"),
    }
    if json_path:
        out = json_path if os.path.isabs(json_path) else os.path.join(_PROJECT_ROOT, json_path)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(structured, f, indent=2, default=str)
        print(f"\n[structured report written to {out}]")
    return structured


def _cohort_stats(rows: pd.DataFrame) -> dict:
    if rows.empty:
        return {"n": 0}
    r = pd.to_numeric(rows["realized_r"], errors="coerce").dropna()
    ret = pd.to_numeric(rows["realized_ret"], errors="coerce").dropna()
    ab = pd.to_numeric(rows["abnormal"], errors="coerce").dropna()
    nt = pd.to_numeric(rows["n_targets"], errors="coerce")
    stopped = rows["reason"].isin(["stop", "gap_stop", "breakeven_stop"])
    n = int(len(r))
    return {
        "n": n,
        "expectancy_r": float(r.mean()),
        "median_r": float(r.median()),
        "win_rate": float((r > 0).mean()),
        "stopped_rate": float(stopped.mean()),   # exited at the stop (a loss for the remainder)
        "no_3r_rate": float((nt == 0).mean()),    # never reached the first target
        "hit_3r": float((nt >= 1).mean()),
        "hit_6r": float((nt >= 2).mean()),
        "hit_8r": float((nt >= 3).mean()),
        "avg_bars_held": float(pd.to_numeric(rows["bars_held"], errors="coerce").mean()),
        "mean_ret": float(ret.mean()) if not ret.empty else None,
        "mean_abnormal": float(ab.mean()) if not ab.empty else None,
    }


def _by(rows: pd.DataFrame, col: str) -> dict:
    if rows.empty or col not in rows.columns:
        return {}
    return {str(k): _cohort_stats(sub) for k, sub in rows.groupby(col)}


def _emit_report(title: str, rows: pd.DataFrame) -> None:
    emit("")
    emit("-" * 72)
    emit(f"  {title}")
    emit("-" * 72)
    overall = _cohort_stats(rows)
    if overall["n"] == 0:
        emit("  (no trades)")
        return
    emit(f"  trades={overall['n']}   EXPECTANCY {_f(overall['expectancy_r'])}R/trade   "
         f"median {_f(overall['median_r'])}R   win {_pct(overall['win_rate'])}")
    emit(f"  reached: 3R {_pct(overall['hit_3r'])}  6R {_pct(overall['hit_6r'])}  "
         f"8R {_pct(overall['hit_8r'])}   stopped-out {_pct(overall['stopped_rate'])}   "
         f"never-3R {_pct(overall['no_3r_rate'])}")
    emit(f"  mean realized return {_pct(overall['mean_ret'])}   "
         f"abnormal vs SPY {_pct(overall['mean_abnormal'])}   "
         f"avg held {overall['avg_bars_held']:.0f} bars")
    emit("")
    emit(f"  {'by tier':<12}{'n':>7}{'exp R':>9}{'win':>8}{'3R':>7}{'6R':>7}{'8R':>7}")
    for tier in ["S", "A", "B", "C"]:
        st = _by(rows, "tier").get(tier)
        if st:
            emit(f"  {tier:<12}{st['n']:>7}{_f(st['expectancy_r']):>9}{_pct(st['win_rate']):>8}"
                 f"{_pct(st['hit_3r']):>7}{_pct(st['hit_6r']):>7}{_pct(st['hit_8r']):>7}")
    emit("")
    emit(f"  {'by regime':<12}{'n':>7}{'exp R':>9}{'win':>8}{'3R':>7}{'6R':>7}{'8R':>7}")
    for reg in ["uptrend", "neutral", "downtrend"]:
        st = _by(rows, "regime").get(reg)
        if st:
            emit(f"  {reg:<12}{st['n']:>7}{_f(st['expectancy_r']):>9}{_pct(st['win_rate']):>8}"
                 f"{_pct(st['hit_3r']):>7}{_pct(st['hit_6r']):>7}{_pct(st['hit_8r']):>7}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Chrollo scaled-exit backtest.")
    ap.add_argument("--db", default=None, help="sqlite archive (default: prod DB, read-only)")
    ap.add_argument("--cache", default=None, help="price panel parquet (default: settings.CACHE_FILENAME)")
    ap.add_argument("--ladder", default="3:0.5,6:0.25,8:0.25",
                    help="R:fraction ladder, e.g. '3:0.5,6:0.25,8:0.25'")
    ap.add_argument("--max-bars", type=int, default=60, help="holding horizon cap (bars)")
    ap.add_argument("--trail-r", type=float, default=None,
                    help="trail the leftover runner this many R below the high-water mark "
                         "(only meaningful when the ladder fractions sum to < 1)")
    ap.add_argument("--json", default=None, help="also write a structured JSON report here")
    args = ap.parse_args()
    ladder = exit_sim.parse_ladder(args.ladder)
    run_exits(db_path=args.db, cache_path=args.cache, ladder=ladder,
              max_bars=args.max_bars, trail_r=args.trail_r, json_path=args.json)


if __name__ == "__main__":
    main()
