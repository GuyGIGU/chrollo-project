"""Shelf-harness — the ONE LPS detector graded over the operator's marked shelves.

Move 3a of the Guided List gap-breach (PLAN task 5). For every marked LPS event
on every calibration BOX mark, this instrument asks the DETECTOR's question:
would ``detect_lps_candidates`` bless exactly the operator's marked shelf
window, judged at the operator's drawn rails over his drawn box span — and if
not, WHICH gate rejects it? The drawn basis is deliberate: it grades the
detector against operator truth, decoupled from election vagaries (the
election's own right-edge behavior is Move 2's domain). Roles stay named:
``tools.calibration_stat_card`` measures the DRAWN geometry descriptively;
THIS instrument measures the DETECTOR's verdict over the same windows.

Deterministic + stamped: frames load strictly by each mark's stored digest
(refusing loudly on a mismatch — a shelf verdict measured on other bars would
quietly shift the envelope), every run stamps the marks fingerprint and the
engine manifest hash, and the same marks + engine yield byte-identical output.
Read-only by construction: ORM reads, no commits, flag overrides self-restore.
EC-10: the detector sees only bars at-or-before the shelf end.

Per-shelf output is Specific (Beck): the verdict, the single reject slug when
rejected (isolated by pinning the detector's window length to the marked
length under ``flag_capture``), and the measured envelope values in the
operator's units (bars, ATR, box-heights) so hot boundaries — e.g. the 1.25
overshoot pullback floor sitting on VIK 1.228 / VLO 1.167 — read directly
off the row.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.shelf_harness [--ticker X] [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import pandas as pd

try:
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path()

import os  # noqa: E402

sys.path.insert(1, os.path.join(_PROJECT_ROOT, "webapp", "backend"))

import database  # noqa: E402
from models import CalibrationMark  # noqa: E402

from config import settings  # noqa: E402
from webapp.backend import frame_store  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.indicators import calculate_atr  # noqa: E402
from engine_alpha.structure.lps import (  # noqa: E402
    _profile_unit,
    _spread_series,
    _zone_tolerance,
    detect_lps_candidates,
    lps_range_threshold,
)
from engine_alpha.structure.market_structure import _pairwise_descent_fraction  # noqa: E402
from tools.calibration_harness import _mark_dict, marks_fingerprint  # noqa: E402
from tools.replay import flag_capture  # noqa: E402

ATR_OFFSET = getattr(settings, "STRUCTURE_ATR_SAMPLE_OFFSET", 6)


def _pos(index: pd.DatetimeIndex, date_str) -> int:
    ts = pd.Timestamp(str(date_str))
    p = int(index.get_indexer([ts])[0])
    if p == -1:
        p = min(int(index.searchsorted(ts)), len(index) - 1)
    return p


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ATR_10"] = calculate_atr(df, 10)
    df["Vol_50"] = df["Volume"].rolling(50).mean()
    df["Spread"] = df["High"] - df["Low"]
    return df


def probe_shelf(frozen: pd.DataFrame, mark, ev) -> dict:
    """One marked shelf through the detector at the drawn basis."""
    R, S = float(mark.resistance), float(mark.support)
    box_height = R - S
    idx = frozen.index
    start_pos = _pos(idx, ev.start_date)
    end_pos = _pos(idx, ev.end_date)
    marked_len = end_pos - start_pos + 1

    work = _enrich(frozen.iloc[: end_pos + 1])
    atr = float(work["ATR_10"].iloc[-ATR_OFFSET]) if len(work) >= ATR_OFFSET \
        else float(work["ATR_10"].iloc[-1])
    box_start_pos = _pos(idx, mark.box_start_date)
    base_df = work.iloc[box_start_pos:]
    thr = lps_range_threshold(base_df, atr)
    anchors = [d for d in (mark.r_anchor_date, mark.s_anchor_date) if d]
    swing_idx = max((_pos(idx, d) for d in anchors), default=box_start_pos)

    row = {
        "ticker": mark.ticker, "as_of": str(mark.as_of_date),
        "shelf": f"{ev.start_date}..{ev.end_date}", "len": marked_len,
        "frame_digest": (mark.frame_digest or "")[:12],
    }

    # Measured envelope values (same lps helpers the detector uses — the
    # operator's units; printed on EVERY row so a reject reads with its
    # numbers in hand).
    window = work.iloc[start_pos: end_pos + 1]
    spreads = _spread_series(window).astype(float)
    profile_unit = _profile_unit(thr, box_height)
    lows = window["Low"].to_numpy(float)
    highs = window["High"].to_numpy(float)
    last_low = float(lows[-1])
    m = {
        "tightness_ratio": (float(spreads.iloc[-1]) / profile_unit
                            if profile_unit else None),
        "window_range_pct_box": float((np.nanmax(highs) - np.nanmin(lows))
                                      / box_height) if box_height > 0 else None,
        "pullback_profile": (float(np.nanmax(highs) - np.nanmin(lows)) / profile_unit
                             if profile_unit else None),
        "position_in_box": ((last_low - S) / box_height) if box_height > 0 else None,
        "low_descent_frac": float(_pairwise_descent_fraction(lows)),
        "high_descent_frac": float(_pairwise_descent_fraction(highs)),
        "vol_contraction": (1.0 - float(window["Volume"].mean())
                            / float(work["Vol_50"].iloc[-1])
                            if np.isfinite(work["Vol_50"].iloc[-1])
                            and work["Vol_50"].iloc[-1] > 0 else None),
    }
    zone_tol = _zone_tolerance(S, R, atr)
    if last_low > R + zone_tol:
        m["zone"] = "OVERSHOOT_R"
    elif last_low < S - zone_tol:
        m["zone"] = "UNDERCUT_S"
    else:
        m["zone"] = "INSIDE"
    row["m"] = {k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in m.items()}

    # Detector verdict at the EXACT marked window (offset 0 on the sliced
    # frame; end_index is exclusive == len(work) for every offset-0 window).
    if marked_len < settings.LPS_LENGTH_MIN or marked_len > settings.LPS_LENGTH_MAX:
        row["verdict"] = "length-outside-range"
        row["reject"] = (f"marked shelf is {marked_len} bars; detector scans "
                         f"[{settings.LPS_LENGTH_MIN}, {settings.LPS_LENGTH_MAX}]")
        return row

    cands, _rejects = detect_lps_candidates(
        work, work.iloc[-1], S, R, atr, thr, len(base_df), swing_idx,
        offset_max=1, diagnose=True)
    exact = [c for c in cands
             if int(c["end_index"]) == len(work)
             and int(c["end_index"]) - int(c["start_index"]) == marked_len]
    if exact:
        row["verdict"] = "pass"
        row["swing_type"] = exact[0].get("swing_type")
        row["zone_type"] = exact[0].get("zone_type")
        return row

    # Isolate the marked window's own reject path: pin the detector's length
    # scan to the marked length (self-restoring override) so the counter can
    # only contain THIS window's first-fail slug.
    with flag_capture(LPS_LENGTH_MIN=marked_len, LPS_LENGTH_MAX=marked_len):
        _c, rejects = detect_lps_candidates(
            work, work.iloc[-1], S, R, atr, thr, len(base_df), swing_idx,
            offset_max=1, diagnose=True)
    row["verdict"] = "reject"
    row["reject"] = (rejects.most_common(1)[0][0] if rejects
                     else "no candidate and no reject counted (unexpected)")
    return row


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Grade the ONE LPS detector over the operator's marked shelves.")
    ap.add_argument("--ticker", help="only this ticker")
    ap.add_argument("--json", dest="json_out", help="also dump per-shelf JSON")
    args = ap.parse_args()

    session = database.SessionLocal()
    try:
        marks = [m for m in session.query(CalibrationMark).all()
                 if m.verdict == "box"
                 and (not args.ticker or m.ticker == args.ticker.upper())]
        all_box = [m for m in session.query(CalibrationMark).all()
                   if m.verdict == "box"]
        fingerprint = marks_fingerprint([_mark_dict(m) for m in all_box])

        rows: list[dict] = []
        for mark in sorted(marks, key=lambda x: (x.ticker, str(x.as_of_date))):
            frozen = frame_store.load_frame(
                mark.ticker, mark.as_of_date, digest=mark.frame_digest)
            if frozen is None or frozen.empty:
                raise RuntimeError(
                    f"{mark.ticker}@{mark.as_of_date}: no frozen frame matches "
                    f"digest {(mark.frame_digest or '?')[:12]} — the drawn basis "
                    "is unbound; refusing (a verdict on other bars would "
                    "quietly shift the envelope).")
            lps_events = sorted((e for e in mark.events
                                 if e.event_type == "lps"),
                                key=lambda e: str(e.start_date))
            for ev in lps_events:
                rows.append(probe_shelf(frozen, mark, ev))
    finally:
        session.close()

    print("=" * 100)
    print("  SHELF-HARNESS — the ONE LPS detector vs the operator's marked shelves"
          " (drawn basis)")
    print("=" * 100)
    print(f"population: calibration marks (EC-9)   marks_fingerprint: {fingerprint[:16]}…")
    print(f"engine_config_version: {manifest_hash()[:16]}…   shelves: {len(rows)}")
    print(f"detector thresholds: len [{settings.LPS_LENGTH_MIN},{settings.LPS_LENGTH_MAX}]"
          f"   descent floors {settings.LPS_MIN_DESCENT_FRAC}/{settings.LPS_MIN_HIGH_DESCENT_FRAC}"
          f"   zone ATR mult {settings.LPS_ZONE_ATR_MULT}")
    print()
    for r in rows:
        m = r.get("m", {})
        nums = ("  ".join(f"{k}={m[k]}" for k in
                          ("zone", "tightness_ratio", "pullback_profile",
                           "position_in_box", "low_descent_frac",
                           "vol_contraction") if m.get(k) is not None))
        head = f"{r['ticker']:6} {r['as_of']}  shelf {r['shelf']} ({r['len']}b)"
        if r["verdict"] == "pass":
            print(f"  PASS    {head}  [{r.get('swing_type') or '?'}]")
        else:
            print(f"  REJECT  {head}")
            print(f"          -> {r.get('reject')}")
        print(f"          {nums}")

    n_pass = sum(1 for r in rows if r["verdict"] == "pass")
    print()
    print(f"detector blesses the marked shelf: {n_pass}/{len(rows)}")
    from collections import Counter
    slugs = Counter(r["reject"] for r in rows if r["verdict"] != "pass")
    if slugs:
        print("reject taxonomy:")
        for slug, n in slugs.most_common():
            print(f"  {n:>2}x  {slug}")

    if args.json_out:
        doc = {"marks_fingerprint": fingerprint,
               "engine_config_version": manifest_hash(),
               "n_shelves": len(rows), "n_pass": n_pass, "rows": rows}
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1, default=str)
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
