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

    python -m tools.calibration_harness                       # live engine
    python -m tools.calibration_harness --fired               # + pops-up-live walk
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

import pandas as pd

from config import settings
from core.freeze.manifest import manifest_hash
from core.pipeline.downloads import _trim_to_period
from core.pipeline.election_identity import (
    DEFAULT_RAIL_TOL_BOX_FRAC,
    projection,
    rails_match,
)
from tools import agreement, replay

# The day-snap policy is OWNED by the replay seam (one value, every
# instrument): re-exported here only for report stamping.
SNAP_BACK_SESSIONS = replay.SNAP_BACK_SESSIONS


def _mark_dict(mark) -> dict:
    """ORM row -> the model-shaped dict the shared judgment expects."""
    d = {c: getattr(mark, c) for c in (
        "ticker", "as_of_date", "label", "verdict", "resistance", "support",
        "box_start_date", "box_end_date", "r_anchor_date", "s_anchor_date",
        "first_rail", "rails_source", "knowable_from_date",
        "note", "data_regime", "engine_config_version", "anchor_close",
        "frame_digest")}
    # Events canonicalized by (type, start, end): the ORM returns children in
    # rowid order, and an edit delete-reinserts them in redraw order, so an
    # unsorted list would let a semantically-null redraw move the marks
    # fingerprint (the EC-9 seal) without the ground truth changing. Grading
    # never reads event order, so this only stabilizes the seal.
    d["events"] = [{
        "event_type": e.event_type, "start_date": e.start_date,
        "end_date": e.end_date, "tip_date": e.tip_date,
        "tip_price": e.tip_price, "source": e.source,
    } for e in sorted(mark.events, key=lambda e: (
        e.event_type or "", e.start_date or "", e.end_date or ""))]
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


# ---------------------------------------------------------------- fired (v2)
# The pops-up-live criterion (operator doctrine 2026-07-11): his bar is the
# ticker appearing in the nightly screener output, so the walk runs the FULL
# eval chain — structure, LPS, gates, scoring — not just the election. Opt-in
# (--fired) because a full eval costs ~1s/session; the walk is bounded and
# the report stamps the bound.
FIRED_WINDOW_SESSIONS = 10   # default backward window ending at the mark's as-of

# Frozen market scalars (marks-corpus twin): scoring-only inputs — they shape
# Score/Tier, never the fire/no-fire decision — pinned so the replay is
# deterministic and needs no SPY/breadth history alongside the frozen frame.
_FROZEN_BREADTH = 0.5
_FROZEN_SPY_6M = 0.0


def _full_live_basis(frozen: pd.DataFrame, ts) -> bool:
    """Does ``frozen.loc[:ts]`` contain the FULL trailing daily-structure
    window the nightly scan evaluated at ``ts``? The live eval trims the 5y
    cache to ``DAILY_STRUCTURE_PERIOD`` behind each session and the root walk
    is left-edge-sensitive, so a slice the trim cannot cut is thinner than
    live — unless the frame the trim cannot cut even at its END is simply the
    ticker's full (young-listing) history, in which case live saw the very
    same bars and every session is faithful."""
    sliced = frozen.loc[:ts]
    trimmed = _trim_to_period(sliced, settings.DAILY_STRUCTURE_PERIOD)
    if trimmed.index[0] > sliced.index[0]:
        return True   # the trim cut lead-in -> the live window is fully present
    full = _trim_to_period(frozen, settings.DAILY_STRUCTURE_PERIOD)
    return len(full) == len(frozen)


def _fired_sessions(frozen: pd.DataFrame, mark: dict) -> tuple[list, str | None]:
    """The mark's fair window as frame sessions ending at its as-of: from
    ``knowable_from_date`` when the mark declares one, else the last
    ``FIRED_WINDOW_SESSIONS`` sessions. Walked oldest-first so the reported
    fire is the FIRST night the pick would have appeared.

    A knowable_from walk is CLAMPED to the frame's faithful-basis zone
    (``_full_live_basis``): the marks-corpus gate freezes full history for
    exactly this reason, and a thin-basis no-fire silently counted as
    assessed would deflate the pops-up-live headline on precisely the marks
    with the widest fair windows. Returns ``(sessions, clamp_note|None)`` —
    the clamp is always NAMED, never silent."""
    idx = frozen.index[frozen.index <= pd.Timestamp(mark["as_of_date"])]
    knowable = mark.get("knowable_from_date")
    if not knowable:
        return list(idx[-FIRED_WINDOW_SESSIONS:]), None
    sessions = list(idx[idx >= pd.Timestamp(knowable)])
    faithful = [ts for ts in sessions if _full_live_basis(frozen, ts)]
    if len(faithful) == len(sessions):
        return sessions, None
    note = (f"walked {len(faithful)}/{len(sessions)} sessions — the frozen "
            f"frame's lead-in cannot reproduce the live "
            f"{settings.DAILY_STRUCTURE_PERIOD} basis before "
            + (faithful[0].strftime("%Y-%m-%d") if faithful else "any session"))
    return faithful, note


def fired_one(mark: dict, variants: list[dict], *, frame_loader=None,
              evaluate=None) -> list:
    """One BOX mark through the FULL pipeline, per variant (harness v2).

    Non-box marks return None fragments: a negative asserts a no-read at ONE
    session and keeps its election-level grade — window-hunting sessions to
    convict a negative would bias it (the grade_one policy, held here too).

    Returns one fragment per variant: ``fired`` True/False/None(unassessable)
    plus diagnostics. Sessions whose frozen lead-in cannot reproduce the live
    daily-structure basis are clamped OUT of the walk and the clamp named in
    the fragment; inside that faithful zone the pipeline's own floors decide
    — the walk never second-guesses the eval.
    """
    if mark["verdict"] != "box":
        return [None for _ in variants]

    from webapp.backend import frame_store
    from core.pipeline.evaluation import EVAL_ERROR

    if evaluate is None:
        from core.pipeline.evaluation import _evaluate_ticker

        def evaluate(ticker, sliced):
            return _evaluate_ticker(ticker, sliced, _FROZEN_SPY_6M, _FROZEN_BREADTH)

    loader = frame_loader or frame_store.load_frame
    frozen = loader(mark["ticker"], mark["as_of_date"],
                    digest=mark.get("frame_digest"))
    if frozen is None:
        return [{"fired": None, "fired_detail": "basis_mismatch — no frozen "
                                                "frame matches this mark's digest"}
                for _ in variants]
    sessions, clamp_note = _fired_sessions(frozen, mark)
    if not sessions:
        return [{"fired": None,
                 "fired_detail": "no frame sessions inside the fair window"}
                for _ in variants]
    window = [sessions[0].strftime("%Y-%m-%d"), sessions[-1].strftime("%Y-%m-%d")]

    fragments = []
    for variant in variants:
        frag: dict = {"fired": False, "fired_window": window,
                      "fired_sessions_walked": len(sessions)}
        with replay.flag_capture(**variant):
            for ts in sessions:
                result = evaluate(mark["ticker"], frozen.loc[:ts])
                if result is EVAL_ERROR:
                    frag = {"fired": None, "fired_window": window,
                            "fired_detail": f"EVAL_ERROR at {ts.date()} — a crash "
                                            "is neither a hit nor a miss"}
                    break
                if result is None:
                    continue
                fire_date = ts.strftime("%Y-%m-%d")
                # Diagnostic tier, never the pass bar: did it fire at HIS
                # geometry? A fire whose LPS re-anchored to the tighter inner
                # box IS a fire at that shelf — his rails may be the inner
                # pair, so both framings are consulted. The fired rails ride
                # along so a near-miss (a rail 0.18 box-heights off) stays
                # distinguishable from a different base without a re-run.
                on_parent = rails_match(
                    mark["resistance"], mark["support"],
                    result["_R"], result["_S"],
                    tol_box_frac=DEFAULT_RAIL_TOL_BOX_FRAC)
                inner_r, inner_s = result.get("_inner_R"), result.get("_inner_S")
                on_inner = (bool(result.get("_lps_in_inner"))
                            and inner_r is not None and inner_s is not None
                            and rails_match(mark["resistance"], mark["support"],
                                            inner_r, inner_s,
                                            tol_box_frac=DEFAULT_RAIL_TOL_BOX_FRAC))
                frag = {
                    "fired": agreement.fired_inside_window(
                        fire_date, mark.get("knowable_from_date"),
                        mark["as_of_date"]),
                    "fired_window": window,
                    "fire_date": fire_date,
                    "fire_tier": result.get("Tier"),
                    "fire_score": result.get("Score"),
                    "fire_R": float(result["_R"]),
                    "fire_S": float(result["_S"]),
                    "fire_lps_in_inner": bool(result.get("_lps_in_inner")),
                    "fire_rails_within_tol": bool(on_parent or on_inner),
                }
                if inner_r is not None and inner_s is not None:
                    frag["fire_inner_R"] = float(inner_r)
                    frag["fire_inner_S"] = float(inner_s)
                break
        if clamp_note:
            frag["fired_window_clamped"] = clamp_note
        fragments.append(frag)
    return fragments


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


def run(ticker: str | None, variant_specs: list[str], json_out: str | None,
        *, fired: bool = False) -> None:
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
    if fired:
        print(f"fired policy: window {FIRED_WINDOW_SESSIONS} sessions "
              f"(knowable_from overrides)   frozen breadth {_FROZEN_BREADTH} / "
              f"spy_6m {_FROZEN_SPY_6M} (scoring-only)")
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
    if fired:
        report["fired_policy"] = {"window_sessions": FIRED_WINDOW_SESSIONS,
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
                               f"{row['fired_sessions_walked']}-session window")
                if row.get("fired_window_clamped"):
                    fired_s += " [window clamped: thin lead-in]"
            print(f"    {row['mark']:<24} {row['verdict']:<13} -> "
                  f"{row['outcome']}{extra}{detail}{fired_s}")
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
    ap.add_argument("--fired", action="store_true",
                    help="also replay each box mark through the FULL pipeline "
                         "over its fair window (pops-up-live criterion; slower)")
    a = ap.parse_args()
    try:
        run(a.ticker, a.variant, a.json, fired=a.fired)
    except ValueError as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
