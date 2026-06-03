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

Read-only: never writes to the DB and never re-downloads market data.

Usage:
    python -m core.archive.seed_recall
"""
from __future__ import annotations

import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
_DB_PATH = os.path.join(_PROJECT_ROOT, "webapp", "backend", "trading_journal.db")


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


def summarize_recall(hits: list[dict], misses: list[dict]) -> dict:
    """Aggregate hits/misses into the recall scorecard."""
    total = len(hits) + len(misses)
    tier_dist: dict[str, int] = defaultdict(int)
    scores: list[float] = []
    for hit in hits:
        tier_dist[hit.get("tier") or "?"] += 1
        if hit.get("score") is not None:
            scores.append(float(hit["score"]))
    scores.sort()
    return {
        "total": total,
        "fired": len(hits),
        "missed": len(misses),
        "recall": (len(hits) / total) if total else 0.0,
        "tier_dist": dict(tier_dist),
        "score_min": scores[0] if scores else None,
        "score_median": scores[len(scores) // 2] if scores else None,
        "score_max": scores[-1] if scores else None,
    }


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


def run(db_path: str = _DB_PATH) -> None:
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    from core.archive.seed import SEED_SETUPS, WINDOW_BACK, WINDOW_FWD

    seed_rows = load_seed_rows(db_path)

    print("=" * 64)
    print("  SEED RECALL — can the engine re-find the winners I picked?")
    print("=" * 64)
    print(f"DB: {db_path}")

    if not seed_rows:
        print()
        print("No source='seed' rows in the archive yet — nothing to measure.")
        print("Run `python -m core.archive.seed` first to populate the seed archive.")
        return

    hits, misses = match_seeds(SEED_SETUPS, seed_rows, WINDOW_BACK, WINDOW_FWD)
    s = summarize_recall(hits, misses)

    print()
    print(f"Seeds (unique):   {s['total']}")
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

    print()
    print("Note: a MISS means no seed row was archived in-window. With a seeded")
    print("archive that means the engine did not fire; if the archive was never")
    print("seeded, run `python -m core.archive.seed` before trusting these numbers.")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Report the screener's recall on the seed winners.")
    ap.add_argument("--db", default=_DB_PATH, help="Path to the archive SQLite DB")
    args = ap.parse_args()
    run(db_path=args.db)


if __name__ == "__main__":
    main()
