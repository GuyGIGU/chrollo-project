"""Shape Profile — HOW the price action fills each drawn box.

Read-only, offline, measure-first (no gates, no points, no engine change).
For every operator CalibrationMark (verdict='box'), load the frozen frame and
measure, ON THE DRAWN RAILS, the consolidation's SHAPE: how much of the box's
work is done by swing limbs travelling rail to rail (the zigzag family), how
much by individual bars covering the box in place (the clustered family), and
what breach-and-recover story the rails saw (springs / upthrusts that resolve).
Both families are GOOD by ruling (operator, 2026-08-29: "both are good ...
they both reach the same result: Consolidation") — this instrument only
describes which one (or which mix) each drawn box is, so that gates built with
one family in mind are never silently judging the other.

Every axis reuses the engine's own measurement arithmetic (measure_equilibrium,
measure_bar_compression, the rail-touch/hang masks, the rail-episode reader,
the calibrated spring/upthrust events). The one NEW derivation is the travel
block: median close-to-close TRAVEL vs median bar SPREAD — in a clustered box
the movement lives inside the bars (spread >> travel), in a zigzag box it
accumulates across them.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.shape_profile              # per-mark profiles + aggregate
    python -m tools.shape_profile --ticker DSGN
    python -m tools.shape_profile --json OUT   # per-mark JSON sidecar
"""
from __future__ import annotations

import argparse
import json
import statistics
from types import SimpleNamespace

import numpy as np

# --- bootstrap repo path (mirror tools/calibration_stat_card.py) -------------
try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from repo root
    from _bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path(backend=True)

import database  # noqa: E402  binds the live SQLite engine + SessionLocal

from config import settings  # noqa: E402
from webapp.backend import frame_store  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.scoring.tags import traversal_density_from_counts  # noqa: E402
from engine_alpha.structure.events.box_events import (  # noqa: E402
    measure_resistance_events,
    measure_support_tests,
)
from engine_alpha.structure.box.box_gates import (  # noqa: E402
    _dwell_bar_basis,
    _engagement_hang_masks,
    _rail_outside_masks,
    _respect_stats,
)
from engine_alpha.structure.narrative.bricks import find_spring  # noqa: E402
from engine_alpha.structure.events.event_map import (  # noqa: E402
    episode_sequence_stats,
    read_rail_episodes,
)
from engine_alpha.structure.metrics.base import (  # noqa: E402
    base_rail_touches,
    measure_bar_compression,
    measure_equilibrium,
)
from tools.calibration_harness import load_box_marks  # noqa: E402
from tools.calibration_stat_card import _num, _round, _safe  # noqa: E402
from tools.replay import drawn_box_window  # noqa: E402


# --- per-mark shape profile --------------------------------------------------
def profile_mark(mark) -> dict:
    out = {
        "ticker": mark.ticker,
        "as_of": mark.as_of_date,
        "label": mark.label or "",
        "box_start": mark.box_start_date,
        "box_end": mark.box_end_date,
        "R": _num(mark.resistance),
        "S": _num(mark.support),
        "errors": [],
        "m": {},
    }
    R, S = out["R"], out["S"]
    if R is None or S is None or not (R > S):
        out["errors"].append("no drawn rails")
        return out

    frozen = frame_store.load_frame(mark.ticker, mark.as_of_date, digest=mark.frame_digest)
    if frozen is None or frozen.empty:
        out["errors"].append("basis_mismatch: no frozen frame for this digest")
        return out
    try:
        window, atr = drawn_box_window(frozen, mark.box_start_date, mark.box_end_date)
    except ValueError as exc:
        out["errors"].append(str(exc))
        return out

    box_height = R - S
    highs = window["High"].to_numpy(dtype=float)
    lows = window["Low"].to_numpy(dtype=float)
    closes = window["Close"].to_numpy(dtype=float)
    m = out["m"]
    m["bars"] = len(window)
    m["box_width_atr"] = round(box_height / atr, 3)
    # advisory: when the two 0.5-ATR touch zones cover most of the box, distinct
    # rail tests merge into one episode (the LEVI zero-counts trap)
    m["touch_zone_pct_box"] = round(settings.TOUCH_TOLERANCE_ATR * atr / box_height, 3)

    # --- limb block: swing limbs travelling rail to rail ------------------
    eq, err = _safe(measure_equilibrium, window, R, S, atr)
    if err:
        out["errors"].append(f"equilibrium: {err}")
    elif isinstance(eq, dict):
        for k in ("n_full_traversals", "n_swings", "max_swing_frac",
                  "top_dead_space", "bottom_dead_space",
                  "rail_reaches_high", "rail_reaches_low"):
            if isinstance(eq.get(k), (int, float)):
                m[k] = _round(eq[k], 3)
        m["traversal_density"] = traversal_density_from_counts(
            eq.get("n_full_traversals"), eq.get("n_swings"))

    # --- bar block: individual bars covering the box in place -------------
    bc, err = _safe(measure_bar_compression, window, box_height, atr)
    if err:
        out["errors"].append(f"bar_compression: {err}")
    elif isinstance(bc, dict):
        for k in ("median_spread_atr", "median_spread_pct_box", "tight_bar_pct"):
            if isinstance(bc.get(k), (int, float)):
                m[k] = _round(bc[k], 3)

    # --- travel block (NEW): does movement live inside bars or across them?
    travel = np.abs(np.diff(closes))
    travel = travel[np.isfinite(travel)]
    spreads = (highs - lows)
    spreads = spreads[np.isfinite(spreads)]
    med_travel = float(np.median(travel)) if len(travel) else None
    med_spread = float(np.median(spreads)) if len(spreads) else None
    if med_travel is not None:
        m["median_travel_pct_box"] = round(med_travel / box_height, 3)
    if med_travel is not None and med_spread is not None and med_spread > 0:
        m["travel_spread_ratio"] = round(med_travel / med_spread, 3)
    # consecutive-bar overlap: in a clustered knot each bar re-covers its
    # neighbour's range (overlap near 1); in a travelling limb bars ladder
    if len(highs) >= 2:
        lo_pair = np.minimum(highs[1:], highs[:-1]) - np.maximum(lows[1:], lows[:-1])
        smaller = np.minimum(highs[1:] - lows[1:], highs[:-1] - lows[:-1])
        ok = np.isfinite(lo_pair) & np.isfinite(smaller) & (smaller > 0)
        if np.any(ok):
            m["bar_overlap"] = round(
                float(np.median(np.clip(lo_pair[ok] / smaller[ok], 0.0, 1.0))), 3)

    # --- rail engagement: touch, hang, rest (top and bottom separately) ---
    r_mask, s_mask, r_thirds, s_thirds = base_rail_touches(window, R, S, atr)
    m["r_touches"] = int(np.sum(r_mask))
    m["s_touches"] = int(np.sum(s_mask))
    m["r_touch_thirds"] = int(r_thirds)
    m["s_touch_thirds"] = int(s_thirds)
    above_r, below_s, r_ceiling, s_floor = _rail_outside_masks(highs, lows, R, S, atr)
    hang_r, hang_s = _engagement_hang_masks(
        above_r, below_s, highs, lows, closes, r_ceiling, s_floor, atr)
    m["outside_r"] = int(np.sum(above_r))
    m["outside_s"] = int(np.sum(below_s))
    m["hang_r"] = int(np.sum(hang_r))
    m["hang_s"] = int(np.sum(hang_s))
    rs = _respect_stats(highs, lows, R, S, atr)
    m["respect_share"] = _round(rs[4], 3)
    ld, md, ud = _dwell_bar_basis(window, R, S)
    m["bar_dwell_lower"] = _round(ld, 3)
    m["bar_dwell_mid"] = _round(md, 3)
    m["bar_dwell_upper"] = _round(ud, 3)
    # raw pierce depth vs the drawn rails (unbuffered, ATR units)
    m["max_above_r_atr"] = round(max(0.0, (float(np.nanmax(highs)) - R) / atr), 3)
    m["max_below_s_atr"] = round(max(0.0, (S - float(np.nanmin(lows))) / atr), 3)

    # --- rail story: episodes + the calibrated spring / R-rail events -----
    read, err = _safe(read_rail_episodes, window, R, S, atr)
    if err:
        out["errors"].append(f"episodes: {err}")
    elif isinstance(read, dict) and read.get("episodes") is not None:
        st, err = _safe(episode_sequence_stats, read)
        if err:
            out["errors"].append(f"episode_stats: {err}")
        elif isinstance(st, dict):
            m["episode_profile"] = st.get("profile")
            for k in ("n_completed_s", "n_completed_r", "n_failed_s",
                      "alternations", "n_episodes"):
                if isinstance(st.get(k), (int, float)):
                    m[k] = int(st[k])

    box_ns = SimpleNamespace(start_bar=0, base_len=len(window), R=R, S=S)
    spring, err = _safe(find_spring, window, box_ns, atr)
    if err:
        out["errors"].append(f"spring: {err}")
    elif spring is not None:
        m["spring_type"] = spring.spring_type
        m["spring_undercut_atr"] = _round(spring.undercut_atr, 3)

    rev, err = _safe(measure_resistance_events, window, R, S, atr)
    if err:
        out["errors"].append(f"r_events: {err}")
    elif isinstance(rev, list):
        m["n_upthrusts"] = sum(1 for e in rev if e.get("type") == "upthrust")
        m["n_sos"] = sum(1 for e in rev if e.get("type") == "SOS")
        m["n_r_breaches"] = sum(1 for e in rev if e.get("breached"))
    sts, err = _safe(measure_support_tests, window, R, S, atr)
    if err:
        out["errors"].append(f"s_tests: {err}")
    elif isinstance(sts, list):
        m["n_s_tests_held"] = sum(1 for e in sts if e.get("type") == "test")
        m["n_s_tests_failed"] = sum(1 for e in sts if e.get("type") == "failed")

    return out


# --- reporting ---------------------------------------------------------------
def _f(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def print_profile(c: dict):
    hdr = f"{c['ticker']} @ {c['as_of']}"
    if c["label"]:
        hdr += f" [{c['label']}]"
    print("=" * 78)
    print(hdr)
    if c["errors"]:
        print("  ! " + "; ".join(c["errors"]))
        if not c["m"]:
            return
    m = c["m"]
    print(f"  box {c['box_start']}..{c['box_end']}  R={_f(c['R'])} S={_f(c['S'])}"
          f"  bars={_f(m.get('bars'))}  boxATR={_f(m.get('box_width_atr'))}"
          f"  zone%box={_f(m.get('touch_zone_pct_box'))}")
    print(f"  limbs: trav={_f(m.get('n_full_traversals'))}"
          f" den={_f(m.get('traversal_density'))}"
          f" swings={_f(m.get('n_swings'))}"
          f" maxswing={_f(m.get('max_swing_frac'))}"
          f" reachR={_f(m.get('rail_reaches_high'))}"
          f" reachS={_f(m.get('rail_reaches_low'))}"
          f" deadT={_f(m.get('top_dead_space'))}"
          f" deadB={_f(m.get('bottom_dead_space'))}")
    print(f"  bars : spread%box={_f(m.get('median_spread_pct_box'))}"
          f" spreadATR={_f(m.get('median_spread_atr'))}"
          f" travel%box={_f(m.get('median_travel_pct_box'))}"
          f" travel/spread={_f(m.get('travel_spread_ratio'))}"
          f" tight%={_f(m.get('tight_bar_pct'))}")
    print(f"  rails: rT={_f(m.get('r_touches'))}/{_f(m.get('r_touch_thirds'))}t"
          f" sT={_f(m.get('s_touches'))}/{_f(m.get('s_touch_thirds'))}t"
          f" hangR={_f(m.get('hang_r'))} hangS={_f(m.get('hang_s'))}"
          f" outR={_f(m.get('outside_r'))} outS={_f(m.get('outside_s'))}"
          f" respect={_f(m.get('respect_share'))}"
          f" dwell L/M/U={_f(m.get('bar_dwell_lower'))}/"
          f"{_f(m.get('bar_dwell_mid'))}/{_f(m.get('bar_dwell_upper'))}")
    story = m.get("episode_profile") or "-"
    spring = m.get("spring_type")
    spring_txt = (f"{spring}@{_f(m.get('spring_undercut_atr'))}ATR"
                  if spring else "-")
    print(f"  story: {story}   (S✓{_f(m.get('n_completed_s'))}"
          f" R✓{_f(m.get('n_completed_r'))} S✗{_f(m.get('n_failed_s'))})"
          f"  spring={spring_txt}"
          f" upthrusts={_f(m.get('n_upthrusts'))} sos={_f(m.get('n_sos'))}"
          f" rBreach={_f(m.get('n_r_breaches'))}"
          f" sTests={_f(m.get('n_s_tests_held'))}✓/{_f(m.get('n_s_tests_failed'))}✗"
          f" pierceR={_f(m.get('max_above_r_atr'))}"
          f" pierceS={_f(m.get('max_below_s_atr'))}")


def print_aggregate(cards):
    good = [c for c in cards if c["m"]]
    if not good:
        print("\nno measurable marks.")
        return
    print("\n" + "=" * 78)
    print(f"AGGREGATE  (n={len(good)} marks with geometry)")
    print("=" * 78)
    fields = {}
    for c in good:
        for k, v in c["m"].items():
            if isinstance(v, (int, float)):
                fields.setdefault(k, []).append(float(v))
    print(f"{'measure':28} {'n':>3} {'median':>9} {'min':>9} {'max':>9}")
    print("-" * 62)
    for k in sorted(fields):
        vals = fields[k]
        print(f"{k:28} {len(vals):>3} {statistics.median(vals):>9.3f} "
              f"{min(vals):>9.3f} {max(vals):>9.3f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticker", help="limit to one ticker")
    ap.add_argument("--json", metavar="PATH", help="dump per-mark profiles to JSON")
    args = ap.parse_args()
    if args.json:
        refuse_sealed_output(args.json)

    session = database.SessionLocal()
    try:
        marks, fingerprint = load_box_marks(session, args.ticker)
        cards = [profile_mark(mk) for mk in marks]
    finally:
        session.close()

    scope = f"filtered: {args.ticker.upper()}" if args.ticker else "all box marks"
    print("=" * 78)
    print("  SHAPE PROFILE — how the price action fills each drawn box")
    print("=" * 78)
    print(f"population: calibration marks ({scope})   "
          f"marks_fingerprint: {fingerprint[:16]}… (exact set profiled)")
    print(f"engine_config_version: {manifest_hash()[:16]}…   marks: {len(cards)}")
    for c in cards:
        print_profile(c)
    print_aggregate(cards)

    if args.json:
        doc = {"population": "calibration_marks", "scope": scope,
               "marks_fingerprint": fingerprint,
               "engine_config_version": manifest_hash(),
               "cards": cards}
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, default=str)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
