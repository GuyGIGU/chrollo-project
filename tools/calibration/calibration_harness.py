"""Agreement harness — engine-vs-operator, per rule variant (Task 9).

The exploratory INSTRUMENT over the operator's EDITABLE calibration marks
(never the sealed docs/marks corpus — that population belongs to the
``tools.regression.marks_corpus`` ratchet GATE; every report here names its population
and stamps a fingerprint of the exact marks set it scored, so two reports are
either comparable or visibly not).

Per mark: validate loudly through the ONE shared judgment (a malformed row
ABORTS the batch naming the offender — a silently skipped mark shrinks every
denominator), verify the frozen frame's digest BEFORE scoring (basis first),
resolve the engine read at the mark's as-of with the frozen day-snap policy
(``core.calibration.replay.snapped_election``; changing snap semantics is a deliberate
re-freeze event, not a knob), and grade through the pure taxonomy
(``core.calibration.agreement``). All rule variants run in ONE walk per mark — the
baseline is never re-derived inside the variant loop.

This module is the command: loading and sealing the marks, the report and
its delta. The per-mark grading (``grade_one``, ``fired_one``) lives in
production, ``webapp/backend/domains/calibration/grading.py``, because the
workbench chips call the very same code — a chip can never drift from this
report.

``--fired`` (v2, opt-in) additionally replays each BOX mark through the FULL
nightly pipeline (``_evaluate_ticker`` — the marks-corpus gate's exact
decision) over the mark's fair window, answering the operator's actual
satisfaction bar: would this pick have popped up on the screener in real
trading time? Surfacing at election is necessary, not sufficient — this is
the sharper criterion the concordance headline points at. Deep
``knowable_from`` walks are clamped to the frame's faithful-basis zone
(every walked session must carry the full live daily-structure lead-in
inside the frozen frame; the clamp is named in the fragment) so a
thin-basis no-fire can never pose as an assessed miss.

Read-only by construction: marks load through the ORM (never hand-built
SQL), the session never commits, flag overrides self-restore, and the test
spine pins a full run byte-identical on the marks table.

    python -m tools.calibration.calibration_harness                       # live engine
    python -m tools.calibration.calibration_harness --fired               # + pops-up-live walk
    python -m tools.calibration.calibration_harness --variant BAND_RAILS_ENABLED=true
    python -m tools.calibration.calibration_harness --ticker BODI --json out.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

try:  # works under both `python -m tools.calibration.calibration_harness` and `python tools/calibration/calibration_harness.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path

_PROJECT_ROOT = configure_path(backend=True)

from core.calibration import agreement
from domains.calibration.grading import (  # the production grading the chips share
    FIRED_EVENT_TAIL_SESSIONS,
    FIRED_WALK_MAX_SESSIONS,
    FIRED_WINDOW_SESSIONS,
    HARNESS_POLICY_VERSION,
    SNAP_BACK_SESSIONS,
    _FROZEN_BREADTH,
    _FROZEN_SPY_6M,
    _mark_dict,
    fired_one,
    grade_one,
)
from engine_alpha.freeze.manifest import manifest_hash
from engine_alpha.election_identity import DEFAULT_RAIL_TOL_BOX_FRAC

# The seal's projection is FROZEN (EC-9). Widening it rotates every pinned
# fingerprint (guided_list_export, event_map_census, near_miss_census), and
# that is an operator re-pin decision made at a graduation sitting
# (decisions.md 2026-08-20: "never let a re-pin ride in on a fix commit") —
# never a side effect of completing the validation dict (``_mark_dict``). Recorded
# omissions awaiting that sitting: trigger_date/trigger_price (2026-08-20)
# and band_high/band_low (2026-08-28).
_SEAL_MARK_KEYS = (
    "ticker", "as_of_date", "label", "verdict", "resistance", "support",
    "box_start_date", "box_end_date", "r_anchor_date", "s_anchor_date",
    "first_rail", "rails_source", "knowable_from_date",
    "note", "data_regime", "engine_config_version", "anchor_close",
    "frame_digest")
_SEAL_EVENT_KEYS = ("event_type", "start_date", "end_date",
                    "tip_date", "tip_price", "source")


def _seal_projection(d: dict) -> dict:
    p = {k: d[k] for k in _SEAL_MARK_KEYS}
    p["events"] = [{k: e[k] for k in _SEAL_EVENT_KEYS} for e in d["events"]]
    return p


def marks_fingerprint(mark_dicts: list[dict]) -> str:
    """sha256 over the FROZEN projection of the exact marks set scored — the
    DB analog of the corpus seal. A changed fingerprint says 'the ground truth
    moved, not the engine'."""
    canon = json.dumps(sorted((_seal_projection(m) for m in mark_dicts),
                              key=lambda m: (
        m["ticker"], m["as_of_date"], m["label"])), sort_keys=True, default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def load_marks(session, ticker: str | None = None) -> list[dict]:
    """ORM read + loud validation: any invalid row aborts with its identity."""
    from marks_validity import validate_mark
    from models import CalibrationMark

    q = session.query(CalibrationMark).order_by(
        CalibrationMark.ticker, CalibrationMark.as_of_date, CalibrationMark.label)
    if ticker:
        q = q.filter(CalibrationMark.ticker == ticker.strip().upper())
    out = []
    for mark in q.all():
        d = _mark_dict(mark)
        problems = validate_mark(d)
        if problems:
            raise ValueError(
                f"calibration mark ({d['ticker']}, {d['as_of_date']}, "
                f"{d['label']!r}) is invalid — batch refused, fix the mark: "
                + "; ".join(problems))
        out.append(d)
    return out


def load_box_marks(session, ticker: str | None = None):
    """The marked-window instruments' shared ORM read (EC-3): box-verdict
    marks, each validated loudly through the ONE shared judgment (an invalid
    row aborts naming the offender — a silently skipped mark shrinks every
    denominator), sorted, plus the fingerprint of EXACTLY the rows returned
    (the harness stamp contract: a filtered report claims only what it
    scored). Rows stay ORM objects — the instruments read event children."""
    from marks_validity import validate_mark
    from models import CalibrationMark

    q = session.query(CalibrationMark).filter(CalibrationMark.verdict == "box")
    if ticker:
        q = q.filter(CalibrationMark.ticker == ticker.strip().upper())
    rows = sorted(q.all(), key=lambda m: (m.ticker, str(m.as_of_date), m.label or ""))
    dicts = [_mark_dict(m) for m in rows]
    for d in dicts:
        problems = validate_mark(d)
        if problems:
            raise ValueError(
                f"calibration mark ({d['ticker']}, {d['as_of_date']}, "
                f"{d['label']!r}) is invalid — batch refused, fix the mark: "
                + "; ".join(problems))
    return rows, marks_fingerprint(dicts)


def parse_variant(spec: str) -> dict:
    """'FLAG=true' -> {'FLAG': True}; values are bool/int/float literals."""
    name, _, raw = spec.partition("=")
    if not name or not raw:
        raise ValueError(f"--variant expects FLAG=VALUE, got {spec!r}")
    lowered = raw.strip().lower()
    if lowered in ("true", "false"):
        value = lowered == "true"
    else:
        value = float(raw) if "." in raw else int(raw)
    return {name.strip(): value}


def _print_delta(report: dict, prev: dict) -> None:
    """Per-mark movement vs a previous report, led by the ONE axis that moved
    (Friedman: the operator must never credit a grading fix as an engine
    improvement, or vice versa). Compares baseline-variant rows by mark key."""
    axes = []
    if prev.get("marks_fingerprint") != report["marks_fingerprint"]:
        axes.append("GROUND TRUTH moved (marks fingerprint changed)")
    if prev.get("harness_policy_version") != report["harness_policy_version"]:
        axes.append(f"MEASUREMENT moved (harness policy "
                    f"v{prev.get('harness_policy_version', 1)} -> "
                    f"v{report['harness_policy_version']})")
    if prev.get("engine_config_version") != report["engine_config_version"]:
        axes.append("ENGINE moved (config hash changed)")
    print("\n--- delta vs previous report "
          f"({prev.get('generated_at', 'undated')})")
    print("  attribution: " + ("; ".join(axes) if axes
                               else "no axis moved (same marks, policy, engine)"))
    prev_rows = {r["mark"]: r for r in
                 prev.get("variants", {}).get("baseline", {}).get("rows", [])}
    cur_rows = report["variants"].get("baseline", {}).get("rows", [])
    moved = 0
    for row in cur_rows:
        old = prev_rows.get(row["mark"])
        if old is None:
            print(f"    {row['mark']:<24} NEW MARK -> {row['outcome']}")
            moved += 1
            continue
        changes = []
        if old.get("outcome") != row.get("outcome"):
            changes.append(f"{old.get('outcome')} -> {row.get('outcome')}")
        if old.get("fired") != row.get("fired"):
            changes.append(f"fired {old.get('fired')} -> {row.get('fired')}")
        if changes:
            print(f"    {row['mark']:<24} " + "; ".join(changes))
            moved += 1
    if not moved:
        print("    no per-mark movement")


def run(ticker: str | None, variant_specs: list[str], json_out: str | None,
        *, fired: bool = False, prev_path: str | None = None) -> None:
    """Score and print the report. An INSTRUMENT, not a gate — there is no
    pass/fail; agreement regressions are read by humans, not exit codes."""
    import database  # noqa: PLC0415 — binds the live SQLite (read-only usage)

    if json_out:
        _refuse_sealed_output(json_out)

    variants: list[dict] = [{}] + [parse_variant(s) for s in variant_specs]
    labels = ["baseline"] + variant_specs

    session = database.SessionLocal()
    try:
        marks = load_marks(session, ticker)
    finally:
        session.close()   # released before any engine work; never committed
    if not marks:
        print("no calibration marks saved yet — mark charts on /calibration first")
        return

    fingerprint = marks_fingerprint(marks)
    t0 = time.perf_counter()
    per_variant: list[list[dict]] = [[] for _ in variants]
    for mark in marks:
        fired_frags = fired_one(mark, variants) if fired else None
        for i, row in enumerate(grade_one(mark, variants)):
            row["mark"] = f"{mark['ticker']}@{mark['as_of_date']}" + (
                f":{mark['label']}" if mark["label"] else "")
            row["verdict"] = mark["verdict"]
            if fired_frags and fired_frags[i] is not None:
                row.update(fired_frags[i])
                # Policy v2: a box that FIRED in-window but reads nothing at
                # the as-of snapshot is a consumed setup (breakout underway /
                # box retired), not engine blindness — name it so the report
                # never counts a correct pre-breakout fire as a miss.
                if row["outcome"] == "engine_no_read" and row.get("fired") is True:
                    row["detail"] = ("consumed — breakout underway "
                                     f"(fired {row.get('fire_date')})")
            per_variant[i].append(row)
    wall = time.perf_counter() - t0

    print("=" * 72)
    print("  AGREEMENT REPORT — population: CALIBRATION MARKS (editable; EC-9)")
    print("=" * 72)
    print(f"marks: {len(marks)}   fingerprint: {fingerprint[:16]}…")
    print(f"engine_config_version: {manifest_hash()[:16]}…   "
          f"harness_policy: v{HARNESS_POLICY_VERSION}   "
          f"rail_tol: {DEFAULT_RAIL_TOL_BOX_FRAC} box-height   "
          f"span_overlap_min: {agreement.DEFAULT_SPAN_OVERLAP_MIN}   "
          f"snap_back: {SNAP_BACK_SESSIONS}")
    if fired:
        print(f"fired policy: v{HARNESS_POLICY_VERSION} — marked-LPS event "
              f"windows +{FIRED_EVENT_TAIL_SESSIONS} tail, union last "
              f"{FIRED_WINDOW_SESSIONS} sessions (knowable_from overrides; "
              f"cap {FIRED_WALK_MAX_SESSIONS})   frozen breadth "
              f"{_FROZEN_BREADTH} / spy_6m {_FROZEN_SPY_6M} (scoring-only)")
    print(f"wall: {wall:.1f}s total, {wall / max(len(marks), 1):.2f}s/mark "
          f"x {len(variants)} variant(s)")
    report = {"population": "calibration_marks", "generated_at":
              datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "marks_fingerprint": fingerprint, "n_marks": len(marks),
              "engine_config_version": manifest_hash(),
              "harness_policy_version": HARNESS_POLICY_VERSION,
              "tolerances": {"rail_tol_box_frac": DEFAULT_RAIL_TOL_BOX_FRAC,
                             "span_overlap_min": agreement.DEFAULT_SPAN_OVERLAP_MIN,
                             "snap_back_sessions": SNAP_BACK_SESSIONS},
              "wall_seconds": round(wall, 2), "variants": {}}
    if fired:
        report["fired_policy"] = {"window_sessions": FIRED_WINDOW_SESSIONS,
                                  "event_tail_sessions": FIRED_EVENT_TAIL_SESSIONS,
                                  "max_walk_sessions": FIRED_WALK_MAX_SESSIONS,
                                  "frozen_breadth": _FROZEN_BREADTH,
                                  "frozen_spy_6m": _FROZEN_SPY_6M}
    for label, rows in zip(labels, per_variant):
        t = agreement.tally(rows)
        print(f"\n--- variant: {label}")
        counts = " ".join(f"{k}:{v}" for k, v in t["counts"].items() if v)
        print(f"  {counts or 'no outcomes'}")
        if t["surfaced_over_scored"] is not None:
            # The operator's satisfaction bar: his picks SURFACE (the engine
            # reads a setup there), not that rails replicate 1:1.
            surfaced = t["counts"]["match"] + t["counts"]["disagree"]
            print(f"  setups surfaced at his picks: {surfaced}/{t['n_scored_boxes']}")
        if t["match_over_scored"] is not None:
            print(f"  geometry-tier matches (diagnostic): "
                  f"{t['counts']['match']}/{t['n_scored_boxes']}")
        if t["upheld_over_negatives"] is not None:
            print(f"  negatives upheld: {t['counts']['negative_upheld']}/{t['n_negatives']}")
        if t["n_excluded"]:
            print(f"  excluded (basis/edge): {t['n_excluded']} — see rows")
        if fired:
            box_frags = [r for r in rows if "fired" in r]
            assessed = [r for r in box_frags if r["fired"] is not None]
            n_yes = sum(1 for r in assessed if r["fired"])
            line = f"  fired in window (pops-up-live): {n_yes}/{len(assessed)} box marks"
            if len(box_frags) > len(assessed):
                line += f"   unassessable: {len(box_frags) - len(assessed)}"
            print(line)
        for row in rows:
            extra = f" snapped={row['snapped']}" if row.get("snapped") else ""
            detail = f" [{row['detail']}]" if row.get("detail") else ""
            # Move 4: the refusal suffix renders on EVERY row that carries the
            # evidence — the fired walk's silent windows AND graded-only rows
            # (an edge_uncertain whose real cause is a universe gate must
            # never print as a bare frame-thin guess).
            pr = row.get("prep_refusals")
            refused_s = ""
            if pr:
                reasons = ", ".join(
                    f"{slug} x{n}" for slug, n in
                    sorted(pr["reasons"].items(), key=lambda kv: -kv[1]))
                refused_s = (f" | REFUSED(universe) "
                             f"{pr['refused']}/{pr['walked']}: {reasons}")
            fired_s = ""
            if "fired" in row:
                if row["fired"] is None:
                    fired_s = f" | fired:? ({row['fired_detail']})"
                elif row["fired"]:
                    at = ("his rails" if row.get("fire_rails_within_tol")
                          else f"off-tol rails R {row['fire_R']:.2f} "
                               f"S {row['fire_S']:.2f}")
                    fired_s = (f" | FIRED {row['fire_date']} "
                               f"tier {row['fire_tier']} ({at})")
                else:
                    fired_s = (f" | no fire in "
                               f"{row['fired_sessions_walked']}-session window"
                               + refused_s)
                if row.get("fired_window_clamped"):
                    fired_s += " [window clamped: thin lead-in]"
            elif refused_s:
                fired_s = refused_s
            print(f"    {row['mark']:<24} {row['verdict']:<13} -> "
                  f"{row['outcome']}{extra}{detail}{fired_s}")
        report["variants"][label] = {"tally": t, "rows": rows}
    if prev_path:
        with open(prev_path, "r", encoding="utf-8") as f:
            _print_delta(report, json.load(f))
    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nreport -> {json_out}")


def _refuse_sealed_output(json_out: str) -> None:
    """The one write this tool performs must never reach a sealed directory
    (EC-7/EC-9). Delegates to the ONE shared guard in tools._bootstrap."""
    from tools._bootstrap import refuse_sealed_output
    refuse_sealed_output(json_out)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Score engine-vs-operator agreement over the calibration "
                    "marks, per rule variant.")
    ap.add_argument("--ticker", default=None, help="only this ticker's marks")
    ap.add_argument("--variant", action="append", default=[],
                    help="FLAG=VALUE engine override, repeatable; baseline "
                         "always runs first")
    ap.add_argument("--json", default=None, help="also write the report JSON here")
    ap.add_argument("--fired", action="store_true",
                    help="also replay each box mark through the FULL pipeline "
                         "over its fair window (pops-up-live criterion; slower)")
    ap.add_argument("--prev", default=None,
                    help="previous report JSON — print per-mark deltas with the "
                         "moved axis named (ground truth / measurement / engine)")
    a = ap.parse_args()
    try:
        run(a.ticker, a.variant, a.json, fired=a.fired, prev_path=a.prev)
    except ValueError as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
