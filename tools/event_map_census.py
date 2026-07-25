"""Event Map census — the promoted rail-episode sequence instrument.

The durable home of the 2026-07-25 sequence probe (Event Map program, PLAN
Task 4): reads every Guided List drawn box and every respect-surviving junk
candidate as a chronological rail-episode sentence, through the ONE engine
reader (``engine_alpha.structure.event_map.read_rail_episodes`` — this tool
contains no reading logic and no mark-loading of its own). Research-grade
computation lives HERE, permanently off the scan path.

Roles stay named: ``tools.calibration_stat_card`` measures drawn geometry,
``tools.shelf_harness`` grades the LPS detector, THIS instrument reads the
sequence story. The v1 parse rule (pre-registered in the probe: completed-S
>= 2 AND completed-R >= 2 AND alternations >= 2 AND no terminal support
drift) is reported as the recorded baseline only — admission-form research
is the census layer on top (PLAN Task 5), and the ruled form will be a
separate predicate, never baked into the reader.

``--check`` is the promotion regression: the headline evidence the program
was approved on (EGBN's three completed support tests + terminal resistance
posture; the drift-junk zeros DGII 0/11, CHCT 0/7, COLM 0/10, FLG 0/2;
15/33 marks under v1; 17 parse-passing junk of 95) must reproduce exactly on
the sealed fixture, else the instrument no longer measures what the evidence
measured (exit 1, named diffs).

Deterministic + stamped (EC-13): marks load through the ONE validated loader,
frames come from the sealed fixtures by digest, and every report stamps the
populations, the marks fingerprint, and the engine manifest hash. Writes are
guarded (EC-14). Read-only against the DB.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.event_map_census            # full report
    python -m tools.event_map_census --check    # pinned promotion regression
    python -m tools.event_map_census --json OUT # report rows as JSON
"""
from __future__ import annotations

import argparse
import json

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    from _bootstrap import configure_path, refuse_sealed_output

_PROJECT_ROOT = configure_path(backend=True)

import database  # noqa: E402

from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.event_map import (  # noqa: E402
    episode_sequence_stats,
    read_rail_episodes,
)
from engine_alpha.structure.narrative import read_structure  # noqa: E402
from tools import negative_corpus  # noqa: E402
from tools.calibration_harness import load_box_marks  # noqa: E402
from tools.marks_corpus import load_corpus, setup_key  # noqa: E402
from tools.rail_margin_evidence import judged_window  # noqa: E402
from tools.replay import (  # noqa: E402
    drawn_box_window,
    fixture_frame,
    load_sealed_fixture,
    prepared_frame,
)

# The probe's pre-registered v1 parse rule — the recorded baseline, nothing
# more. Candidate admission forms are Task-5 research; the ruled form is a
# separate predicate at the pool seam.
def _v1_parses(st: dict) -> bool:
    return (st["n_completed_s"] >= 2 and st["n_completed_r"] >= 2
            and st["alternations"] >= 2 and not st["terminal_s_drift"])


def read_mark_sentences() -> list[dict]:
    """Every Guided List drawn box (drawn window + drawn rails) as a sentence."""
    frames, baseline = load_sealed_fixture()
    setups = load_corpus()
    status = {e["key"]: e["status"] for e in baseline["setups"]}

    session = database.SessionLocal()
    try:
        marks, fingerprint = load_box_marks(session)
    finally:
        session.close()
    by_key = {(m.ticker, str(m.as_of_date)): m for m in marks}

    rows = []
    for s in setups:
        key = setup_key(s)
        mark = by_key[(s["ticker"], s["as_of"])]
        raw = fixture_frame(frames, key)
        base_df, atr = drawn_box_window(raw, mark.box_start_date,
                                        mark.box_end_date)
        read = read_rail_episodes(base_df, float(s["rails_drawn"]["R"]),
                                  float(s["rails_drawn"]["S"]), atr)
        st = episode_sequence_stats(read)
        rows.append({
            "key": key, "status": status[key], "n_bars": len(base_df),
            "parses_v1": _v1_parses(st), **st,
        })
    rows.sort(key=lambda r: r["key"])
    return rows, fingerprint


def read_junk_sentences() -> list[dict]:
    """Every respect-surviving strict candidate on the negative corpus (the
    probe's population: not rescued, and not killed at width/window/respect)."""
    jframes, meta = negative_corpus._load_fixture()
    rows = []
    for case in meta["cases"]:
        key = case.get("key", case["ticker"])
        df, atr = prepared_frame(jframes.get(key), case["as_of"])
        trace = []
        read_structure(df, atr, trace=trace)
        seen = set()
        for root in trace:
            for rec in root.get("box_cascade") or []:
                if rec["rescued"] or rec["stage"] in ("width", "window", "respect"):
                    continue
                sig = (rec["R"], rec["S"], rec["cand_start"])
                if sig in seen:
                    continue
                seen.add(sig)
                window = judged_window(df, int(rec["cand_start"]))
                if len(window) < 2:
                    continue
                st = episode_sequence_stats(read_rail_episodes(
                    window, float(rec["R"]), float(rec["S"]), atr))
                rows.append({
                    "key": key, "label": case["label"],
                    "died_at": rec["stage"] or "passed",
                    "parses_v1": _v1_parses(st), **st,
                })
    rows.sort(key=lambda r: r["key"])
    return rows


def _report(mark_rows, junk_rows, fingerprint) -> None:
    print("=" * 78)
    print("  EVENT MAP CENSUS — chronological rail-episode sentences")
    print(f"  marks fingerprint {fingerprint}  |  engine {manifest_hash()[:16]}")
    print("  populations: Guided List drawn boxes (sealed corpus + calibration "
          "DB windows); negative-corpus respect-surviving strict candidates")
    print("=" * 78)
    print("\nMARKS — drawn windows + drawn rails:")
    print(f"  {'case':22} {'st':4} {'n':>3}  S+/R+/alt drift v1     profile")
    for r in mark_rows:
        print(f"  {r['key']:22} {'HIT ' if r['status'] == 'hit' else 'MISS'}"
              f" {r['n_bars']:>3}  {r['n_completed_s']}/{r['n_completed_r']}"
              f"/{r['alternations']}   {'Y' if r['terminal_s_drift'] else '.'}"
              f"    {'PASS' if r['parses_v1'] else 'FAIL'}"
              f"   {r['profile']}")
    n_parse = sum(r["parses_v1"] for r in mark_rows)
    print(f"\n  marks parse (v1): {n_parse}/{len(mark_rows)}")

    per_case: dict[str, list[int]] = {}
    for r in junk_rows:
        per_case.setdefault(r["key"], [0, 0])
        per_case[r["key"]][1] += 1
        per_case[r["key"]][0] += r["parses_v1"]
    n_pass = sum(r["parses_v1"] for r in junk_rows)
    print(f"\nJUNK — {len(junk_rows)} respect-surviving candidates; "
          f"parse-pass (v1): {n_pass}")
    for key, (p, t) in sorted(per_case.items()):
        print(f"    {key:12} {p}/{t}{'   <-- parse-pass' if p else ''}")


# The promotion regression: the exact evidence the program was approved on
# (probe capture 2026-07-25, .council/implement-output/2026-07-25-1707/).
_PINNED_MARKS_PARSE_V1 = 15
_PINNED_MARKS_TOTAL = 33
_PINNED_JUNK_TOTAL = 95
_PINNED_JUNK_PARSE_V1 = 17
_PINNED_CASES = {
    "EGBN:2026-01-15": {"n_completed_s": 3, "n_completed_r": 0,
                        "terminal_r_posture": True,
                        "profile": "S+ S+ S+ R^"},
}
_PINNED_JUNK_ZEROS = {"DGII": 11, "CHCT": 7, "COLM": 10, "FLG": 2}


def check(mark_rows, junk_rows) -> list[str]:
    """Exact-match assertions on the headline evidence; returns named diffs."""
    diffs = []

    def _pin(name, got, want):
        if got != want:
            diffs.append(f"{name}: got {got!r}, pinned {want!r}")

    _pin("marks total", len(mark_rows), _PINNED_MARKS_TOTAL)
    _pin("marks parse (v1)", sum(r["parses_v1"] for r in mark_rows),
         _PINNED_MARKS_PARSE_V1)
    _pin("junk candidates", len(junk_rows), _PINNED_JUNK_TOTAL)
    _pin("junk parse-pass (v1)", sum(r["parses_v1"] for r in junk_rows),
         _PINNED_JUNK_PARSE_V1)

    by_key = {r["key"]: r for r in mark_rows}
    for key, want in _PINNED_CASES.items():
        row = by_key.get(key)
        if row is None:
            diffs.append(f"{key}: missing from mark rows")
            continue
        for field, val in want.items():
            _pin(f"{key}.{field}", row[field], val)

    for key, total in _PINNED_JUNK_ZEROS.items():
        rows = [r for r in junk_rows if r["key"] == key]
        _pin(f"{key} candidates", len(rows), total)
        _pin(f"{key} parse-pass", sum(r["parses_v1"] for r in rows), 0)
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="pinned promotion regression (exit 1 on drift)")
    ap.add_argument("--json", help="write report rows as JSON to this path")
    args = ap.parse_args()

    mark_rows, fingerprint = read_mark_sentences()
    junk_rows = read_junk_sentences()

    if args.json:
        path = refuse_sealed_output(args.json)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"fingerprint": fingerprint,
                       "engine_manifest": manifest_hash(),
                       "marks": mark_rows, "junk": junk_rows}, fh, indent=1)
        print(f"wrote {path}")

    if args.check:
        diffs = check(mark_rows, junk_rows)
        if diffs:
            print("EVENT MAP CENSUS CHECK: DRIFT — the instrument no longer "
                  "reproduces the recorded evidence:")
            for d in diffs:
                print(f"  {d}")
            return 1
        print(f"EVENT MAP CENSUS CHECK: OK — headline evidence reproduces "
              f"(marks {_PINNED_MARKS_PARSE_V1}/{_PINNED_MARKS_TOTAL} v1, "
              f"junk {_PINNED_JUNK_PARSE_V1}/{_PINNED_JUNK_TOTAL}; "
              f"fingerprint {fingerprint}, engine {manifest_hash()[:16]})")
        return 0

    _report(mark_rows, junk_rows, fingerprint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
