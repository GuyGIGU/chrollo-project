"""Layer-2 staircase eyeball — read_box_staircase on real elected boxes.

Read-only. For each ticker that fires on the latest archived scan (or an explicit
list), replay the live spine to the active equilibrium box the LPS lives in, then
run the L2 staircase reader (``read_box_staircase``) over that box's base and
print the labeled, chronological HH/HL/LH/LL staircase with each swing's rail
event (touch/breach R/S) and box-zone.

The eyeball: does the printed staircase match the chart's actual zigzag — do the
peaks/valleys land where price turned, do the rail touches/breaches line up with
R/S, and does ``is_zigzag`` agree with whether a real two-sided equilibrium
exists? It changes nothing and gates nothing.

    python -m tools.l2_staircase_audit                 # latest-scan fires
    python -m tools.l2_staircase_audit AEF NMAI BHF     # explicit tickers
    python -m tools.l2_staircase_audit --cluster        # the swing-census cluster
"""
from __future__ import annotations

import argparse
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_THIS, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd

from config import settings
from engine_alpha.structure.metrics import (
    assemble_box_narrative,
    measure_resistance_events,
    read_box_staircase,
)
from tools.lps_swing_census import CLUSTER, _first_complete, _latest_scan_fires
from tools.structure_case_audit import _prep


def _date_at(df: pd.DataFrame, idx: int) -> str:
    if 0 <= idx < len(df):
        try:
            return str(df.index[idx])[:10]
        except (IndexError, TypeError, ValueError):
            return "?"
    return "?"


def audit(tickers: list[str]) -> None:
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    level0 = set(d.columns.get_level_values(0))

    for t in tickers:
        t = t.upper()
        if t not in level0:
            print(f"{t}: not-in-cache")
            continue
        prep = _prep(d[t].dropna())
        if prep[0] is None:
            print(f"{t}: prep-reject ({prep[1]})")
            continue
        df, atr = prep
        box, lps = _first_complete(df, atr)
        if box is None:
            print(f"{t}: no-complete-narrative (does not fire today)")
            continue

        start = int(box.start_bar)
        base = df.iloc[start:]
        out = read_box_staircase(base, float(box.R), float(box.S), atr)

        c = out["counts"]
        print(f"\n{t}  box S={box.S:.2f} R={box.R:.2f}  "
              f"n_swings={out['n_swings']}  HH:{c['HH']} HL:{c['HL']} "
              f"LH:{c['LH']} LL:{c['LL']}  trend={out['trend_state']}  "
              f"rail_to_rail={out['rail_to_rail']}  is_zigzag={out['is_zigzag']}")
        if not out["swings"]:
            continue
        print(f"    {'date':>10} {'kind':>6} {'label':>5} {'boxPos':>7} "
              f"{'zone':>5} {'rail_event':>10}")
        for s in out["swings"]:
            date = _date_at(df, start + int(s["bar"]))
            print(f"    {date:>10} {s['kind']:>6} {s['label']:>5} "
                  f"{s['box_pos']:>7.2f} {s['zone']:>5} {s['rail_event']:>10}")

        events = measure_resistance_events(df.iloc[start:], float(box.R),
                                           float(box.S), atr)
        named = [e for e in events
                 if e["type"] in ("SOS", "markup", "upthrust", "in_progress")]
        if named:
            print(f"    R-rail events: "
                  + "; ".join(
                      f"{e['type']}@{_date_at(df, start + e['peak_bar'])}"
                      f"(ph{e['phase']} linger={e['linger_bars']} "
                      f"strBox={e['strength_box']} pkPos={e['peak_box_pos']})"
                      for e in named))
        n_rej = sum(1 for e in events if e["type"] == "rejection")
        n_range = sum(1 for e in events if e["type"] == "range")
        if n_rej or n_range:
            print(f"    (+ {n_rej} R-rejections, {n_range} Phase-B range reaches "
                  f"[not SOS])")

        # E2: the assembled narrative (the puzzle) + the explainable trace.
        nar = assemble_box_narrative(df, box, atr)
        s = nar["spine"]

        def _anchor(piece):
            return _date_at(df, start + int(piece["anchor_bar"])) if piece else "-"

        ut = " +terminal-upthrust" if nar["upthrust_terminal"] else ""
        print(f"    narrative: chronology={nar['chronology']} "
              f"completeness={nar['completeness']}/4{ut}  "
              f"spine[spring={_anchor(s['spring'])} sos={_anchor(s['sos'])} "
              f"lps={_anchor(s['lps'])}]  tests={nar['tests']}")
        for line in nar["trace"]:
            print(f"      | {line}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Layer-2 staircase eyeball.")
    ap.add_argument("tickers", nargs="*", help="tickers (default: latest-scan fires)")
    ap.add_argument("--cluster", action="store_true", help="the swing-census cluster")
    a = ap.parse_args()
    if a.cluster:
        tickers = CLUSTER
    elif a.tickers:
        tickers = a.tickers
    else:
        tickers = (_latest_scan_fires() or CLUSTER)[:12]   # cap default sweep
    audit(tickers)


if __name__ == "__main__":
    main()
