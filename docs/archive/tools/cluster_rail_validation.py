"""ARCHIVED 2026-08-20 — this instrument's event is over; it is kept as the record of
how a recorded finding was measured, not as a runnable tool. It has moved out of
tools/, so the `python -m tools.<name>` usage lines below no longer resolve, and
its imports of sibling tools may not either. To re-run it, restore it to tools/
from git history first. Nothing in the live tree imports it.

Cluster-rail statistic validation â€” all 33 drawn boxes (Rail Program Task 6).

Grades `engine_alpha.structure.rail_qualification.cluster_rails` (the
representative-resting-extreme statistic, defaults from the touch machinery:
EQ_MIN_TOUCHES_PER_RAIL within TOUCH_TOLERANCE_ATR ATRs) against the
operator's drawn rails over EVERY Guided List box, on his drawn window, on
the sealed fixture basis. The acceptance criteria are PRE-REGISTERED in
docs/cluster_rail_validation_2026-07.md before any run â€” a definition that
matches only NKTR is a tail fit and the answer is NO (protocol Â§8).

Also reports the plain extreme anchor (max High / min Low of the drawn
window â€” the current candidate-anchor basis) so the delta the statistic buys
on wick-inflated windows is visible next to what it costs elsewhere.

Read-only, offline: sealed fixture + calibration DB (window spans) only.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.cluster_rail_validation            # print per-box deltas
    python -m tools.cluster_rail_validation --json OUT # also dump rows
"""
from __future__ import annotations

import argparse
import json
import statistics

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from repo root
    from _bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path(backend=True)

from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.rail_qualification import cluster_rails  # noqa: E402
from tools.marks_corpus import load_corpus, setup_key  # noqa: E402
from tools.replay import (  # noqa: E402
    drawn_box_window,
    fixture_frame,
    load_sealed_fixture,
)

# Pre-registered acceptance (docs/cluster_rail_validation_2026-07.md Â§2) â€”
# mirrored here so the verdict line is computed, never eyeballed.
ACCEPT_TOL_ATR = 0.5        # a rail within the touch tolerance IS the level
ACCEPT_MIN_RAILS = 60       # of 66 (33 boxes x 2 rails) within tolerance
ACCEPT_MAX_MEDIAN_ATR = 0.25


def validate_one(setup: dict, mark, frames: dict) -> dict:
    key = setup_key(setup)
    raw = fixture_frame(frames, key)
    if raw is None or raw.empty:
        raise SystemExit(f"cluster validation: no sealed fixture frame for {key}")
    base_df, atr = drawn_box_window(raw, mark.box_start_date, mark.box_end_date)
    highs = base_df["High"].to_numpy(dtype=float)
    lows = base_df["Low"].to_numpy(dtype=float)
    R_d = float(setup["rails_drawn"]["R"])
    S_d = float(setup["rails_drawn"]["S"])
    R_c, S_c = cluster_rails(highs, lows, atr)
    row = {"case": key, "n": len(base_df), "atr": round(atr, 4),
           "R_drawn": R_d, "S_drawn": S_d,
           "R_cluster": R_c, "S_cluster": S_c,
           "R_extreme": float(highs.max()), "S_extreme": float(lows.min())}
    for side, drawn, cluster, extreme in (
            ("R", R_d, R_c, row["R_extreme"]),
            ("S", S_d, S_c, row["S_extreme"])):
        row[f"d{side}_cluster_atr"] = (None if cluster is None
                                       else round((cluster - drawn) / atr, 3))
        row[f"d{side}_extreme_atr"] = round((extreme - drawn) / atr, 3)
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", metavar="PATH", help="dump rows to JSON")
    args = ap.parse_args()
    if args.json:
        refuse_sealed_output(args.json)

    import database  # noqa: PLC0415 â€” lazy: binds the live SQLite engine
    from tools.calibration_harness import load_box_marks

    frames, baseline = load_sealed_fixture()
    setups = load_corpus()
    session = database.SessionLocal()
    try:
        marks, _fp = load_box_marks(session)
    finally:
        session.close()
    by_key = {(m.ticker, str(m.as_of_date)): m for m in marks}

    rows = []
    for s in setups:
        mark = by_key.get((s["ticker"], s["as_of"]))
        if mark is None or not mark.box_start_date or not mark.box_end_date:
            raise SystemExit(f"cluster validation: no DB box span for {setup_key(s)}")
        rows.append(validate_one(s, mark, frames))

    print("=" * 78)
    print("  CLUSTER-RAIL VALIDATION â€” the resting-extreme statistic vs 33 drawn boxes")
    print("=" * 78)
    print(f"population: guided-list ({len(rows)} boxes)   "
          f"marks_fingerprint: {baseline['marks_fingerprint'][:16]}...")
    print(f"engine_config_version: {manifest_hash()[:16]}...   "
          "statistic: cluster_rails (EQ_MIN_TOUCHES_PER_RAIL within "
          "TOUCH_TOLERANCE_ATR)")
    print(f"acceptance (pre-registered): |delta| <= {ACCEPT_TOL_ATR} ATR on "
          f">= {ACCEPT_MIN_RAILS}/66 rails, median <= {ACCEPT_MAX_MEDIAN_ATR} "
          "ATR, both NKTR rails in, NKTR must beat the plain extreme anchor")

    hdr = (f"{'case':18} {'n':>4} {'dR_clu':>7} {'dR_ext':>7} "
           f"{'dS_clu':>7} {'dS_ext':>7}")
    print("\n" + hdr + "   (ATR units; cluster vs plain-extreme anchor)")
    print("-" * len(hdr))
    deltas = []
    none_rails = 0
    for row in sorted(rows, key=lambda r: r["case"]):
        cells = []
        for k in ("dR_cluster_atr", "dR_extreme_atr",
                  "dS_cluster_atr", "dS_extreme_atr"):
            v = row[k]
            cells.append("   None" if v is None else f"{v:>7.2f}")
        print(f"{row['case']:18} {row['n']:>4} " + " ".join(cells))
        for k in ("dR_cluster_atr", "dS_cluster_atr"):
            if row[k] is None:
                none_rails += 1
            else:
                deltas.append(abs(row[k]))

    within = sum(1 for d in deltas if d <= ACCEPT_TOL_ATR)
    med = statistics.median(deltas) if deltas else None
    worst = max(deltas) if deltas else None
    nktr = next((r for r in rows if r["case"].startswith("NKTR")), None)
    print(f"\nrails within {ACCEPT_TOL_ATR} ATR: {within}/66 "
          f"({none_rails} with no cluster level)   "
          f"median |delta| {med:.3f} ATR   worst {worst:.2f} ATR")
    verdict_ok = (within >= ACCEPT_MIN_RAILS
                  and med is not None and med <= ACCEPT_MAX_MEDIAN_ATR)
    nktr_ok = False
    nktr_beats = False
    if nktr is not None:
        dr, ds = nktr["dR_cluster_atr"], nktr["dS_cluster_atr"]
        nktr_ok = (dr is not None and ds is not None
                   and abs(dr) <= ACCEPT_TOL_ATR and abs(ds) <= ACCEPT_TOL_ATR)
        nktr_beats = any(
            nktr[f"d{side}_cluster_atr"] is not None
            and abs(nktr[f"d{side}_cluster_atr"])
            < abs(nktr[f"d{side}_extreme_atr"]) - 1e-9
            for side in ("R", "S"))
        print(f"NKTR: cluster dR {dr} dS {ds} ATR vs plain-extreme "
              f"dR {nktr['dR_extreme_atr']} dS {nktr['dS_extreme_atr']} â€” "
              f"{'within tolerance' if nktr_ok else 'OUT of tolerance'}, "
              f"{'beats' if nktr_beats else 'does NOT beat'} the extreme anchor")
    print("\nVERDICT: " + ("PASS â€” the statistic reproduces the drawn rails "
                           "and lands on NKTR's"
                           if verdict_ok and nktr_ok and nktr_beats else
                           "NO â€” pre-registered acceptance not met "
                           f"(coverage {within}/66 need {ACCEPT_MIN_RAILS}, "
                           f"median {med}, NKTR in-tol {nktr_ok}, "
                           f"NKTR beats extreme {nktr_beats})"))

    if args.json:
        doc = {"population": "guided-list",
               "marks_fingerprint": baseline["marks_fingerprint"],
               "engine_config_version": manifest_hash(),
               "acceptance": {"tol_atr": ACCEPT_TOL_ATR,
                              "min_rails": ACCEPT_MIN_RAILS,
                              "max_median_atr": ACCEPT_MAX_MEDIAN_ATR},
               "rows": rows}
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
