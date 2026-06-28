"""LPS anchor-swing census — the dissection surface for the "up-swing LPS" bug.

Read-only. For each ticker it replays the live spine (root walk -> first complete
A->B->(C?)->D, exactly as ``read_structure`` resolves), then inspects the elected
Phase-D LPS and measures whether its ANCHOR bar is a bullish thrust to a fresh
high (the GTX-class fault) versus a genuine reaction into support.

The question this answers: is there a clean numeric separator between
"thrust-at-crest LPS" and a legitimate high-in-box reaction (BUEC shelf)?

    python -m tools.lps_swing_census                 # latest-scan fires from the archive
    python -m tools.lps_swing_census GTX RMAX SMG     # explicit tickers
    python -m tools.lps_swing_census --cluster        # just the known 7 cluster names

Everything reads the live parquet cache and the calibrated bricks; it changes
nothing and gates nothing.
"""
from __future__ import annotations

import argparse
import os
import sqlite3

from tools._bootstrap import configure_path

_ROOT = configure_path()

import numpy as np
import pandas as pd

from config import settings
from core.structure import bricks
from tools.structure_case_audit import _complete_narrative, _prep

# The cluster the latest-scan archive query flagged (short LPS + high-in-box +
# ascending Phase D). GTX is the clean exemplar.
CLUSTER = ["RMAX", "RRR", "SMG", "MTRX", "GTX", "ALTG", "PPSI"]

_DB_PATH = os.path.join(_ROOT, "webapp", "backend", "trading_journal.db")


def _latest_scan_fires() -> list[str]:
    """Tickers that fired LPS/REBOUND on the most recent archived scan."""
    if not os.path.exists(_DB_PATH):
        return []
    con = sqlite3.connect(_DB_PATH)
    try:
        latest = con.execute("SELECT MAX(scan_date) FROM setup_archive").fetchone()[0]
        rows = con.execute(
            "SELECT DISTINCT ticker FROM setup_archive "
            "WHERE scan_date=? AND setup_type IN ('LPS','REBOUND')",
            (latest,),
        ).fetchall()
    finally:
        con.close()
    return sorted(r[0] for r in rows)


def _first_complete(df, atr):
    """Walk roots oldest-first; return (box, lps) for the FIRST root that
    completes the narrative — exactly the spine's resolution order."""
    search_from = 0
    for _ in range(64):  # _MAX_ANCHORS parity
        root = bricks.find_root_swing(df, search_from_bar=search_from, atr=atr)
        if root is None:
            return None, None
        search_from = int(root.climax_bar) + 1
        box = bricks.validate_equilibrium(df, root, atr)
        if box is None:
            continue
        lps, _lps_in_inner, inner, _spring = _complete_narrative(df, box, atr)
        if lps is not None:
            # _complete_narrative tries inner-box LPS first; report the box the
            # LPS actually lives in so the rails match the elected window.
            return (inner if (_lps_in_inner and inner is not None) else box), lps
    return None, None


def _anchor_features(df, box, lps, atr) -> dict:
    """Is the LPS a clean 'peak that goes down' — first bar = window peak, last
    bar = window trough — or does it rise into a later peak / bounce up at the end?

    Operator's definition: the LPS swing is measured from the HIGH of the first
    bar to the LOW of the last bar. So a valid LPS must START at its highest high
    and END at its lowest low. Two violations make it an 'up-swing LPS':
      - peak_not_first: a later bar's high exceeds the first bar's high (price
        rose into a later peak — the swing is not anchored at the top).
      - trough_not_last: the lowest low is earlier than the last bar (price
        bounced back up at the end — the swing finishes on an up-move).
    """
    eps_hi = lps.window_high * 0.001
    eps_lo = lps.window_low * 0.001
    first_is_peak = lps.first_high >= lps.window_high - eps_hi
    last_is_trough = lps.last_low <= lps.window_low + eps_lo
    return {
        "first_is_peak": bool(first_is_peak),
        "last_is_trough": bool(last_is_trough),
        "peak_drop_box": (lps.window_high - lps.first_high) / (box.R - box.S) if (box.R - box.S) > 0 else 0.0,
        "trough_rise_box": (lps.last_low - lps.window_low) / (box.R - box.S) if (box.R - box.S) > 0 else 0.0,
        "clean_peak_down": bool(first_is_peak and last_is_trough),
    }


def census(tickers: list[str]) -> None:
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    level0 = set(d.columns.get_level_values(0))

    hdr = (f"{'ticker':>7} {'len':>3} {'off':>3} {'zone':>9} {'swing_type':>20} "
           f"{'1stPeak':>7} {'lastLow':>7} {'pkDrop':>7} {'trRise':>7} {'hiDesc':>6} {'loDesc':>6}  flag")
    print(hdr)
    print("-" * len(hdr))

    rows = []
    for t in tickers:
        t = t.upper()
        if t not in level0:
            print(f"{t:>7}  not-in-cache")
            continue
        raw = d[t].dropna()
        prep = _prep(raw)
        if prep[0] is None:
            print(f"{t:>7}  prep-reject: {prep[1]}")
            continue
        df, atr = prep
        box, lps = _first_complete(df, atr)
        if lps is None:
            print(f"{t:>7}  no-complete-narrative (does not fire today)")
            continue
        feats = _anchor_features(df, box, lps, atr)
        flag = "" if feats["clean_peak_down"] else "<< UP-SWING"
        print(f"{t:>7} {lps.length:>3} {lps.offset:>3} {lps.zone_type:>9} {lps.swing_type:>20} "
              f"{('Y' if feats['first_is_peak'] else 'n'):>7} {('Y' if feats['last_is_trough'] else 'n'):>7} "
              f"{feats['peak_drop_box']:>7.2f} {feats['trough_rise_box']:>7.2f} "
              f"{lps.high_descent_frac:>6.2f} {lps.descent_frac:>6.2f}  {flag}")
        rows.append({"ticker": t, "clean": feats["clean_peak_down"],
                     "first_is_peak": feats["first_is_peak"], "last_is_trough": feats["last_is_trough"],
                     "swing_type": lps.swing_type, "len": lps.length, "off": lps.offset,
                     "hi_desc": lps.high_descent_frac, "lo_desc": lps.descent_frac})

    _separator_summary(rows)


def _separator_summary(rows: list[dict]) -> None:
    if not rows:
        return
    bad = [r for r in rows if not r["clean"]]
    print()
    print(f"PEAK-GOING-DOWN SCAN  ({len(rows)} fires)")
    print(f"  clean peak->trough : {sum(1 for r in rows if r['clean'])}/{len(rows)}")
    print(f"  peak NOT first bar : {sum(1 for r in rows if not r['first_is_peak'])}")
    print(f"  trough NOT last bar: {sum(1 for r in rows if not r['last_is_trough'])}")
    if bad:
        print(f"  UP-SWING fires ({len(bad)}): "
              + ", ".join(f"{r['ticker']}({r['swing_type']})" for r in bad))
    # Where are the known-good cluster names?
    for t in CLUSTER:
        r = next((r for r in rows if r["ticker"] == t), None)
        if r is not None:
            print(f"    {t:>6}: {'CLEAN' if r['clean'] else 'UP-SWING'} "
                  f"(1stPeak={'Y' if r['first_is_peak'] else 'n'} lastLow={'Y' if r['last_is_trough'] else 'n'})")


def main() -> None:
    ap = argparse.ArgumentParser(description="LPS anchor-swing census.")
    ap.add_argument("tickers", nargs="*", help="tickers (default: latest-scan fires)")
    ap.add_argument("--cluster", action="store_true", help="just the known 7 cluster names")
    a = ap.parse_args()
    if a.cluster:
        tickers = CLUSTER
    elif a.tickers:
        tickers = a.tickers
    else:
        tickers = _latest_scan_fires() or CLUSTER
    census(tickers)


if __name__ == "__main__":
    main()
