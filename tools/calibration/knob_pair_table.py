"""Knob pair table — every election knob co-expressed as measured pairs over
the operator's DRAWN marks (consolidation-method Task 15, Friedman).

Read-only, offline. For every box mark, judge the drawn rails through the ONE
refusal-naming read the workbench serves (``metrics.mark_refusal_read`` —
EC-18: the same gate predicates the election consults, never a re-typed
twin), then print, per knob, the pair the operator tunes by: **what your mark
measures vs where the floor sits** — and, under ``--what-if``, the exact list
of marks a proposed threshold move flips (so "two completed tests should be
enough" arrives with its own flip list).

**Printing rule:** every number in one printed BLOCK — a floor and the marks
listed under it — renders at ONE shared precision, widened (exactly as the
shared pair formatter widens a pair) until no two DISTINCT numbers in that
block render the same string, so distinct marks never collapse onto each other
and no mark can read as arithmetically impossible against its own header.

Sidecar-only (EC-46), sealed-output-guarded (EC-14), population + fingerprint
+ engine-epoch stamped (EC-13). Never touches the archive, never the engine.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.calibration.knob_pair_table                       # the pair table
    python -m tools.calibration.knob_pair_table --ticker EGBN         # one mark's card
    python -m tools.calibration.knob_pair_table --what-if lower_dwell=0.125
    python -m tools.calibration.knob_pair_table --json output/knob_pairs.json
"""
from __future__ import annotations

import argparse
import json
import math

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from repo root
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path(backend=True)

import database  # noqa: E402, F401  binds the live SQLite engine + SessionLocal

from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.box.box_gates import GATE_LEG_INDEX  # noqa: E402
from engine_alpha.structure.metrics.base import mark_refusal_read  # noqa: E402
# The ONE operator vocabulary and its number formatter (EC-3/EC-18): the same
# names ``leg_sentence`` renders the per-mark sentences at the bottom of this
# output with, imported rather than copied so a signed re-wording reaches this
# table the day it lands. Private by design, imported the way
# ``metrics.mark_refusal_read`` imports box_gates' own leg helpers.
from engine_alpha.structure.box.trace_export import (  # noqa: E402
    _LEG_PHRASES, _fmt)
from tools.calibration.calibration_harness import load_box_marks  # noqa: E402
from core.calibration.replay import drawn_box_window  # noqa: E402
from webapp.backend import frame_store  # noqa: E402

_OPS = {">=": lambda m, t: m >= t, "<=": lambda m, t: m <= t}
# The quanta whose measured values are true COUNTS — trace_export's own list.
# A window is 41 trading days, never 41.00, and never widens.
_COUNT_QUANTA = ("bars", "touches", "thirds", "traversals")
_MAX_DECIMALS = 6      # the shared pair formatter's own widening ceiling


def _collides(values, decimals: int) -> bool:
    """Do two DISTINCT numbers render the same string at this precision?"""
    seen: dict[str, float] = {}
    for value in values:
        shown = f"{value:.{decimals}f}"
        if seen.setdefault(shown, value) != value:
            return True
    return False


def fmt_block(measured_values, threshold, quantum: str) -> tuple[list[str], str]:
    """Render one printed BLOCK — a floor and the marks listed under it — at
    ONE shared precision. Returns ``(measured_strings, threshold_string)``.

    Fraction/ratio quanta start at the shared formatter's two decimals and
    widen, exactly as ``_fmt_pair`` widens a pair, until no two DISTINCT
    numbers in the block collide; count quanta stay counts.

    A PAIR formatter cannot do this job, because it only ever compares one mark
    against the floor: measured 0.118, 0.121 and 0.1249 at a proposed floor of
    0.10 each differ from the floor at two decimals, so all three print
    "(0.12)" and the ordering a threshold ruling turns on is destroyed; and a
    mark at 0.1449 widens against 0.145 to "(0.1449)" while the header floor,
    formatted alone, prints "0.14" — a line that is arithmetically impossible
    on its face (completeness pass 2026-09-01). One precision per block fixes
    both: distinct values stay distinct, and the floor is printed at the
    precision its own marks are read at."""
    if quantum in _COUNT_QUANTA:
        return ([_fmt(m, quantum) for m in measured_values],
                _fmt(threshold, quantum))
    try:
        values = [float(m) for m in measured_values] + [float(threshold)]
    except (TypeError, ValueError):
        return ([_fmt(m, quantum) for m in measured_values],
                _fmt(threshold, quantum))
    decimals = 2
    while decimals < _MAX_DECIMALS and _collides(values, decimals):
        decimals += 1
    return ([f"{v:.{decimals}f}" for v in values[:-1]],
            f"{values[-1]:.{decimals}f}")


def leg_phrase(leg: str) -> str:
    """The leg's plain operator phrase for a header — the shared vocabulary's
    own wording with the number placeholders dropped ("time in the lower
    third"). An unregistered leg renders as its id, never blank."""
    phrase = _LEG_PHRASES.get(leg)
    if phrase is None:
        return leg
    return phrase.split("{m}")[0].strip()


def parse_what_if(arg: str) -> tuple[str, float]:
    """``LEG=VALUE`` -> ``(leg, proposed)``, refusing loudly in this tool's own
    style rather than dying on a traceback or judging a number that judges
    nothing: ``nan`` makes EVERY comparison false, which would print every
    currently-passing mark as newly refused — a fabricated flip list stamped
    with a real marks fingerprint and engine epoch — and ``inf`` silently
    inverts one direction."""
    leg, sep, raw = arg.partition("=")
    if leg not in GATE_LEG_INDEX:
        raise SystemExit(f"unknown leg {leg!r}; legs: "
                         f"{sorted(GATE_LEG_INDEX)}")
    if not sep or not raw.strip():
        raise SystemExit(f"--what-if needs LEG=VALUE, e.g. --what-if "
                         f"{leg}=0.125; got {arg!r}")
    try:
        proposed = float(raw)
    except ValueError:
        raise SystemExit(f"--what-if value {raw.strip()!r} is not a number; "
                         f"expected a plain threshold, e.g. --what-if "
                         f"{leg}=0.125")
    if not math.isfinite(proposed):
        raise SystemExit(f"--what-if value {raw.strip()!r} is not a finite "
                         "number, so it judges nothing: every mark would "
                         "compare false and print as newly refused. Expected "
                         f"a real threshold, e.g. --what-if {leg}=0.125")
    return leg, proposed


def judge_marks(marks) -> tuple[list[dict], list[dict]]:
    """One refusal-naming read per mark (delegation, never a twin). Returns
    ``(rows, unreadable)`` — a mark whose frame/window/read refuses is
    reported loudly in ``unreadable``, never silently skipped."""
    rows, unreadable = [], []
    for mark in marks:
        ident = {"ticker": mark.ticker, "as_of": mark.as_of_date,
                 "label": mark.label or ""}
        frozen = frame_store.load_frame(mark.ticker, mark.as_of_date,
                                        digest=mark.frame_digest)
        if frozen is None or frozen.empty:
            unreadable.append({**ident, "why": "no frozen frame for digest"})
            continue
        try:
            win, atr = drawn_box_window(frozen, mark.box_start_date,
                                        mark.box_end_date)
        except ValueError as e:
            unreadable.append({**ident, "why": str(e)})
            continue
        read = mark_refusal_read(win, mark.resistance, mark.support, atr)
        if read is None:
            unreadable.append({**ident, "why": "unreadable geometry (NULL)"})
            continue
        rows.append({**ident, **read})
    return rows, unreadable


def what_if_flips(rows: list[dict], leg: str, proposed: float) -> dict:
    """The exact marks a proposed threshold flips, both directions — derived
    from the leg registry's own comparison (EC-43: never a re-typed rule).

    The flip list is the artifact a threshold ruling is read from, so the
    proposed floor and EVERY flipped mark are formatted as one block (see
    ``fmt_block``): a raw float would print the operator 17 digits, a plain
    round would let a hinge mark render as the proposal itself, and a
    mark-by-mark pair would both collapse distinct hinge marks onto one string
    and print a floor the marks beneath it contradict. ``proposed_shown`` is
    the floor at that block's precision — the string the header must carry."""
    spec = GATE_LEG_INDEX[leg]
    op = _OPS[spec.op]
    flipped = []          # (measured, mark, newly-admitted?), in row order
    for row in rows:
        rec = next(r for r in row["legs"] if r["leg"] == leg)
        m = rec["measured"]
        if m is None:
            continue
        old_ok, new_ok = rec["ok"], op(m, proposed)
        if old_ok and not new_ok:
            flipped.append((m, f"{row['ticker']}@{row['as_of']}", False))
        elif new_ok and not old_ok:
            flipped.append((m, f"{row['ticker']}@{row['as_of']}", True))
    shown, proposed_shown = fmt_block([f[0] for f in flipped], proposed,
                                      spec.quantum)
    now_pass, would_pass = [], []
    for (_m, mark, admitted), measured in zip(flipped, shown):
        name = f"{mark} ({measured})"
        (would_pass if admitted else now_pass).append(name)
    return {"leg": leg, "proposed": proposed, "proposed_shown": proposed_shown,
            "newly_admitted": would_pass, "newly_refused": now_pass}


def pair_table(rows: list[dict]) -> dict:
    """Per knob: every mark's measured value beside the live floor, sorted so
    the hinge marks come first (the values nearest the threshold)."""
    out: dict = {}
    if not rows:
        return out
    for spec_leg in rows[0]["legs"]:
        leg = spec_leg["leg"]
        entries = []
        for row in rows:
            rec = next(r for r in row["legs"] if r["leg"] == leg)
            if rec["measured"] is None:
                continue
            entries.append({"mark": f"{row['ticker']}@{row['as_of']}",
                            "measured": rec["measured"],
                            "ok": rec["ok"]})
        threshold = spec_leg["threshold"]
        entries.sort(key=lambda e: abs(float(e["measured"]) - float(threshold)))
        out[leg] = {"threshold": threshold,
                    "op": GATE_LEG_INDEX[leg].op,
                    "n_pass": sum(1 for e in entries if e["ok"]),
                    "n": len(entries),
                    "marks": entries}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--ticker", help="limit to one ticker's marks")
    ap.add_argument("--what-if", dest="what_if", metavar="LEG=VALUE",
                    help="re-judge one leg at a proposed threshold and list "
                         "the marks that flip")
    ap.add_argument("--json", dest="json_out",
                    help="also dump the table + rows as a sidecar")
    args = ap.parse_args()
    # Pre-flight: a bad --what-if refuses BEFORE a single mark is scored.
    what_if = parse_what_if(args.what_if) if args.what_if else None

    session = database.SessionLocal()
    try:
        # The ONE validated loader, which stamps EXACTLY the set returned —
        # a filtered run claims only what it scored (EC-13).
        marks, fingerprint = load_box_marks(session, ticker=args.ticker)
    finally:
        session.close()
    rows, unreadable = judge_marks(marks)

    print("=" * 64)
    print("  KNOB PAIR TABLE - your marks vs the live floors")
    print("=" * 64)
    print(f"population: calibration-marks DB (box marks)  n_scored: {len(rows)}"
          f"  marks_fingerprint: {fingerprint[:16]}…")
    print(f"engine_config_version: {manifest_hash()[:16]}…\n")

    table = pair_table(rows)
    for leg, block in table.items():
        spec = GATE_LEG_INDEX[leg]
        listed = block["marks"][:5]       # the hinge marks first
        # The floor and the marks printed under it share ONE precision, so two
        # hinge marks a hair apart can never print as the same number.
        shown, threshold_shown = fmt_block([e["measured"] for e in listed],
                                           block["threshold"], spec.quantum)
        # The leg id stays (it is the --what-if input key), with the plain
        # phrase beside it and every number in the leg's native quantum.
        print(f"{leg}  ({leg_phrase(leg)} {spec.op} {threshold_shown})   "
              f"pass {block['n_pass']}/{block['n']}")
        for e, measured in zip(listed, shown):
            flag = "PASS" if e["ok"] else "FAIL"
            print(f"    {flag}  {e['mark']:<22} {measured}")
        if len(block["marks"]) > 5:
            print(f"    ... and {len(block['marks']) - 5} more "
                  "(full list in --json)")
    for row in rows:
        if row["blocking_sentence"]:
            # The episode clause is the read's OWN plain-words rendering
            # (``episode_summary`` — always a closed value), never the raw
            # ``sentence`` profile tape: that tape is machine vocabulary
            # ("S+ R^") and reaches no operator surface (council review
            # 2026-09-01, finding 3). One wording, served, never re-typed.
            print(f"\n  {row['ticker']}@{row['as_of']}: "
                  f"{row['blocking_sentence']}  |  {row['episode_summary']}")
    if unreadable:
        print("\nUNREADABLE (reported, never silently skipped):")
        for u in unreadable:
            print(f"    {u['ticker']}@{u['as_of']}: {u['why']}")

    result: dict = {"population": "calibration-marks DB (box marks)",
                    "marks_fingerprint": fingerprint,
                    "engine_config_version": manifest_hash(),
                    "n_scored": len(rows), "table": table,
                    "rows": rows, "unreadable": unreadable}
    if what_if:
        leg, proposed = what_if
        flips = what_if_flips(rows, leg, proposed)
        result["what_if"] = flips
        # The floor prints at the block's OWN precision (never formatted alone
        # — that is how a mark at 0.1449 came to sit under a floor of "0.14").
        print(f"\nWHAT-IF {leg} ({leg_phrase(leg)}) -> "
              f"{flips['proposed_shown']}:")
        print(f"  newly admitted: {flips['newly_admitted'] or '—'}")
        print(f"  newly refused:  {flips['newly_refused'] or '—'}")

    if args.json_out:
        path = refuse_sealed_output(args.json_out)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(result, fh, indent=1, sort_keys=True)
        print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
