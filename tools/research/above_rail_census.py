"""Above-the-rail census — is a rest ABOVE resistance already an LPS, and how far above may it sit?

Read-only, offline, measure-only (no gate, no points, no engine change). The
committed instrument behind the 2026-09-02 correction row in ``docs/decisions.md``.
The operator ruled 2026-09-01 that a rest sitting above the resistance line is
also "LPS at resistance" because it is in the rail's area; the ask raised right
after it assumed the engine could not express that and owed him a fresh bound.
This census measures that assumption and REFUTES it.

Three legs, all on committed corpora, so the run is hermetic and CI-safe:

  1. DRAWN — his 33 Guided-List marks, each drawn LPS span measured against HIS
     drawn R on the sealed frame for that mark's digest. Engine-independent, and
     the strongest evidence here. It reproduces the below-side figures the 0.30
     razor was placed on (DSGN 0.010 / MATX 0.087 / MSGS 0.148 under R) — which
     is what validates the basis, because a method that could not re-derive
     those has no standing to report new numbers.
  2. ELECTED — the same marks read through the real cascade at their sealed
     first-fire session, reporting the ELECTED LPS's zone type and its low
     against the elected R. This is the leg that answers the question: an
     OVERSHOOT_R election IS a rest above the line, admitted and fired.
  3. JUNK — the 18 negative-corpus frames at their frozen as_of. Reported
     because the razor BELOW the line was placed against junk, and the honest
     finding is that junk cannot place this one: those frames elect boxes but
     complete no LPS at all, so they offer no shelf on either side to measure.

FROZEN CONVENTIONS (changing one silently re-derives the recorded evidence):
  * the drawn statistic is ``(min Low over the drawn lps span - drawn R) / ATR``,
    signed, POSITIVE above the line. Wick basis, no tolerance anywhere.
  * ATR is the marks convention — ``ATR_10`` at ``replay.MARK_ATR_OFFSET`` on the
    frame sliced to the span end, the same yardstick the shelf harness and the
    ratchet use. A different offset moves every number in this report.
  * the elected leg reads at the SEALED ``first_fire``, never at "today".

Usage (the repo venv, from the repo root):
    python -m tools.research.above_rail_census
    python -m tools.research.above_rail_census --json OUT
"""
from __future__ import annotations

import argparse
import json

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

_PROJECT_ROOT = configure_path(backend=True)

from config import settings                                          # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash               # noqa: E402
from engine_alpha.structure.narrative import read_structure          # noqa: E402
from tools.regression.marks_corpus import load_corpus, setup_key                # noqa: E402
from core.calibration.replay import (                                           # noqa: E402
    MARK_ATR_OFFSET,
    enrich_marked_frame,
    fixture_frame,
    load_sealed_fixture,
)

_BASIS_CHECK = ("DSGN:2026-03-31", "MATX:2026-07-01", "MSGS:2026-05-22")


def _atr_at(frame_to_end):
    """The marks-convention ATR for a frame sliced to the span end."""
    work = enrich_marked_frame(frame_to_end)
    idx = -MARK_ATR_OFFSET if len(work) >= MARK_ATR_OFFSET else -1
    return work, float(work["ATR_10"].iloc[idx])


def drawn_leg(setups, frames) -> list[dict]:
    """His drawn shelves against his drawn R — engine-independent."""
    rows = []
    for setup in setups:
        key = setup_key(setup)
        df = fixture_frame(frames, key,
                           None if setup.get("frame_digest") else setup["ticker"])
        if df is None:
            rows.append({"key": key, "error": "frame missing from the sealed fixture"})
            continue
        resistance = float(setup["rails_drawn"]["R"])
        start, end = setup["lps"]
        span = df.loc[str(start):str(end)]
        if span.empty:
            rows.append({"key": key, "error": "drawn span has no frame sessions"})
            continue
        _, atr = _atr_at(df.loc[:str(end)])
        low = float(span["Low"].min())
        rows.append({"key": key, "bars": int(len(span)), "drawn_R": resistance,
                     "shelf_low": low, "atr": atr,
                     "low_minus_R_atr": (low - resistance) / atr})
    return rows


def elected_leg(baseline, frames) -> list[dict]:
    """The sealed hits read through the real cascade at their first fire."""
    rows = []
    for setup in baseline["setups"]:
        if setup.get("status") != "hit" or not setup.get("first_fire"):
            continue
        key = setup["key"]
        df = fixture_frame(frames, key, None)
        if df is None:
            continue
        work, atr = _atr_at(df.loc[:setup["first_fire"]])
        structure = read_structure(work, atr)
        lps = getattr(structure, "lps", None)
        box = getattr(structure, "box", None)
        row = {"key": key, "first_fire": setup["first_fire"], "zone": None}
        if lps is not None and box is not None:
            row.update({"zone": lps.zone_type, "elected_R": float(box.R),
                        "lps_low": float(lps.low), "atr": atr,
                        "low_minus_R_atr": (float(lps.low) - float(box.R)) / atr})
        rows.append(row)
    return rows


def junk_leg() -> dict:
    """Junk frames: do they offer any LPS shelf to place a bar against?"""
    from tools.regression import negative_corpus
    from tools.research.rail_margin_evidence import prepared_frame
    frames, meta = negative_corpus._load_fixture()
    roots = boxed = with_lps = 0
    for case in meta["cases"]:
        key = case.get("key", case["ticker"])
        prepared = prepared_frame(frames.get(key), case["as_of"])
        if prepared is None:
            continue
        df, atr = prepared
        trace: list = []
        read_structure(df, atr, trace=trace)
        for root in trace:
            roots += 1
            boxed += bool(root.get("box"))
            with_lps += bool(root.get("lps"))
    return {"cases": len(meta["cases"]), "roots": roots,
            "roots_electing_a_box": boxed, "roots_with_an_lps": with_lps}


def report(payload) -> str:
    bound = payload["lps_zone_atr_mult"]
    drawn = [r for r in payload["drawn"] if "low_minus_R_atr" in r]
    above = sorted((r for r in drawn if r["low_minus_R_atr"] > 0),
                   key=lambda r: -r["low_minus_R_atr"])
    elected = payload["elected"]
    over = sorted((r for r in elected if r.get("zone") == "OVERSHOOT_R"),
                  key=lambda r: -r["low_minus_R_atr"])
    lines = [
        "=" * 66,
        "  ABOVE-THE-RAIL CENSUS - is a rest above R already an LPS?",
        "=" * 66,
        f"engine {payload['engine_config_version'][:16]}... | "
        f"marks {payload['marks_fingerprint'][:16]}...",
        f"the LIVE bound: LPS_ZONE_ATR_MULT = {bound} "
        f"(OVERSHOOT_R admits R < low <= R + {bound} x ATR)",
        "",
        f"LEG 1 - DRAWN: {len(above)} of {len(drawn)} drawn shelves sit ABOVE his R",
    ]
    for row in above:
        lines.append(f"    {row['key']:20s} +{row['low_minus_R_atr']:.3f} ATR "
                     f"  ({row['bars']} bars)")
    lines.append("  basis check - the figures the 0.30 razor was placed on:")
    for key in _BASIS_CHECK:
        hit = next((r for r in drawn if r["key"] == key), None)
        if hit:
            lines.append(f"    {key:20s} {hit['low_minus_R_atr']:+.3f} ATR")
    lines += [
        "",
        f"LEG 2 - ELECTED: {len(over)} of {len(elected)} sealed hits elect an "
        f"OVERSHOOT_R LPS",
        "  (a rest ABOVE the line - already admitted, already firing)",
    ]
    for row in over:
        lines.append(f"    {row['key']:20s} +{row['low_minus_R_atr']:.3f} ATR above "
                     f"elected R   (fire {row['first_fire']})")
    junk = payload["junk"]
    lines += [
        "",
        f"LEG 3 - JUNK: {junk['cases']} frames, {junk['roots']} roots, "
        f"{junk['roots_electing_a_box']} elected a box, "
        f"{junk['roots_with_an_lps']} completed an LPS",
        "  -> junk offers NO shelf on either side, so it cannot place this bar.",
        "=" * 66,
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", dest="out", help="also write the rows to JSON")
    args = parser.parse_args()

    setups = load_corpus()
    frames, baseline = load_sealed_fixture()
    payload = {
        "engine_config_version": manifest_hash(),
        "marks_fingerprint": baseline["marks_fingerprint"],
        "lps_zone_atr_mult": settings.LPS_ZONE_ATR_MULT,
        "mark_atr_offset": MARK_ATR_OFFSET,
        "drawn": drawn_leg(setups, frames),
        "elected": elected_leg(baseline, frames),
        "junk": junk_leg(),
    }
    print(report(payload))
    if args.out:
        refuse_sealed_output(args.out)
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
