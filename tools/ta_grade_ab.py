"""The TA-grade A/B flip instrument (TA-grade build task 13) — the decision
surface the operator's flip eyeball consumes.

One archived live fire = one fixed-shape row: the OLD score/tier as stored
(as-seen provenance, never recomputed), the NEW 0-100 computed from the SAME
row's archived facts (per-term points, event-map scalars, HTF state — the
grade is a pure function of them, so this is read-only replay, no chart is
re-read), and the rank-order delta over the scan's own fire list (the honest
unit the operator actually scans). ``--top`` drills the biggest movers into
their per-chapter points, promoted-term points, and warning costs — what v2
sees that v1 didn't, and vice versa (breadth leaving the number is the one
structural subtraction).

McKinney's two rank diffs stay STRICTLY apart:
  * the AFFINE IDENTITY — ordering by the computed 0-100 must equal ordering
    by the computed raw sum, exactly; a violation is a BUG (exit 2, loud
    banner), never "movement";
  * the v1→v2 MOVEMENT — expected to be nonzero (story terms, warnings,
    breadth's exit); it is the thing the operator judges, reported per row.

Integrity: read-only against the archive (EC-9 one-way stays intact);
stamps engine_config_version + the EXACT population scored (EC-13);
``--json`` passes the sealed-output guard (EC-14). Empty is an affirmative
report (which scan dates exist, how fires appear), never silence. The flip
decision's evidence is distilled into a committed docs/ record before the
flag-ledger row cites it (EC-15/16 — the task-15 choreography).

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.ta_grade_ab                    # latest archived scan
    python -m tools.ta_grade_ab --scan-date 2026-08-07
    python -m tools.ta_grade_ab --top 10           # drill the biggest movers
    python -m tools.ta_grade_ab --json OUT.json
"""
from __future__ import annotations

import argparse
import json

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    from _bootstrap import configure_path, refuse_sealed_output

configure_path(backend=True)

from config import settings                                   # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash        # noqa: E402
from engine_alpha.scoring import taxonomy                     # noqa: E402
from engine_alpha.scoring.scoring import compose_ta_grade     # noqa: E402


def _row_grade(row) -> dict:
    """The would-be v2 grade for one archived fire, from its OWN row.

    The archived facts are the as-of scalars the live composite consumes
    (AP-8 basis); the sub-score columns carry the scored term points. The
    registry's flag-gated terms must be emitted for the WOULD-BE read, so
    the flag is forced ON in this process only (a read-only report; nothing
    persists)."""
    sub = {t.key: getattr(row, t.column)
           for t in taxonomy.REGISTRY if t.present_when is None}
    event_map = {
        col: getattr(row, col)
        for col in ("event_map_completed_s", "event_map_completed_r",
                    "event_map_alternations", "event_map_terminal_posture",
                    "event_map_terminal_drift", "event_map_episode_nan_bars")
    }
    htf = {"htf_m_trend_state": getattr(row, "htf_m_trend_state", None)}
    return compose_ta_grade(
        sub,
        has_spring=bool(getattr(row, "bin_c_present", None)),
        event_map=event_map if any(v is not None for v in event_map.values()) else None,
        htf=htf if htf["htf_m_trend_state"] is not None else None,
    )


def _ranks(keyed: list) -> dict:
    """{ticker: 1-based rank} for a (sort_value desc, ticker asc) order."""
    ordered = sorted(keyed, key=lambda kv: (-kv[1], kv[0]))
    return {ticker: i + 1 for i, (ticker, _v) in enumerate(ordered)}


def build_report(session, scan_date: str | None) -> dict:
    from archive_models import SetupArchive

    dates = [d for (d,) in session.query(SetupArchive.scan_date)
             .distinct().order_by(SetupArchive.scan_date.desc()).limit(10)]
    if scan_date is None:
        scan_date = dates[0] if dates else None
    if scan_date is None:
        return {"scan_date": None, "rows": [], "recent_dates": [],
                "engine_config_version": manifest_hash(), "identity_ok": True}

    rows = (session.query(SetupArchive)
            .filter(SetupArchive.scan_date == scan_date).all())

    # In-process only, restored after the read (nothing persists; the flag
    # must be ON so the registry emits the flag-gated terms for the
    # would-be composite).
    prev_flag = settings.TA_SCORE_V2
    settings.TA_SCORE_V2 = True
    graded = []
    try:
        for row in rows:
            grade = _row_grade(row)
            graded.append({
                "ticker": row.ticker,
                "source": row.source,
                "old_score": row.score,
                "old_tier": row.tier,
                "ta_grade": grade["ta_grade"],
                "ta_grade_raw": grade["ta_grade_raw"],
                "chapters": grade["ta_grade_chapters"],
                "warnings": grade["ta_grade_warnings"],
                "promoted": {t.key: grade.get(t.key) for t in taxonomy.REGISTRY
                             if t.present_when == "TA_SCORE_V2"},
                "breadth_excluded": sub_breadth(row),
            })
    finally:
        settings.TA_SCORE_V2 = prev_flag

    old_ranks = _ranks([(g["ticker"], g["old_score"] or 0.0) for g in graded])
    new_ranks = _ranks([(g["ticker"], g["ta_grade"]) for g in graded])
    raw_ranks = _ranks([(g["ticker"], g["ta_grade_raw"]) for g in graded])
    for g in graded:
        g["rank_old"] = old_ranks[g["ticker"]]
        g["rank_new"] = new_ranks[g["ticker"]]
        g["rank_delta"] = g["rank_old"] - g["rank_new"]   # + = climbed under v2

    # The affine identity: the normalized ordering must equal the raw
    # ordering EXACTLY. A violation is a bug in the map, never "movement".
    identity_ok = all(new_ranks[t] == raw_ranks[t] for t in new_ranks)

    graded.sort(key=lambda g: g["rank_new"])
    by_source: dict = {}
    for g in graded:
        by_source[g["source"] or "?"] = by_source.get(g["source"] or "?", 0) + 1
    return {
        "scan_date": scan_date,
        "recent_dates": dates,
        "rows": graded,
        "population": {"n": len(graded), "by_source": by_source},
        "engine_config_version": manifest_hash(),
        "identity_ok": identity_ok,
        "basis": "computed from archived facts (read-only would-be replay)",
    }


def sub_breadth(row):
    value = getattr(row, "score_breadth_bonus", None)
    return float(value) if value is not None else None


def _print_report(report: dict, top: int) -> None:
    print("TA-grade A/B — old score/tier vs the would-be 0-100 per archived fire")
    print(f"engine_config_version: {report['engine_config_version']}")
    if not report["rows"]:
        print(f"\n0 fires for scan_date={report['scan_date']!r} — an affirmative empty:")
        print("  recent archived scan dates:",
              ", ".join(report["recent_dates"]) or "(archive is empty)")
        print("  fires appear when the nightly scan archives; pass --scan-date "
              "to target one of the dates above.")
        return
    pop = report["population"]
    print(f"scan_date {report['scan_date']} — {pop['n']} fires "
          f"({', '.join(f'{k}:{v}' for k, v in sorted(pop['by_source'].items()))}); "
          f"basis: {report['basis']}")
    if not report["identity_ok"]:
        print("\n*** AFFINE IDENTITY VIOLATED — the 0-100 ordering differs from "
              "the raw ordering. This is a BUG in the map, not movement. ***")
    print(f"\n{'ticker':<8}{'old':>8}{'tier':>6}{'ta_grade':>10}{'rank Δ':>8}  warnings")
    for g in report["rows"]:
        warn = ",".join(g["warnings"]) if g["warnings"] else "-"
        print(f"{g['ticker']:<8}{g['old_score'] or 0:>8.1f}{g['old_tier'] or '?':>6}"
              f"{g['ta_grade']:>10.1f}{g['rank_delta']:>+8d}  {warn}")
    movers = sorted(report["rows"], key=lambda g: -abs(g["rank_delta"]))[:top]
    if movers and top > 0:
        print(f"\ntop {len(movers)} movers — per-chapter points (the drill):")
        for g in movers:
            ch = " ".join(f"{k[:2]}:{v:.1f}" for k, v in g["chapters"].items())
            promoted = " ".join(f"{k}:{v:.1f}" for k, v in g["promoted"].items()
                                if v not in (None, 0.0))
            extra = f" | promoted {promoted}" if promoted else ""
            breadth = (f" | breadth excluded {g['breadth_excluded']:.1f}"
                       if g["breadth_excluded"] else "")
            print(f"  {g['ticker']:<8} Δ{g['rank_delta']:+d}  {ch}{extra}{breadth}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.ta_grade_ab")
    parser.add_argument("--scan-date", default=None)
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--json", default=None,
                        help="write the full report as JSON (sealed-output guarded)")
    args = parser.parse_args(argv)

    import database
    session = database.SessionLocal()
    try:
        report = build_report(session, args.scan_date)
    finally:
        session.close()

    if args.json:
        path = refuse_sealed_output(args.json)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"wrote {path} ({len(report['rows'])} rows)")
    else:
        _print_report(report, args.top)
    return 0 if report["identity_ok"] else 2


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
