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
operator's units (bars, ATR, box-heights). The printed ``pullback_profile``
is the DETECTOR'S own gated statistic — first-bar high minus terminal low
over the profile unit; pass rows print the blessed candidate's exact value —
never the (always-wider) whole-window range, which stays available as
``window_range_pct_box``.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.shelf_harness [--ticker X] [--json OUT]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    from _bootstrap import configure_path, refuse_sealed_output

_PROJECT_ROOT = configure_path(backend=True)

import database  # noqa: E402

from config import settings  # noqa: E402
from webapp.backend import frame_store  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.lps.detection import (  # noqa: E402
    _profile_unit,
    _spread_series,
    _zone_tolerance,
    detect_lps_candidates,
    lps_range_threshold,
)
from engine_alpha.structure.events.market_structure import _pairwise_descent_fraction  # noqa: E402
from tools.calibration_harness import load_box_marks  # noqa: E402
from tools.replay import (  # noqa: E402
    MARK_ATR_OFFSET,
    enrich_marked_frame,
    flag_capture,
    session_pos,
)


def probe_shelf(frozen: pd.DataFrame, mark, ev) -> dict:
    """One marked shelf through the detector at the drawn basis."""
    R, S = float(mark.resistance), float(mark.support)
    box_height = R - S
    idx = frozen.index
    start_pos = session_pos(idx, ev.start_date)
    end_pos = session_pos(idx, ev.end_date, boundary="end")
    marked_len = end_pos - start_pos + 1

    work = enrich_marked_frame(frozen.iloc[: end_pos + 1])
    atr = float(work["ATR_10"].iloc[-MARK_ATR_OFFSET]) if len(work) >= MARK_ATR_OFFSET \
        else float(work["ATR_10"].iloc[-1])
    if not np.isfinite(atr) or atr <= 0:
        # A NaN ATR would flow into the range threshold and zone tolerance,
        # where NaN comparisons silently pass everything — the worst failure
        # for an instrument. Refuse the shelf loudly instead.
        raise RuntimeError(
            f"{mark.ticker}@{mark.as_of_date}: ATR unavailable at the shelf "
            f"end ({ev.start_date}..{ev.end_date}; frame too thin) — refusing "
            "a quiet verdict")
    box_start_pos = session_pos(idx, mark.box_start_date)
    base_df = work.iloc[box_start_pos:]
    thr = lps_range_threshold(base_df, atr)
    anchors = [d for d in (mark.r_anchor_date, mark.s_anchor_date) if d]
    swing_idx = max((session_pos(idx, d) for d in anchors), default=box_start_pos)

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
    first_high = float(highs[0])
    m = {
        "tightness_ratio": (float(spreads.iloc[-1]) / profile_unit
                            if profile_unit else None),
        "window_range_pct_box": float((np.nanmax(highs) - np.nanmin(lows))
                                      / box_height) if box_height > 0 else None,
        # The DETECTOR's gated statistic (first-bar high − terminal low, over
        # the profile unit — its primary support-low form); a pass row below
        # overwrites this with the blessed candidate's exact value. Never the
        # whole-window range: that is always ≥ the gate's own number and
        # would overstate every boundary-proximity diagnosis.
        "pullback_profile": ((first_high - last_low) / profile_unit
                             if profile_unit else None),
        "position_in_box": ((last_low - S) / box_height) if box_height > 0 else None,
        "low_descent_frac": float(_pairwise_descent_fraction(lows)),
        "high_descent_frac": float(_pairwise_descent_fraction(highs)),
        "vol_contraction": (1.0 - float(window["Volume"].mean())
                            / float(work["Vol_50"].iloc[-1])
                            if np.isfinite(work["Vol_50"].iloc[-1])
                            and work["Vol_50"].iloc[-1] > 0 else None),
    }
    # Descriptive only, and deliberately NOT named "zone": the detector's own
    # zone_type (printed on pass rows) calls the valid throwback band
    # OVERSHOOT_R, while this classifies the terminal low against the
    # tolerance limits the detector REJECTS beyond — one word, one meaning.
    zone_tol = _zone_tolerance(S, R, atr)
    if last_low > R + zone_tol:
        m["low_beyond_tol"] = "above_R"
    elif last_low < S - zone_tol:
        m["low_beyond_tol"] = "below_S"
    else:
        m["low_beyond_tol"] = "inside"
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
        pp = exact[0].get("pullback_profile")
        if pp is not None:
            # The blessed candidate's EXACT gated value (covers the detector's
            # rising-shelf window-low re-anchor, which the row estimate can't see).
            row["m"]["pullback_profile"] = round(float(pp), 4)
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


def _metrics_line(m: dict) -> str:
    """Constant order, fixed width, '-' placeholders — one metric = one
    column down the whole report, so a boundary scan never re-hunts a key."""
    def num(key: str) -> str:
        v = m.get(key)
        return f"{v:>7.4f}" if isinstance(v, (int, float)) else f"{'-':>7}"

    return (f"beyond_tol={m.get('low_beyond_tol') or '-':<8}"
            f" tight={num('tightness_ratio')}"
            f" pullback={num('pullback_profile')}"
            f" pos_box={num('position_in_box')}"
            f" low_desc={num('low_descent_frac')}"
            f" vol_ctr={num('vol_contraction')}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Grade the ONE LPS detector over the operator's marked shelves.")
    ap.add_argument("--ticker", help="only this ticker")
    ap.add_argument("--json", dest="json_out", help="also dump per-shelf JSON")
    args = ap.parse_args()
    if args.json_out:
        refuse_sealed_output(args.json_out)

    session = database.SessionLocal()
    try:
        # The shared validated loader (EC-3): loud per-mark validation, and
        # the fingerprint covers EXACTLY the marks scored — a --ticker run
        # stamps the filtered set, never a claim over marks it didn't measure.
        marks, fingerprint = load_box_marks(session, args.ticker)

        rows: list[dict] = []
        for mark in marks:
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

    scope = f"filtered: {args.ticker.upper()}" if args.ticker else "all box marks"
    print("=" * 100)
    print("  SHELF-HARNESS — the ONE LPS detector vs the operator's marked shelves"
          " (drawn basis)")
    print("=" * 100)
    print(f"population: calibration marks (EC-9; {scope})   "
          f"marks_fingerprint: {fingerprint[:16]}… (exact set scored)")
    print(f"engine_config_version: {manifest_hash()[:16]}…   shelves: {len(rows)}")
    print(f"detector thresholds: len [{settings.LPS_LENGTH_MIN},{settings.LPS_LENGTH_MAX}]"
          f"   descent floors {settings.LPS_MIN_DESCENT_FRAC}/{settings.LPS_MIN_HIGH_DESCENT_FRAC}"
          f"   zone ATR mult {settings.LPS_ZONE_ATR_MULT}")
    print()
    for r in rows:
        head = f"{r['ticker']:6} {r['as_of']}  shelf {r['shelf']} ({r['len']}b)"
        if r["verdict"] == "pass":
            print(f"  PASS    {head}  [{r.get('swing_type') or '?'}]")
        else:
            print(f"  REJECT  {head}")
            print(f"          -> {r.get('reject')}")
        print(f"          {_metrics_line(r.get('m', {}))}")

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
        doc = {"population": "calibration_marks",
               "scope": scope,
               "marks_fingerprint": fingerprint,
               "engine_config_version": manifest_hash(),
               "n_shelves": len(rows), "n_pass": n_pass, "rows": rows}
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1, default=str)
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
