"""Rail margin evidence — count distributions for the Rail Program campaign.

Task 2 of PLAN-rail-program.md, governed by docs/rail_program_protocol_2026-07.md
(the sealed pre-registration: grids, accept conditions, verdict templates).

Computes each worked-equilibrium gate's OWN statistic — as INTEGER BAR COUNTS,
not rates (at these window lengths every quoted margin is worth less than one
bar) — over three populations:

  (a) drawn    — all 33 Guided List boxes at the operator's exact rails/window
  (b) elected  — the 26 ratchet hits' elected boxes at their pinned first-fire
  (c) junk     — every strict candidate the election examined on the 18
                 negative-corpus frames (margin blast-radius: how close junk
                 sits to each floor)

All measurement goes through the gate's own helpers (`_is_boundary_respected`,
`_validate_base_quality`) on the same windows the election judges — never a
re-implementation. Junk candidate windows come from the election's own
box_cascade trace; the recomputed respect share is self-checked against the
number embedded in each respect-stage trace detail, and a mismatch VOIDS the
run (window semantics drift, not a shrug). Rescued framings are judged on
trimmed windows the trace does not carry, so they are skipped and counted.

Read-only instrument: no election behavior, no engine writes, no baselines
touched. Leg-level admission reported here is NOT a fire prediction — other
gates still stand; Task 3's flag-ON A/B is the only fire evidence.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.rail_margin_evidence            # print the evidence report
    python -m tools.rail_margin_evidence --json OUT # also dump rows to JSON
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics

import pandas as pd

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from repo root
    from _bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path(backend=True)

from config import settings  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.box_gates import (  # noqa: E402
    _is_boundary_respected,
    _validate_base_quality,
)
from engine_alpha.structure.narrative import read_structure  # noqa: E402
from tools import negative_corpus  # noqa: E402
from tools.marks_corpus import load_corpus, setup_key  # noqa: E402
from tools.replay import (  # noqa: E402
    MARK_ATR_OFFSET,
    enrich_marked_frame,
    fixture_frame,
    load_sealed_fixture,
    prepared_frame,
    session_pos,
)

# The pre-registered grids (docs/rail_program_protocol_2026-07.md §2). Sealed:
# these tuples mirror the protocol document and are never grown here.
DWELL_GRID = (0.125, 0.10)
MID_GRID = (0.50, 0.55)
RESPECT_GRID = (0.75,)

_EPS = 1e-9
_RESPECT_DETAIL = re.compile(r"respect (\d\.\d+) <")


# --- count math: the gate's fraction thresholds as integer bars -------------
def dwell_needed(floor_frac: float, n: int) -> int:
    """closes required in a third: dwell >= floor  <=>  count >= ceil(floor*n)."""
    return math.ceil(floor_frac * n - _EPS)


def mid_allowed(cap_frac: float, n: int) -> int:
    """closes allowed in the middle third: dwell <= cap <=> count <= floor(cap*n)."""
    return math.floor(cap_frac * n + _EPS)


def outside_allowed(rate: float, n: int) -> int:
    """outside bars allowed: 1 - outside/n >= rate <=> outside <= floor((1-rate)*n)."""
    return math.floor((1.0 - rate) * n + _EPS)


def tolerance_allowed(rate: float, n: int) -> int:
    """Protocol L3b: the documented rate plus grace for exactly one bar."""
    return outside_allowed(rate, n) + 1


def frac_count(frac: float, n: int) -> int:
    """Recover the integer numerator from a fraction the gate rounded to 4dp."""
    return int(round(frac * n))


# --- one window through the gate's own helpers ------------------------------
def gate_stats(base_df: pd.DataFrame, R: float, S: float, atr: float) -> dict:
    highs = base_df["High"].to_numpy(dtype=float)
    lows = base_df["Low"].to_numpy(dtype=float)
    _, _, _, total_outside, share = _is_boundary_respected(highs, lows, R, S, atr)
    _, _, eq, _ = _validate_base_quality(base_df, R, S, atr)
    n = len(base_df)
    row = {"n": n, "outside": int(total_outside), "respect": round(float(share), 4),
           "low": None, "mid": None, "up": None}
    if isinstance(eq, dict):  # None = crash filter tripped; dwell not measured
        row["low"] = frac_count(eq["lower_dwell"], n)
        row["mid"] = frac_count(eq["mid_dwell"], n)
        row["up"] = frac_count(eq["upper_dwell"], n)
    return row


def dwell_margin(row: dict, floor_frac: float) -> int | None:
    """Signed bars of headroom on the BINDING half-dwell (lower AND upper)."""
    if row["low"] is None:
        return None
    need = dwell_needed(floor_frac, row["n"])
    return min(row["low"] - need, row["up"] - need)


def mid_margin(row: dict, cap_frac: float) -> int | None:
    if row["mid"] is None:
        return None
    return mid_allowed(cap_frac, row["n"]) - row["mid"]


def respect_margin(row: dict, rate: float, *, tolerance: bool = False) -> int:
    allowed = tolerance_allowed(rate, row["n"]) if tolerance \
        else outside_allowed(rate, row["n"])
    return allowed - row["outside"]


# --- population (a): the operator's drawn boxes -----------------------------
def drawn_rows(setups: list[dict], frames: dict) -> tuple[list[dict], str]:
    import database  # lazy: binds the live SQLite engine
    from tools.calibration_harness import load_box_marks

    session = database.SessionLocal()
    try:
        marks, fingerprint = load_box_marks(session)
    finally:
        session.close()
    by_key = {(m.ticker, str(m.as_of_date)): m for m in marks}

    rows = []
    for s in setups:
        key = setup_key(s)
        mark = by_key.get((s["ticker"], s["as_of"]))
        if mark is None or not mark.box_start_date or not mark.box_end_date:
            raise SystemExit(f"drawn population: no DB box span for {key} — the "
                             "drawn window lives in the calibration DB; refusing "
                             "a partial population")
        raw = fixture_frame(frames, key)
        if raw is None or raw.empty:
            raise SystemExit(f"drawn population: no sealed fixture frame for {key}")
        frozen = enrich_marked_frame(raw)
        end = session_pos(frozen.index, mark.box_end_date, boundary="end")
        df = frozen.iloc[: end + 1]
        atr_val = df["ATR_10"].iloc[-MARK_ATR_OFFSET]
        if pd.isna(atr_val) or float(atr_val) <= 0:
            raise SystemExit(f"drawn population: ATR unavailable at box_end for {key}")
        bs = session_pos(df.index, mark.box_start_date)
        R = float(s["rails_drawn"]["R"])
        S = float(s["rails_drawn"]["S"])
        row = gate_stats(df.iloc[bs:], R, S, float(atr_val))
        row.update({"case": key, "pop": "drawn"})
        rows.append(row)
    return rows, fingerprint


def judged_window(df: pd.DataFrame, cand_start: int) -> pd.DataFrame:
    """The exact window the pair election judged a strict candidate on:
    ``validate_equilibrium`` enumerates over ``df.iloc[:-STRUCTURE_EDGE_SKIP_BARS]``
    (the box as of ~5 bars ago, uncontaminated by the live edge), so a
    candidate's window is cand_start .. len(df) - skip — NOT the frame end.
    The junk self-check against the trace's own detail numbers certifies this
    slice; a drift there voids the run."""
    skip = settings.STRUCTURE_EDGE_SKIP_BARS
    end = len(df) - skip if len(df) > skip else len(df)
    return df.iloc[cand_start:end]


# --- population (b): the ratchet hits' elected boxes ------------------------
def elected_rows(baseline: dict, frames: dict) -> list[dict]:
    rows = []
    for entry in baseline["setups"]:
        if entry["status"] != "hit":
            continue
        key = entry["key"]
        raw = fixture_frame(frames, key)
        if raw is None or raw.empty:
            raise SystemExit(f"elected population: no sealed fixture frame for {key}")
        prep = prepared_frame(raw, entry["first_fire"])
        if prep is None:
            raise SystemExit(f"elected population: {key} refuses universe prep at "
                             f"its pinned first_fire {entry['first_fire']}")
        df, atr = prep
        trace: list = []
        structure = read_structure(df, atr, trace=trace)
        if structure is None:
            raise SystemExit(f"elected population: {key} does not elect at its "
                             f"pinned first_fire {entry['first_fire']} — baseline "
                             "drift; re-run the ratchet before trusting evidence")
        elected = [rec for root in trace for rec in root.get("box_cascade") or []
                   if rec["verdict"] == "elected"]
        if not elected:
            raise SystemExit(f"elected population: {key} elected a box but the "
                             "cascade carries no elected record — trace contract "
                             "drift")
        rec = elected[-1]
        row = gate_stats(judged_window(df, int(rec["cand_start"])),
                         float(rec["R"]), float(rec["S"]), atr)
        row.update({"case": key, "pop": "elected"})
        rows.append(row)
    return rows


# --- population (a'): the engine's examined candidate at the drawn rails ----
def examined_rows(baseline: dict, setups: list[dict], frames: dict) -> list[dict]:
    """For each ratchet MISS, the strict candidate the election examined
    NEAREST the operator's drawn rails at as_of — the campaign's converting
    statistic: a margin lever converts a miss by making THIS candidate pass,
    so separation is judged on ITS values, not the drawn-window measure
    (the two windows end differently; see judged_window)."""
    by_key = {setup_key(s): s for s in setups}
    rows = []
    for entry in baseline["setups"]:
        if entry["status"] != "miss":
            continue
        key = entry["key"]
        s = by_key[key]
        raw = fixture_frame(frames, key)
        if raw is None or raw.empty:
            raise SystemExit(f"examined population: no sealed fixture frame for {key}")
        prep = prepared_frame(raw, s["as_of"])
        if prep is None:
            print(f"  (examined: {key} refuses universe prep at as_of — "
                  "no candidate to measure; universe-gate miss)")
            continue
        df, atr = prep
        trace: list = []
        read_structure(df, atr, trace=trace)
        R_d = float(s["rails_drawn"]["R"])
        S_d = float(s["rails_drawn"]["S"])
        bh = R_d - S_d
        best = None
        for root in trace:
            for rec in root.get("box_cascade") or []:
                if rec["rescued"]:
                    continue
                miss_bh = max(abs(rec["R"] - R_d), abs(rec["S"] - S_d)) / bh
                if best is None or miss_bh < best[0]:
                    best = (miss_bh, rec)
        if best is None:
            print(f"  (examined: {key} — no strict candidate in the cascade)")
            continue
        miss_bh, rec = best
        window = judged_window(df, int(rec["cand_start"]))
        if len(window) < 2:
            continue
        row = gate_stats(window, float(rec["R"]), float(rec["S"]), atr)
        row.update({"case": key, "pop": "examined",
                    "stage": rec["stage"] or "passed",
                    "miss_bh": round(float(miss_bh), 3)})
        rows.append(row)
    return rows


# --- population (c): every strict candidate on the junk frames --------------
def junk_rows() -> tuple[list[dict], dict, int, int]:
    frames, meta = negative_corpus._load_fixture()
    rows: list[dict] = []
    checked = 0
    rescued_skipped = 0
    mismatches: list[str] = []
    for case in meta["cases"]:
        key = case.get("key", case["ticker"])
        raw = frames.get(key)
        if raw is None or raw.empty:
            raise SystemExit(f"junk population: frame missing for {key} — rebuild "
                             "the negative fixture")
        prep = prepared_frame(raw, case["as_of"])
        if prep is None:
            raise SystemExit(f"junk population: {key} refused universe prep at its "
                             "frozen as_of — fixture basis drift")
        df, atr = prep
        trace: list = []
        read_structure(df, atr, trace=trace)
        seen = set()
        for root in trace:
            for rec in root.get("box_cascade") or []:
                if rec["rescued"]:
                    rescued_skipped += 1
                    continue
                stage = rec["stage"]
                if stage in ("width", "window"):
                    continue  # killed before the respect gate — out of scope
                sig = (rec["R"], rec["S"], rec["cand_start"], stage)
                if sig in seen:
                    continue
                seen.add(sig)
                window = judged_window(df, rec["cand_start"])
                if len(window) < 2:
                    continue
                row = gate_stats(window, rec["R"], rec["S"], atr)
                if stage == "respect":
                    m = _RESPECT_DETAIL.search(rec.get("detail") or "")
                    if m:
                        checked += 1
                        if abs(row["respect"] - float(m.group(1))) > 0.0051:
                            mismatches.append(
                                f"{key}: trace says {m.group(1)}, recomputed "
                                f"{row['respect']:.4f} on df[{rec['cand_start']}:]")
                row.update({"case": key, "pop": "junk", "label": case["label"],
                            "stage": stage or "passed",
                            "reached_occupancy": stage != "respect"})
                rows.append(row)
    if mismatches:
        for line in mismatches:
            print(f"SELF-CHECK MISMATCH: {line}")
        raise SystemExit("junk population: recomputed respect does not match the "
                         "election's own trace — candidate-window semantics have "
                         "drifted; this evidence is VOID until the instrument is "
                         "realigned")
    if checked == 0:
        raise SystemExit("junk population: zero respect-stage candidates to "
                         "self-check against — cannot certify window semantics")
    return rows, meta, checked, rescued_skipped


# --- report -----------------------------------------------------------------
def _fmt_margin(v) -> str:
    if v is None:
        return "-"
    return f"{v:+d}"


def print_marks_table(rows: list[dict]) -> None:
    f = settings.EQ_MIN_HALF_DWELL
    c = settings.EQ_MAX_MID_DWELL
    r = settings.MIN_BOUNDARY_RESPECT_PCT
    print(f"\n== marks: the gate's statistics in bars (floors at baseline "
          f"dwell>={f} mid<={c} respect>={r}) ==")
    hdr = (f"{'case':18} {'pop':8} {'n':>4} {'low':>4} {'need':>4} {'dLow':>5} "
           f"{'mid':>4} {'alw':>4} {'dMid':>5} {'up':>4} {'dUp':>5} "
           f"{'out':>4} {'alw':>4} {'dOut':>5}")
    print(hdr)
    print("-" * len(hdr))
    for row in rows:
        n = row["n"]
        need = dwell_needed(f, n)
        alw_mid = mid_allowed(c, n)
        alw_out = outside_allowed(r, n)
        low = row["low"]
        d_low = _fmt_margin(None if low is None else low - need)
        d_mid = _fmt_margin(None if row["mid"] is None else alw_mid - row["mid"])
        d_up = _fmt_margin(None if row["up"] is None else row["up"] - need)
        print(f"{row['case']:18} {row['pop']:8} {n:>4} "
              f"{'-' if low is None else low:>4} {need:>4} {d_low:>5} "
              f"{'-' if row['mid'] is None else row['mid']:>4} {alw_mid:>4} {d_mid:>5} "
              f"{'-' if row['up'] is None else row['up']:>4} {d_up:>5} "
              f"{row['outside']:>4} {alw_out:>4} "
              f"{_fmt_margin(alw_out - row['outside']):>5}")


def _junk_lever_line(case_rows: list[dict], margin_fn, grid_margins) -> dict:
    """Aggregate one junk case for one lever: candidates failing the leg at
    baseline, how many newly pass at each grid value, nearest-failing margin."""
    margins = [(margin_fn(row), row) for row in case_rows]
    margins = [(m, row) for m, row in margins if m is not None]
    fail_base = [(m, row) for m, row in margins if m < 0]
    out = {"cands": len(margins),
           "pass_base": len(margins) - len(fail_base),
           "nearest": max((m for m, _ in fail_base), default=None)}
    for label, g_fn in grid_margins:
        newly = [row for m, row in fail_base if (g := g_fn(row)) is not None and g >= 0]
        out[label] = len(newly)
    return out


def print_junk_tables(jrows: list[dict]) -> None:
    cases: dict[str, list[dict]] = {}
    for row in jrows:
        cases.setdefault(f"{row['case']} ({row['label']})", []).append(row)

    f = settings.EQ_MIN_HALF_DWELL
    c = settings.EQ_MAX_MID_DWELL
    r = settings.MIN_BOUNDARY_RESPECT_PCT

    print(f"\n== junk, L1 half-dwell leg (baseline floor {f}; candidates that "
          "passed respect) ==")
    print("  'newly@X' = candidates whose BINDING half-dwell count newly passes the "
          "leg at floor X\n  (leg admission only — every other gate still stands)")
    hdr = (f"{'junk case':44} {'cands':>5} {'pass':>5} {'near':>5} "
           + " ".join(f"{'newly@' + str(g):>10}" for g in DWELL_GRID))
    print(hdr)
    print("-" * len(hdr))
    for name, case_rows in cases.items():
        occ = [row for row in case_rows if row["reached_occupancy"]]
        agg = _junk_lever_line(
            occ, lambda row: dwell_margin(row, f),
            [(f"@{g}", lambda row, g=g: dwell_margin(row, g)) for g in DWELL_GRID])
        cells = " ".join(f"{agg['@' + str(g)]:>10}" for g in DWELL_GRID)
        print(f"{name:44} {agg['cands']:>5} {agg['pass_base']:>5} "
              f"{_fmt_margin(agg['nearest']):>5} {cells}")

    print(f"\n== junk, L2 mid-churn leg (baseline cap {c}) ==")
    hdr = (f"{'junk case':44} {'cands':>5} {'pass':>5} {'near':>5} "
           + " ".join(f"{'newly@' + str(g):>10}" for g in MID_GRID))
    print(hdr)
    print("-" * len(hdr))
    for name, case_rows in cases.items():
        occ = [row for row in case_rows if row["reached_occupancy"]]
        agg = _junk_lever_line(
            occ, lambda row: mid_margin(row, c),
            [(f"@{g}", lambda row, g=g: mid_margin(row, g)) for g in MID_GRID])
        cells = " ".join(f"{agg['@' + str(g)]:>10}" for g in MID_GRID)
        print(f"{name:44} {agg['cands']:>5} {agg['pass_base']:>5} "
              f"{_fmt_margin(agg['nearest']):>5} {cells}")

    print(f"\n== junk, L3 respect leg (baseline rate {r}; all candidates that "
          "reached respect) ==")
    print("  'tol' = protocol L3b one-bar tolerance at the baseline rate "
          "(n-dependent loosening:\n  worth ~5 respect points on a 20-bar window, "
          "~1.7 on a 60-bar window)")
    grid = [(f"@{g}", lambda row, g=g: respect_margin(row, g)) for g in RESPECT_GRID]
    grid.append(("tol", lambda row: respect_margin(row, r, tolerance=True)))
    hdr = (f"{'junk case':44} {'cands':>5} {'pass':>5} {'near':>5} "
           + " ".join(f"{'newly' + lbl:>10}" for lbl, _ in grid))
    print(hdr)
    print("-" * len(hdr))
    for name, case_rows in cases.items():
        agg = _junk_lever_line(case_rows, lambda row: respect_margin(row, r), grid)
        cells = " ".join(f"{agg[lbl]:>10}" for lbl, _ in grid)
        print(f"{name:44} {agg['cands']:>5} {agg['pass_base']:>5} "
              f"{_fmt_margin(agg['nearest']):>5} {cells}")


def print_separation(mrows: list[dict], jrows: list[dict]) -> None:
    """Protocol §4D raw material: converting marks vs the junk band, per lever
    and grid value, on the moved statistic. The converting-mark values are the
    ENGINE's examined candidates at the drawn rails (pop 'examined') — the
    statistic a lever must actually flip."""
    print("\n== separation view (protocol §4D): converting marks (engine-examined "
          "candidate) vs nearest junk ==")
    drawn = {row["case"]: row for row in mrows if row["pop"] == "examined"}
    occ_junk = [row for row in jrows if row["reached_occupancy"]]

    def top_junk(margin_fn, k=3):
        scored = [(margin_fn(row), row) for row in occ_junk]
        scored = [(m, row) for m, row in scored if m is not None and m < 0]
        return sorted(scored, key=lambda t: -t[0])[:k]

    for g in DWELL_GRID:
        print(f"\nL1 dwell floor @ {g}:")
        for key in ("EGBN:2026-01-15", "YPF:2026-05-18"):
            row = drawn.get(key)
            if row is None or row["low"] is None:
                continue
            need = dwell_needed(g, row["n"])
            print(f"  mark {key}: low {row['low']}/{row['n']} needs {need} "
                  f"(margin {_fmt_margin(dwell_margin(row, g))})")
        for m, row in top_junk(lambda row, g=g: dwell_margin(row, g)):
            print(f"  junk {row['case']:6} ({row['label']}): binding "
                  f"{min(row['low'], row['up'])}/{row['n']} margin {_fmt_margin(m)}")
    for g in MID_GRID:
        print(f"\nL2 mid cap @ {g}:")
        row = drawn.get("YPF:2026-05-18")
        if row is not None and row["mid"] is not None:
            print(f"  mark YPF:2026-05-18: mid {row['mid']}/{row['n']} allowed "
                  f"{mid_allowed(g, row['n'])} (margin {_fmt_margin(mid_margin(row, g))})")
        for m, row in top_junk(lambda row, g=g: mid_margin(row, g)):
            print(f"  junk {row['case']:6} ({row['label']}): mid {row['mid']}/{row['n']} "
                  f"margin {_fmt_margin(m)}")

    all_junk = jrows
    def top_junk_respect(margin_fn, k=3):
        scored = [(margin_fn(row), row) for row in all_junk]
        scored = [(m, row) for m, row in scored if m < 0]
        return sorted(scored, key=lambda t: -t[0])[:k]

    for label, fn in ([(f"L3a respect rate @ {g}",
                        lambda row, g=g: respect_margin(row, g))
                       for g in RESPECT_GRID]
                      + [("L3b one-bar tolerance @ baseline rate",
                          lambda row: respect_margin(
                              row, settings.MIN_BOUNDARY_RESPECT_PCT,
                              tolerance=True))]):
        print(f"\n{label}:")
        row = drawn.get("PKE:2026-02-24")
        if row is not None:
            print(f"  mark PKE:2026-02-24: outside {row['outside']}/{row['n']} "
                  f"(margin {_fmt_margin(fn(row))})")
        for m, row in top_junk_respect(fn):
            print(f"  junk {row['case']:6} ({row['label']}): outside "
                  f"{row['outside']}/{row['n']} margin {_fmt_margin(m)}")


def print_fleet() -> None:
    """Archived live-fleet eq_* evidence, cohorted by engine_config_version.
    NULL = not measured (EC-2), never zero. Fractions only — the archive does
    not carry the judged window length, so counts live in the case tables."""
    import database

    cols = ["eq_respect_frac", "eq_close_lower_dwell", "eq_close_mid_dwell",
            "eq_close_upper_dwell"]
    session = database.SessionLocal()
    try:
        df = pd.read_sql_query(
            "SELECT engine_config_version, " + ", ".join(cols)
            + " FROM setup_archive", session.get_bind())
    finally:
        session.close()
    print(f"\n== archive fleet evidence (n={len(df)} rows; cohort = "
          "engine_config_version; NULL = not measured) ==")
    if df.empty:
        print("  (archive empty)")
        return
    cohort = df["engine_config_version"].where(
        df["engine_config_version"].notna(), "(pre-manifest)")
    for name, grp in df.groupby(cohort.str.slice(0, 12)):
        print(f"  cohort {name}…  rows={len(grp)}")
        for col in cols:
            vals = grp[col][grp[col].notna()].astype(float)
            if not len(vals):
                print(f"    {col:24} n=0 (not measured in this cohort)")
                continue
            print(f"    {col:24} n={len(vals):<5} median={statistics.median(vals):.3f} "
                  f"min={min(vals):.3f} max={max(vals):.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", metavar="PATH", help="dump all rows to JSON")
    args = ap.parse_args()
    if args.json:
        refuse_sealed_output(args.json)

    frames, baseline = load_sealed_fixture()
    setups = load_corpus()

    print("=" * 78)
    print("  RAIL MARGIN EVIDENCE — three populations, counts not rates")
    print("=" * 78)
    print("protocol: docs/rail_program_protocol_2026-07.md (sealed grids: "
          f"dwell {DWELL_GRID}, mid {MID_GRID}, respect {RESPECT_GRID} + one-bar tolerance)")

    d_rows, db_fingerprint = drawn_rows(setups, frames)
    x_rows = examined_rows(baseline, setups, frames)
    e_rows = elected_rows(baseline, frames)
    j_rows, jmeta, checked, rescued_skipped = junk_rows()

    print(f"population drawn:   guided-list, {len(d_rows)} boxes "
          f"(corpus fingerprint {baseline['marks_fingerprint'][:16]}…)")
    print(f"population elected: ratchet hits, {len(e_rows)} boxes at pinned first-fire")
    print(f"population junk:    negative corpus, {len(jmeta['cases'])} cases, "
          f"{len(j_rows)} strict candidates ({rescued_skipped} rescued framings "
          f"skipped — trimmed windows the trace does not carry)")
    print(f"self-check: {checked} respect-stage candidates recomputed == trace detail")
    print(f"engine_config_version now: {manifest_hash()[:16]}…   "
          f"(baseline sealed at {baseline['engine_config_version'][:16]}…)")
    if db_fingerprint != baseline["marks_fingerprint"]:
        print("NOTE: live calibration-DB fingerprint differs from the sealed corpus "
              "fingerprint — drawn windows read from the DB; rails/identity from the "
              "sealed corpus (EC-9: the sealed set is what is scored)")

    print_marks_table(d_rows + x_rows + e_rows)
    if x_rows:
        print("\n  examined = the engine's nearest strict candidate to the drawn "
              "rails at as_of (the converting statistic):")
        for row in x_rows:
            print(f"    {row['case']:18} {row['miss_bh']:.3f} box-heights off the "
                  f"drawn rails, killed at: {row['stage']}")
    print_junk_tables(j_rows)
    print_separation(x_rows, j_rows)
    print_fleet()

    if args.json:
        doc = {"population": "guided-list + ratchet-hits + negative-corpus",
               "marks_fingerprint": baseline["marks_fingerprint"],
               "engine_config_version": manifest_hash(),
               "protocol": "docs/rail_program_protocol_2026-07.md",
               "grids": {"dwell": DWELL_GRID, "mid": MID_GRID,
                         "respect": RESPECT_GRID},
               "junk_meta_captured_at": jmeta["captured_at"],
               "rows": d_rows + x_rows + e_rows + j_rows}
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
