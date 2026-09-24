"""Rail margin A/B campaign driver (Rail Program Task 3).

Runs the PRE-REGISTERED variant grid of docs/rail_program_protocol_2026-07.md
§2 — settings-value levers only, CLI-subprocess-only, never the backend's
in-process seam — and reports the protocol's mechanical accept-condition
checks per variant:

  A. predicted conversions only (any other conversion is flagged loudly)
  B. zero new negative-corpus fires (all 18 junk cases, by name)
  E. ratchet pins held with elections AND rails diffed — every baseline hit
     must keep its pinned first-fire AND its elected box identity
     (start bar, R, S) at that session; a displaced winner fails E even when
     the fire count looks unchanged (the arbitration lesson)

Conditions C (junk margin consumption) and D (separation) are distribution
questions answered by tools.rail_margin_evidence at the same grid values —
this driver reports fire evidence; the campaign record joins both.

Every variant runs under tools.replay.flag_capture (self-restoring; refuses
unknown knob names) and stamps the variant's own effective manifest hash —
baseline and variant evidence must pair or it is void (protocol §1).

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.rail_margin_ab             # the full pre-registered grid
    python -m tools.rail_margin_ab --json OUT  # also dump results
"""
from __future__ import annotations

import argparse
import json

import pandas as pd

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from repo root
    from _bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path(backend=True)

from engine_alpha.evaluation import EVAL_ERROR  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.narrative.reader import read_structure  # noqa: E402
from tools import negative_corpus  # noqa: E402
from tools.marks_corpus import _replay_setup, load_corpus, setup_key  # noqa: E402
from tools.replay import (  # noqa: E402
    FROZEN_SPY_6M,
    fixture_frame,
    flag_capture,
    load_sealed_fixture,
    prepared_frame,
)

# The pre-registered grid (protocol §2 — closed; L3b is a code reframing with
# its own EC-8 build decision, not a settings variant, so it is not here).
VARIANTS = [
    ("L1@0.125", {"EQ_MIN_HALF_DWELL": 0.125}, {"EGBN:2026-01-15"}),
    ("L1@0.10", {"EQ_MIN_HALF_DWELL": 0.10}, {"EGBN:2026-01-15"}),
    ("L2@0.50", {"EQ_MAX_MID_DWELL": 0.50}, set()),
    ("L2@0.55", {"EQ_MAX_MID_DWELL": 0.55}, set()),
    ("L1+L2@0.125/0.50", {"EQ_MIN_HALF_DWELL": 0.125,
                          "EQ_MAX_MID_DWELL": 0.50},
     {"EGBN:2026-01-15", "YPF:2026-05-18"}),
    ("L3a@0.75", {"MIN_BOUNDARY_RESPECT_PCT": 0.75}, {"PKE:2026-02-24"}),
]


def _election_at(df_full: pd.DataFrame, ts) -> tuple | None:
    """The elected box identity (start_bar, R, S) at one session, or None."""
    prep = prepared_frame(df_full, ts)
    if prep is None:
        return None
    df, atr = prep
    structure = read_structure(df, atr)
    if structure is None:
        return None
    box = structure.box
    return (int(box.start_bar), round(float(box.R), 4), round(float(box.S), 4))


def _junk_fires() -> list[str]:
    """Names of negative-corpus cases that fire (or crash) under the CURRENT
    settings — the same frames, evaluator, and frozen scalars check_corpus
    replays; reported by name instead of folded to one bool."""
    frames, meta = negative_corpus._load_fixture()
    fires = []
    for case in meta["cases"]:
        key = case.get("key", case["ticker"])
        df = frames.get(key)
        if df is None or df.empty:
            fires.append(f"{key} (frame MISSING)")
            continue
        result = negative_corpus._evaluate_ticker(
            case["ticker"], df, float(case["spy_6m_return"]),
            float(meta["breadth_pct"]))
        if result is EVAL_ERROR:
            fires.append(f"{key} (EVAL_ERROR)")
        elif result is not None:
            fires.append(f"{key} ({case['label']})")
    return fires


def run_variant(name: str, overrides: dict, predicted: set, frames: dict,
                baseline: dict, base_elections: dict, setups: dict) -> dict:
    with flag_capture(**overrides):
        v_hash = manifest_hash()
        out = {"variant": name, "overrides": overrides,
               "manifest": v_hash, "predicted": sorted(predicted),
               "hits_kept": [], "hits_broken": [], "conversions": [],
               "unpredicted": [], "junk_fires": []}
        for entry in baseline["setups"]:
            key = entry["key"]
            raw = fixture_frame(frames, key)
            setup = setups[key]
            got = _replay_setup(setup, raw, FROZEN_SPY_6M)
            if entry["status"] == "hit":
                if got.get("status") != "hit" or got.get("first_fire") != entry["first_fire"]:
                    out["hits_broken"].append(
                        f"{key}: {got.get('status')} @ {got.get('first_fire')} "
                        f"(pinned {entry['first_fire']})")
                    continue
                election = _election_at(raw, pd.Timestamp(entry["first_fire"]))
                if election != base_elections[key]:
                    out["hits_broken"].append(
                        f"{key}: elected box moved {base_elections[key]} -> "
                        f"{election} (displaced winner — arbitration lesson)")
                else:
                    out["hits_kept"].append(key)
            else:
                if got.get("status") == "hit":
                    rec = f"{key} first_fire {got['first_fire']} tier {got.get('tier')}"
                    out["conversions"].append(rec)
                    if key not in predicted:
                        out["unpredicted"].append(rec)
        out["junk_fires"] = _junk_fires()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", metavar="PATH", help="dump results to JSON")
    args = ap.parse_args()
    if args.json:
        refuse_sealed_output(args.json)

    frames, baseline = load_sealed_fixture()
    base_hash = manifest_hash()
    if base_hash != baseline["engine_config_version"]:
        raise SystemExit(
            f"baseline manifest {baseline['engine_config_version'][:16]} != "
            f"current {base_hash[:16]} — reseal or explain before running the "
            "campaign (evidence must pair, protocol §1)")

    print("=" * 78)
    print("  RAIL MARGIN A/B — the pre-registered grid, fire evidence")
    print("=" * 78)
    print(f"baseline manifest: {base_hash[:16]}...   marks_fingerprint: "
          f"{baseline['marks_fingerprint'][:16]}...")
    base_junk = _junk_fires()
    if base_junk:
        raise SystemExit(f"baseline junk fires {base_junk} — the corpus gate "
                         "is red; fix before any variant evidence counts")
    print("baseline junk: 18/18 reject   baseline ratchet: pinned "
          f"{sum(1 for s in baseline['setups'] if s['status'] == 'hit')}/33 hits")

    base_elections = {}
    for entry in baseline["setups"]:
        if entry["status"] != "hit":
            continue
        raw = fixture_frame(frames, entry["key"])
        base_elections[entry["key"]] = _election_at(
            raw, pd.Timestamp(entry["first_fire"]))
        if base_elections[entry["key"]] is None:
            raise SystemExit(f"{entry['key']}: no election at its pinned "
                             "first_fire under baseline — drift; stop")

    setups = {setup_key(s): s for s in load_corpus()}
    results = []
    for name, overrides, predicted in VARIANTS:
        res = run_variant(name, overrides, predicted, frames, baseline,
                          base_elections, setups)
        results.append(res)
        ok_a = not res["unpredicted"]
        ok_b = not res["junk_fires"]
        ok_e = not res["hits_broken"]
        print(f"\n== {name}  ({', '.join(f'{k} {v}' for k, v in res['overrides'].items())})"
              f"   manifest {res['manifest'][:16]}... ==")
        print(f"  E ratchet: hits kept {len(res['hits_kept'])}/"
              f"{len(base_elections)}"
              + ("" if ok_e else "   BROKEN: " + " | ".join(res["hits_broken"])))
        print(f"  A conversions: "
              + (", ".join(res["conversions"]) if res["conversions"] else "none")
              + (f"   (predicted: {', '.join(res['predicted']) or 'none'})"))
        if res["unpredicted"]:
            print("    UNPREDICTED (investigate before any pin): "
                  + " | ".join(res["unpredicted"]))
        print(f"  B junk: " + ("18/18 still reject" if ok_b
                               else "FIRES: " + " | ".join(res["junk_fires"])))
        print(f"  mechanical A/B/E: "
              f"{'PASS' if ok_a and ok_b and ok_e else 'FAIL'}"
              "   (C/D from tools.rail_margin_evidence at this value)")

    if args.json:
        doc = {"baseline_manifest": base_hash,
               "marks_fingerprint": baseline["marks_fingerprint"],
               "protocol": "docs/rail_program_protocol_2026-07.md",
               "results": results}
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
