"""Bar-state census — the operator's THREE ceiling states, counted mechanically.

Read-only, offline. Serves the 2026-08-30 rail-area rulings: *Resting on
Resistance / At Resistance / Semi dwelling* are "just a visual thing" and the
rail area is SYMMETRIC at +/-0.50 ATR. Both rows rest on this census, which
answered the operator's symmetry hedge (*"IDK man we got to dig deeper on
that"*) by building the harsher-above rule BOTH ways and counting whom it
flags.

Two populations, one state machine, two rails:

  drawn — every operator ``CalibrationMark(verdict='box')`` on HIS rails over
          HIS window (``tools.calibration.replay.drawn_box_window``, the shared EC-13
          derivation). 35 marks / 1,492 bars when the evidence was sealed.
  junk  — every negative-corpus strict candidate framing that SURVIVED the
          boundary-respect gate (not rescued; stage not in width/window/
          respect), judged on ``tools.calibration.replay.judged_window``. 98 framings /
          2,949 bars when sealed.

Per bar, per rail (tol = ``TOUCH_TOLERANCE_ATR`` * ATR):
  R side: resting  low >= R          (whole bar above the rail)
          semi     high > R > low    (straddles the line)
          at_rail  R - tol <= high <= R   (touches the ceiling from inside)
          away     otherwise
  S side mirrored: resting (high <= S), semi (low < S < high),
          at_rail (S <= low <= S + tol), away.

Committed as the evidence instrument behind the 2026-08-30 rail-area rows
(EC-16): the census that closed the symmetry hedge ran from a session
scratchpad, so nothing committed reproduced its numbers. Sidecar-only
(EC-46); population + marks fingerprint + manifest stamped (EC-13); --json
passes the sealed-output guard (EC-14). It proposes no gate and no threshold
— every number is a measurement.

REPRODUCIBILITY NOTE — the census-local conventions are FROZEN here. None of
them is an engine artifact; changing any one silently re-derives the recorded
evidence:
  * ``RESOLVE_ATR`` (0.5) is the what-follows resolution band and the
    seller's-tail crash line. It coincided with ``TOUCH_TOLERANCE_ATR`` and
    ``BOUNDARY_ATR_BUFFER`` at seal time; it is frozen as recorded arithmetic
    so this census keeps measuring the sealed convention if either knob moves.
  * ``FOLLOW_BARS`` (10) / ``TAIL_CRASH_BARS`` (5) / ``TAIL_SPREAD_ATR``
    (1.5, with 2.0 as the secondary cut) are the census's own horizons, named
    in the report and nowhere in the engine.
  * what-follows is anchored at a run's EXTREME breach bar, never at the run
    END — a run only ends when a bar goes away, which would force the answer.
  * ``STATE_ORDER`` is the dominant-state tie-break: most-frequent state wins,
    ties resolve resting > semi > at_rail.
  * "mostly above/below" is the BAR MIDPOINT ((High+Low)/2) against the rail —
    a census harshness variant, not an engine reading.
  * the junk enumeration dedupes framings by ``(R, S, cand_start, stage)`` and
    requires a >= 3-bar judged window; the sibling censuses
    (``event_map_census``, ``near_miss_census``) key and floor theirs slightly
    differently, and the 98-framing denominator is THIS convention's.
  * ONE frame-level ATR per box (the drawn-window instrument ATR, the junk
    prep's live ATR snapshot) — the same convention as the rail-area
    instrument. The resting/semi states themselves are tolerance-free
    (whole-bar-beyond and straddle are exact); only ``at_rail`` uses the
    tolerance.

Usage (the repo venv, from the repo root):
    python -m tools.research.bar_state_census [--json OUT.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter

import numpy as np

try:  # works under both `python -m tools.research.bar_state_census` and `python tools/research/bar_state_census.py`
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

_ROOT = configure_path(backend=True)

import database  # noqa: E402  binds the SQLite engine + SessionLocal

from config import settings  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.events.box_events import measure_resistance_events  # noqa: E402
from engine_alpha.structure.narrative.reader import read_structure  # noqa: E402
from tools.regression import negative_corpus  # noqa: E402
from tools.calibration.calibration_harness import load_box_marks  # noqa: E402
from tools.calibration.replay import (  # noqa: E402
    drawn_box_window,
    judged_window,
    prepared_frame_with_reason,
)
from webapp.backend import frame_store  # noqa: E402

TOL_ATR = float(settings.TOUCH_TOLERANCE_ATR)   # 0.5 — the rail-area tolerance
RESOLVE_ATR = 0.5        # census-local resolution band (see the note above)
FOLLOW_BARS = 10         # what-follows horizon
TAIL_CRASH_BARS = 5      # seller's-tail crash-back horizon
TAIL_SPREAD_ATR = 1.5    # seller's-tail spread cut
TAIL_SPREAD_WIDE = 2.0   # the secondary (stricter) spread cut
STATE_ORDER = ("resting", "semi", "at_rail")   # dominant-state tie-break
MIN_WINDOW_BARS = 3
JUNK_SKIP_STAGES = ("width", "window", "respect")
ANCHOR_TICKERS = ("DSGN", "MATX", "MSGS", "NOK")

HARSH_RULES = (
    ("resting_above_outside_markup", "resting_above(out-markup)"),
    ("mostly_above_outside_markup", "mostly_above(out-markup)"),
    ("resting_above_outside_markup_or_inprog", "resting_above(out-markup+inprog)"),
    ("mostly_above_outside_markup_or_inprog", "mostly_above(out-markup+inprog)"),
    ("resting_below", "resting_below"),
    ("mostly_below", "mostly_below"),
)
HARSH_THRESHOLDS = (1, 2, 3, 5)


def _r(v, nd=4):
    if v is None:
        return None
    v = float(v)
    return round(v, nd) if math.isfinite(v) else None


def dist(vals) -> dict | None:
    """n / median / p75 / p90 / max over the finite values (the report shape)."""
    v = sorted(float(x) for x in vals
               if x is not None and math.isfinite(float(x)))
    if not v:
        return None
    a = np.array(v, dtype=float)
    return {"n": len(v), "median": _r(np.median(a)), "p75": _r(np.percentile(a, 75)),
            "p90": _r(np.percentile(a, 90)), "max": _r(a.max())}


def _runs(mask) -> list[tuple[int, int]]:
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def classify(highs, lows, R, S, atr) -> tuple[list[str], list[str]]:
    """Per-bar state on EACH rail — 'resting' (whole bar beyond the rail) /
    'semi' (straddles it) / 'at_rail' (touches the area from inside) / 'away'."""
    tol = TOL_ATR * atr
    r_states, s_states = [], []
    for h, l in zip(highs, lows):
        if l >= R:
            r_states.append("resting")
        elif h > R:
            r_states.append("semi")
        elif R - tol <= h:
            r_states.append("at_rail")
        else:
            r_states.append("away")
        if h <= S:
            s_states.append("resting")
        elif l < S:
            s_states.append("semi")
        elif l <= S + tol:
            s_states.append("at_rail")
        else:
            s_states.append("away")
    return r_states, s_states


def measure_box(window, R, S, atr, *, case, pop, extra=None) -> dict:
    """Every measure this census reports, for ONE box. Keys prefixed with '_'
    are working detail (per-bar reach values, run records) consumed by the
    aggregation and stripped from the sidecar."""
    out = {"case": case, "pop": pop, "R": _r(R), "S": _r(S), "atr": _r(atr),
           "measured": False, "errors": []}
    if extra:
        out.update(extra)
    box = float(R) - float(S)
    if not (box > 0) or atr is None or not math.isfinite(float(atr)) or float(atr) <= 0:
        out["errors"].append("degenerate box or ATR")
        return out
    atr, R, S = float(atr), float(R), float(S)
    highs = window["High"].to_numpy(dtype=float)
    lows = window["Low"].to_numpy(dtype=float)
    closes = window["Close"].to_numpy(dtype=float)
    n = len(highs)
    out["bars"] = n
    out["box_height_atr"] = _r(box / atr)
    if n < MIN_WINDOW_BARS:
        out["errors"].append("window too short")
        return out

    r_states, s_states = classify(highs, lows, R, S, atr)
    mids = (highs + lows) / 2.0
    out["r_state_counts"] = dict(Counter(r_states))
    out["s_state_counts"] = dict(Counter(s_states))

    # The engine's own R-rail wave typing carries the "bigger swing upwards"
    # exclusion. Right-edge departures are typed in_progress and never markup
    # (no-lookahead), so the wider mask is measured as a second variant.
    try:
        r_events = measure_resistance_events(window, R, S, atr)
    except Exception as exc:                      # noqa: BLE001
        r_events = []
        out["errors"].append(f"r_events: {exc}")
    in_markup = np.zeros(n, dtype=bool)
    in_markup_ip = np.zeros(n, dtype=bool)
    for e in r_events:
        a, b = max(0, int(e["zone_start"])), min(n, int(e["zone_end"]) + 1)
        if e["type"] == "markup":
            in_markup[a:b] = True
            in_markup_ip[a:b] = True
        elif e["type"] == "in_progress":
            in_markup_ip[a:b] = True
    out["n_markup_waves"] = sum(1 for e in r_events if e["type"] == "markup")

    def _wave_types(a, b) -> list[str]:
        return sorted({e["type"] for e in r_events
                       if max(a, int(e["zone_start"])) <= min(b, int(e["zone_end"]))})

    def _what_follows(rail, peak_bar) -> str:
        """From the run's EXTREME breach bar, first-hit-wins over the next
        FOLLOW_BARS closes (band = RESOLVE_ATR * ATR).
        R: close > R+band -> left_up; close < R-band -> back inside, then
           sub-classified within the same horizon (any close below the box
           MIDPOINT -> crash_back_through_box, else resumed_consolidation —
           his 'the consolidation continues normally' case); neither ->
           consolidating_near_rail.
        S mirrored: broke_down / reclaimed_into_box / held_near_support /
           consolidating_near_rail.
        Fewer than FOLLOW_BARS printed bars and no resolution -> right_edge."""
        band = RESOLVE_ATR * atr
        mid = (R + S) / 2.0
        j0, j1 = peak_bar + 1, min(n, peak_bar + 1 + FOLLOW_BARS)
        for j in range(j0, j1):
            c = closes[j]
            if rail == "R":
                if c > R + band:
                    return "left_up"
                if c < R - band:
                    deep = any(closes[k] < mid for k in range(j, j1))
                    return "crash_back_through_box" if deep else "resumed_consolidation"
            else:
                if c < S - band:
                    return "broke_down"
                if c > S + band:
                    deep = any(closes[k] > mid for k in range(j, j1))
                    return "reclaimed_into_box" if deep else "held_near_support"
        if j1 == n and (j1 - j0) < FOLLOW_BARS:
            return "right_edge"
        return "consolidating_near_rail"

    def _make_runs(states, rail) -> list[dict]:
        recs = []
        for a, b in _runs([st != "away" for st in states]):
            seg = states[a:b + 1]
            c = Counter(seg)
            dom = max(STATE_ORDER,
                      key=lambda s: (c.get(s, 0), -STATE_ORDER.index(s)))
            reach = (float(np.max(highs[a:b + 1]) - R) / atr if rail == "R"
                     else float(S - np.min(lows[a:b + 1])) / atr)
            breaches = any(st in ("resting", "semi") for st in seg)
            rec = {"rail": rail, "start": a, "end": b, "n_bars": b - a + 1,
                   "states": dict(c), "dominant": dom,
                   "max_reach_atr": _r(reach), "breaches": breaches,
                   "len_class": ("singular" if b == a
                                 else "short" if b - a == 1 else "dwell")}
            if rail == "R":
                rest_idx = [i for i in range(a, b + 1) if states[i] == "resting"]
                rec["has_resting"] = bool(rest_idx)
                rec["resting_in_markup"] = bool(
                    rest_idx and any(in_markup[i] for i in rest_idx))
                rec["overlapping_wave_types"] = _wave_types(a, b)
            if breaches:
                peak = (a + int(np.argmax(highs[a:b + 1])) if rail == "R"
                        else a + int(np.argmin(lows[a:b + 1])))
                rec["peak_bar"] = peak
                rec["outcome"] = _what_follows(rail, peak)
            recs.append(rec)
        return recs

    out["_r_runs"] = _make_runs(r_states, "R")
    out["_s_runs"] = _make_runs(s_states, "S")

    # Seller's tail: a breach bar with a huge spread that crashed back inside.
    tails = []
    band = RESOLVE_ATR * atr
    for i in range(n):
        if r_states[i] not in ("resting", "semi"):
            continue
        rng = (highs[i] - lows[i]) / atr
        if rng < TAIL_SPREAD_ATR:
            continue
        tails.append({"i": i, "range_atr": _r(rng),
                      "crashed_back": any(
                          closes[j] < R - band
                          for j in range(i + 1, min(n, i + 1 + TAIL_CRASH_BARS)))})
    out["_tails"] = tails

    # Per-box harshness counts — the flag grid aggregates these.
    out["harsh"] = {
        "resting_above_outside_markup": sum(
            1 for i in range(n) if r_states[i] == "resting" and not in_markup[i]),
        "mostly_above_outside_markup": sum(
            1 for i in range(n) if mids[i] > R and not in_markup[i]),
        "resting_above_outside_markup_or_inprog": sum(
            1 for i in range(n) if r_states[i] == "resting" and not in_markup_ip[i]),
        "mostly_above_outside_markup_or_inprog": sum(
            1 for i in range(n) if mids[i] > R and not in_markup_ip[i]),
        "resting_below": s_states.count("resting"),
        "mostly_below": int(np.sum(mids < S)),
    }
    # Per-bar distance detail, pooled by the population summary only.
    out["_reach"] = {
        "R_resting": [_r((highs[i] - R) / atr) for i in range(n)
                      if r_states[i] == "resting"],
        "R_resting_clearance": [_r((lows[i] - R) / atr) for i in range(n)
                                if r_states[i] == "resting"],
        "R_semi": [_r((highs[i] - R) / atr) for i in range(n)
                   if r_states[i] == "semi"],
        "R_at_rail_gap": [_r((R - highs[i]) / atr) for i in range(n)
                          if r_states[i] == "at_rail"],
        "S_resting": [_r((S - lows[i]) / atr) for i in range(n)
                      if s_states[i] == "resting"],
        "S_resting_clearance": [_r((S - highs[i]) / atr) for i in range(n)
                                if s_states[i] == "resting"],
        "S_semi": [_r((S - lows[i]) / atr) for i in range(n)
                   if s_states[i] == "semi"],
        "S_at_rail_gap": [_r((lows[i] - S) / atr) for i in range(n)
                          if s_states[i] == "at_rail"],
    }
    out["measured"] = True
    return out


# --- populations -------------------------------------------------------------
def drawn_population() -> tuple[list[dict], str]:
    """The operator's drawn boxes, through the ONE validated marks loader."""
    session = database.SessionLocal()
    try:
        marks, fingerprint = load_box_marks(session)
        rows = []
        for mk in marks:
            case = (f"{mk.ticker}@{mk.as_of_date}"
                    + (f"[{mk.label}]" if mk.label else ""))
            extra = {"ticker": mk.ticker, "as_of": str(mk.as_of_date),
                     "label": mk.label or ""}
            R, S = mk.resistance, mk.support
            if R is None or S is None or not (R > S):
                rows.append({"case": case, "pop": "drawn", "errors":
                             ["no drawn rails"], **extra})
                continue
            frozen = frame_store.load_frame(mk.ticker, mk.as_of_date,
                                            digest=mk.frame_digest)
            if frozen is None or frozen.empty:
                rows.append({"case": case, "pop": "drawn", "errors":
                             ["basis_mismatch: no frozen frame for this digest"],
                             **extra})
                continue
            try:
                window, atr = drawn_box_window(frozen, mk.box_start_date,
                                               mk.box_end_date)
            except ValueError as exc:
                rows.append({"case": case, "pop": "drawn",
                             "errors": [str(exc)], **extra})
                continue
            rows.append(measure_box(window, float(R), float(S), atr,
                                    case=case, pop="drawn", extra=extra))
        return rows, fingerprint
    finally:
        session.close()


def junk_population() -> tuple[list[dict], dict]:
    """Negative-corpus strict candidate framings that SURVIVED the respect gate.

    A missing frame or a refused prep aborts loudly: a silently skipped case
    shrinks the 98-framing denominator every cited rate divides by."""
    frames, meta = negative_corpus._load_fixture()
    rows = []
    for case in meta["cases"]:
        key = case.get("key", case["ticker"])
        raw = frames.get(key)
        if raw is None or raw.empty:
            raise SystemExit(f"junk population: frame missing for {key}")
        prep, reason = prepared_frame_with_reason(raw, case["as_of"])
        if prep is None:
            raise SystemExit(f"junk population: {key} refused prep "
                             f"({reason[0]}) — fixture basis drift")
        df, atr = prep
        trace: list = []
        read_structure(df, atr, trace=trace)
        seen: set = set()
        for root in trace:
            for rec in root.get("box_cascade") or []:
                if rec["rescued"] or rec["stage"] in JUNK_SKIP_STAGES:
                    continue     # rescued framings and pre-respect kills
                sig = (rec["R"], rec["S"], rec["cand_start"], rec["stage"])
                if sig in seen:
                    continue
                seen.add(sig)
                win = judged_window(df, int(rec["cand_start"]))
                if len(win) < MIN_WINDOW_BARS:
                    continue
                rows.append(measure_box(
                    win, float(rec["R"]), float(rec["S"]), atr,
                    case=f"{key}#{rec['cand_start']}", pop="junk",
                    extra={"ticker": case["ticker"], "label": case["label"],
                           "stage": rec["stage"] or "passed"}))
    return rows, meta


# --- population summary ------------------------------------------------------
def summarize(rows, pop_name) -> dict:
    good = [r for r in rows if r.get("measured")]
    doc = {"population": pop_name, "n_boxes": len(rows),
           "n_measurable": len(good),
           "total_bars": sum(r["bars"] for r in good)}

    for rail in ("R", "S"):
        k = "r" if rail == "R" else "s"
        freq = Counter()
        for r in good:
            freq.update(r[f"{k}_state_counts"])
        doc[f"{rail}_state_bars"] = dict(freq)
        doc[f"{rail}_boxes_with_state"] = {
            st: sum(1 for r in good if r[f"{k}_state_counts"].get(st, 0) > 0)
            for st in STATE_ORDER}
        for name in ("resting", "resting_clearance", "semi", "at_rail_gap"):
            doc[f"{rail}_{name}_atr"] = dist(
                [v for r in good for v in r["_reach"][f"{rail}_{name}"]])

        runs = [x for r in good for x in r[f"_{k}_runs"]]
        doc[f"{rail}_runs"] = {
            "n_runs": len(runs),
            "len_split": dict(Counter(x["len_class"] for x in runs)),
            "dominant_split": dict(Counter(x["dominant"] for x in runs)),
            "run_len": dist([x["n_bars"] for x in runs]),
            "max_reach_atr": dist([x["max_reach_atr"] for x in runs]),
            "singular_semi_runs": sum(
                1 for x in runs
                if x["len_class"] == "singular" and x["dominant"] == "semi"),
            "boxes_with_singular_semi": sum(
                1 for r in good
                if any(x["len_class"] == "singular" and x["dominant"] == "semi"
                       for x in r[f"_{k}_runs"])),
        }
        breach = [x for x in runs if x["breaches"]]
        doc[f"{rail}_what_follows"] = {
            "n_breach_runs": len(breach),
            "outcomes": dict(Counter(x["outcome"] for x in breach)),
            "by_dominant_state": {
                st: dict(Counter(x["outcome"] for x in breach
                                 if x["dominant"] == st))
                for st in STATE_ORDER
                if any(x["dominant"] == st for x in breach)},
        }

    rest_runs = [x for r in good for x in r["_r_runs"] if x.get("has_resting")]
    doc["resting_runs_R"] = {
        "n_with_resting": len(rest_runs),
        "markup_overlapping": sum(1 for x in rest_runs if x["resting_in_markup"]),
        "true_rests": sum(1 for x in rest_runs if not x["resting_in_markup"]),
        "boxes_with_true_rest": sum(
            1 for r in good
            if any(x.get("has_resting") and not x["resting_in_markup"]
                   for x in r["_r_runs"])),
        "wave_types_all": dict(Counter(
            t for x in rest_runs for t in x["overlapping_wave_types"])),
        "wave_types_true_rests": dict(Counter(
            t for x in rest_runs if not x["resting_in_markup"]
            for t in x["overlapping_wave_types"])),
        "true_rest_reach_atr": dist([x["max_reach_atr"] for x in rest_runs
                                     if not x["resting_in_markup"]]),
        "markup_reach_atr": dist([x["max_reach_atr"] for x in rest_runs
                                  if x["resting_in_markup"]]),
    }

    tails = [(r["case"], t) for r in good for t in r["_tails"]]
    crashed = [c for c, t in tails if t["crashed_back"]]
    doc["tails"] = {
        "n_big_breach_bars": len(tails),
        "n_tail_crash": len(crashed),
        "n_big_breach_bars_wide": sum(1 for _, t in tails
                                      if t["range_atr"] >= TAIL_SPREAD_WIDE),
        "n_tail_crash_wide": sum(1 for _, t in tails
                                 if t["range_atr"] >= TAIL_SPREAD_WIDE
                                 and t["crashed_back"]),
        "boxes_with_tail_crash": sorted(set(crashed)),
    }

    doc["harshness_grid"] = {}
    for key, label in HARSH_RULES:
        counts = [r["harsh"][key] for r in good]
        row = {f">={t}": sum(1 for c in counts if c >= t) for t in HARSH_THRESHOLDS}
        row["n_boxes"] = len(counts)
        doc["harshness_grid"][label] = row
    return doc


# --- report ------------------------------------------------------------------
def _fmt(d) -> str:
    if not d:
        return "-"
    return f"n={d['n']} med={d['median']} p75={d['p75']} p90={d['p90']} max={d['max']}"


def _pct(a, b) -> str:
    return f"{a}/{b} ({100.0 * a / b:.0f}%)" if b else f"{a}/0"


def report_lines(ds, js, drawn_rows) -> list[str]:
    L: list[str] = []
    w = L.append
    pops = ((ds, "DRAWN"), (js, "JUNK-SURVIVED"))

    w(f"Tolerance = {TOL_ATR} ATR (TOUCH_TOLERANCE_ATR). Distances in ATR "
      f"(the ruled unit).")
    w("State machine (per bar, per rail): resting = whole bar beyond the rail "
      "(R: low >= R; S: high <= S); semi = straddles the rail; at_rail = "
      f"touches the area from inside (within {TOL_ATR} ATR); away otherwise.")
    w(f"Populations: drawn = {ds['n_measurable']}/{ds['n_boxes']} measurable "
      f"operator boxes ({ds['total_bars']} bars); junk-survived = "
      f"{js['n_measurable']}/{js['n_boxes']} respect-surviving framings "
      f"({js['total_bars']} bars).")
    w("")

    for s, name in pops:
        w(f"## 1. State frequencies — {name}")
        w("")
        for rail in ("R", "S"):
            tb = s["total_bars"]
            f = s[f"{rail}_state_bars"]
            bx = s[f"{rail}_boxes_with_state"]
            w(f"**{rail} rail** — bars: " + ", ".join(
                f"{st} {f.get(st, 0)} ({100.0 * f.get(st, 0) / tb:.1f}%)"
                for st in ("resting", "semi", "at_rail", "away")))
            w("  boxes containing state >=1x: " + ", ".join(
                f"{st} {_pct(bx[st], s['n_measurable'])}" for st in STATE_ORDER))
            w(f"  reach beyond rail, resting bars (ATR): "
              f"{_fmt(s[f'{rail}_resting_atr'])}")
            w(f"  whole-bar clearance beyond rail, resting bars (ATR): "
              f"{_fmt(s[f'{rail}_resting_clearance_atr'])}")
            w(f"  reach beyond rail, semi bars (ATR): {_fmt(s[f'{rail}_semi_atr'])}")
            w(f"  gap inside rail, at_rail bars (ATR): "
              f"{_fmt(s[f'{rail}_at_rail_gap_atr'])}")
            w("")

    w("## 2. Singular vs run (engaged-bar runs, any non-away state)")
    w("")
    for s, name in pops:
        for rail in ("R", "S"):
            r = s[f"{rail}_runs"]
            w(f"**{name} {rail}**: runs={r['n_runs']} len split {r['len_split']} "
              f"dominant {r['dominant_split']}")
            w(f"  run length {_fmt(r['run_len'])}; max reach ATR "
              f"{_fmt(r['max_reach_atr'])}")
            w(f"  singular SEMI runs (his forgiveness case): "
              f"{r['singular_semi_runs']} runs across "
              f"{_pct(r['boxes_with_singular_semi'], s['n_measurable'])} boxes")
            w("")

    w("## 3. The 'bigger swing upwards' exclusion (markup overlap, R rail)")
    w("")
    for s, name in pops:
        rr = s["resting_runs_R"]
        w(f"**{name}**: runs containing a resting bar: {rr['n_with_resting']}; "
          f"markup-overlapping (departure legs): {rr['markup_overlapping']}; "
          f"TRUE RESTS: {rr['true_rests']} across "
          f"{_pct(rr['boxes_with_true_rest'], s['n_measurable'])} boxes")
        w(f"  wave types overlapping ALL resting runs: {rr['wave_types_all']}")
        w(f"  wave types overlapping TRUE rests: {rr['wave_types_true_rests']}")
        w(f"  true-rest max reach ATR: {_fmt(rr['true_rest_reach_atr'])}; "
          f"markup-leg reach ATR: {_fmt(rr['markup_reach_atr'])}")
        w("")

    w(f"## 4. What-follows (context) — breaching runs, next {FOLLOW_BARS} bars")
    w("")
    w(f"Resolution rule: anchored at the run's EXTREME breach bar; first close "
      f"beyond +/-{RESOLVE_ATR} ATR of the rail wins over the next {FOLLOW_BARS} "
      "bars. R: close > R+band -> left_up; close < R-band -> back inside, "
      "sub-classified by whether any close in the horizon falls below the box "
      "MIDPOINT (crash_back_through_box) or not (resumed_consolidation); "
      "neither -> consolidating_near_rail; too few printed bars -> right_edge. "
      "S mirrored: broke_down / reclaimed_into_box / held_near_support.")
    w("")
    for s, name in pops:
        for rail in ("R", "S"):
            wf = s[f"{rail}_what_follows"]
            w(f"**{name} {rail}**: breach runs={wf['n_breach_runs']} "
              f"outcomes {wf['outcomes']}")
            for st, c in wf["by_dominant_state"].items():
                w(f"  dominant={st}: {c}")
            w("")

    w(f"## 5. Seller's-tail bars (breach bar spread >= {TAIL_SPREAD_ATR} ATR, "
      f"crash-back within {TAIL_CRASH_BARS} bars)")
    w("")
    for s, name in pops:
        t = s["tails"]
        w(f"**{name}**: big breach bars(>={TAIL_SPREAD_ATR} ATR)="
          f"{t['n_big_breach_bars']}, of which tail-crashed={t['n_tail_crash']} "
          f"across {_pct(len(t['boxes_with_tail_crash']), s['n_measurable'])} "
          f"boxes ({100.0 * t['n_tail_crash'] / s['total_bars']:.1f}% of bars); "
          f"at >={TAIL_SPREAD_WIDE} ATR: {t['n_big_breach_bars_wide']} big, "
          f"{t['n_tail_crash_wide']} crashed.")
        w(f"  boxes with a tail-crash: {t['boxes_with_tail_crash']}")
        w("")

    w("## 6. THE HARSHNESS TEST — boxes flagged per rule")
    w("")
    w("| rule (bars per box) | pop | n_boxes | >=1 bar | >=2 | >=3 | >=5 |")
    w("|---|---|---|---|---|---|---|")
    for s, name in ((ds, "drawn"), (js, "junk")):
        for label, row in s["harshness_grid"].items():
            w(f"| {label} | {name} | {row['n_boxes']} | "
              + " | ".join(str(row[f">={t}"]) for t in HARSH_THRESHOLDS) + " |")
    w("")
    w("Flag RATES at >=1 bar (drawn should be LOW if the rule is safe):")
    for label in ds["harshness_grid"]:
        w(f"- {label}: drawn "
          f"{_pct(ds['harshness_grid'][label]['>=1'], ds['n_measurable'])} vs junk "
          f"{_pct(js['harshness_grid'][label]['>=1'], js['n_measurable'])}")
    w("")

    w("## 7. Symmetry closure — R vs S, drawn population")
    w("")
    w("| measure | R (ceiling) | S (floor) |")
    w("|---|---|---|")
    tb = ds["total_bars"]
    for st in STATE_ORDER:
        rv, sv = ds["R_state_bars"].get(st, 0), ds["S_state_bars"].get(st, 0)
        w(f"| {st} bars | {rv} ({100.0 * rv / tb:.1f}%) | "
          f"{sv} ({100.0 * sv / tb:.1f}%) |")
        w(f"| boxes with {st} | {_pct(ds['R_boxes_with_state'][st], ds['n_measurable'])}"
          f" | {_pct(ds['S_boxes_with_state'][st], ds['n_measurable'])} |")
    for name, key in (("resting reach median (ATR)", "resting_atr"),
                      ("semi reach median (ATR)", "semi_atr")):
        rd, sd = ds[f"R_{key}"], ds[f"S_{key}"]
        w(f"| {name} | {rd['median'] if rd else '-'} | {sd['median'] if sd else '-'} |")
    w(f"| runs | {ds['R_runs']['n_runs']} | {ds['S_runs']['n_runs']} |")
    w(f"| run length median | {ds['R_runs']['run_len']['median']} | "
      f"{ds['S_runs']['run_len']['median']} |")
    w("")

    w("## Sanity anchors — known ceiling-rest chapters")
    w("")
    for r in drawn_rows:
        if r.get("ticker") not in ANCHOR_TICKERS or not r.get("measured"):
            continue
        w(f"- **{r['case']}** ({r['bars']} bars): R-side runs: " + ("; ".join(
            f"[{x['start']}-{x['end']}] {x['n_bars']}b dom={x['dominant']} "
            f"states={x['states']} reach={x['max_reach_atr']}ATR"
            + (" MARKUP" if x.get("resting_in_markup") else "")
            for x in r["_r_runs"]) or "none"))
    return L


def _public(box: dict) -> dict:
    """The sidecar view of a box row — working detail ('_' keys) stripped."""
    return {k: v for k, v in box.items() if not k.startswith("_")}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", metavar="PATH", help="JSON sidecar path")
    args = ap.parse_args()
    if args.json:
        # Tripwire at the door (EC-14): a mistyped sealed path must fail before
        # minutes of census work, not after.
        refuse_sealed_output(args.json)

    drawn, fingerprint = drawn_population()
    junk, meta = junk_population()
    ds = summarize(drawn, "drawn")
    js = summarize(junk, "junk_survived_respect")

    print("=" * 96)
    print("  BAR-STATE CENSUS — Resting / At / Semi, both rails, both populations")
    print("=" * 96)
    print(f"marks_fingerprint: {fingerprint[:16]}...   "
          f"engine_config_version: {manifest_hash()[:16]}...")
    print(f"junk corpus cases: {len(meta['cases'])}   "
          f"survived-respect framings: {len(junk)}   "
          f"stages: {dict(Counter(r.get('stage') for r in junk))}")
    print("")
    for line in report_lines(ds, js, drawn):
        print(line)

    if args.json:
        doc = {"populations": {"drawn": "calibration_marks(verdict=box)",
                               "junk_survived_respect":
                                   "negative_corpus strict framings past the "
                                   "respect gate"},
               "marks_fingerprint": fingerprint,
               "engine_config_version": manifest_hash(),
               "census_conventions": {
                   "TOUCH_TOLERANCE_ATR": settings.TOUCH_TOLERANCE_ATR,
                   "RESOLVE_ATR": RESOLVE_ATR,
                   "FOLLOW_BARS": FOLLOW_BARS,
                   "TAIL_CRASH_BARS": TAIL_CRASH_BARS,
                   "TAIL_SPREAD_ATR": TAIL_SPREAD_ATR,
                   "TAIL_SPREAD_WIDE": TAIL_SPREAD_WIDE,
                   "STATE_ORDER": list(STATE_ORDER),
                   "MIN_WINDOW_BARS": MIN_WINDOW_BARS,
               },
               "summary": {"drawn": ds, "junk_survived_respect": js},
               "drawn_boxes": [_public(r) for r in drawn],
               "junk_boxes": [_public(r) for r in junk]}
        refuse_sealed_output(args.json)   # re-checked at the write itself
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
