"""
Limb-traversal "would-reject" report — the eyeball surface for the v1 shadow read.

Runs the REAL per-ticker pipeline over the frozen shadow fixture (offline, no
network) and, for every FIRING setup, reads the freshly-measured limb-traversal
fields (`_trav_*`). It flags the setups whose selected outer box has fewer than
``settings.TRAVERSAL_MIN`` genuine rail-to-rail traversals — i.e. exactly the
dead-space framings the v2 pool-aware gate would re-anchor or drop.

This changes nothing and gates nothing (v1 is measure-first). It exists so we can
eyeball "what would the gate touch, and is it really the ugly-but-high-ranked
dead-space pathology?" BEFORE flipping TRAVERSAL_GATE_ENABLED. The tier breakdown
is the point: a clean engine should mostly flag C/D chop, and any S/A it flags is
a wide-box-ranking-high case worth a chart look.

    python -m tools.traversal_report
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import settings
from core.pipeline.screener import _evaluate_ticker
from tools.shadow_diff import _load_fixture

_TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}


def _fire_universe() -> list[dict]:
    """Run the offline fixture pipeline and return one row per firing setup,
    carrying the traversal diagnostics alongside Tier / Score / Box Width."""
    frames, scalars = _load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None

    rows: list[dict] = []
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        res = _evaluate_ticker(ticker, df, spy_6m, breadth)
        if res is None:
            continue
        rows.append({
            "ticker": ticker,
            "tier": res.get("Tier", "?"),
            "score": res.get("Score"),
            "box_width": res.get("Box Width"),
            "n_full": res.get("_trav_n_full_traversals"),
            "n_swings": res.get("_trav_n_swings"),
            "top_dead": res.get("_trav_top_dead_space"),
            "bottom_dead": res.get("_trav_bottom_dead_space"),
            "max_swing": res.get("_trav_max_swing_frac"),
        })
    return rows


def _fmt(v, nd=2) -> str:
    if v is None:
        return "  -"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def _sort_key(r: dict):
    # Worst offenders first: high tier (S before D), then high score within tier.
    return (_TIER_ORDER.get(r["tier"], 9), -(r["score"] or 0.0))


def main() -> None:
    rows = _fire_universe()
    if not rows:
        print("No firing setups in the fixture — nothing to report.")
        return

    thr = settings.TRAVERSAL_MIN
    reject = [r for r in rows if (r["n_full"] or 0) < thr]
    keep = [r for r in rows if (r["n_full"] or 0) >= thr]

    print("=" * 80)
    print(f"  LIMB-TRAVERSAL WOULD-REJECT REPORT  (TRAVERSAL_MIN = {thr})")
    print("=" * 80)
    print(f"  firing setups: {len(rows)}    would-reject (< {thr} full traversals): "
          f"{len(reject)}    would-keep: {len(keep)}")
    print(f"  (gate is {'ON' if settings.TRAVERSAL_GATE_ENABLED else 'OFF -- v1 shadow / measure-first'})")

    # Tier breakdown — the headline. Flagged S/A = wide-box-ranking-high cases.
    print("\n  flagged-by-tier (firing / flagged):")
    for tier in ("S", "A", "B", "C", "D"):
        fire_n = sum(1 for r in rows if r["tier"] == tier)
        flag_n = sum(1 for r in reject if r["tier"] == tier)
        if fire_n:
            print(f"    {tier}: {fire_n:>3} / {flag_n:<3}")

    if reject:
        print(f"\n  WOULD-REJECT setups (worst-ranked first — eyeball these charts):")
        print(f"    {'ticker':8} {'tier':>4} {'score':>6} {'box':>6} "
              f"{'nFull':>5} {'nSw':>4} {'topDead':>7} {'botDead':>7} {'maxSwing':>8}")
        for r in sorted(reject, key=_sort_key):
            print(f"    {r['ticker']:8} {r['tier']:>4} {_fmt(r['score'], 1):>6} "
                  f"{_fmt(r['box_width'], 3):>6} {_fmt(r['n_full'], 0):>5} "
                  f"{_fmt(r['n_swings'], 0):>4} {_fmt(r['top_dead'], 2):>7} "
                  f"{_fmt(r['bottom_dead'], 2):>7} {_fmt(r['max_swing'], 2):>8}")

    # Sanity: dead-space should run higher in the reject set than the keep set.
    def _avg(rs, key):
        vals = [r[key] for r in rs if r[key] is not None]
        return sum(vals) / len(vals) if vals else None

    print("\n  mean dead-space  (reject vs keep) -- reject should read worse:")
    print(f"    top_dead_space:    {_fmt(_avg(reject, 'top_dead'))}  vs  "
          f"{_fmt(_avg(keep, 'top_dead'))}")
    print(f"    bottom_dead_space: {_fmt(_avg(reject, 'bottom_dead'))}  vs  "
          f"{_fmt(_avg(keep, 'bottom_dead'))}")


if __name__ == "__main__":
    main()
