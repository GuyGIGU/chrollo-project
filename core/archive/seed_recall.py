"""
Seed recall report — how many of the cherry-picked seed winners does the engine
actually re-detect, and which does it miss?

The seed archive (``core/archive/seed.py`` ``SEED_SETUPS``) is a recall
benchmark: each ``(ticker, trigger_date)`` is a known historical winner, and
``core.archive.seed`` runs the REAL screener pipeline retrospectively on it,
scanning a ``-WINDOW_BACK / +WINDOW_FWD`` day window. If the engine fires the
setup is archived (``source='seed'``); if it never fires the seed is silently
dropped (only a log line). This report recovers the recall RATE — and, more
usefully, *which* known winners the engine fails to re-find — by comparing the
``SEED_SETUPS`` list against the archived seed rows.

It answers the original question behind the seed archive: "is the engine good
enough to find the winners I already know?" (The live ``/archive/missed-winners``
track answers the forward-looking question; this is the backward-looking recall.)

The default archive-backed report is read-only and never downloads market data.
Fresh modes re-download historical seed data; ``--fresh-capture`` writes only the
baseline JSON, never the archive DB.

Usage:
    python -m core.archive.seed_recall
    python -m core.archive.seed_recall --fresh-check
    python -m core.archive.seed_recall --fresh-capture
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, timedelta
from typing import Mapping, Optional

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
_DB_PATH = os.path.join(_PROJECT_ROOT, "webapp", "backend", "trading_journal.db")
_BASELINE_PATH = os.path.join(_PROJECT_ROOT, "tests", "baselines", "seed_recall_baseline.json")

SeedKey = tuple[str, str]

# Known seed setups where yfinance's adjusted fund history has drifted enough
# that the historical chart no longer represents the operator-labeled setup.
# Keep them visible in reports, but exclude them from recall math.
SEED_RECALL_IGNORES: dict[SeedKey, str] = {
    ("USO", "2026-02-26"): "yfinance adjusted-history drift on fund data",
    ("BRZU", "2026-03-31"): "yfinance adjusted-history drift on leveraged-fund data",
}


# ------------------------------------------------------------------
# Pure logic (unit-tested; no DB / no network)
# ------------------------------------------------------------------
def _dedup(seed_setups: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop duplicate (ticker, date) pairs, preserving order — mirrors the
    in-batch dedup core.archive.seed does."""
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for ticker, day in seed_setups:
        if (ticker, day) in seen:
            continue
        seen.add((ticker, day))
        out.append((ticker, day))
    return out


def filter_ignored_seeds(
    seed_setups: list[tuple[str, str]],
    ignored_seeds: Optional[Mapping[SeedKey, str]] = None,
) -> tuple[list[tuple[str, str]], list[dict]]:
    """Split seed setups into active seeds and explicitly ignored bad-data seeds."""
    ignored_lookup = SEED_RECALL_IGNORES if ignored_seeds is None else ignored_seeds
    active: list[tuple[str, str]] = []
    ignored: list[dict] = []
    for ticker, trigger in _dedup(seed_setups):
        reason = ignored_lookup.get((ticker, trigger))
        if reason:
            ignored.append({
                "ticker": ticker,
                "trigger_date": trigger,
                "reason": reason,
            })
        else:
            active.append((ticker, trigger))
    return active, ignored


def match_seeds(
    seed_setups: list[tuple[str, str]],
    seed_rows: list[dict],
    window_back: int = 10,
    window_fwd: int = 3,
) -> tuple[list[dict], list[dict]]:
    """Split seeds into (hits, misses) by whether the engine re-detected them.

    A seed ``(ticker, trigger_date)`` is a HIT if an archived seed row exists for
    the same ticker whose ``scan_date`` falls within
    ``[trigger_date - window_back, trigger_date + window_fwd]`` calendar days —
    the same window ``core.archive.seed`` scans when deciding whether the
    screener fired. Otherwise it is a MISS (the engine never fired in-window).
    """
    rows_by_ticker: dict[str, list[dict]] = defaultdict(list)
    for row in seed_rows:
        rows_by_ticker[row["ticker"]].append(row)

    hits: list[dict] = []
    misses: list[dict] = []
    for ticker, trigger in _dedup(seed_setups):
        try:
            trigger_d = date.fromisoformat(trigger)
        except ValueError:
            misses.append({"ticker": ticker, "trigger_date": trigger})
            continue
        lo = trigger_d - timedelta(days=window_back)
        hi = trigger_d + timedelta(days=window_fwd)

        match = None
        for row in rows_by_ticker.get(ticker, []):
            try:
                scan_d = date.fromisoformat(row["scan_date"])
            except (ValueError, TypeError):
                continue
            if lo <= scan_d <= hi:
                match = row
                break

        if match is not None:
            hits.append({
                "ticker": ticker,
                "trigger_date": trigger,
                "scan_date": match["scan_date"],
                "tier": match.get("tier"),
                "score": match.get("score"),
            })
        else:
            misses.append({"ticker": ticker, "trigger_date": trigger})

    return hits, misses


def summarize_recall(hits: list[dict], misses: list[dict], ignored: Optional[list[dict]] = None) -> dict:
    """Aggregate hits/misses into the recall scorecard."""
    ignored = ignored or []
    total = len(hits) + len(misses)
    raw_total = total + len(ignored)
    tier_dist: dict[str, int] = defaultdict(int)
    scores: list[float] = []
    for hit in hits:
        tier_dist[hit.get("tier") or "?"] += 1
        if hit.get("score") is not None:
            scores.append(float(hit["score"]))
    scores.sort()
    return {
        "total": total,
        "raw_total": raw_total,
        "fired": len(hits),
        "missed": len(misses),
        "ignored": len(ignored),
        "recall": (len(hits) / total) if total else 0.0,
        "tier_dist": dict(tier_dist),
        "score_min": scores[0] if scores else None,
        "score_median": scores[len(scores) // 2] if scores else None,
        "score_max": scores[-1] if scores else None,
    }


def summarize_fresh_results(
    seed_setups: list[tuple[str, str]],
    results: Mapping[SeedKey, Optional[dict]],
    ignored_seeds: Optional[Mapping[SeedKey, str]] = None,
) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """Build a recall scorecard from fresh engine results.

    ``core.archive.seed.fired_seeds_fresh`` returns ``result|None`` by seed key.
    This normalizes those results to the same ``(summary, hits, misses, ignored)``
    shape used by the archive-backed report.
    """
    active, ignored = filter_ignored_seeds(seed_setups, ignored_seeds)
    hits: list[dict] = []
    misses: list[dict] = []
    for ticker, trigger in active:
        result = results.get((ticker, trigger))
        if result is None:
            misses.append({"ticker": ticker, "trigger_date": trigger})
            continue
        hits.append({
            "ticker": ticker,
            "trigger_date": trigger,
            "scan_date": result.get("scan_date"),
            "tier": result.get("tier"),
            "score": result.get("score"),
        })
    return summarize_recall(hits, misses, ignored), hits, misses, ignored


def diff_against_baseline(
    current: dict,
    current_misses: list[dict],
    baseline: dict,
    tol: float = 1e-9,
) -> tuple[bool, list[str]]:
    """Compare a fresh recall run against a captured baseline.

    Returns ``(ok, lines)``. The guard FAILS (ok=False) when either:
      - recall regresses below the baseline rate (beyond ``tol``), or
      - a known winner that used to be re-found is now missed (a NEW entry in
        the miss-set) — the stricter, more useful signal than the rate alone.

    Recovered names (previously missed, now found) are reported but never fail
    the guard — finding more winners is always allowed.
    """
    lines: list[str] = []
    ok = True

    base_recall = float(baseline.get("recall", 0.0))
    cur_recall = float(current.get("recall", 0.0))
    if cur_recall + tol < base_recall:
        ok = False
        lines.append(f"RECALL REGRESSED: {cur_recall * 100:.1f}% < baseline {base_recall * 100:.1f}%")
    else:
        lines.append(f"recall {cur_recall * 100:.1f}% (baseline {base_recall * 100:.1f}%)")

    base_miss = {(m["ticker"], m["trigger_date"]) for m in baseline.get("misses", [])}
    cur_miss = {(m["ticker"], m["trigger_date"]) for m in current_misses}

    new_misses = sorted(cur_miss - base_miss)
    if new_misses:
        ok = False
        lines.append(f"NEW MISSES ({len(new_misses)}) - winners no longer re-found:")
        lines.extend(f"  {t:<6} {d}" for t, d in new_misses)

    recovered = sorted(base_miss - cur_miss)
    if recovered:
        lines.append(f"Recovered ({len(recovered)}) - previously-missed winners now found:")
        lines.extend(f"  {t:<6} {d}" for t, d in recovered)

    return ok, lines


# ------------------------------------------------------------------
# DB load (read-only) + report
# ------------------------------------------------------------------
def load_seed_rows(db_path: str = _DB_PATH) -> list[dict]:
    """Read archived seed rows (source='seed') from the archive DB, read-only."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Archive DB not found at {db_path}")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.execute(
            "SELECT ticker, scan_date, tier, score FROM setup_archive WHERE source = 'seed'"
        )
        return [
            {"ticker": t, "scan_date": d, "tier": tier, "score": score}
            for (t, d, tier, score) in cur.fetchall()
        ]
    finally:
        con.close()


def _recall_now(db_path: str = _DB_PATH) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """Compute the current recall scorecard from the archive.

    Returns ``(summary, hits, misses, ignored)``. Raises if the seed archive is empty —
    a recall measurement is meaningless without seed rows to match against.
    """
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    from core.archive.seed import SEED_SETUPS, WINDOW_BACK, WINDOW_FWD

    seed_rows = load_seed_rows(db_path)
    if not seed_rows:
        raise RuntimeError(
            "No source='seed' rows in the archive yet — run "
            "`python -m core.archive.seed` first to populate the seed archive."
        )
    active_seeds, ignored = filter_ignored_seeds(SEED_SETUPS)
    hits, misses = match_seeds(active_seeds, seed_rows, WINDOW_BACK, WINDOW_FWD)
    return summarize_recall(hits, misses, ignored), hits, misses, ignored


def _baseline_payload(s: dict, misses: list[dict], ignored: list[dict], basis: str) -> dict:
    return {
        "basis": basis,
        "recall": s["recall"],
        "fired": s["fired"],
        "missed": s["missed"],
        "total": s["total"],
        "raw_total": s["raw_total"],
        "ignored": s["ignored"],
        "ignored_seeds": sorted(
            ignored,
            key=lambda m: (m["trigger_date"], m["ticker"]),
        ),
        "misses": sorted(
            ({"ticker": m["ticker"], "trigger_date": m["trigger_date"]} for m in misses),
            key=lambda m: (m["trigger_date"], m["ticker"]),
        ),
    }


def _write_baseline(baseline: dict, baseline_path: str) -> None:
    os.makedirs(os.path.dirname(baseline_path), exist_ok=True)
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)


def capture_baseline(db_path: str = _DB_PATH, baseline_path: str = _BASELINE_PATH) -> dict:
    """Snapshot the current recall + miss-set to a baseline JSON for the guard."""
    s, _hits, misses, ignored = _recall_now(db_path)
    baseline = _baseline_payload(s, misses, ignored, basis="archive")
    _write_baseline(baseline, baseline_path)
    print(f"Captured recall baseline -> {baseline_path}")
    print(
        f"  recall {s['recall'] * 100:.1f}%  "
        f"({s['fired']}/{s['total']} active fired, {s['missed']} missed, {s['ignored']} ignored)"
    )
    return baseline


def check_baseline(db_path: str = _DB_PATH, baseline_path: str = _BASELINE_PATH) -> bool:
    """Compare current recall to the captured baseline. Returns True if it holds.

    The baseline records its measurement basis. ``basis=fresh`` means the guard
    re-runs the current engine instead of comparing against possibly stale local
    archive rows.
    """
    if not os.path.exists(baseline_path):
        print(f"No baseline at {baseline_path} - run with --capture or --fresh-capture first.")
        return False
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    if baseline.get("basis") == "fresh":
        print("Baseline basis is fresh; running the fresh engine guard.")
        return fresh_check_baseline(baseline_path=baseline_path)

    s, _hits, misses, _ignored = _recall_now(db_path)
    ok, lines = diff_against_baseline(s, misses, baseline)

    print("=" * 64)
    print("  SEED RECALL GUARD - archive rows vs. captured baseline")
    print("=" * 64)
    for line in lines:
        print(line)
    print()
    print("PASS - recall held and no winners were lost." if ok
          else "FAIL - recall guard failed; see drift above.")
    if not ok:
        print("Tip: run with --fresh-check before re-seeding; an archive-only fail can mean stale seed rows.")
    return ok


def fresh_check_baseline(baseline_path: str = _BASELINE_PATH) -> bool:
    """Compare the current engine on fresh data to the captured baseline."""
    if not os.path.exists(baseline_path):
        print(f"No baseline at {baseline_path} - run with --capture or --fresh-capture first.")
        return False
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    from core.archive.seed import SEED_SETUPS, fired_seeds_fresh

    results = fired_seeds_fresh(SEED_SETUPS)
    s, _hits, misses, _ignored = summarize_fresh_results(SEED_SETUPS, results)
    ok, lines = diff_against_baseline(s, misses, baseline)

    print("=" * 64)
    print("  SEED RECALL GUARD - fresh engine vs. captured baseline")
    print("=" * 64)
    for line in lines:
        print(line)
    print()
    print("PASS - fresh recall held and no winners were lost." if ok
          else "FAIL - fresh recall guard failed; see drift above.")
    return ok


def capture_fresh_baseline(baseline_path: str = _BASELINE_PATH) -> dict:
    """Snapshot fresh current-engine recall + miss-set to the baseline JSON."""
    from core.archive.seed import SEED_SETUPS, fired_seeds_fresh

    results = fired_seeds_fresh(SEED_SETUPS)
    s, _hits, misses, ignored = summarize_fresh_results(SEED_SETUPS, results)
    baseline = _baseline_payload(s, misses, ignored, basis="fresh")
    _write_baseline(baseline, baseline_path)
    print(f"Captured fresh recall baseline -> {baseline_path}")
    print(
        f"  recall {s['recall'] * 100:.1f}%  "
        f"({s['fired']}/{s['total']} active fired, {s['missed']} missed, {s['ignored']} ignored)"
    )
    return baseline


def run(db_path: str = _DB_PATH) -> None:
    print("=" * 64)
    print("  SEED RECALL — can the engine re-find the winners I picked?")
    print("=" * 64)
    print(f"DB: {db_path}")

    try:
        s, hits, misses, ignored = _recall_now(db_path)
    except RuntimeError as e:
        print()
        print(str(e))
        return

    from core.archive.seed import WINDOW_BACK, WINDOW_FWD

    print()
    print(f"Seeds (unique):   {s['raw_total']}")
    print(f"Measured seeds:   {s['total']}")
    print(f"Ignored:          {s['ignored']}")
    print(f"Re-detected:      {s['fired']}")
    print(f"Missed:           {s['missed']}")
    print(f"RECALL:           {s['recall'] * 100:.1f}%")
    print(f"  (window matched: trigger -{WINDOW_BACK} / +{WINDOW_FWD} calendar days)")

    print()
    print("Hit tier distribution:")
    if s["tier_dist"]:
        for tier in sorted(s["tier_dist"]):
            print(f"  {tier}: {s['tier_dist'][tier]}")
    else:
        print("  (none)")
    if s["score_median"] is not None:
        print(f"Hit score:        min {s['score_min']:.1f} / med {s['score_median']:.1f} / max {s['score_max']:.1f}")

    print()
    print(f"MISSES ({len(misses)}) — known winners the engine did NOT re-find in-window:")
    if misses:
        for m in sorted(misses, key=lambda x: x["trigger_date"]):
            print(f"  {m['ticker']:<6} {m['trigger_date']}")
    else:
        print("  (none — perfect recall on the seed set)")

    if ignored:
        print()
        print(f"IGNORED ({len(ignored)}) — excluded from recall math because source data is unreliable:")
        for m in sorted(ignored, key=lambda x: x["trigger_date"]):
            print(f"  {m['ticker']:<6} {m['trigger_date']}  {m['reason']}")

    print()
    print("Note: a MISS means no seed row was archived in-window. With a seeded")
    print("archive that means the engine did not fire; if the archive was never")
    print("seeded, run `python -m core.archive.seed` before trusting these numbers.")


def run_fresh() -> None:
    """Re-evaluate the CURRENT engine against the seed winners on FRESH data,
    bypassing the archive entirely.

    The DB-based report reads whatever rows the archive holds — which can be
    STALE (written by an older engine) and report yesterday's recall. ``--fresh``
    re-runs the live engine on freshly downloaded data so engine changes that
    silently drop winners surface immediately (the blind spot that hid a
    14-winner regression in 2026-06). Needs network + a few minutes — use
    ``--fresh-check`` after touching the detector. Plain ``--check`` also runs
    the fresh guard when the captured baseline is ``basis=fresh``.
    """
    from collections import Counter

    from core.archive.seed import SEED_SETUPS, fired_seeds_fresh

    print("=" * 64)
    print("  SEED RECALL — FRESH re-eval of the CURRENT engine (not the archive)")
    print("=" * 64)
    results = fired_seeds_fresh(SEED_SETUPS)
    s, hits, misses, ignored = summarize_fresh_results(SEED_SETUPS, results)
    total = s["total"]

    print()
    print(f"Measured seeds:   {total}")
    print(f"Re-detected:      {s['fired']}")
    print(f"Missed:           {s['missed']}")
    print(f"RECALL (fresh):   {s['recall'] * 100:.1f}%" if total else "RECALL: n/a")
    tiers = Counter(hit["tier"] for hit in hits)
    print(f"Hit tiers:        {dict(sorted(tiers.items()))}")

    print()
    print(f"MISSES ({len(misses)}) — winners the live engine did NOT re-fire in-window:")
    for miss in sorted(misses, key=lambda x: x["trigger_date"]):
        print(f"  {miss['ticker']:<6} {miss['trigger_date']}")
    if ignored:
        print()
        print(f"IGNORED ({len(ignored)}): "
              f"{[m['ticker'] for m in ignored]}  (unreliable source data)")
    print()
    print("Tip: a FRESH miss the DB-based report counts as a HIT means the archive")
    print("is stale — re-seed (`python -m core.archive.seed --force`) to refresh it.")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Report the screener's recall on the seed winners.")
    ap.add_argument("--db", default=_DB_PATH, help="Path to the archive SQLite DB")
    ap.add_argument("--baseline", default=_BASELINE_PATH, help="Path to the recall baseline JSON")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--capture", action="store_true",
                       help="Snapshot current archive-row recall + miss-set as the baseline")
    group.add_argument("--check", action="store_true",
                       help="Fail (exit 1) if recall regressed or a known winner is newly missed. "
                            "Uses the captured baseline basis.")
    group.add_argument("--fresh", action="store_true",
                       help="Re-evaluate the CURRENT engine on fresh data, bypassing the "
                            "(possibly stale) archive (network; slower)")
    group.add_argument("--fresh-check", action="store_true",
                       help="Run the baseline guard against fresh engine results instead of "
                            "archive rows (network; slower; read-only)")
    group.add_argument("--fresh-capture", action="store_true",
                       help="Snapshot fresh current-engine recall + miss-set as the baseline "
                            "(network; slower; writes only the baseline JSON)")
    args = ap.parse_args()

    try:
        if args.capture:
            capture_baseline(db_path=args.db, baseline_path=args.baseline)
        elif args.check:
            ok = check_baseline(db_path=args.db, baseline_path=args.baseline)
            sys.exit(0 if ok else 1)
        elif args.fresh:
            run_fresh()
        elif args.fresh_check:
            ok = fresh_check_baseline(baseline_path=args.baseline)
            sys.exit(0 if ok else 1)
        elif args.fresh_capture:
            capture_fresh_baseline(baseline_path=args.baseline)
        else:
            run(db_path=args.db)
    except RuntimeError as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
