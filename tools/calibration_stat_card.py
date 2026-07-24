"""Setup Stat Card — measure the operator's DRAWN calibration geometry.

Read-only, offline. For every operator CalibrationMark (verdict='box'), load the
frozen point-in-time frame the mark was drawn on and compute the engine's
descriptive measure set ON THE DRAWN RAILS (resistance/support/box span/LPS span)
by calling the engine_alpha measure functions directly — no box election, no
scoring. Then evaluate the drawn box against the engine's own gate thresholds and
name which gate (if any) the drawn box fails.

This never fires the engine and changes no engine behavior; it points the existing
measures at the operator's geometry so we can see what his marked setups look like
and where the engine's reading diverges from his eye.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.calibration_stat_card            # print cards + aggregate
    python -m tools.calibration_stat_card --json OUT # also dump per-mark JSON
    python -m tools.calibration_stat_card --ticker EGBN
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

import numpy as np
import pandas as pd

# --- bootstrap repo path (mirror tools/calibration_harness.py) --------------
try:
    from tools._bootstrap import configure_path
except ImportError:  # invoked as a script from repo root
    from _bootstrap import configure_path  # type: ignore
_ROOT = configure_path()
sys.path.insert(1, os.path.join(_ROOT, "webapp", "backend"))

import database  # noqa: E402  binds the live SQLite engine + SessionLocal
from models import CalibrationMark  # noqa: E402

from config import settings  # noqa: E402
from webapp.backend import frame_store  # noqa: E402
from engine_alpha.structure.indicators import (  # noqa: E402
    adr_pct,
    calculate_atr,
    distance_to_52w_high_pct,
    trend_template,
)
from engine_alpha.structure.box_gates import (  # noqa: E402
    _is_boundary_respected,
    _occupancy_failures,
    _validate_base_quality,
)
from engine_alpha.structure.metrics import (  # noqa: E402
    measure_bar_compression,
    measure_contractions,
    measure_dwell_balance,
    measure_equilibrium,
    measure_gate_margins,
    measure_support_slope,
    measure_touch_volume,
    descent_tail_rejects,
)
from engine_alpha.structure.lps import lps_range_threshold, _profile_unit  # noqa: E402
from engine_alpha.structure.market_structure import _pairwise_descent_fraction  # noqa: E402

ATR_OFFSET = getattr(settings, "STRUCTURE_ATR_SAMPLE_OFFSET", 6)


# --- helpers ----------------------------------------------------------------
def _safe(fn, *a, **k):
    """Call a measure; return (value, None) or (None, 'error: ...')."""
    try:
        return fn(*a, **k), None
    except Exception as exc:  # noqa: BLE001 measure functions raise on thin/edge data
        return None, f"{type(exc).__name__}: {exc}"


def _pos(index: pd.DatetimeIndex, date_str: str) -> int:
    ts = pd.Timestamp(date_str)
    p = int(index.get_indexer([ts])[0])
    if p == -1:
        p = int(index.searchsorted(ts))
        p = min(p, len(index) - 1)
    return p


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ATR_10"] = calculate_atr(df, 10)
    df["ATR_50"] = calculate_atr(df, 50)
    df["Vol_50"] = df["Volume"].rolling(50).mean()
    df["Spread"] = df["High"] - df["Low"]
    return df


def _num(x):
    try:
        f = float(x)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


# --- per-mark measurement ---------------------------------------------------
def measure_mark(mark) -> dict:
    out = {
        "ticker": mark.ticker,
        "as_of": mark.as_of_date,
        "label": mark.label or "",
        "box_start": mark.box_start_date,
        "box_end": mark.box_end_date,
        "R": _num(mark.resistance),
        "S": _num(mark.support),
        "trigger_date": mark.trigger_date,
        "errors": [],
        "gate_fails": [],
        "m": {},  # measures
    }
    R, S = out["R"], out["S"]
    if R is None or S is None or not (R > S):
        out["errors"].append("no drawn rails")
        return out

    frozen = frame_store.load_frame(mark.ticker, mark.as_of_date, digest=mark.frame_digest)
    if frozen is None or frozen.empty:
        out["errors"].append("basis_mismatch: no frozen frame for this digest")
        return out
    frozen = _enrich(frozen)

    # slice to the box's right edge so the engine's "box ends at last bar" convention holds
    end_idx_full = _pos(frozen.index, mark.box_end_date)
    df = frozen.iloc[: end_idx_full + 1]
    if len(df) < ATR_OFFSET + 1:
        out["errors"].append(f"too few bars before box_end ({len(df)})")
        return out
    atr = _num(df["ATR_10"].iloc[-ATR_OFFSET])
    if atr is None or atr <= 0:
        out["errors"].append("ATR unavailable at box_end")
        return out

    bs = _pos(df.index, mark.box_start_date)
    be = len(df) - 1
    base_df = df.iloc[bs : be + 1]
    box_height = R - S
    box_width = (R - S) / S
    m = out["m"]
    m["box_width"] = round(box_width, 4)
    m["box_width_atr"] = round(box_height / atr, 3)
    m["base_length"] = int(be - bs + 1)
    m["atr_squeeze"] = _num(df["ATR_10"].iloc[-ATR_OFFSET]) and round(
        float(df["ATR_10"].iloc[-ATR_OFFSET]) / float(df["ATR_50"].iloc[-ATR_OFFSET]), 3
    ) if _num(df["ATR_50"].iloc[-ATR_OFFSET]) else None

    highs = base_df["High"].to_numpy()
    lows = base_df["Low"].to_numpy()

    # --- boundary respect -------------------------------------------------
    resp, err = _safe(_is_boundary_respected, highs, lows, R, S, atr)
    if err:
        out["errors"].append(f"respect: {err}")
    elif resp is not None:
        respected, r_broken, s_broken, total_outside, respect_share = resp
        m["respect_share"] = round(float(respect_share), 3)
        m["outside_days"] = int(total_outside)
        if not respected:
            out["gate_fails"].append(
                f"respect {respect_share:.2f} < {settings.MIN_BOUNDARY_RESPECT_PCT}"
            )

    # --- worked-equilibrium validity (the box gate) -----------------------
    vbq, err = _safe(_validate_base_quality, base_df, R, S, atr)
    if err:
        out["errors"].append(f"validate_base_quality: {err}")
    elif vbq is not None:
        r_touches, s_touches, eq, is_valid = vbq
        m["r_touches"] = int(r_touches)
        m["s_touches"] = int(s_touches)
        if isinstance(eq, dict):
            for k in ("lower_dwell", "mid_dwell", "upper_dwell", "coverage",
                      "r_touch_thirds", "s_touch_thirds"):
                if k in eq:
                    m[f"eq_{k}"] = round(float(eq[k]), 3) if isinstance(eq[k], (int, float)) else eq[k]
        if not is_valid:
            fails, ferr = _safe(_occupancy_failures, eq, r_touches, s_touches)
            if fails:
                out["gate_fails"].extend(f"occupancy: {f}" for f in fails)
            else:
                out["gate_fails"].append("worked-equilibrium: invalid")

    # width / base-age gates
    if box_width > settings.MAX_BOX_WIDTH:
        out["gate_fails"].append(f"box_width {box_width:.3f} > MAX_BOX_WIDTH {settings.MAX_BOX_WIDTH}")
    if m["base_length"] < settings.MIN_BASE_DAYS:
        out["gate_fails"].append(f"base_length {m['base_length']} < MIN_BASE_DAYS {settings.MIN_BASE_DAYS}")
    if float(lows.min()) < S * settings.CRASH_FILTER_MULT:
        out["gate_fails"].append("crash filter: low < S x 0.70")

    # --- descriptive measure bundle --------------------------------------
    eqm, err = _safe(measure_equilibrium, base_df, R, S, atr)
    if err:
        out["errors"].append(f"equilibrium: {err}")
    elif isinstance(eqm, dict):
        for k in ("n_full_traversals", "n_swings", "traversal_density",
                  "top_dead_space", "bottom_dead_space", "max_swing_frac",
                  "last_support_time_pos", "low_position_in_box"):
            if k in eqm and isinstance(eqm[k], (int, float)):
                m[k] = round(float(eqm[k]), 3)
        # descent-tail reject (freshness of the coil)
        lsf = eqm.get("last_support_time_pos")
        cfp = eqm.get("low_position_in_box")
        if isinstance(lsf, (int, float)) and isinstance(cfp, (int, float)):
            dt, _ = _safe(descent_tail_rejects, lsf, cfp, box_width)
            if dt:
                out["gate_fails"].append("descent-tail: support abandoned early under a late coil")

    dwm, err = _safe(measure_gate_margins, base_df, R, S, atr)
    if isinstance(dwm, dict):
        for k in ("respect_frac", "close_lower_dwell", "close_mid_dwell", "close_upper_dwell"):
            if k in dwm and isinstance(dwm[k], (int, float)):
                m[k] = round(float(dwm[k]), 3)

    tv, err = _safe(measure_touch_volume, base_df, R, S, atr)
    if isinstance(tv, tuple) and len(tv) == 2:
        m["r_touch_vol_z"] = _num(tv[0]) and round(_num(tv[0]), 3)
        m["s_touch_vol_z"] = _num(tv[1]) and round(_num(tv[1]), 3)

    con, err = _safe(measure_contractions, base_df)
    if err:
        out["errors"].append(f"contractions: {err}")
    elif isinstance(con, dict):
        for src, dst in (("n_contractions", "contraction_count"),
                         ("contraction_count", "contraction_count"),
                         ("quality", "contraction_quality"),
                         ("final_depth", "final_contraction_depth"),
                         ("vol_trend", "contraction_vol_trend")):
            if src in con and isinstance(con[src], (int, float)):
                m[dst] = round(float(con[src]), 3)

    bc, err = _safe(measure_bar_compression, base_df, box_height, atr)
    if isinstance(bc, dict):
        for k in ("median_spread_atr", "p80_spread_atr", "median_spread_pct_box", "tight_bar_pct"):
            if k in bc and isinstance(bc[k], (int, float)):
                m[k] = round(float(bc[k]), 3)

    ss, err = _safe(measure_support_slope, base_df, atr)
    if isinstance(ss, dict):
        for k in ("support_slope_atr", "higher_low_frac", "ascending_support_quality"):
            if k in ss and isinstance(ss[k], (int, float)):
                m[k] = round(float(ss[k]), 3)

    dwb, err = _safe(measure_dwell_balance, base_df, R, S, atr)
    if isinstance(dwb, dict):
        for k in ("lower_dwell", "mid_dwell", "upper_dwell", "coverage"):
            if k in dwb and isinstance(dwb[k], (int, float)):
                m[f"occ_{k}"] = round(float(dwb[k]), 3)

    # --- ADR / trend context (on the full <= box_end frame) --------------
    adr, _ = _safe(adr_pct, df, settings.ADR_WINDOW)
    m["adr_pct"] = _num(adr) and round(_num(adr), 2)
    price = _num(df["Close"].iloc[be])
    dhp, _ = _safe(distance_to_52w_high_pct, df["High"], price, 252)
    m["dist_52w_high_pct"] = _num(dhp) and round(_num(dhp), 3)
    tt, _ = _safe(trend_template, df, dist_52w_high_pct=_num(dhp))
    if isinstance(tt, dict) and "trend_pass_count" in tt:
        m["stage2_trend_pass_count"] = tt.get("trend_pass_count")

    # --- LPS window (measured on the operator's marked span) -------------
    lps_events = [e for e in mark.events if e.event_type == "lps"]
    if lps_events:
        ev = lps_events[-1]  # the completing shelf
        _measure_lps(out, df, base_df, ev, R, S, atr, box_height)

    return out


def _measure_lps(out, df, base_df, ev, R, S, atr, box_height):
    m = out["m"]
    try:
        ls = _pos(df.index, ev.start_date)
        le = _pos(df.index, ev.end_date)
        if le < ls:
            ls, le = le, ls
        window = df.iloc[ls : le + 1]
        lps_low = _num(ev.tip_price)
        if lps_low is None:
            lps_low = float(window["Low"].min())
        first_high = float(window["High"].iloc[0])
        m["lps_length"] = int(le - ls + 1)
        # zone
        if lps_low < S:
            m["lps_zone"] = "UNDERCUT_S"
        elif lps_low > R:
            m["lps_zone"] = "OVERSHOOT_R"
        else:
            m["lps_zone"] = "INSIDE"
        m["lps_position_in_box"] = round((lps_low - S) / box_height, 3)
        m["lps_stretch_atr"] = round((lps_low - R) / atr, 3)
        m["lps_stretch_box"] = round((lps_low - R) / box_height, 3)
        # raw window stats
        thr, _ = _safe(lps_range_threshold, base_df, atr)
        if thr is not None:
            pu, _ = _safe(_profile_unit, thr, box_height)
            if pu:
                m["lps_pullback_profile"] = round((first_high - lps_low) / pu, 3)
                spreads = (window["High"] - window["Low"])
                m["lps_tightness_ratio"] = round(float(spreads.iloc[-1]) / pu, 3)
        v50 = _num(df["Vol_50"].iloc[le])
        if v50:
            avg_vol = float(window["Volume"].mean())
            m["lps_vol_contraction"] = round((v50 - avg_vol) / v50, 3)
        m["lps_window_range_pct_box"] = round(
            (float(window["High"].max()) - float(window["Low"].min())) / box_height, 3
        )
        m["lps_descent_frac"] = round(float(_pairwise_descent_fraction(window["Low"].to_numpy())), 3)
        # LPS gate flags
        if not (settings.LPS_LENGTH_MIN <= m["lps_length"] <= settings.LPS_LENGTH_MAX):
            out["gate_fails"].append(
                f"lps_length {m['lps_length']} outside [{settings.LPS_LENGTH_MIN},{settings.LPS_LENGTH_MAX}]"
            )
        pp = m.get("lps_pullback_profile")
        if pp is not None:
            lo = settings.LPS_PULLBACK_PROFILE_MIN
            if m["lps_zone"] == "OVERSHOOT_R":
                lo = settings.LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R
            if not (lo <= pp <= settings.LPS_PULLBACK_PROFILE_MAX):
                out["gate_fails"].append(f"lps_pullback_profile {pp} outside [{lo},{settings.LPS_PULLBACK_PROFILE_MAX}]")
        vc = m.get("lps_vol_contraction")
        if vc is not None and vc > settings.LPS_VOL_CONTRACTION_MAX:
            out["gate_fails"].append(f"lps_vol_contraction {vc} > {settings.LPS_VOL_CONTRACTION_MAX}")
    except Exception as exc:  # noqa: BLE001
        out["errors"].append(f"lps: {type(exc).__name__}: {exc}")


# --- reporting --------------------------------------------------------------
def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def print_card(c: dict):
    hdr = f"{c['ticker']} @ {c['as_of']}"
    if c["label"]:
        hdr += f" [{c['label']}]"
    print("=" * 78)
    print(hdr)
    if c["errors"]:
        print("  ! " + "; ".join(c["errors"]))
        if not c["m"]:
            return
    print(f"  box {c['box_start']}..{c['box_end']}   R={_fmt(c['R'])} S={_fmt(c['S'])}"
          + (f"   trigger {c['trigger_date']}" if c["trigger_date"] else ""))
    m = c["m"]
    keys = [k for k in m if not k.startswith("occ_")]
    for i in range(0, len(keys), 4):
        row = keys[i : i + 4]
        print("  " + "   ".join(f"{k}={_fmt(m[k])}" for k in row))
    if c["gate_fails"]:
        print("  GATE FAILS: " + " | ".join(c["gate_fails"]))
    else:
        print("  GATE FAILS: none  (drawn box passes the measured gates)")


def print_aggregate(cards):
    good = [c for c in cards if c["m"]]
    if not good:
        print("\nno measurable marks.")
        return
    print("\n" + "=" * 78)
    print(f"AGGREGATE FINGERPRINT  (n={len(good)} marks with geometry)")
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
    # gate-fail tally
    failed = [c for c in good if c["gate_fails"]]
    print(f"\ndrawn boxes that FAIL >=1 measured gate: {len(failed)}/{len(good)}")
    for c in failed:
        print(f"  {c['ticker']} @ {c['as_of']}: " + " | ".join(c["gate_fails"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticker", help="limit to one ticker")
    ap.add_argument("--json", metavar="PATH", help="dump per-mark measures to JSON")
    args = ap.parse_args()

    session = database.SessionLocal()
    try:
        q = session.query(CalibrationMark).filter(CalibrationMark.verdict == "box")
        if args.ticker:
            q = q.filter(CalibrationMark.ticker == args.ticker.upper())
        marks = q.order_by(CalibrationMark.ticker, CalibrationMark.as_of_date,
                           CalibrationMark.label).all()
        cards = [measure_mark(mk) for mk in marks]
    finally:
        session.close()

    for c in cards:
        print_card(c)
    print_aggregate(cards)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(cards, fh, indent=2, default=str)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
