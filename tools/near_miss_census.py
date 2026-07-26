"""Near-miss margin census — the evidence instrument the Task-6 ruling reads.

The complete signed-margin vector (engine_alpha.structure.gate_margins —
native quanta, raw integer numerators, sign-locked against the gates) over
three populations:

  drawn     all 33 Guided List boxes at the operator's exact rails/window
  examined  the engine's nearest strict candidate to the drawn rails at each
            mark's as_of (the AP-8 basis-honesty analog: a margin ruling
            converts a miss by moving THIS candidate, so separation is judged
            on ITS values)
  junk      EVERY proposed candidate on the negative-corpus frames — all
            stages including width/window kills AND passing candidates
            (their headroom quantifies how close junk winners live to each
            floor; the rail campaign proved floors sit where junk begins)

Co-failure structure is reported at BOTH taxonomy granularities (the eight
occupancy checks as one family vs as eight legs) because "exactly one leg"
is granularity-sensitive — the Task-6 taxonomy is ruled FROM these tables,
never asserted. One traced engine walk per case, one measurement pass per
pair; ruling research iterates on the cached JSON rows (``--json`` then
``--from``) — never re-walks. A cached file whose engine manifest differs
from the live engine is REFUSED (margins are relative to knobs; a knob move
re-bases every distribution).

Deterministic + stamped (EC-13): marks identity rides the sealed baseline's
fingerprint; junk identity rides the negative fixture's captured_at (content
digests are the corpus gates' job — delegated, not re-verified here); every
report stamps both plus the engine manifest. Writes are guarded (EC-14);
modes refuse to combine. Read-only against every ground-truth store.

HARD GATE REMINDER (PLAN Task 6): no lane code that FILTERS by margin exists
before the operator ruling. This instrument measures and reports everything;
it draws no narrowness line.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.near_miss_census              # full report (walks engine)
    python -m tools.near_miss_census --json OUT   # walk once, cache rows
    python -m tools.near_miss_census --from IN    # re-render from cached rows
    python -m tools.near_miss_census --check      # pinned identity+headline gate
"""
from __future__ import annotations

import argparse
import json
from collections import Counter

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    from _bootstrap import configure_path, refuse_sealed_output

_PROJECT_ROOT = configure_path(backend=True)

import database  # noqa: E402

from engine_alpha.election_identity import framing_date_key  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.box_gates import GATE_LEGS  # noqa: E402
from engine_alpha.structure.gate_margins import complete_leg_vector  # noqa: E402
from engine_alpha.structure.narrative import read_structure  # noqa: E402
from tools import negative_corpus  # noqa: E402
from tools.calibration_harness import load_box_marks  # noqa: E402
from tools.marks_corpus import load_corpus, setup_key  # noqa: E402
from tools.replay import (  # noqa: E402
    drawn_box_window,
    fixture_frame,
    judged_window,
    load_sealed_fixture,
    prepared_frame_with_reason,
)

# The eight occupancy checks as ONE family for the coarse-granularity view.
# Crash stays its own leg at both granularities (in-or-out is itself a
# pre-registered Task-6 question); width/window/respect/traversal are
# unambiguous at both.
OCCUPANCY_LEGS = ("r_touches", "s_touches", "r_touch_thirds", "s_touch_thirds",
                  "lower_dwell", "upper_dwell", "mid_dwell", "coverage")
INT_QUANTA = {"bars", "touches", "thirds", "traversals"}
_LEG_ORDER = [spec.leg for spec in GATE_LEGS]


def _row(pop, case, legs, *, n, R, S, identity, died_at=None, status=None,
         label=None, miss_bh=None):
    failing = [leg for leg in _LEG_ORDER if leg in legs and not legs[leg]["passed"]]
    return {"pop": pop, "case": case, "status": status, "label": label,
            "died_at": died_at, "miss_bh": miss_bh, "n": n,
            "R": round(float(R), 4), "S": round(float(S), 4),
            "identity": list(identity), "legs": legs, "failing": failing}


# --- population walks --------------------------------------------------------

def drawn_rows(frames, baseline, setups) -> tuple[list[dict], str]:
    session = database.SessionLocal()
    try:
        marks, fingerprint = load_box_marks(session)
    finally:
        session.close()
    by_key = {(m.ticker, str(m.as_of_date)): m for m in marks}
    status = {e["key"]: e["status"] for e in baseline["setups"]}

    rows = []
    for s in setups:
        key = setup_key(s)
        mark = by_key.get((s["ticker"], s["as_of"]))
        if mark is None or not mark.box_start_date or not mark.box_end_date:
            raise SystemExit(f"drawn population: no DB box span for {key} — "
                             "refusing a partial population")
        raw = fixture_frame(frames, key)
        base_df, atr = drawn_box_window(raw, mark.box_start_date,
                                        mark.box_end_date)
        R = float(s["rails_drawn"]["R"])
        S = float(s["rails_drawn"]["S"])
        legs = complete_leg_vector(base_df, R, S, atr)
        if legs is None:
            raise SystemExit(f"drawn population: degenerate basis for {key}")
        ident = (s["ticker"], R, S, str(mark.box_start_date),
                 str(mark.box_end_date))
        rows.append(_row("drawn", key, legs, n=len(base_df), R=R, S=S,
                         identity=ident, status=status[key]))
    rows.sort(key=lambda r: r["case"])
    return rows, fingerprint


def examined_rows(frames, baseline, setups) -> list[dict]:
    by_key = {setup_key(s): s for s in setups}
    rows = []
    for entry in baseline["setups"]:
        key = entry["key"]
        s = by_key[key]
        raw = fixture_frame(frames, key)
        prep, reason = prepared_frame_with_reason(raw, s["as_of"])
        if prep is None:
            rows.append({"pop": "examined", "case": key,
                         "status": entry["status"], "refused": reason[0]})
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
            rows.append({"pop": "examined", "case": key,
                         "status": entry["status"], "refused": "no-candidate"})
            continue
        miss_bh, rec = best
        window = judged_window(df, int(rec["cand_start"]))
        legs = complete_leg_vector(window, float(rec["R"]), float(rec["S"]), atr)
        if legs is None or len(window) < 2:
            rows.append({"pop": "examined", "case": key,
                         "status": entry["status"], "refused": "degenerate"})
            continue
        ident = framing_date_key(s["ticker"], rec["R"], rec["S"], df.index,
                                 rec["r_anchor_bar"], rec["s_anchor_bar"])
        rows.append(_row("examined", key, legs, n=len(window),
                         R=rec["R"], S=rec["S"], identity=ident,
                         died_at=rec["stage"] or "passed",
                         status=entry["status"],
                         miss_bh=round(float(miss_bh), 3)))
    rows.sort(key=lambda r: r["case"])
    return rows


def junk_rows() -> tuple[list[dict], dict, int]:
    jframes, meta = negative_corpus._load_fixture()
    rows: list[dict] = []
    rescued_skipped = 0
    for case in meta["cases"]:
        key = case.get("key", case["ticker"])
        raw = jframes.get(key)
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
                if rec["rescued"]:
                    rescued_skipped += 1
                    continue
                if rec["stage"] in ("rescue_unused", "dethroned", "story"):
                    continue      # policy stages: no judged strict window
                ident = framing_date_key(key, rec["R"], rec["S"], df.index,
                                         rec["r_anchor_bar"],
                                         rec["s_anchor_bar"])
                if ident in seen:
                    continue
                seen.add(ident)
                window = judged_window(df, int(rec["cand_start"]))
                if len(window) < 2:
                    continue
                legs = complete_leg_vector(window, float(rec["R"]),
                                           float(rec["S"]), atr)
                if legs is None:
                    continue
                rows.append(_row("junk", key, legs, n=len(window),
                                 R=rec["R"], S=rec["S"], identity=ident,
                                 died_at=rec["stage"] or "passed",
                                 label=case["label"]))
    rows.sort(key=lambda r: (r["case"], r["identity"]))
    return rows, meta, rescued_skipped


# --- analysis (pure over rows — the --from path runs only this) --------------

def failing_coarse(row) -> list[str]:
    """The failing set with the occupancy family collapsed to one leg."""
    out, occ = [], False
    for leg in row["failing"]:
        if leg in OCCUPANCY_LEGS:
            occ = True
        else:
            out.append(leg)
    if occ:
        out.append("occupancy")
    return out


def k_fail_hists(rows) -> tuple[Counter, Counter]:
    fine = Counter(len(r["failing"]) for r in rows)
    coarse = Counter(len(failing_coarse(r)) for r in rows)
    return fine, coarse


def co_failure_pairs(rows, top=12) -> list[tuple[str, int]]:
    pairs: Counter = Counter()
    for r in rows:
        f = r["failing"]
        for i in range(len(f)):
            for j in range(i + 1, len(f)):
                pairs[f"{f[i]}+{f[j]}"] += 1
    return pairs.most_common(top)


def _quantum(leg) -> str:
    return next(spec.quantum for spec in GATE_LEGS if spec.leg == leg)


def one_leg_bands(rows) -> dict:
    """Per leg: junk candidates failing ONLY that leg, banded by deficit —
    the junk mass immediately under each floor, the number the operator must
    see before any narrowness ruling."""
    out: dict[str, dict] = {}
    for leg in _LEG_ORDER:
        only = [r for r in rows if r["failing"] == [leg]]
        margins = sorted((r["legs"][leg]["margin"] for r in only), reverse=True)
        entry: dict = {"n": len(only), "quantum": _quantum(leg)}
        if margins:
            # Integer margins (bars/touches/thirds/bins/traversals AND the
            # count-form dwell legs) band exactly; float legs report nearest.
            if isinstance(margins[0], int):
                entry["bands"] = {
                    "-1": sum(1 for m in margins if m == -1),
                    "-2": sum(1 for m in margins if m == -2),
                    "-3": sum(1 for m in margins if m == -3),
                    "<=-4": sum(1 for m in margins if m <= -4),
                }
            entry["nearest"] = [round(float(m), 4) for m in margins[:5]]
        out[leg] = entry
    return out


def passing_headroom(rows) -> list[dict]:
    """Junk candidates that pass EVERY leg (elected/valid framings): where is
    their thinnest headroom? Floors sit where junk begins."""
    out = []
    for r in rows:
        if r["failing"]:
            continue
        thinnest = min(r["legs"].values(), key=lambda x: x["margin"])
        out.append({"case": r["case"], "died_at": r["died_at"],
                    "leg": thinnest["leg"], "margin": thinnest["margin"]})
    return out


# --- report -------------------------------------------------------------------

def _fmt_legs(row, only_failing=True) -> str:
    parts = []
    for leg in _LEG_ORDER:
        if leg not in row["legs"]:
            continue
        cell = row["legs"][leg]
        if only_failing and cell["passed"]:
            continue
        m = cell["margin"]
        m_s = f"{m:+d}" if isinstance(m, int) else f"{m:+.3f}"
        meas = cell["measured"]
        if isinstance(meas, float):
            meas = round(meas, 4)
        parts.append(f"{leg} {meas}/{cell['threshold']} ({m_s})")
    return "; ".join(parts) or "all pass"


def _report(doc) -> None:
    d_rows = doc["drawn"]
    x_rows = doc["examined"]
    j_rows = doc["junk"]
    print("=" * 78)
    print("  NEAR-MISS MARGIN CENSUS — full leg vectors, native quanta")
    print(f"  marks fingerprint {doc['marks_fingerprint']}")
    print(f"  junk basis captured_at {doc['junk_captured_at']}  |  engine "
          f"{doc['engine_manifest'][:16]}…")
    print("  populations: drawn (33 boxes) / examined (nearest strict candidate "
          "at as_of) / junk (every proposed candidate incl. passing)")
    print("=" * 78)

    print("\nMARKS — drawn windows + drawn rails (failing legs only):")
    for r in d_rows:
        flag = "HIT " if r["status"] == "hit" else "MISS"
        print(f"  {r['case']:20} {flag} n={r['n']:>3}  {_fmt_legs(r)}")

    print("\nMARKS — the engine-EXAMINED candidate at as_of (the converting "
          "statistic):")
    for r in x_rows:
        flag = "HIT " if r["status"] == "hit" else "MISS"
        if r.get("refused"):
            print(f"  {r['case']:20} {flag} REFUSED({r['refused']})")
            continue
        print(f"  {r['case']:20} {flag} n={r['n']:>3} "
              f"off={r['miss_bh']:.3f}bh died={r['died_at']:9} {_fmt_legs(r)}")

    fine, coarse = k_fail_hists(j_rows)
    print(f"\nJUNK — {len(j_rows)} deduped proposed candidates "
          f"({doc['rescued_skipped']} rescued/band framings skipped — trimmed "
          "windows the trace does not carry; the Task-7 seam capture is the fix)")
    print(f"  exactly-k failing legs (FINE, occupancy as eight): "
          f"{dict(sorted(fine.items()))}")
    print(f"  exactly-k failing legs (COARSE, occupancy as one): "
          f"{dict(sorted(coarse.items()))}")
    print(f"  top co-failing leg pairs: {co_failure_pairs(j_rows)}")

    print("\nJUNK MASS UNDER EACH FLOOR — candidates failing ONLY that leg:")
    bands = one_leg_bands(j_rows)
    for leg, e in bands.items():
        if e["n"] == 0:
            continue
        band_s = f"  bands {e['bands']}" if "bands" in e else ""
        print(f"  {leg:18} n={e['n']:>3}{band_s}  nearest {e['nearest']}")

    head = passing_headroom(j_rows)
    print(f"\nJUNK PASSING-CANDIDATE HEADROOM — {len(head)} candidates pass "
          "every leg; thinnest legs:")
    hist = Counter(h["leg"] for h in head)
    print(f"  thinnest-leg histogram: {dict(hist.most_common())}")
    near = sorted(head, key=lambda h: h["margin"])[:8]
    for h in near:
        m = h["margin"]
        m_s = f"{m:+d}" if isinstance(m, int) else f"{m:+.3f}"
        print(f"    {h['case']:12} {h['leg']:16} margin {m_s} "
              f"(died_at={h['died_at']})")

    print("\nSEPARATION — ratchet-miss examined candidates vs the junk band "
          "on each failing leg:")
    for r in x_rows:
        if r.get("refused") or r["status"] != "miss" or not r["failing"]:
            continue
        for leg in r["failing"]:
            cell = r["legs"][leg]
            only = bands.get(leg, {})
            m = cell["margin"]
            m_s = f"{m:+d}" if isinstance(m, int) else f"{m:+.3f}"
            print(f"  {r['case']:20} {leg:16} margin {m_s}   junk-only-this-leg "
                  f"n={only.get('n', 0)} nearest={only.get('nearest', [])[:3]}")


# --- pins (--check) -----------------------------------------------------------
# Filled from the first sealed run (2026-07-26). A failed pin names the
# drifted axis: fingerprint = the drawn ground truth moved; captured_at = the
# junk basis was rebuilt; engine = a knob/flag moved (EVERY distribution
# re-bases; re-pin deliberately in the same change); counts = the instrument
# or the cascade changed shape.
_PINNED = {
    "marks_fingerprint":
        "b671e056a91fc14fea5b8a724b843c7321a26f4d7d7a6aa5b00741dc93df2523",
    "junk_captured_at": "2026-07-03T12:20:14+00:00",
    "engine_manifest":
        "53c208dc1e2482206a3cb9946effc27f01d8365d2d2029b01875bae75a5cbaa2",
    "n_drawn": 33,
    "n_examined": 33,
    "n_junk": 1805,
    "junk_one_leg_fine": 75,
    "junk_zero_fail": 19,
}


def check(doc) -> list[str]:
    diffs = []

    def _pin(name, got):
        want = _PINNED[name]
        if want is None:
            diffs.append(f"{name}: pin UNSEALED (instrument not yet sealed)")
        elif got != want:
            diffs.append(f"{name}: got {got!r}, pinned {want!r}")

    _pin("marks_fingerprint", doc["marks_fingerprint"])
    _pin("junk_captured_at", doc["junk_captured_at"])
    _pin("engine_manifest", doc["engine_manifest"])
    _pin("n_drawn", len(doc["drawn"]))
    _pin("n_examined", len(doc["examined"]))
    _pin("n_junk", len(doc["junk"]))
    fine, _coarse = k_fail_hists(doc["junk"])
    _pin("junk_one_leg_fine", fine.get(1, 0))
    _pin("junk_zero_fail", fine.get(0, 0))
    return diffs


def _build_doc() -> dict:
    frames, baseline = load_sealed_fixture()
    setups = load_corpus()
    d_rows, fingerprint = drawn_rows(frames, baseline, setups)
    x_rows = examined_rows(frames, baseline, setups)
    j_rows, jmeta, rescued_skipped = junk_rows()
    return {"marks_fingerprint": fingerprint,
            "junk_captured_at": jmeta["captured_at"],
            "engine_manifest": manifest_hash(),
            "rescued_skipped": rescued_skipped,
            "drawn": d_rows, "examined": x_rows, "junk": j_rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="pinned identity+headline regression (exit 1 on drift)")
    ap.add_argument("--json", help="walk once, cache all rows to this path")
    ap.add_argument("--from", dest="from_json",
                    help="re-render the report from cached rows (no engine walk)")
    args = ap.parse_args()

    modes = [bool(args.check), bool(args.json), bool(args.from_json)]
    if sum(modes) > 1:
        ap.error("modes run alone: pick ONE of --check / --json / --from")

    if args.from_json:
        with open(args.from_json, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        live = manifest_hash()
        if doc.get("engine_manifest") != live:
            raise SystemExit(
                f"cached rows were measured at engine "
                f"{str(doc.get('engine_manifest'))[:16]}… but the live engine "
                f"is {live[:16]}… — margins are relative to knobs; REFUSING "
                "stale evidence (re-walk with --json)")
        _report(doc)
        return 0

    doc = _build_doc()

    if args.check:
        diffs = check(doc)
        if diffs:
            print("NEAR-MISS CENSUS CHECK: DRIFT —")
            for d in diffs:
                print(f"  {d}")
            return 1
        print(f"NEAR-MISS CENSUS CHECK: OK (fingerprint "
              f"{doc['marks_fingerprint'][:16]}…, junk {len(doc['junk'])} "
              f"candidates, engine {doc['engine_manifest'][:16]}…)")
        return 0

    if args.json:
        path = refuse_sealed_output(args.json)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
        print(f"wrote {path} (stamped: fingerprint "
              f"{doc['marks_fingerprint'][:16]}…, engine "
              f"{doc['engine_manifest'][:16]}…)")
        return 0

    _report(doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
