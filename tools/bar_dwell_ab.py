"""Bar-dwell fire A/B — the sealed campaign of docs/bar_dwell_protocol_2026-07.md.

ONE variant: ``EQ_DWELL_BAR_BASIS = True`` (a measurement-basis correction at
unchanged knob values). Reuses the rail campaign's certified machinery
(tools.rail_margin_ab): flag_capture with a per-variant manifest stamp,
predicted-only conversions (condition A), junk fires by name (condition B),
and the elections+rails diff at every pinned first-fire (condition E).

Predicted (protocol §4): EGBN + YPF convert, each electing at drawn-box
identity; NKTR / NOK conversions allowed (pre-registered possible, geometry
disclosed); everything else unchanged. The verdict prints mechanically.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.bar_dwell_ab             # run the sealed variant
    python -m tools.bar_dwell_ab --json OUT  # also dump results
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

from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from tools.marks_corpus import load_corpus, setup_key  # noqa: E402
from tools.rail_margin_ab import _election_at, _junk_fires, run_variant  # noqa: E402
from tools.replay import fixture_frame, load_sealed_fixture  # noqa: E402

VARIANT = ("bar-basis", {"EQ_DWELL_BAR_BASIS": True},
           {"EGBN:2026-01-15", "YPF:2026-05-18"})
ALLOWED_EXTRA = {"NKTR:2026-04-10", "NOK:2026-02-17"}  # possible, not required

# The drawn-box identity each MANDATORY conversion must elect at (protocol §4A:
# the examined candidates sit at 0.000 bh from the drawn rails, so the elected
# (R, S) must equal the drawn rails to the cent).
DRAWN_RAILS = {}  # filled from the corpus at runtime


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
            f"current {base_hash[:16]} — reseal before running (evidence must pair)")

    print("=" * 78)
    print("  BAR-DWELL FIRE A/B — docs/bar_dwell_protocol_2026-07.md")
    print("=" * 78)
    print(f"baseline manifest: {base_hash[:16]}...   marks_fingerprint: "
          f"{baseline['marks_fingerprint'][:16]}...")
    base_junk = _junk_fires()
    if base_junk:
        raise SystemExit(f"baseline junk fires {base_junk} — corpus gate red; stop")
    n_hits = sum(1 for s in baseline["setups"] if s["status"] == "hit")
    print(f"baseline junk: 18/18 reject   baseline ratchet: {n_hits}/33 hits")

    base_elections = {}
    for entry in baseline["setups"]:
        if entry["status"] != "hit":
            continue
        raw = fixture_frame(frames, entry["key"])
        base_elections[entry["key"]] = _election_at(
            raw, pd.Timestamp(entry["first_fire"]))
        if base_elections[entry["key"]] is None:
            raise SystemExit(f"{entry['key']}: no baseline election at pinned "
                             "first_fire — drift; stop")

    setups = {setup_key(s): s for s in load_corpus()}
    for key in VARIANT[2]:
        s = setups[key]
        DRAWN_RAILS[key] = (round(float(s["rails_drawn"]["R"]), 4),
                            round(float(s["rails_drawn"]["S"]), 4))

    name, overrides, predicted = VARIANT
    res = run_variant(name, overrides, predicted, frames, baseline,
                      base_elections, setups)

    converted = {c.split(" ")[0] for c in res["conversions"]}
    unpredicted_bad = [c for c in res["unpredicted"]
                       if c.split(" ")[0] not in ALLOWED_EXTRA]
    missing = sorted(predicted - converted)

    # Condition A geometry: the mandatory conversions must elect the drawn rails.
    geometry = []
    for key in sorted(predicted & converted):
        entry = next(e for e in baseline["setups"] if e["key"] == key)
        conv = next(c for c in res["conversions"] if c.startswith(key))
        fire_ts = conv.split("first_fire ")[1].split(" ")[0]
        raw = fixture_frame(frames, key)
        from tools.replay import flag_capture
        with flag_capture(**overrides):
            election = _election_at(raw, pd.Timestamp(fire_ts))
        want = DRAWN_RAILS[key]
        got = None if election is None else (election[1], election[2])
        geometry.append((key, want, got, got == want))

    ok_e = not res["hits_broken"]
    ok_b = not res["junk_fires"]
    ok_a = not missing and not unpredicted_bad and all(g[3] for g in geometry)

    print(f"\n== {name}  manifest {res['manifest'][:16]}... ==")
    print(f"  E hit identity: {len(res['hits_kept'])}/{n_hits} kept"
          + ("" if ok_e else "   BROKEN: " + " | ".join(res["hits_broken"])))
    print(f"  A conversions: "
          + (", ".join(res["conversions"]) if res["conversions"] else "none"))
    for key, want, got, ok in geometry:
        print(f"      {key}: drawn rails {want} -> elected {got} "
              f"{'MATCH' if ok else 'MISMATCH'}")
    if missing:
        print(f"      MISSING predicted conversion(s): {', '.join(missing)}")
    allowed_seen = [c for c in res["unpredicted"]
                    if c.split(" ")[0] in ALLOWED_EXTRA]
    if allowed_seen:
        print("      allowed-extra (pre-registered possible): "
              + " | ".join(allowed_seen))
    if unpredicted_bad:
        print("      UNPREDICTED outside the allowed set (FAIL): "
              + " | ".join(unpredicted_bad))
    print(f"  B junk: " + ("18/18 still reject" if ok_b
                           else "FIRES: " + " | ".join(res["junk_fires"])))
    verdict = "YES — flip per protocol §5" if (ok_a and ok_b and ok_e) \
        else "NO — record tested-DEAD per protocol §6"
    print(f"\n  VERDICT (mechanical): {verdict}")

    if args.json:
        doc = {"baseline_manifest": base_hash,
               "marks_fingerprint": baseline["marks_fingerprint"],
               "protocol": "docs/bar_dwell_protocol_2026-07.md",
               "geometry": [{"key": k, "want": w, "got": g, "match": ok}
                            for k, w, g, ok in geometry],
               "verdict": verdict, "result": res}
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
