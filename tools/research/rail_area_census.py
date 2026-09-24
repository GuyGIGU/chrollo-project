"""Rail-area census — how thick is the area around a rail, and in what unit?

Read-only, offline, measure-first (no gate, no points, no engine change). This
is the committed instrument behind the two 2026-08-30 rail-area rulings in
``docs/decisions.md`` — the ±0.50-ATR symmetric area, and the ATR-not-box-
fraction unit. It reproduces the headline numbers those rows cite; the full
exploration they came from was three lanes wide and lived in a session
scratchpad (EC-16 gap, caught at the 2026-08-30 pre-merge review).

Three measurements, two populations, one archive by-product:

  1. the operator's OWN drawn rests — his ``lps``/``last_supper``/
     ``mini_consolidation`` spans measured against HIS rails on HIS window.
     Engine-independent; the strongest evidence in the run.
  2. the DISTANCE-BLIND cut — excursions beyond a rail split by DURATION only
     (poke <= 2 bars vs dwell >= 3 bars), then the best Youden-J cut on max
     distance. The split never consults distance, so the cut it produces is a
     measurement rather than a definition.
  3. the pierce comparison — per-box max pierce, drawn vs box-shaped junk.
     The negative finding: junk pierces its rails LESS than his boxes do, so
     raw distance is not a junk filter and must never become one.
  + the unit bridge from the archive: ``lps_stretch_box / lps_stretch_atr`` is
     the same numerator over two denominators, i.e. ATR per box height.

Populations: drawn = every box-verdict CalibrationMark through the ONE
validated loader (EC-13); junk = the negative corpus's strict candidate boxes
via the ``rail_margin_evidence.junk_rows`` recipe, of which the SURVIVED-
RESPECT sub-population is the fair contrast against a drawn box. Sidecar-only
(EC-46); ``--json`` passes the sealed-output guard (EC-14).

REPRODUCIBILITY NOTE — the census-local conventions below are deliberately
FROZEN; changing any of them silently re-derives the recorded evidence:
  * an EXCURSION is a maximal run of consecutive bars with ``High > R`` (or
    ``Low < S``) — strict, wick basis, no tolerance anywhere. Lens 2's
    ``DWELL_MIN_BARS = 3`` is the duration split and is distance-blind by
    construction; that is the whole point of the cut it produces.
  * ``REST_TYPES``/``GRAZE_TYPES``/``SPIKE_TYPES`` regroup the engine's OWN
    event words into three census classes. CIRCULARITY WARNING, stated
    loudly because it bounds what this lens can prove: ``upthrust`` vs
    ``rejection`` is decided by ``BOUNDARY_ATR_BUFFER`` (0.50 ATR when the
    evidence was sealed), ``measure_support_tests`` skips ``breach_S`` by the
    same buffer, and ``SOS`` vs ``markup`` by ``SOS_NEAR_R_MAX_BOX``. A
    distance split between those classes partly re-derives 0.5. Weigh the
    drawn rests and the distance-blind cut first.
  * ``_CEILING_THIRD``/``_SUPPORT_THIRD`` (0.70/0.30) bucket a drawn span by
    where its LOW sits in the box. They coincided with ``TRAVERSAL_HIGH_ZONE``
    / ``TRAVERSAL_LOW_ZONE`` when the evidence was sealed and are frozen here
    as census literals — if either knob moves, this census keeps measuring the
    sealed convention, not the live zone.
  * ``best_cut`` breaks a Youden-J tie toward the LOWEST candidate cut, and
    the candidate set is the union of the two classes' own values.
  * the junk lane's SURVIVED-RESPECT filter is "cascade stage is not
    ``respect``" — the 1,500-odd candidates that die at the respect gate are
    wildly mis-framed windows (median pierce ~6.4 ATR above R) and are
    reported but never the comparison.
  * ``_ATR_OVER_BOX`` bounds (|stretch_atr| > 0.05, ratio in 0.005..3.0)
    reject the degenerate rows of the recovered exchange rate; the population
    is one row per episode (``core.archive.episodes`` first-seen grouper).

Usage (the repo venv, from the repo root):
    python -m tools.research.rail_area_census [--json OUT.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from types import SimpleNamespace

import numpy as np

try:  # works under both `python -m tools.research.rail_area_census` and `python tools/research/rail_area_census.py`
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

_ROOT = configure_path(backend=True)

import database  # noqa: E402  binds the SQLite engine + SessionLocal
import pandas as pd  # noqa: E402

from config import settings  # noqa: E402
from core.archive.episodes import (  # noqa: E402
    SetupRow,
    build_episodes,
    canonical_ids,
)
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.events.box_events import (  # noqa: E402
    measure_resistance_events,
    measure_support_tests,
)
from engine_alpha.structure.narrative.bricks import find_spring  # noqa: E402
from engine_alpha.structure.narrative.reader import read_structure  # noqa: E402
from tools.regression import negative_corpus  # noqa: E402
from tools.calibration.calibration_harness import load_box_marks  # noqa: E402
from core.calibration.replay import (  # noqa: E402
    drawn_box_window,
    judged_window,
    prepared_frame,
    session_pos,
)
from webapp.backend import frame_store  # noqa: E402

# --- the frozen census conventions -----------------------------------------
REST_TYPES = ("SOS", "range", "test", "lps")
GRAZE_TYPES = ("rejection",)
SPIKE_TYPES = ("upthrust", "spring", "markup", "failed")
DWELL_MIN_BARS = 3              # lens 2: this long or longer is a DWELL
_CEILING_THIRD = 0.70           # a drawn span's low at/above this box position
_SUPPORT_THIRD = 0.30           # a drawn span's low at/below this box position
_REST_EVENTS = ("lps", "last_supper", "mini_consolidation")
_ATR_TICKS = (0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75, 1.0)

# The headline figures the 2026-08-30 decisions.md rail-area rows cite, frozen
# as (recorded value, tolerance). The census prints itself against them, so a
# divergence surfaces as a finding instead of quietly re-fitting the record.
_RECORDED = {
    "lens2 cut · drawn R (ATR)": (0.510, 0.001),
    "lens2 cut · drawn S (ATR)": (0.510, 0.001),
    "lens2 cut · junk-survived R (ATR)": (0.528, 0.001),
    "lens2 cut · junk-survived S (ATR)": (0.442, 0.001),
    "lens2 cut · drawn R (box)": (0.308, 0.001),
    "lens2 cut · drawn S (box)": (0.283, 0.001),
    "lens2 cut · junk-survived R (box)": (0.120, 0.001),
    "lens2 cut · junk-survived S (box)": (0.090, 0.001),
    "ceiling rests n": (22, 0),
    "ceiling rests contained at 0.50 ATR": (0.86, 0.005),
    "ceiling rests contained at 0.30 ATR": (0.64, 0.005),
    "ceiling rests sitting ABOVE R": (7, 0),
    "support rests n": (16, 0),
    "support rests contained at 0.50 ATR": (0.75, 0.005),
    "support rests sitting ABOVE S": (11, 0),
    "S:rest (test) n": (66, 0),
    "S:rest (test) contained at 0.30 ATR": (0.47, 0.005),
    "box height median · drawn (ATR)": (1.73, 0.005),
    "box height median · junk-survived (ATR)": (3.05, 0.005),
    "max pierce above R · drawn (ATR)": (1.267, 0.001),
    "max pierce above R · junk-survived (ATR)": (0.349, 0.001),
    "max pierce below S · drawn (ATR)": (1.089, 0.001),
    "max pierce below S · junk-survived (ATR)": (0.000, 0.001),
    "1 ATR in box heights · archive median": (0.403, 0.001),
    "1 ATR in box heights · archive n": (3407, 0),
}


def _r(v, nd=4):
    if v is None:
        return None
    v = float(v)
    return round(v, nd) if math.isfinite(v) else None


def dist(vals) -> dict | None:
    """n / min / p25 / median / p75 / p90 / max over the finite values."""
    v = sorted(float(x) for x in vals
               if x is not None and math.isfinite(float(x)))
    if not v:
        return None
    a = np.array(v, dtype=float)
    return {"n": len(v), "min": _r(a.min()), "p25": _r(np.percentile(a, 25)),
            "median": _r(np.median(a)), "p75": _r(np.percentile(a, 75)),
            "p90": _r(np.percentile(a, 90)), "max": _r(a.max())}


def contained(vals, tol) -> float | None:
    """Share of ``vals`` at or inside a candidate rail-area thickness."""
    v = [float(x) for x in vals if x is not None and math.isfinite(float(x))]
    return None if not v else sum(1 for x in v if x <= tol) / len(v)


def best_cut(low, high) -> dict | None:
    """Best single cut between two distributions (Youden J), with the errors
    it costs. ``low`` is expected NEAR the rail, ``high`` far from it. A tie
    resolves toward the lowest candidate cut (frozen)."""
    a = [float(x) for x in low if x is not None and math.isfinite(float(x))]
    b = [float(x) for x in high if x is not None and math.isfinite(float(x))]
    if not a or not b:
        return None
    best = None
    for t in sorted(set(a) | set(b)):
        sens = sum(1 for x in a if x <= t) / len(a)      # near-rail kept in
        spec = sum(1 for x in b if x > t) / len(b)       # far ones kept out
        j = sens + spec - 1.0
        if best is None or j > best[0]:
            best = (j, t, sens, spec)
    j, t, sens, spec = best
    return {"n_low": len(a), "n_high": len(b), "best_cut": _r(t),
            "youden_j": _r(j), "low_at_or_below_cut": _r(sens),
            "high_above_cut": _r(spec)}


# --- the core measurement ---------------------------------------------------
def _runs(mask):
    """Maximal runs of True in a bool array -> list of (start, end) inclusive."""
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


def _type_excursion(rail, a, b, r_events, s_tests, spring):
    """Type one excursion with EXISTING engine machinery only. Anchor-first:
    an event whose own anchor bar falls inside the run wins; otherwise the
    covering event with the largest zone overlap. Nothing covers it ->
    ``untyped``, recorded honestly, never invented."""
    def _ov(zs, ze):
        return max(0, min(b, int(ze)) - max(a, int(zs)) + 1)

    def _best(events):
        hit = None
        for e in events:
            ov = _ov(e["zone_start"], e["zone_end"])
            if ov > 0 and (hit is None or ov > hit[0]):
                hit = (ov, e["type"])
        return hit[1] if hit else "untyped"

    if rail == "R":
        for e in r_events:
            if a <= int(e["peak_bar"]) <= b:
                return e["type"]
        return _best(r_events)

    # S rail: the spring (breach-and-reclaim) owns its bars before a test does.
    if spring is not None and a <= spring["tip_bar"] <= b:
        return "spring"
    for e in s_tests:
        if a <= int(e["valley_bar"]) <= b:
            return e["type"]
    if spring is not None and _ov(spring["zone_start"], spring["zone_end"]) > 0:
        return "spring"
    return _best(s_tests)


def measure_box(window, R, S, atr, *, case, pop, stage=None) -> dict:
    """Every rail excursion in ONE box, in both units, typed and classified."""
    out = {"case": case, "pop": pop, "stage": stage, "errors": [],
           "excursions": []}
    box = float(R) - float(S)
    if not (box > 0) or atr is None or not math.isfinite(float(atr)) or float(atr) <= 0:
        out["errors"].append("degenerate box or ATR")
        return out
    atr = float(atr)
    highs = window["High"].to_numpy(dtype=float)
    lows = window["Low"].to_numpy(dtype=float)
    n = len(highs)
    if n < 3:
        out["errors"].append("window too short")
        return out

    above, below = highs - R, S - lows
    out["bars"] = n
    out["box_height_atr"] = _r(box / atr)
    out["max_above_r_atr"] = _r(max(0.0, float(np.nanmax(above))) / atr)
    out["max_above_r_boxfrac"] = _r(max(0.0, float(np.nanmax(above))) / box)
    out["max_below_s_atr"] = _r(max(0.0, float(np.nanmax(below))) / atr)
    out["max_below_s_boxfrac"] = _r(max(0.0, float(np.nanmax(below))) / box)

    try:
        r_events = measure_resistance_events(window, R, S, atr)
    except Exception as exc:            # noqa: BLE001 — report, never crash a population
        r_events = []
        out["errors"].append(f"r_events: {exc}")
    try:
        s_tests = measure_support_tests(window, R, S, atr)
    except Exception as exc:            # noqa: BLE001
        s_tests = []
        out["errors"].append(f"s_tests: {exc}")
    spring = None
    try:
        sp = find_spring(window, SimpleNamespace(start_bar=0, base_len=n,
                                                 R=float(R), S=float(S)), atr)
        if sp is not None:
            spring = {"tip_bar": int(sp.tip_bar), "zone_start": int(sp.tip_bar),
                      "zone_end": int(max(sp.tip_bar, sp.recovery_bar))}
    except Exception as exc:            # noqa: BLE001
        out["errors"].append(f"spring: {exc}")

    for rail, mask, raw in (("R", highs > R, above), ("S", lows < S, below)):
        for a, b in _runs(mask):
            mx = float(raw[a:b + 1].max())
            etype = _type_excursion(rail, a, b, r_events, s_tests, spring)
            out["excursions"].append({
                "rail": rail, "start": a, "end": b, "n_bars": b - a + 1,
                "max_atr": _r(mx / atr), "max_boxfrac": _r(mx / box),
                "type": etype,
                "lens1": ("rest" if etype in REST_TYPES else
                          "graze" if etype in GRAZE_TYPES else
                          "spike" if etype in SPIKE_TYPES else "other"),
                "lens2": "dwell" if (b - a + 1) >= DWELL_MIN_BARS else "poke",
            })
    out["n_excursions_r"] = sum(1 for e in out["excursions"] if e["rail"] == "R")
    out["n_excursions_s"] = sum(1 for e in out["excursions"] if e["rail"] == "S")
    return out


# --- population (a): the operator's drawn boxes -----------------------------
def drawn_population():
    """His boxes, plus the drawn REST spans measured against his own rails."""
    session = database.SessionLocal()
    try:
        marks, fingerprint = load_box_marks(session)
        rows, rests = [], []
        for mk in marks:
            case = f"{mk.ticker}@{mk.as_of_date}" + (f"[{mk.label}]" if mk.label else "")
            R, S = mk.resistance, mk.support
            if R is None or S is None or not (R > S):
                rows.append({"case": case, "pop": "drawn", "excursions": [],
                             "errors": ["no drawn rails"]})
                continue
            frozen = frame_store.load_frame(mk.ticker, mk.as_of_date,
                                            digest=mk.frame_digest)
            if frozen is None or frozen.empty:
                rows.append({"case": case, "pop": "drawn", "excursions": [],
                             "errors": ["no frozen frame for this digest"]})
                continue
            try:
                window, atr = drawn_box_window(frozen, mk.box_start_date,
                                               mk.box_end_date)
            except ValueError as exc:
                rows.append({"case": case, "pop": "drawn", "excursions": [],
                             "errors": [str(exc)]})
                continue
            R, S, box = float(R), float(S), float(R) - float(S)
            rows.append(measure_box(window, R, S, atr, case=case, pop="drawn"))

            idx = window.index
            highs = window["High"].to_numpy(dtype=float)
            lows = window["Low"].to_numpy(dtype=float)
            for ev in mk.events:
                if ev.event_type not in _REST_EVENTS:
                    continue
                try:
                    a = session_pos(idx, ev.start_date)
                    b = session_pos(idx, ev.end_date, boundary="end")
                except Exception:            # noqa: BLE001 — a date off the window
                    continue
                a, b = min(a, b), max(a, b)
                lo = float(lows[a:b + 1].min())
                pos = (lo - S) / box
                third = ("ceiling" if pos >= _CEILING_THIRD else
                         "support" if pos <= _SUPPORT_THIRD else "mid")
                rests.append({
                    "case": case, "ticker": mk.ticker, "event": ev.event_type,
                    "span": f"{ev.start_date}..{ev.end_date}",
                    "n_bars": b - a + 1, "third": third,
                    "span_low_box_pos": _r(pos, 3),
                    # signed: NEGATIVE means the rest sits ABOVE the rail
                    "low_vs_R_atr": _r((R - lo) / atr),
                    "low_vs_S_atr": _r((S - lo) / atr),
                    "span_high_above_R_atr": _r(
                        (float(highs[a:b + 1].max()) - R) / atr),
                })
        return rows, rests, fingerprint
    finally:
        session.close()


# --- population (b): the negative corpus's strict candidate boxes ------------
def junk_population():
    """Every strict candidate box the election examined on the frozen junk
    frames — the ``rail_margin_evidence.junk_rows`` recipe (rescued framings
    skipped, candidates killed before the respect gate skipped)."""
    frames, meta = negative_corpus._load_fixture()
    rows = []
    for case in meta["cases"]:
        key = case.get("key", case["ticker"])
        raw = frames.get(key)
        if raw is None or raw.empty:
            raise SystemExit(f"junk population: frame missing for {key} — "
                             "rebuild the negative fixture")
        prep = prepared_frame(raw, case["as_of"])
        if prep is None:
            raise SystemExit(f"junk population: {key} refused universe prep at "
                             "its frozen as_of — fixture basis drift")
        df, atr = prep
        trace: list = []
        read_structure(df, atr, trace=trace)
        seen = set()
        for root in trace:
            for rec in root.get("box_cascade") or []:
                if rec["rescued"] or rec["stage"] in ("width", "window"):
                    continue
                sig = (rec["R"], rec["S"], rec["cand_start"], rec["stage"])
                if sig in seen:
                    continue
                seen.add(sig)
                win = judged_window(df, int(rec["cand_start"]))
                if len(win) < 3:
                    continue
                rows.append(measure_box(
                    win, float(rec["R"]), float(rec["S"]), atr,
                    case=f"{key}#{rec['cand_start']}", pop="junk",
                    stage=rec["stage"] or "passed"))
    return rows, meta


# --- the archive by-product: the ATR <-> box-height exchange rate ------------
def exchange_rate() -> dict:
    """1 ATR, in box heights. ``lps_stretch_box / lps_stretch_atr`` is the same
    numerator over two denominators, so the ratio IS ATR / active box height.
    One row per episode; read-only, sidecar-only (EC-46)."""
    session = database.SessionLocal()
    try:
        df = pd.read_sql_query(
            "SELECT id, ticker, scan_date, setup_type, universe_type, "
            "lps_stretch_atr, lps_stretch_box FROM setup_archive",
            session.get_bind())
    finally:
        session.close()
    if df.empty:
        return {"n": 0, "note": "archive empty"}
    rows = [SetupRow(int(r.id), r.ticker, r.scan_date, r.setup_type,
                     r.universe_type or "us_equities") for r in df.itertuples()]
    keep = canonical_ids(build_episodes(rows))
    a, b = df["lps_stretch_atr"], df["lps_stretch_box"]
    k = b / a.where(a.abs() > 0.05)
    k = k.where((k > 0.005) & (k < 3.0))[df["id"].isin(keep)].dropna()
    if k.empty:
        return {"n": 0, "note": "no measurable episode rows"}
    return {"n": int(len(k)), "rows": int(len(df)),
            "episodes": int(df["id"].isin(keep).sum()),
            "median": _r(float(k.median()), 3),
            "p5": _r(float(k.quantile(0.05)), 3),
            "p25": _r(float(k.quantile(0.25)), 3),
            "p75": _r(float(k.quantile(0.75)), 3),
            "p95": _r(float(k.quantile(0.95)), 3)}


# --- summarising ------------------------------------------------------------
def _exc(rows, rail, field, pred=None):
    return [e[field] for r in rows for e in r.get("excursions", [])
            if e["rail"] == rail and (pred is None or pred(e))]


def summarize(rows, name) -> dict:
    good = [r for r in rows if r.get("bars")]
    doc = {"population": name, "n_boxes": len(rows), "n_measurable": len(good),
           "box_height_atr": dist([r["box_height_atr"] for r in good])}
    for k in ("max_above_r_atr", "max_above_r_boxfrac",
              "max_below_s_atr", "max_below_s_boxfrac"):
        doc[f"pierce_{k}"] = dist([r[k] for r in good])
    doc["cuts"] = {}
    for rail in ("R", "S"):
        for unit in ("atr", "boxfrac"):
            doc["cuts"][f"{rail}:{unit}"] = best_cut(
                _exc(good, rail, f"max_{unit}", lambda e: e["lens2"] == "poke"),
                _exc(good, rail, f"max_{unit}", lambda e: e["lens2"] == "dwell"))
    doc["grid"] = {}
    for rail in ("R", "S"):
        for lens, cls in (("lens1", "rest"), ("lens1", "graze"),
                          ("lens1", "spike"), ("lens2", "poke"),
                          ("lens2", "dwell")):
            v = [x for x in _exc(good, rail, "max_atr",
                                 lambda e, l=lens, c=cls: e[l] == c)
                 if x is not None]
            if v:
                doc["grid"][f"{rail}:{cls}"] = {
                    "n": len(v),
                    **{str(t): _r(contained(v, t), 3) for t in _ATR_TICKS}}
    return doc


def rest_cluster(rests, third) -> dict:
    """His drawn rests at one rail: the signed cluster, and how much of it a
    candidate thickness would contain. Distance is measured as |d| — the sign
    (above vs below the line) is the symmetry evidence, not a magnitude."""
    key = "low_vs_R_atr" if third == "ceiling" else "low_vs_S_atr"
    sel = [e for e in rests if e["third"] == third]
    signed = sorted(e[key] for e in sel if e[key] is not None)
    absd = [abs(x) for x in signed]
    return {"third": third, "n": len(signed),
            "n_marks": len({e["case"] for e in sel}),
            "signed_cluster": signed,
            "above_the_rail": sum(1 for x in signed if x < 0),
            "on_the_rail": sum(1 for x in signed if x == 0),
            "below_the_rail": sum(1 for x in signed if x > 0),
            "abs": dist(absd),
            "contained": {str(t): _r(contained(absd, t), 3)
                          for t in (0.3, 0.5, 0.75)}}


# --- reporting --------------------------------------------------------------
def _fmt(d):
    return ("        -" if not d else
            f"n={d['n']:>4} med={d['median']:>8.3f} p75={d['p75']:>8.3f} "
            f"p90={d['p90']:>8.3f} max={d['max']:>8.3f}")


def _cut_row(label, c):
    if not c:
        return f"    {label:34} -"
    return (f"    {label:34} cut={c['best_cut']:>7}  J={c['youden_j']:>6}  "
            f"pokes<=cut {c['low_at_or_below_cut']:>6}  dwells>cut "
            f"{c['high_above_cut']:>6}  (n {c['n_low']}/{c['n_high']})")


def print_report(drawn, junk_all, junk_survived, ceiling, support, rate):
    print("=" * 96)
    print("  RAIL-AREA CENSUS — how thick is the area around a rail, and in "
          "what unit?")
    print("=" * 96)

    print("\n1. THE OPERATOR'S OWN DRAWN RESTS (his rails, his window — "
          "engine-independent)")
    for c in (ceiling, support):
        rail = "R" if c["third"] == "ceiling" else "S"
        print(f"  {c['third']:8} rests: n={c['n']} spans over {c['n_marks']} "
              f"marks   |rest low - {rail}| {_fmt(c['abs'])}")
        print("    contained: " + "  ".join(
            f"<={t} ATR {v:.1%}" if v is not None else f"<={t} ATR -"
            for t, v in c["contained"].items()))
        print(f"    SIGN (negative = the rest sits ABOVE the rail): "
              f"{c['above_the_rail']} above / {c['on_the_rail']} exactly on / "
              f"{c['below_the_rail']} below, of {c['n']}")
        print(f"    raw cluster: {c['signed_cluster']}")

    print("\n2. THE DISTANCE-BLIND CUT (poke <=2 bars vs dwell >=3 bars; the "
          "split never sees distance)")
    for s in (drawn, junk_survived):
        for rail in ("R", "S"):
            print(_cut_row(f"{s['population']:22} {rail} · ATR",
                           s["cuts"][f"{rail}:atr"]))
    print("  ... the SAME cuts in box fractions:")
    for s in (drawn, junk_survived):
        for rail in ("R", "S"):
            print(_cut_row(f"{s['population']:22} {rail} · box",
                           s["cuts"][f"{rail}:boxfrac"]))

    print("\n3. THE UNIT TEST — which figure survives a change of box height?")
    for s in (drawn, junk_survived):
        print(f"    {s['population']:22} box height {_fmt(s['box_height_atr'])}")
    atr_cuts = [s["cuts"][f"{r}:atr"]["best_cut"] for s in (drawn, junk_survived)
                for r in ("R", "S") if s["cuts"][f"{r}:atr"]]
    box_cuts = [s["cuts"][f"{r}:boxfrac"]["best_cut"] for s in (drawn, junk_survived)
                for r in ("R", "S") if s["cuts"][f"{r}:boxfrac"]]
    hb = [s["box_height_atr"]["median"] for s in (drawn, junk_survived)
          if s["box_height_atr"]]
    if len(hb) == 2 and atr_cuts and box_cuts:
        print(f"    box-height ratio between the populations: "
              f"{max(hb) / min(hb):.2f}x")
        print(f"    ATR cuts {min(atr_cuts)}..{max(atr_cuts)}  -> spread "
              f"{max(atr_cuts) / min(atr_cuts):.2f}x")
        print(f"    box cuts {min(box_cuts)}..{max(box_cuts)}  -> spread "
              f"{max(box_cuts) / min(box_cuts):.2f}x")

    print("\n4. DECISION GRID — share of each class CONTAINED at each candidate "
          "thickness (ATR)")
    for s in (drawn, junk_survived):
        print(f"  {s['population']}")
        print("    " + f"{'class':14}{'n':>5}" + "".join(f"{t:>8}" for t in _ATR_TICKS))
        for k, row in s["grid"].items():
            print("    " + f"{k:14}{row['n']:>5}"
                  + "".join(f"{row[str(t)]:>8}" for t in _ATR_TICKS))

    print("\n5. PER-BOX MAX PIERCE — the negative finding (distance runs the "
          "WRONG way)")
    print(f"    {'measure':28}" + "".join(f"{s['population']:>24}"
                                          for s in (drawn, junk_survived, junk_all)))
    for k, lbl in (("pierce_max_above_r_atr", "max above R, ATR"),
                   ("pierce_max_above_r_boxfrac", "max above R, box"),
                   ("pierce_max_below_s_atr", "max below S, ATR"),
                   ("pierce_max_below_s_boxfrac", "max below S, box"),
                   ("box_height_atr", "box height, ATR")):
        print(f"    {lbl:28}" + "".join(
            f"{(s[k]['median'] if s[k] else float('nan')):>24.3f}"
            for s in (drawn, junk_survived, junk_all)))
    print("    (the 'junk ALL' column is a framing artifact — 94% of those "
          "candidates die at the\n     respect gate on windows whose rails are "
          "nowhere near the price action. Never quote it.)")

    print("\n6. THE UNIT BRIDGE — 1 ATR, in box heights (archive by-product)")
    if rate.get("n"):
        print(f"    n={rate['n']} episode rows of {rate['episodes']} episodes "
              f"({rate['rows']} raw)   median {rate['median']}   "
              f"p5 {rate['p5']}  p25 {rate['p25']}  p75 {rate['p75']}  "
              f"p95 {rate['p95']}")
        print(f"    so +-0.50 ATR ~ +-{0.5 * rate['median']:.3f} box heights at "
              f"the median, {0.5 * rate['p5']:.3f}..{0.5 * rate['p95']:.3f} "
              "across p5-p95")
    else:
        print(f"    - ({rate.get('note', 'unavailable')})")


def check_recorded(drawn, junk_survived, ceiling, support, rate) -> list[dict]:
    """Every headline the 2026-08-30 rulings cite, recomputed and compared."""
    got = {
        "ceiling rests n": ceiling["n"],
        "ceiling rests contained at 0.50 ATR": ceiling["contained"]["0.5"],
        "ceiling rests contained at 0.30 ATR": ceiling["contained"]["0.3"],
        "ceiling rests sitting ABOVE R": ceiling["above_the_rail"],
        "support rests n": support["n"],
        "support rests contained at 0.50 ATR": support["contained"]["0.5"],
        "support rests sitting ABOVE S": support["above_the_rail"],
        "S:rest (test) n": drawn["grid"].get("S:rest", {}).get("n"),
        "S:rest (test) contained at 0.30 ATR":
            drawn["grid"].get("S:rest", {}).get("0.3"),
        "box height median · drawn (ATR)": drawn["box_height_atr"]["median"],
        "box height median · junk-survived (ATR)":
            junk_survived["box_height_atr"]["median"],
        "1 ATR in box heights · archive median": rate.get("median"),
        "1 ATR in box heights · archive n": rate.get("n"),
    }
    for s, tag in ((drawn, "drawn"), (junk_survived, "junk-survived")):
        for rail in ("R", "S"):
            for unit, ulbl in (("atr", "ATR"), ("boxfrac", "box")):
                c = s["cuts"][f"{rail}:{unit}"]
                got[f"lens2 cut · {tag} {rail} ({ulbl})"] = c and c["best_cut"]
        for side, key in (("above R", "pierce_max_above_r_atr"),
                          ("below S", "pierce_max_below_s_atr")):
            got[f"max pierce {side} · {tag} (ATR)"] = (
                s[key]["median"] if s[key] else None)
    out = []
    for label, (recorded, tol) in _RECORDED.items():
        v = got.get(label)
        ok = v is not None and abs(float(v) - float(recorded)) <= tol
        out.append({"measure": label, "recorded": recorded, "reproduced": v,
                    "agrees": bool(ok)})
    return out


def print_check(rows):
    print("\n" + "=" * 96)
    print("  RECORDED (decisions.md 2026-08-30) vs REPRODUCED")
    print("=" * 96)
    print(f"    {'measure':44}{'recorded':>12}{'reproduced':>13}   verdict")
    for r in rows:
        v = "-" if r["reproduced"] is None else f"{float(r['reproduced']):.3f}"
        print(f"    {r['measure']:44}{float(r['recorded']):>12.3f}{v:>13}   "
              + ("ok" if r["agrees"] else "DIVERGES"))
    bad = [r for r in rows if not r["agrees"]]
    print(f"\n    {len(rows) - len(bad)}/{len(rows)} headline figures reproduce"
          + ("" if not bad else "; DIVERGING: "
             + ", ".join(r["measure"] for r in bad)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", metavar="PATH", help="JSON sidecar path")
    args = ap.parse_args()
    if args.json:
        # Tripwire at the door (EC-14): a mistyped sealed path must fail before
        # minutes of census work, not after.
        refuse_sealed_output(args.json)

    d_rows, rests, fingerprint = drawn_population()
    j_rows, meta = junk_population()
    j_survived = [r for r in j_rows if r.get("stage") != "respect"]
    drawn = summarize(d_rows, "drawn (his marks)")
    junk_all = summarize(j_rows, "junk ALL")
    junk_survived = summarize(j_survived, "junk survived-respect")
    ceiling = rest_cluster(rests, "ceiling")
    support = rest_cluster(rests, "support")
    rate = exchange_rate()

    print(f"population: calibration marks (all box marks) + negative corpus "
          f"({len(meta['cases'])} frozen cases)")
    print(f"marks_fingerprint: {fingerprint[:16]}...   "
          f"engine_config_version: {manifest_hash()[:16]}...")
    print(f"incumbents: TOUCH_TOLERANCE_ATR={settings.TOUCH_TOLERANCE_ATR}  "
          f"BOUNDARY_ATR_BUFFER={settings.BOUNDARY_ATR_BUFFER}  "
          f"LPS_CEILING_REST_MAX_BELOW_R_ATR="
          f"{settings.LPS_CEILING_REST_MAX_BELOW_R_ATR}")
    print_report(drawn, junk_all, junk_survived, ceiling, support, rate)
    checks = check_recorded(drawn, junk_survived, ceiling, support, rate)
    print_check(checks)

    if args.json:
        doc = {"population": "calibration_marks + negative_corpus",
               "marks_fingerprint": fingerprint,
               "engine_config_version": manifest_hash(),
               "junk_cases": [c.get("key", c["ticker"]) for c in meta["cases"]],
               "settings": {
                   "TOUCH_TOLERANCE_ATR": settings.TOUCH_TOLERANCE_ATR,
                   "BOUNDARY_ATR_BUFFER": settings.BOUNDARY_ATR_BUFFER,
                   "SOS_NEAR_R_MAX_BOX": settings.SOS_NEAR_R_MAX_BOX,
                   "LPS_CEILING_REST_MAX_BELOW_R_ATR":
                       settings.LPS_CEILING_REST_MAX_BELOW_R_ATR,
               },
               "conventions": {"REST_TYPES": REST_TYPES,
                               "GRAZE_TYPES": GRAZE_TYPES,
                               "SPIKE_TYPES": SPIKE_TYPES,
                               "DWELL_MIN_BARS": DWELL_MIN_BARS,
                               "CEILING_THIRD": _CEILING_THIRD,
                               "SUPPORT_THIRD": _SUPPORT_THIRD},
               "drawn": drawn, "junk_all": junk_all,
               "junk_survived": junk_survived,
               "drawn_rests": {"ceiling": ceiling, "support": support,
                               "spans": rests},
               "exchange_rate": rate,
               "recorded_vs_reproduced": checks,
               # per-box detail for the two populations a reader can check by
               # eye: his 35 marks in full, and the 98 box-shaped junk
               # framings without their excursion lists. The 1,500-odd
               # respect-stage candidates ride the summaries only — they are
               # never the comparison, and they are 4 MB of them.
               "boxes": {"drawn": d_rows,
                         "junk_survived": [
                             {k: v for k, v in r.items() if k != "excursions"}
                             for r in j_survived]}}
        refuse_sealed_output(args.json)  # re-checked at the write itself
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, default=str)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
