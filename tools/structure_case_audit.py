"""Root-swing / box-integrity case audit — the dissection surface for the
"stale root sees through to a modern box" question (ROIV / TDAY / ADM / BWMX ...).

For each named ticker this REPLICATES the live spine's root walk
(``read_structure`` in core.structure.narrative): it enumerates the candidate
root swings oldest-first exactly as the spine does, and for every root reports
whether its Phase-B equilibrium validates, how far the worked box starts AFTER
the automatic-reaction low (the "root-to-box gap"), the box's rail-to-rail
traversal density, and whether a Phase-D LPS completes the narrative.

The spine returns the FIRST root that completes A->B->(C?)->D, so the audit marks
that winner and then answers the calibration questions directly:

  * Which root won, and on which box?
  * Did an OLDER root win on a box that starts far from its reaction (a stale
    root reaching through to a later structure)?
  * WOULD the proposed root-to-box gap rule (box.start_bar - root.ar_bar <=
    AR_MAX_BARS) re-anchor to a more local root? -- simulated read-only here by
    filtering the same brick outputs, touching no detector math.
  * Did the LPS / trigger survive?

Everything is read-only: it reads the live parquet cache and calls the real,
calibrated bricks. It changes nothing and gates nothing.

    python -m tools.structure_case_audit                       # default cases
    python -m tools.structure_case_audit ROIV ADM BWMX
"""
from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_THIS, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import argparse

import pandas as pd

from config import settings
from core.archive.seed import _evaluate_at_date
from core.pipeline.evaluation import apply_baseline_filters
from core.structure import bricks
from core.structure.box_primitives import (
    _is_boundary_respected,
    _pivot_order,
    _validate_base_quality,
)
from core.structure.indicators import calculate_atr
from core.structure.metrics import measure_traversal
from core.structure.narrative import read_structure
from core.structure.pivots import _build_zigzag, _find_pivots

# The cases that drove the Root-Swing + Box-Integrity repair discussion.
DEFAULT = ["ROIV", "TDAY", "ADM", "BWMX", "NMM", "BBVA"]

# Spine parity: read_structure caps its backtracking loop at this many roots.
_MAX_ANCHORS = 64


def _date(df: pd.DataFrame, bar) -> str:
    """Human-readable date for a full-df bar index (falls back to the raw index)."""
    if bar is None:
        return "   -   "
    try:
        b = int(bar)
    except (TypeError, ValueError):
        return "   -   "
    if b < 0 or b >= len(df):
        return f"#{b}?"
    idx = df.index[b]
    ts = getattr(idx, "date", None)
    return ts().isoformat() if callable(ts) else str(idx)


def _prep(raw: pd.DataFrame):
    """Run the exact live prep (baseline filters + ATR cols) the screener uses.

    Returns (df, atr) or (None, reason)."""
    base = apply_baseline_filters(raw.copy())
    if base is None:
        return None, "rejected at baseline filters (price / vol / trend / return)"
    df, _ = base
    df = df.copy()
    df["ATR_10"] = calculate_atr(df, 10)
    df["ATR_50"] = calculate_atr(df, 50)
    if len(df) < 6:
        return None, "too few bars for an ATR snapshot"
    atr = float(df.iloc[-6]["ATR_10"])
    if not (atr > 0):
        return None, "non-positive ATR snapshot"
    return df, atr


def _complete_narrative(df, box, atr):
    """Mirror the spine's Phase-D resolution: inner-box LPS first, else parent.

    Returns (lps, lps_in_inner, inner, spring) — lps is None when no Phase-D
    minimum completes the story."""
    spring = bricks.find_spring(df, box, atr)
    inner = bricks.find_inner_box(df, box, atr)
    lps = None
    lps_in_inner = False
    if inner is not None:
        lps = bricks.find_lps(df, inner, atr)
        lps_in_inner = lps is not None
    if lps is None:
        lps = bricks.find_lps(df, box, atr)
    return lps, lps_in_inner, inner, spring


def _walk_roots(df, atr):
    """Enumerate roots oldest-first exactly as ``read_structure`` does, evaluating
    each one's box / gap / traversal / LPS INDEPENDENTLY (no short-circuit), so we
    can see the whole landscape — including the roots the live spine never reaches
    because an earlier root already won."""
    rows = []
    search_from = 0
    for _ in range(_MAX_ANCHORS):
        root = bricks.find_root_swing(df, search_from_bar=search_from, atr=atr)
        if root is None:
            break
        search_from = int(root.climax_bar) + 1

        box = bricks.validate_equilibrium(df, root, atr)
        row = {
            "root": root,
            "box": box,
            "gap": None,
            "gap_ok": None,
            "lps": None,
            "lps_in_inner": False,
            "inner": None,
            "spring": None,
            "complete": False,
        }
        if box is not None:
            gap = int(box.start_bar) - int(root.ar_bar)
            row["gap"] = gap
            row["gap_ok"] = gap <= settings.AR_MAX_BARS
            lps, lps_in_inner, inner, spring = _complete_narrative(df, box, atr)
            row["lps"] = lps
            row["lps_in_inner"] = lps_in_inner
            row["inner"] = inner
            row["spring"] = spring
            row["complete"] = lps is not None
        rows.append(row)
    return rows


def _live_winner_idx(rows):
    """Index of the root the live spine returns: the first complete narrative."""
    for i, r in enumerate(rows):
        if r["complete"]:
            return i
    return None


def _gap_rule_winner_idx(rows):
    """Index the spine WOULD return under the proposed root-to-box gap rule:
    the first root whose box is local (gap <= AR_MAX_BARS) AND completes."""
    for i, r in enumerate(rows):
        if r["complete"] and r["gap_ok"]:
            return i
    return None


def _print_winner_detail(df, rows, idx, atr, live):
    r = rows[idx]
    root, box, lps = r["root"], r["box"], r["lps"]
    print(f"  LIVE STRUCTURE  (spine returns root #{idx})")
    print(f"    seed root  climax {_date(df, root.climax_bar)} -> AR {_date(df, root.ar_bar)}"
          f"   ({root.kind}, reaction {root.reaction_pct*100:.1f}% over {root.reaction_bars} bars)")
    # What the chart overlay ACTUALLY draws as Phase A: resolve_phase_a may
    # re-localize the climax->AR pointer near the box, independent of the seed.
    if live is not None:
        dist = abs(int(live.ar_bar) - int(box.start_bar))
        tag = "LOCAL to box" if dist <= settings.AR_MAX_BARS else f"STALE ({dist} bars from box start)"
        print(f"    Phase A    climax {_date(df, live.climax_bar)} -> AR {_date(df, live.ar_bar)}"
              f"   [resolve_phase_a -> overlay; {tag}]")
    print(f"    Phase B  box {_date(df, box.start_bar)} .. (R={box.R:.2f} S={box.S:.2f} "
          f"width={box.box_width:.3f} base_len={box.base_len})")
    print(f"             root-to-box gap = {r['gap']} bars "
          f"({'LOCAL' if r['gap_ok'] else 'STALE >'+str(settings.AR_MAX_BARS)})   "
          f"traversals nFull={box.n_full_traversals} density={box.traversal_density:.3f} "
          f"touches r/s={box.r_touches}/{box.s_touches}")
    if r["spring"] is not None:
        sp = r["spring"]
        print(f"    Phase C  spring tip {_date(df, sp.tip_bar)} "
              f"(undercut {sp.undercut_atr:.2f} ATR, recover {sp.recovery_bars} bars)")
    if r["inner"] is not None:
        inr = r["inner"]
        print(f"    inner    {_date(df, inr.start_bar)} .. "
              f"(R={inr.R:.2f} S={inr.S:.2f} width={inr.box_width:.3f})")
    where = "inner" if r["lps_in_inner"] else "parent"
    print(f"    Phase D  LPS [{where}] start {_date(df, lps.start_bar)} "
          f"trigger={lps.trigger:.2f} zone={lps.zone_type} setup={lps.setup_type} "
          f"offset={lps.offset} len={lps.length}")


def _print_roots_table(df, rows, live_idx, gap_idx):
    print("  CANDIDATE ROOTS (oldest-first — the order the spine walks):")
    print(f"    {'#':>2} {'climax':>10} {'AR':>10} {'kind':>4} {'rx%':>5} "
          f"{'box-start':>10} {'gap':>4} {'loc':>3} {'width':>6} {'nF':>3} "
          f"{'dens':>5} {'lps':>4}  mark")
    for i, r in enumerate(rows):
        root, box = r["root"], r["box"]
        mark = []
        if i == live_idx:
            mark.append("<< LIVE WIN")
        if i == gap_idx and gap_idx != live_idx:
            mark.append("<< GAP-RULE WIN")
        if box is None:
            print(f"    {i:>2} {_date(df, root.climax_bar):>10} {_date(df, root.ar_bar):>10} "
                  f"{root.kind:>4} {root.reaction_pct*100:>4.1f} "
                  f"{'-- no worked equilibrium / traversal-gated --':>10}   {' '.join(mark)}")
            continue
        loc = "yes" if r["gap_ok"] else "NO"
        lps = "yes" if r["complete"] else "no"
        print(f"    {i:>2} {_date(df, root.climax_bar):>10} {_date(df, root.ar_bar):>10} "
              f"{root.kind:>4} {root.reaction_pct*100:>4.1f} "
              f"{_date(df, box.start_bar):>10} {r['gap']:>4} {loc:>3} "
              f"{box.box_width:>6.3f} {box.n_full_traversals:>3} "
              f"{box.traversal_density:>5.3f} {lps:>4}  {' '.join(mark)}")


def _print_diagnosis(rows, live_idx, gap_idx):
    print("  DIAGNOSIS:")
    # How many DISTINCT boxes do the completing roots actually produce? If it is
    # one, the box is emergent from candidate enumeration and the seed root is
    # merely a scan origin — not the cause the box-integrity plan assumes.
    box_starts = {int(r["box"].start_bar) for r in rows if r["complete"]}
    if box_starts:
        n_complete = sum(1 for r in rows if r["complete"])
        print(f"    {n_complete} completing roots -> {len(box_starts)} distinct box(es). "
              f"{'Same box from every seed: the root is a scan origin, not the cause.' if len(box_starts) == 1 else 'Seed choice changes which box wins.'}")
    if live_idx is None:
        print("    no root completes a narrative — the stock does not fire.")
        return
    live = rows[live_idx]
    if live["gap_ok"]:
        print(f"    live winner root #{live_idx} is LOCAL (gap={live['gap']} "
              f"<= {settings.AR_MAX_BARS}) — not a stale-root case.")
    else:
        print(f"    live winner root #{live_idx} is STALE — its box starts "
              f"{live['gap']} bars after the reaction (> {settings.AR_MAX_BARS}); "
              f"an old root is reaching through to a later structure.")
    if gap_idx is None:
        print("    root-to-box gap rule would leave NO completing root -> the gate "
              "would DROP this ticker (recall risk — check whether that is correct).")
    elif gap_idx != live_idx:
        print(f"    root-to-box gap rule WOULD RE-ANCHOR: winner moves "
              f"#{live_idx} -> #{gap_idx} (a more local root). <-- change 2 acts here.")
    else:
        print("    root-to-box gap rule leaves the winner unchanged.")
    # Traversal-floor sensitivity (change 4): does the live box survive 0.12?
    if live_idx is not None and rows[live_idx]["box"] is not None:
        d = rows[live_idx]["box"].traversal_density
        for floor in (0.08, 0.12):
            verdict = "survives" if d >= floor else "FAILS"
            print(f"    live box density {d:.3f} {verdict} a {floor:.2f} floor.")


def _validity_reject(eq, r_touches, s_touches) -> str:
    """First failing worked-equilibrium sub-gate of ``_validate_base_quality``."""
    checks = [
        ("r_touches", r_touches, settings.EQ_MIN_TOUCHES_PER_RAIL, ">="),
        ("s_touches", s_touches, settings.EQ_MIN_TOUCHES_PER_RAIL, ">="),
        ("r_touch_thirds", eq["r_touch_thirds"], settings.EQ_MIN_TOUCH_THIRDS, ">="),
        ("s_touch_thirds", eq["s_touch_thirds"], settings.EQ_MIN_TOUCH_THIRDS, ">="),
        ("lower_dwell", eq["lower_dwell"], settings.EQ_MIN_HALF_DWELL, ">="),
        ("upper_dwell", eq["upper_dwell"], settings.EQ_MIN_HALF_DWELL, ">="),
        ("mid_dwell", eq["mid_dwell"], settings.EQ_MAX_MID_DWELL, "<="),
        ("coverage", eq["coverage"], settings.EQ_MIN_COVERAGE, ">="),
    ]
    for name, val, thr, op in checks:
        ok = (val >= thr) if op == ">=" else (val <= thr)
        if not ok:
            return f"{name}={val} (need {op}{thr})"
    return "PASS?"


def _diagnose_candidates(df, root, atr) -> None:
    """Pass-0 box diagnostic: for a root whose strict Phase-B box fails, enumerate
    the zigzag R/S candidates and report each one's FIRST binding reject — the REAL
    box_primitives gates (width -> boundary respect -> worked-equilibrium dwell/
    coverage -> traversal) run in pipeline order — plus a recovered-support hint.
    Read-only; mirrors ``validate_equilibrium``'s framing (eval_df[:-skip], AR-low)."""
    skip = settings.STRUCTURE_EDGE_SKIP_BARS
    eval_df = df.iloc[:-skip] if len(df) > skip else df
    if root.ar_bar >= len(eval_df):
        print("      (AR beyond eval window)")
        return
    eq_df = eval_df.iloc[root.ar_bar:]
    if len(eq_df) < settings.MIN_BASE_DAYS:
        print("      (post-AR window < MIN_BASE_DAYS)")
        return
    eq_highs, eq_lows = eq_df["High"].values, eq_df["Low"].values
    peaks, valleys = _find_pivots(eq_highs, eq_lows, _pivot_order(len(eq_df)))
    if not peaks or not valleys:
        print("      (no pivots in window)")
        return
    zz = _build_zigzag(peaks, valleys, eq_highs, eq_lows)
    print(f"        {'R':>8} {'S':>8} {'width':>6} {'start':>11}  first-reject")
    shown = 0
    for i in range(len(zz) - 1):
        zi, zj = zz[i], zz[i + 1]
        if zi[1] == "peak" and zj[1] == "valley":
            R_val, S_val, r_a, s_a = zi[2], zj[2], zi[0], zj[0]
        elif zi[1] == "valley" and zj[1] == "peak":
            R_val, S_val, r_a, s_a = zj[2], zi[2], zj[0], zi[0]
        else:
            continue
        if R_val <= S_val:
            continue
        width = (R_val - S_val) / S_val
        cstart = min(r_a, s_a)
        sub = eq_df.iloc[cstart:]
        chi, clo = eq_highs[cstart:], eq_lows[cstart:]
        if width > settings.MAX_BOX_WIDTH:
            reject = f"width {width:.3f} > {settings.MAX_BOX_WIDTH}"
        elif not _is_boundary_respected(chi, clo, R_val, S_val, atr)[0]:
            reject = "boundary_respect"
        else:
            rt, st, eq, valid = _validate_base_quality(sub, R_val, S_val, atr)
            if eq is None:
                reject = "width/crash"
            elif not valid:
                reject = _validity_reject(eq, rt, st)
            else:
                trav = measure_traversal(sub, R_val, S_val, atr)
                nf, ns = trav["n_full_traversals"], trav["n_swings"]
                dens = nf / ns if ns else 0.0
                if settings.TRAVERSAL_GATE_ENABLED and (
                        nf < settings.TRAVERSAL_MIN or dens < settings.TRAVERSAL_MIN_DENSITY):
                    reject = f"traversal nF={nf} dens={dens:.3f} (<{settings.TRAVERSAL_MIN}/{settings.TRAVERSAL_MIN_DENSITY})"
                else:
                    reject = "PASS (would validate)"
        print(f"        {R_val:>8.2f} {S_val:>8.2f} {width:>6.3f} "
              f"{_date(df, root.ar_bar + cstart):>11}  {reject}")
        shown += 1
        if shown >= 12:
            print("        ... (more candidates truncated)")
            break
    if shown == 0:
        print("        (no peak/valley R<S candidate pairs)")
    # Recovered-support / high-shelf hint from the post-AR window extremes.
    R_ext, S_ext = float(eq_highs.max()), float(eq_lows.min())
    if R_ext > S_ext:
        trav = measure_traversal(eq_df, R_ext, S_ext, atr)
        lsf, cfp = trav.get("last_support_frac"), trav.get("coil_floor_pos")
        if lsf is not None and cfp is not None:
            tag = ("recovered-support candidate (old floor abandoned early)"
                   if (lsf <= 0.40 and cfp >= 0.20) else "no early-abandonment signal")
            print(f"      window: last_support_frac={lsf:.3f} coil_floor_pos={cfp:.3f} "
                  f"-> {tag}")


def audit(ticker: str, raw: pd.DataFrame) -> None:
    print("=" * 92)
    print(ticker)
    df, atr = _prep(raw)
    if df is None:
        print(f"  {atr}")   # atr carries the rejection reason here
        return

    rows = _walk_roots(df, atr)
    if not rows:
        print("  no qualifying root swings (no climax->reaction anchor in the window).")
        return

    live_idx = _live_winner_idx(rows)
    gap_idx = _gap_rule_winner_idx(rows)

    live = read_structure(df, atr)
    if live_idx is not None:
        _print_winner_detail(df, rows, live_idx, atr, live)
        # Faithfulness cross-check: our manual walk must match the real spine.
        if live is not None:
            w = rows[live_idx]["box"]
            ok = (int(live.phase_b_start_bar) == int(w.start_bar)
                  and abs(float(live.R) - float(w.R)) < 1e-6)
            if not ok:
                print(f"    [warn] manual walk diverged from read_structure "
                      f"(spine box-start {_date(df, live.phase_b_start_bar)} "
                      f"R={live.R:.2f}) — audit logic needs a look.")
    else:
        print("  LIVE STRUCTURE: none — no root completes A->B->(C?)->D.")
    print()
    _print_roots_table(df, rows, live_idx, gap_idx)
    print()
    _print_diagnosis(rows, live_idx, gap_idx)

    if live_idx is None:
        print()
        print("  WHY NO BOX — strict candidate rejects (most-recent 4 roots, where "
              "a recent setup lives):")
        lo = max(0, len(rows) - 4)
        for i in range(lo, len(rows)):
            rt = rows[i]["root"]
            print(f"    root #{i}  climax {_date(df, rt.climax_bar)} -> AR {_date(df, rt.ar_bar)}:")
            _diagnose_candidates(df, rt, atr)


def _spy_6m(d, level0) -> float:
    """SPY 6-month return as of the latest cached bar. Feeds only the RS score
    bonus (never gates), so one snapshot is fine across as-of offsets."""
    spy = settings.SPY_SYMBOL
    if spy not in level0:
        return 0.0
    sc = d[spy]["Close"].dropna()
    if len(sc) <= settings.RS_LOOKBACK_BARS:
        return 0.0
    return float(sc.iloc[-1] / sc.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0)


def find_last_valid(raw: pd.DataFrame, spy_6m: float, scan_back: int):
    """Walk backward from the latest bar; return (offset, result_dict, truncated_df)
    for the MOST RECENT as-of date the full pipeline fires, or (None, None, None).

    Dropping the last ``offset`` bars = "pretend the rest doesn't exist", so a
    setup whose LPS was later ruined is still seen at the date it was live. Uses
    the real ``_evaluate_at_date`` (full baseline -> structure -> LPS -> score)."""
    n = len(raw)
    for off in range(0, scan_back + 1):
        sl = raw.iloc[: n - off] if off else raw
        if len(sl) < 200:
            break
        res = _evaluate_at_date(sl.copy(), spy_6m_return=spy_6m)
        if res is not None:
            return off, res, sl
    return None, None, None


def print_engine_trace(ticker: str, raw: pd.DataFrame) -> None:
    """Print the engine's OWN narrative trace (read_structure(trace=...)) rather
    than re-walking the roots externally. Groups identical stories so the
    emergent box (same box from ~every root) reads as 'N roots -> this story'."""
    print("=" * 92)
    print(f"{ticker}  — engine narrative trace")
    df, atr = _prep(raw)
    if df is None:
        print(f"  {atr}")
        return
    trace: list = []
    structure = read_structure(df, atr, trace=trace)
    if not trace:
        print("  no root swings — no story to tell.")
        return

    n_box = sum(1 for r in trace if r["box"] is not None)
    n_done = sum(1 for r in trace if r["outcome"] == "complete")
    print(f"  roots tried: {len(trace)}   reached a worked box: {n_box}   "
          f"completed A->B->(C?)->D: {n_done}")
    print(f"  RESULT: {'FIRES' if structure is not None else 'NO SETUP'}")
    print()

    # Collapse identical (box-start, outcome, parent-LPS-rejects) stories.
    groups: dict = {}
    order: list = []
    for r in trace:
        key = (
            r["box"]["start_bar"] if r["box"] else None,
            r["outcome"],
            tuple(sorted((r["lps_rejects"] or {}).get("parent", {}).items())),
        )
        if key not in groups:
            groups[key] = {"count": 0, "rep": r}
            order.append(key)
        groups[key]["count"] += 1

    for key in order:
        g = groups[key]
        r = g["rep"]
        tag = {"complete": "<< COMPLETE", "no_lps": "box OK, NO LPS",
               "no_box": "no worked box"}.get(r["outcome"], r["outcome"])
        print(f"  [{g['count']:>3} root(s)]  e.g. #{r['root_index']} "
              f"{_date(df, r['climax_bar'])}->{_date(df, r['ar_bar'])} {r['kind']} "
              f"rx{r['reaction_pct'] * 100:.0f}%   {tag}")
        b = r["box"]
        if b:
            print(f"       B box {_date(df, b['start_bar'])}  R={b['R']:.2f} S={b['S']:.2f} "
                  f"w={b['box_width']:.3f} len={b['base_len']} "
                  f"trav={b['n_full_traversals']}/{b['traversal_density']:.2f} "
                  f"touch r/s={b['r_touches']}/{b['s_touches']}")
        if r["spring"]:
            sp = r["spring"]
            print(f"       C spring tip {_date(df, sp['tip_bar'])} undercut {sp['undercut_atr']:.2f}ATR")
        if r["inner"]:
            inr = r["inner"]
            print(f"       inner {_date(df, inr['start_bar'])} w={inr['box_width']:.3f} len={inr['base_len']}")
        if r["lps"]:
            l = r["lps"]
            where = "inner" if l["in_inner"] else "parent"
            print(f"       D LPS [{where}] {_date(df, l['start_bar'])} len={l['length']} "
                  f"off={l['offset']} zone={l['zone_type']} swing={l['swing_type']} trig={l['trigger']:.2f}")
        elif r["outcome"] == "no_lps" and r["lps_rejects"]:
            rj = r["lps_rejects"]
            print(f"       D NO LPS — parent rejects: {dict(rj.get('parent', {}))}")
            if rj.get("inner"):
                print(f"                  inner rejects: {dict(rj['inner'])}")
        print()


def main() -> None:
    ap = argparse.ArgumentParser(description="Root-swing / box-integrity case audit.")
    ap.add_argument("tickers", nargs="*",
                    help="tickers to audit (default: the repair set)")
    ap.add_argument("--scan-back", type=int, default=0, metavar="N",
                    help="find each ticker's most recent valid date within the last "
                         "N bars and dissect the structure THERE (later bars treated "
                         "as non-existent), instead of auditing today.")
    ap.add_argument("--as-of", type=str, default=None, metavar="YYYY-MM-DD",
                    help="slice each ticker to end at this date (later bars treated as "
                         "non-existent) before auditing — for historical seed cases.")
    ap.add_argument("--trace", action="store_true",
                    help="print the engine's own narrative trace (read_structure's "
                         "per-root story + LPS reject reasons) instead of the audit walk.")
    a = ap.parse_args()

    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    level0 = set(d.columns.get_level_values(0))
    spy_6m = _spy_6m(d, level0)
    tickers = [t.upper() for t in a.tickers] or DEFAULT

    for t in tickers:
        if t not in level0:
            print("=" * 92)
            print(f"{t}: not in cache")
            continue
        raw = d[t].dropna()
        if a.as_of:
            raw = raw[raw.index <= pd.Timestamp(a.as_of)]
        if a.trace:
            print_engine_trace(t, raw)
            continue
        if a.scan_back:
            off, res, sl = find_last_valid(raw, spy_6m, a.scan_back)
            if res is None:
                print(f"\n>>> {t}: did NOT fire in the last {a.scan_back} bars "
                      f"(latest {raw.index[-1].date()}) — auditing today for context.")
                audit(t, raw)
            else:
                trig, bw, sc = res.get("trigger_price"), res.get("box_width"), res.get("score")
                trig_s = f"{trig:.2f}" if isinstance(trig, (int, float)) else str(trig)
                bw_s = f"{bw:.3f}" if isinstance(bw, (int, float)) else str(bw)
                sc_s = f"{sc:.0f}" if isinstance(sc, (int, float)) else str(sc)
                print(f"\n>>> {t}: LAST VALID {sl.index[-1].date()} (off -{off})  "
                      f"Tier {res.get('tier')}  score {sc_s}  {res.get('setup_type')}  "
                      f"trigger {trig_s}  box {bw_s}  LPS_len {res.get('lps_length')}")
                audit(t, sl)
        else:
            audit(t, raw)
    print("=" * 92)


if __name__ == "__main__":
    main()
