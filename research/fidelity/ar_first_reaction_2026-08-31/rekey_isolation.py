"""Isolate the 2026-08-19 climax re-key (e4471e0) inside the AR-diff measurement.

Read-only. Runs the SAME faithful 2y-frame capture the committed
``tools.ar_first_reaction_diff --scan`` runs, twice per ticker:

  current  : bricks._cause_is_up as shipped (covering confirmed segment, cause-wins)
  legacy   : the pre-e4471e0 polarity (root.kind BC/SC only, else pass through)

so the flag-OFF vs flag-ON picture can be compared on ONE cache with only the
re-key varying. Nothing is written into the repo.
"""
from __future__ import annotations

import json
import os
import statistics
import sys

_ROOT = r"C:\Users\User\Documents\Projects\Chrollo Project\.claude\worktrees\zen-satoshi-d1122d"
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from config import settings                                        # noqa: E402
from engine_alpha.structure import bricks                          # noqa: E402
from tools.ar_first_reaction_diff import (                         # noqa: E402
    _load_cache, _prep_live, capture_overlays,
)


def _legacy_cause_is_up(df, root, pbs, terminal_floor=None):
    """Verbatim pre-e4471e0 polarity: the seed's BC/SC label, nothing else."""
    kind = getattr(root, "kind", None)
    if kind == "BC":
        return True
    if kind == "SC":
        return False
    return None


def _capture_legacy(args):
    """Only the legacy half — the current half is the committed tool's own scan,
    run on the same cache with the same prep, so re-running it would be waste."""
    t, df, atr = args
    orig = bricks._cause_is_up
    try:
        bricks._cause_is_up = _legacy_cause_is_up
        leg = capture_overlays(df, atr)
    finally:
        bricks._cause_is_up = orig
    return t, leg


def summarise(rows, label):
    """rows: [(ticker, {mode: (cx, ar, bs)|None})] -> the ledger's five numbers."""
    fires = [(t, o) for t, o in rows if o["off"] is not None]
    movers = []
    for t, o in fires:
        if o["on"] is None:
            continue
        tighten = o["off"][1] - o["on"][1]
        if tighten:
            movers.append((t, o, tighten))
    out = {
        "label": label,
        "fires": len(fires),
        "reanchor": len(movers),
    }
    if movers:
        off_spans = [o["off"][1] - o["off"][0] for _, o, _ in movers]
        on_spans = [o["on"][1] - o["on"][0] for _, o, _ in movers]
        pulls = [p for _, _, p in movers]
        out.update({
            "off_span_median": statistics.median(off_spans),
            "off_span_ge58": sum(1 for s in off_spans if s >= 58),
            "on_span_median": statistics.median(on_spans),
            "on_span_le7": sum(1 for s in on_spans if s <= 7),
            "tighten_median": statistics.median(pulls),
            "tighten_max": max(pulls),
            "tighten_total": sum(pulls),
        })
    out["movers"] = [
        (t, list(o["off"][:2]), list(o["on"][:2]), p) for t, o, p in
        sorted(movers, key=lambda r: r[2], reverse=True)
    ]
    return out


def main():
    jobs = int(sys.argv[1]) if len(sys.argv) > 1 else max(1, (os.cpu_count() or 4) - 2)
    d, level0 = _load_cache()
    exclude = {getattr(settings, "MARKET_INDEX_SYMBOL", "SPY"), "SPY"}
    tickers = sorted(t for t in level0 if t not in exclude)

    prepped = []
    for t in tickers:
        try:
            df, atr = _prep_live(d[t].dropna())
        except Exception:
            continue
        if df is None:
            continue
        prepped.append((t, df, atr))
    print(f"  {len(prepped)}/{len(tickers)} survive baseline; jobs={jobs}",
          file=sys.stderr, flush=True)

    leg_rows = []
    from multiprocessing import Pool
    with Pool(jobs) as pool:
        for i, (t, leg) in enumerate(
                pool.imap_unordered(_capture_legacy, prepped, chunksize=8)):
            if i and i % 300 == 0:
                print(f"  ...{i}/{len(prepped)}", file=sys.stderr, flush=True)
            leg_rows.append((t, leg))

    res = {
        "universe": len(tickers),
        "survive_baseline": len(prepped),
        "legacy": summarise(leg_rows, "legacy (pre-e4471e0 root.kind polarity)"),
    }

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "rekey_isolation.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)

    s = res["legacy"]
    print(f"\n== {s['label']}")
    print(f"   fires {s['fires']}   re-anchor {s['reanchor']}")
    if s["reanchor"]:
        print(f"   OFF span median {s['off_span_median']} "
              f"({s['off_span_ge58']} at >=58)")
        print(f"   ON  span median {s['on_span_median']} "
              f"({s['on_span_le7']} at <=7)")
        print(f"   tighten median {s['tighten_median']}  "
              f"max {s['tighten_max']}  total {s['tighten_total']}")


if __name__ == "__main__":
    main()
