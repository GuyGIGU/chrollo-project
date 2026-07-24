"""Anchor-bar study — what makes a bar THE operator's rail anchor.

The Rail Program's closing finding (docs/rail_program_close_2026-07.md): the
operator's rail is a representative INTERIOR bar's extreme, not the outermost
level with k resting neighbors. This instrument studies the choice directly —
all 33 Guided List marks carry his declared r_anchor_date / s_anchor_date and
which rail he drew first — and characterizes, per side:

  * fidelity   — is the drawn rail the anchor bar's own High/Low? (the
                 rails-at-H/L ruling, measured)
  * rank       — where the anchor bar's extreme ranks among the drawn
                 window's bars (1 = the window extreme)
  * ignored    — how much outlier the drawn rail leaves outside (window
                 extreme minus rail, in ATRs)
  * position   — where the anchor bar sits in the drawn window (0..1)
  * support    — bars whose extreme rests within 0.25 ATR of the rail
  * character  — the anchor bar's spread vs the window median, volume vs
                 Vol_50, close position inside its own range, local-pivot
                 flag (extreme vs +-3 neighbors)
  * proven     — touches of the rail AFTER the anchor bar (TOUCH_TOLERANCE_ATR)
  * engine     — the engine's own anchor bars for the elected (hits) or
                 nearest-to-drawn (misses) candidate at as_of, and how far
                 they sit from his (bars and ATRs)

Read-only evidence: sealed fixture + calibration DB; no election, no scoring,
no engine writes. EC-13 loaders; EC-9 stamps; --json via EC-14.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.anchor_bar_study            # per-mark lines + aggregates
    python -m tools.anchor_bar_study --json OUT
"""
from __future__ import annotations

import argparse
import json
import statistics

import numpy as np
import pandas as pd

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from repo root
    from _bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path(backend=True)

from config import settings  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.narrative import read_structure  # noqa: E402
from tools.marks_corpus import load_corpus, setup_key  # noqa: E402
from tools.replay import (  # noqa: E402
    drawn_box_window,
    fixture_frame,
    load_sealed_fixture,
    prepared_frame,
)

REST_TOL_ATR = 0.25   # "rests at the rail" tolerance for the support count
PIVOT_WING = 3        # +-bars for the local-pivot flag


def _side_stats(base_df: pd.DataFrame, atr: float, rail: float, anchor_pos: int,
                *, is_r: bool) -> dict:
    ext = base_df["High"].to_numpy(dtype=float) if is_r \
        else base_df["Low"].to_numpy(dtype=float)
    n = len(ext)
    bar_ext = float(ext[anchor_pos])
    window_ext = float(np.nanmax(ext)) if is_r else float(np.nanmin(ext))
    # rank of the anchor bar's extreme: 1 = the window extreme
    order = np.argsort(-ext) if is_r else np.argsort(ext)
    rank = int(np.where(order == anchor_pos)[0][0]) + 1
    sign = 1.0 if is_r else -1.0
    row = {
        "fidelity_atr": round(abs(rail - bar_ext) / atr, 3),
        "rank": rank,
        "n": n,
        "ignored_atr": round(sign * (window_ext - rail) / atr, 3),
        "position": round(anchor_pos / max(n - 1, 1), 3),
        "support_bars": int((np.abs(ext - rail) <= REST_TOL_ATR * atr).sum()),
    }
    lo = max(0, anchor_pos - PIVOT_WING)
    hi = min(n, anchor_pos + PIVOT_WING + 1)
    wing = np.delete(ext[lo:hi], anchor_pos - lo)
    row["local_pivot"] = bool(len(wing) and (
        bar_ext >= np.nanmax(wing) if is_r else bar_ext <= np.nanmin(wing)))
    after = ext[anchor_pos + 1:]
    row["later_touches"] = int(
        (np.abs(after - rail) <= settings.TOUCH_TOLERANCE_ATR * atr).sum())
    return row


def _bar_character(base_df: pd.DataFrame, atr: float, anchor_pos: int) -> dict:
    bar = base_df.iloc[anchor_pos]
    spread = float(bar["High"] - bar["Low"])
    med_spread = float((base_df["High"] - base_df["Low"]).median())
    out = {"spread_atr": round(spread / atr, 3),
           "spread_vs_median": round(spread / med_spread, 3) if med_spread else None}
    v50 = bar.get("Vol_50")
    out["vol_ratio"] = (round(float(bar["Volume"]) / float(v50), 3)
                        if v50 and pd.notna(v50) and float(v50) > 0 else None)
    if spread > 0:
        out["close_pos_in_bar"] = round(
            (float(bar["Close"]) - float(bar["Low"])) / spread, 3)
    else:
        out["close_pos_in_bar"] = None
    return out


def _engine_anchors(raw: pd.DataFrame, as_of: str, R_d: float, S_d: float):
    """The engine's anchor bars at as_of: the elected candidate's if one
    elects, else the strict candidate nearest the drawn rails."""
    prep = prepared_frame(raw, as_of)
    if prep is None:
        return None
    df, atr = prep
    trace: list = []
    structure = read_structure(df, atr, trace=trace)
    recs = [rec for root in trace for rec in root.get("box_cascade") or []
            if not rec["rescued"]]
    if not recs:
        return None
    elected = [rec for rec in recs if rec["verdict"] == "elected"]
    bh = R_d - S_d
    rec = elected[-1] if elected else min(
        recs, key=lambda r: max(abs(r["R"] - R_d), abs(r["S"] - S_d)) / bh)
    def _date(bar):
        return df.index[bar].date().isoformat() if 0 <= bar < len(df) else None
    return {"elected": bool(elected),
            "r_anchor": _date(int(rec["r_anchor_bar"])),
            "s_anchor": _date(int(rec["s_anchor_bar"])),
            "dR_atr": round((float(rec["R"]) - R_d) / atr, 3),
            "dS_atr": round((float(rec["S"]) - S_d) / atr, 3)}


def study_mark(setup: dict, mark, frames: dict, status: str) -> dict:
    key = setup_key(setup)
    raw = fixture_frame(frames, key)
    if raw is None or raw.empty:
        raise SystemExit(f"anchor study: no sealed fixture frame for {key}")
    base_df, atr = drawn_box_window(raw, mark.box_start_date, mark.box_end_date)
    R_d = float(setup["rails_drawn"]["R"])
    S_d = float(setup["rails_drawn"]["S"])
    out = {"case": key, "status": status, "first_rail": mark.first_rail,
           "atr": round(atr, 4)}
    for side, date, rail, is_r in (("R", mark.r_anchor_date, R_d, True),
                                   ("S", mark.s_anchor_date, S_d, False)):
        ts = pd.Timestamp(str(date))
        if ts not in base_df.index:
            out[side] = {"error": f"anchor date {date} outside the drawn window"}
            continue
        pos = int(base_df.index.get_indexer([ts])[0])
        out[side] = {"date": str(date),
                     **_side_stats(base_df, atr, rail, pos, is_r=is_r),
                     **_bar_character(base_df, atr, pos)}
    out["engine"] = _engine_anchors(raw, setup["as_of"], R_d, S_d)
    if out["engine"] is not None:
        for side in ("R", "S"):
            his = out.get(side, {}).get("date")
            eng = out["engine"].get(f"{side.lower()}_anchor")
            if his and eng:
                idx = base_df.index
                p_his = int(idx.searchsorted(pd.Timestamp(his)))
                p_eng = int(idx.searchsorted(pd.Timestamp(eng)))
                out["engine"][f"{side.lower()}_bars_apart"] = abs(p_his - p_eng)
    return out


def _agg(rows: list[dict], side: str, field: str) -> list[float]:
    vals = []
    for row in rows:
        v = row.get(side, {}).get(field)
        if isinstance(v, (int, float)):
            vals.append(float(v))
    return vals


def print_aggregates(rows: list[dict]) -> None:
    print("\n== aggregate: what makes a bar HIS anchor ==")
    fields = ["fidelity_atr", "rank", "ignored_atr", "position",
              "support_bars", "later_touches", "spread_vs_median",
              "vol_ratio", "close_pos_in_bar"]
    hdr = f"{'measure':20} {'side':>4} {'n':>3} {'median':>8} {'p25':>8} {'p75':>8} {'max':>8}"
    print(hdr)
    print("-" * len(hdr))
    for field in fields:
        for side in ("R", "S"):
            vals = _agg(rows, side, field)
            if not vals:
                continue
            q = statistics.quantiles(vals, n=4) if len(vals) > 2 else [vals[0]] * 3
            print(f"{field:20} {side:>4} {len(vals):>3} "
                  f"{statistics.median(vals):>8.3f} {q[0]:>8.3f} {q[2]:>8.3f} "
                  f"{max(vals):>8.3f}")
    pivots = {s: sum(1 for r in rows if r.get(s, {}).get("local_pivot") is True)
              for s in ("R", "S")}
    measured = {s: sum(1 for r in rows if "local_pivot" in r.get(s, {}))
                for s in ("R", "S")}
    print(f"\nlocal pivot (+-{PIVOT_WING} bars): "
          f"R {pivots['R']}/{measured['R']}   S {pivots['S']}/{measured['S']}")
    first = [r["first_rail"] for r in rows if r.get("first_rail")]
    print(f"first rail drawn: resistance {first.count('resistance')} / "
          f"support {first.count('support')}")
    apart = [r["engine"][k] for r in rows if r.get("engine")
             for k in ("r_bars_apart", "s_bars_apart") if k in r["engine"]]
    same = sum(1 for a in apart if a == 0)
    if apart:
        print(f"engine anchor vs his: same bar {same}/{len(apart)}, "
              f"median {statistics.median(apart):.0f} bars apart, "
              f"max {max(apart):.0f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", metavar="PATH", help="dump rows to JSON")
    args = ap.parse_args()
    if args.json:
        refuse_sealed_output(args.json)

    import database  # noqa: PLC0415 — lazy: binds the live SQLite engine
    from tools.calibration_harness import load_box_marks

    frames, baseline = load_sealed_fixture()
    setups = load_corpus()
    status_by_key = {e["key"]: e["status"] for e in baseline["setups"]}
    session = database.SessionLocal()
    try:
        marks, _fp = load_box_marks(session)
    finally:
        session.close()
    by_key = {(m.ticker, str(m.as_of_date)): m for m in marks}

    rows = []
    for s in setups:
        mark = by_key.get((s["ticker"], s["as_of"]))
        if mark is None or not mark.r_anchor_date or not mark.s_anchor_date:
            raise SystemExit(f"anchor study: {setup_key(s)} lacks declared "
                             "anchor dates — refusing a partial population")
        rows.append(study_mark(s, mark, frames,
                               status_by_key.get(setup_key(s), "?")))

    print("=" * 78)
    print("  ANCHOR-BAR STUDY — the operator's declared rail anchors, measured")
    print("=" * 78)
    print(f"population: guided-list ({len(rows)} marks, all with declared "
          f"anchors)   marks_fingerprint: {baseline['marks_fingerprint'][:16]}...")
    print(f"engine_config_version: {manifest_hash()[:16]}...")

    hdr = (f"{'case':18} {'st':>4} {'side':>4} {'fid':>5} {'rank':>5} "
           f"{'ign':>6} {'pos':>5} {'sup':>4} {'tch':>4} {'piv':>4}")
    print("\n" + hdr)
    print("-" * len(hdr))
    for row in rows:
        for side in ("R", "S"):
            d = row.get(side, {})
            if "error" in d:
                print(f"{row['case']:18} {row['status'][:4]:>4} {side:>4} "
                      f"  ! {d['error']}")
                continue
            print(f"{row['case']:18} {row['status'][:4]:>4} {side:>4} "
                  f"{d['fidelity_atr']:>5.2f} {d['rank']:>3}/{d['n']:<3} "
                  f"{d['ignored_atr']:>6.2f} {d['position']:>5.2f} "
                  f"{d['support_bars']:>4} {d['later_touches']:>4} "
                  f"{'Y' if d['local_pivot'] else '.':>4}")

    print_aggregates(rows)
    print_aggregates([r for r in rows if r["status"] == "miss"]) if any(
        r["status"] == "miss" for r in rows) else None
    print("\n(second aggregate block, when shown, is the 7 MISSES alone)")

    if args.json:
        doc = {"population": "guided-list",
               "marks_fingerprint": baseline["marks_fingerprint"],
               "engine_config_version": manifest_hash(),
               "rest_tol_atr": REST_TOL_ATR, "pivot_wing": PIVOT_WING,
               "rows": rows}
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
