"""Agreement harness — engine-vs-operator, per rule variant (Task 9).

The exploratory INSTRUMENT over the operator's EDITABLE calibration marks
(never the sealed docs/marks corpus — that population belongs to the
``tools.marks_corpus`` ratchet GATE; every report here names its population
and stamps a fingerprint of the exact marks set it scored, so two reports are
either comparable or visibly not).

Per mark: validate loudly through the ONE shared judgment (a malformed row
ABORTS the batch naming the offender — a silently skipped mark shrinks every
denominator), verify the frozen frame's digest BEFORE scoring (basis first),
resolve the engine read at the mark's as-of with the frozen day-snap policy
(``tools.replay.snapped_election``; changing snap semantics is a deliberate
re-freeze event, not a knob), and grade through the pure taxonomy
(``tools.agreement``). All rule variants run in ONE walk per mark — the
baseline is never re-derived inside the variant loop.

Read-only by construction: marks load through the ORM (never hand-built
SQL), the session never commits, and the test spine pins a full run
byte-identical on the marks table.

    python -m tools.calibration_harness                       # live engine
    python -m tools.calibration_harness --variant BAND_RAILS_ENABLED=true
    python -m tools.calibration_harness --ticker BODI --json out.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone

try:
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path()

import os

sys.path.insert(1, os.path.join(_PROJECT_ROOT, "webapp", "backend"))

from core.freeze.manifest import manifest_hash
from core.pipeline.election_identity import DEFAULT_RAIL_TOL_BOX_FRAC, projection
from tools import agreement, replay

# The day-snap policy is OWNED by the replay seam (one value, every
# instrument): re-exported here only for report stamping.
SNAP_BACK_SESSIONS = replay.SNAP_BACK_SESSIONS


def _mark_dict(mark) -> dict:
    """ORM row -> the model-shaped dict the shared judgment expects."""
    d = {c: getattr(mark, c) for c in (
        "ticker", "as_of_date", "label", "verdict", "resistance", "support",
        "box_start_date", "box_end_date", "rails_source", "knowable_from_date",
        "note", "data_regime", "engine_config_version", "anchor_close",
        "frame_digest")}
    d["events"] = [{
        "event_type": e.event_type, "start_date": e.start_date,
        "end_date": e.end_date, "tip_date": e.tip_date,
        "tip_price": e.tip_price, "source": e.source,
    } for e in mark.events]
    return d


def marks_fingerprint(mark_dicts: list[dict]) -> str:
    """sha256 over the exact marks set scored — the DB analog of the corpus
    seal. A changed fingerprint says 'the ground truth moved, not the engine'."""
    canon = json.dumps(sorted(mark_dicts, key=lambda m: (
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


def grade_one(mark: dict, variants: list[dict], *, frame_loader=None,
              election=replay.snapped_election) -> list[dict]:
    """One mark graded under every variant (ONE snapped walk). Returns one
    row per variant: {outcome, ..., snapped, eval_session}."""
    from webapp.backend import frame_store

    # Digest-resolved load: the store returns whichever frozen rendering
    # matches THIS mark's digest (the base freeze, or the restatement sibling
    # it was actually drawn on) — a mark is never silently replayed on bars
    # its rails weren't drawn against.
    loader = frame_loader or frame_store.load_frame
    frozen = loader(mark["ticker"], mark["as_of_date"],
                    digest=mark.get("frame_digest"))
    if frozen is None:
        return [agreement.ungraded("basis_mismatch",
                                   "no frozen frame matches this mark's digest — "
                                   "the frame store lost its basis")
                for _ in variants]

    # Negative verdicts assert "the engine reads nothing at THIS session" and
    # are graded there only (snap 0). The snap-back walk exists for box
    # verdicts — day-sensitive elections must be shown where they EXIST;
    # hunting prior sessions to convict a negative would bias
    # upheld_over_negatives on days the operator asserted nothing about.
    # Changing either policy is a deliberate re-freeze event.
    snap = SNAP_BACK_SESSIONS if mark["verdict"] == "box" else 0
    snapped = election(frozen, mark["as_of_date"], variants, snap_back=snap)
    if snapped is None:
        return [agreement.ungraded("edge_uncertain",
                                   "prep refuses every candidate session "
                                   "(frame too thin)")
                for _ in variants]
    (df, _atr, reads), eval_ts, snapped_k = snapped
    frame_start = df.index[0].strftime("%Y-%m-%d")
    rows = []
    for read in reads:
        g = agreement.grade_mark(mark, projection(read, df),
                                 frame_start=frame_start)
        g.update({"eval_session": eval_ts.strftime("%Y-%m-%d"),
                  "snapped": snapped_k})
        rows.append(g)
    return rows


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


def run(ticker: str | None, variant_specs: list[str], json_out: str | None) -> None:
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
        for i, row in enumerate(grade_one(mark, variants)):
            row["mark"] = f"{mark['ticker']}@{mark['as_of_date']}" + (
                f":{mark['label']}" if mark["label"] else "")
            row["verdict"] = mark["verdict"]
            per_variant[i].append(row)
    wall = time.perf_counter() - t0

    print("=" * 72)
    print("  AGREEMENT REPORT — population: CALIBRATION MARKS (editable; EC-9)")
    print("=" * 72)
    print(f"marks: {len(marks)}   fingerprint: {fingerprint[:16]}…")
    print(f"engine_config_version: {manifest_hash()[:16]}…   "
          f"rail_tol: {DEFAULT_RAIL_TOL_BOX_FRAC} box-height   "
          f"span_overlap_min: {agreement.DEFAULT_SPAN_OVERLAP_MIN}   "
          f"snap_back: {SNAP_BACK_SESSIONS}")
    print(f"wall: {wall:.1f}s total, {wall / max(len(marks), 1):.2f}s/mark "
          f"x {len(variants)} variant(s)")
    report = {"population": "calibration_marks", "generated_at":
              datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "marks_fingerprint": fingerprint, "n_marks": len(marks),
              "engine_config_version": manifest_hash(),
              "tolerances": {"rail_tol_box_frac": DEFAULT_RAIL_TOL_BOX_FRAC,
                             "span_overlap_min": agreement.DEFAULT_SPAN_OVERLAP_MIN,
                             "snap_back_sessions": SNAP_BACK_SESSIONS},
              "wall_seconds": round(wall, 2), "variants": {}}
    for label, rows in zip(labels, per_variant):
        t = agreement.tally(rows)
        print(f"\n--- variant: {label}")
        counts = " ".join(f"{k}:{v}" for k, v in t["counts"].items() if v)
        print(f"  {counts or 'no outcomes'}")
        if t["match_over_scored"] is not None:
            print(f"  boxes matched: {t['counts']['match']}/{t['n_scored_boxes']}")
        if t["upheld_over_negatives"] is not None:
            print(f"  negatives upheld: {t['counts']['negative_upheld']}/{t['n_negatives']}")
        if t["n_excluded"]:
            print(f"  excluded (basis/edge): {t['n_excluded']} — see rows")
        for row in rows:
            extra = f" snapped={row['snapped']}" if row.get("snapped") else ""
            detail = f" [{row['detail']}]" if row.get("detail") else ""
            print(f"    {row['mark']:<24} {row['verdict']:<13} -> "
                  f"{row['outcome']}{extra}{detail}")
        report["variants"][label] = {"tally": t, "rows": rows}
    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nreport -> {json_out}")


def _refuse_sealed_output(json_out: str) -> None:
    """The one write this tool performs must never reach the sealed corpus
    (EC-7/EC-9): a mistyped --json path could clobber a docs/marks spec."""
    sealed = os.path.abspath(os.path.join(_PROJECT_ROOT, "docs", "marks"))
    target = os.path.abspath(json_out)
    if target == sealed or target.startswith(sealed + os.sep):
        raise ValueError(f"--json refuses paths under the sealed corpus "
                         f"({sealed}) — write the report elsewhere")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Score engine-vs-operator agreement over the calibration "
                    "marks, per rule variant.")
    ap.add_argument("--ticker", default=None, help="only this ticker's marks")
    ap.add_argument("--variant", action="append", default=[],
                    help="FLAG=VALUE engine override, repeatable; baseline "
                         "always runs first")
    ap.add_argument("--json", default=None, help="also write the report JSON here")
    a = ap.parse_args()
    try:
        run(a.ticker, a.variant, a.json)
    except ValueError as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
