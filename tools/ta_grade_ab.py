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
  * the AFFINE IDENTITY — ordering by the PRE-WARNING normalized grade (the
    chapter subtotals' sum — the affine image of raw) must equal ordering by
    the computed raw sum, exactly; a violation is a BUG (exit 2, verdict
    printed on BOTH output modes), never "movement". The post-warning
    headline is raw × per-row warning factors — NOT affine — so
    warning-driven reordering reports as movement, never as a bug;
  * the v1→v2 MOVEMENT — expected to be nonzero (story terms, warnings,
    breadth's exit); it is the thing the operator judges, reported per row.

Population discipline (EC-13): ONE universe (the equities default), the
scored row set fingerprinted, the config hash stamped INSIDE the forced-flag
window so it names the configuration that produced the numbers.

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


def _identity_ranks(graded: list) -> tuple[dict, dict]:
    """The affine identity's two rank orders, on QUANTIZED operands.

    raw accumulates term-by-term while prewarn sums the chapter subtotals, so
    two rows whose TRUE sums are equal can land ~1e-14 apart in one operand
    and bit-identical in the other — the noisy operand splits them, the tied
    operand falls back to the ticker tiebreak, and the identity false-alarms
    exit 2 (first live population, 2026-08-08: OHI/NTES both truly raw
    84.28). 1e-9 sits orders of magnitude above float noise and below any
    real term-point distinction; a genuine affine break (a per-chapter
    clamp/floor) moves points, not 1e-14s."""
    raw = _ranks([(g["ticker"], round(g["ta_grade_raw"], 9)) for g in graded])
    prewarn = _ranks([(g["ticker"], round(g["ta_grade_prewarn"], 9))
                      for g in graded])
    return raw, prewarn


def build_report(session, scan_date: str | None) -> dict:
    import hashlib

    from archive_models import SetupArchive
    from core.pipeline.universe import default_universe_type

    # The population is ONE universe — the equities default (EC-1 one
    # source). Without the scope, ETF/sector rows sharing the scan_date
    # pooled into the rank list and a cross-universe ticker collision could
    # silently collapse two rows onto one rank entry (2026-08-08 review,
    # finding 7); every sibling decision surface already scopes this way.
    universe = default_universe_type()
    dates = [d for (d,) in session.query(SetupArchive.scan_date)
             .filter(SetupArchive.universe_type == universe)
             .distinct().order_by(SetupArchive.scan_date.desc()).limit(10)]
    if scan_date is None:
        scan_date = dates[0] if dates else None
    if scan_date is None:
        return {"scan_date": None, "universe_type": universe, "rows": [],
                "recent_dates": [], "setup_quality_absent_rows": 0,
                "engine_config_version": manifest_hash(), "identity_ok": True}

    rows = (session.query(SetupArchive)
            .filter(SetupArchive.scan_date == scan_date,
                    SetupArchive.universe_type == universe).all())

    # setup_quality is the ONE replay input younger than the archive: rows
    # archived before the grade columns existed carry it NULL, the replay
    # grades it absence-neutral 0, and the stored v1 score still contains its
    # points — so on such rows the v1→v2 rank movement is the missing setup-quality
    # differential, not the grade's opinion (first live A/B, 2026-08-08: the
    # entire ±31 movers list was exactly this). Counted here, bannered on
    # every output mode below.
    setup_quality_absent = sum(
        1 for r in rows if getattr(r, "score_setup_quality", None) is None)

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
                # Pre-warning normalized grade — the chapters sum to it
                # exactly; this is the affine image of raw, so THIS is the
                # identity check's operand (the post-warning headline may
                # legitimately reorder once TA_WARN_* costs land).
                "ta_grade_prewarn": sum(
                    grade["ta_grade_chapters"].values()),
                "chapters": grade["ta_grade_chapters"],
                "warnings": grade["ta_grade_warnings"],
                "promoted": {t.key: grade.get(t.key) for t in taxonomy.REGISTRY
                             if t.present_when == "TA_SCORE_V2"},
                "breadth_excluded": sub_breadth(row),
            })
        # Stamped INSIDE the forced-flag window so the hash names the
        # configuration that actually produced these numbers (the would-be
        # flag-on config — pre-flip, hashing after the restore stamped the
        # flag-OFF config; 2026-08-08 review, finding 7).
        ecv = manifest_hash()
    finally:
        settings.TA_SCORE_V2 = prev_flag

    # Identity within one universe+date is unique by the archive's index;
    # keep it loud rather than assumed (bare-ticker rank keys collapse on
    # a collision and would mask the identity tripwire).
    tickers = [g["ticker"] for g in graded]
    if len(set(tickers)) != len(tickers):
        raise RuntimeError(
            f"duplicate ticker(s) in the {universe} {scan_date} population — "
            "rank keys would collide; the archive identity index is broken")

    old_ranks = _ranks([(g["ticker"], g["old_score"] or 0.0) for g in graded])
    new_ranks = _ranks([(g["ticker"], g["ta_grade"]) for g in graded])
    raw_ranks, prewarn_ranks = _identity_ranks(graded)
    for g in graded:
        g["rank_old"] = old_ranks[g["ticker"]]
        g["rank_new"] = new_ranks[g["ticker"]]
        g["rank_delta"] = g["rank_old"] - g["rank_new"]   # + = climbed under v2

    # The affine identity: the PRE-WARNING normalized ordering must equal the
    # raw ordering EXACTLY — that pair is the affine map. A violation is a
    # bug in the map, never "movement". (The post-warning headline is raw ×
    # per-row warning factors — NOT affine — so warning-driven reordering
    # reports as movement, where the operator judges it; 2026-08-08 review,
    # finding 2: checking the headline here false-alarmed the day a
    # TA_WARN_* cost landed.)
    identity_ok = all(prewarn_ranks[t] == raw_ranks[t] for t in prewarn_ranks)

    graded.sort(key=lambda g: g["rank_new"])
    by_source: dict = {}
    for g in graded:
        by_source[g["source"] or "?"] = by_source.get(g["source"] or "?", 0) + 1
    # EC-13: fingerprint EXACTLY the row set scored — the archive population
    # for a date is mutable after the fact (manual adds, seed overwrites),
    # and two runs must be distinguishable by their stamps alone.
    fingerprint = hashlib.sha256("|".join(
        sorted(f"{r.id}:{r.ticker}" for r in rows)).encode()).hexdigest()[:16]
    return {
        "scan_date": scan_date,
        "universe_type": universe,
        "recent_dates": dates,
        "rows": graded,
        "setup_quality_absent_rows": setup_quality_absent,
        "population": {"n": len(graded), "by_source": by_source,
                       "fingerprint": fingerprint},
        "engine_config_version": ecv,
        "config_basis": "TA_SCORE_V2 forced ON in-process for the would-be replay",
        "identity_ok": identity_ok,
        "basis": "computed from archived facts (read-only would-be replay)",
    }


def sub_breadth(row):
    value = getattr(row, "score_breadth_bonus", None)
    return float(value) if value is not None else None


def _warn_cell(warnings: dict) -> str:
    """Warnings with their COST visible — a fired-but-neutral warning (factor
    1.0, costs nothing until the operator's A/B) must never impersonate a
    costed discount on the decision surface (2026-08-08 review, finding 11)."""
    if not warnings:
        return "-"
    parts = []
    for wid, factor in warnings.items():
        try:
            f = float(factor)
        except (TypeError, ValueError):
            parts.append(f"{wid}:?")
            continue
        parts.append(f"{wid}:neutral" if f >= 1.0
                     else f"{wid}:-{round((1.0 - f) * 100)}%")
    return ",".join(parts)


def _basis_banner_lines(report: dict) -> list[str]:
    """The epoch-basis note, spoken on EVERY output mode (the finding-2 rule:
    an operator reads words, not exit codes or JSON fields)."""
    n = report.get("setup_quality_absent_rows", 0)
    if not n or not report["rows"]:
        return []
    total = len(report["rows"])
    which = f"ALL {total}" if n == total else f"{n} of {total}"
    return [f"note: {which} rows carry no archived setup_quality (they "
            "predate the grade columns) — the replay grades setup_quality as "
            "neutral 0 there while the stored v1 score still contains its "
            "points, so the rank Δ column includes the missing setup-quality "
            "differential. Judge movement on a scan archived by the merged "
            "code."]


def _identity_verdict_lines(report: dict) -> list[str]:
    """The identity verdict, spoken on EVERY output mode — --json runs used
    to file the violation silently into the evidence record (finding 2)."""
    if report["identity_ok"]:
        return ["affine identity: OK (pre-warning ordering == raw ordering)"]
    return ["*** AFFINE IDENTITY VIOLATED — the pre-warning ordering differs "
            "from the raw ordering. This is a BUG in the map, not movement. "
            "(exit code 2) ***"]


def _print_report(report: dict, top: int) -> None:
    print("TA-grade A/B — old score/tier vs the would-be 0-100 per archived fire")
    print(f"engine_config_version: {report['engine_config_version']} "
          f"({report.get('config_basis', '')})")
    if not report["rows"]:
        print(f"\n0 fires for scan_date={report['scan_date']!r} — an affirmative empty:")
        print("  recent archived scan dates:",
              ", ".join(report["recent_dates"]) or "(archive is empty)")
        print("  fires appear when the nightly scan archives; pass --scan-date "
              "to target one of the dates above.")
        return
    pop = report["population"]
    print(f"scan_date {report['scan_date']} ({report['universe_type']}) — "
          f"{pop['n']} fires "
          f"({', '.join(f'{k}:{v}' for k, v in sorted(pop['by_source'].items()))}, "
          f"fingerprint {pop['fingerprint']}); basis: {report['basis']}")
    for line in _basis_banner_lines(report):
        print("\n" + line)
    for line in _identity_verdict_lines(report):
        print("\n" + line)
    print("rank Δ legend: + = climbed under v2, − = fell under v2")
    print(f"\n{'ticker':<8}{'old':>8}{'tier':>6}{'ta_grade':>10}{'rank Δ':>8}  warnings")
    for g in report["rows"]:
        print(f"{g['ticker']:<8}{g['old_score'] or 0:>8.1f}{g['old_tier'] or '?':>6}"
              f"{g['ta_grade']:>10.1f}{g['rank_delta']:>+8d}  "
              f"{_warn_cell(g['warnings'])}")
    movers = sorted(report["rows"], key=lambda g: -abs(g["rank_delta"]))[:top]
    if movers and top > 0:
        print(f"\ntop {len(movers)} movers — per-chapter points (the drill):")
        for g in movers:
            ch = " ".join(f"{k}:{v:.1f}" for k, v in g["chapters"].items())
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
        # The verdict AND the basis banner speak on this path too — the flip
        # checklist routes the evidence through --json, and an operator reads
        # words, not exit codes (2026-08-08 review, finding 2).
        for line in _basis_banner_lines(report):
            print(line)
        for line in _identity_verdict_lines(report):
            print(line)
        print(f"wrote {path} ({len(report['rows'])} rows)")
    else:
        _print_report(report, args.top)
    return 0 if report["identity_ok"] else 2


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
