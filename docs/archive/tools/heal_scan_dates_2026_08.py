"""ARCHIVED 2026-08-20 — this instrument's event is over; it is kept as the record of
how a recorded finding was measured, not as a runnable tool. It has moved out of
tools/, so the `python -m tools.<name>` usage lines below no longer resolve, and
its imports of sibling tools may not either. To re-run it, restore it to tools/
from git history first. Nothing in the live tree imports it.
One-time archive heal (operator ruling 2026-08-11, "purge & heal"): purge
non-trading-dated rows and re-label evidenced legacy cohorts to their true
sessions.

Background: until 2026-08-11 (fix 306c34c) scan_date was stamped from the
machine's LOCAL calendar date on an ET+7 box whose nightly scan runs after
local midnight â€” weekend re-scans of Friday's data filed as NEW
Saturday/Sunday rows, and every nightly weekday stamp named the day AFTER
the session it actually read. The fix stops new damage; this tool heals
legacy rows, driven by a per-cohort EVIDENCE file (current_price matched
against the price cache at stamp-date vs previous-trading-session), never a
blanket assumption â€” so seed/manual cohorts whose stamps are true stay put.

What the evidence pass (2026-08-11) established, and how this tool acts:
  verdict 'prev'          -> shift the cohort to its previous trading session
  verdict 'stamp'         -> leave in place (seed/manual backdates; the
                             2026-07-06 evening-rescan cohort)
  NO_EVIDENCE + advisory  -> the 2026-08-11 cohorts: the cache simply has no
  'prev'                     bar for the stamp date yet, and every row matches
                             the previous session exactly -> treated as 'prev'
  NO_EVIDENCE, all seed   -> leave in place (seed stamps are true by design)
  AMBIGUOUS               -> DEFERRED with --defer-ambiguous (the June
                             forming-bar era is a row-grain problem awaiting
                             an operator ruling); any 'prev' cohort whose
                             target slot is occupied by a deferred/staying
                             cohort cascade-defers with it, EXCEPT when the
                             occupant is the same true session written by a
                             different scan â€” then the shift MERGES: incumbent
                             rows win (their outcomes matured on the correct
                             date), same-key shifted duplicates are dropped.

Usage:
    python -m tools.heal_scan_dates_2026_08 --evidence PATH [--defer-ambiguous]          # dry run
    python -m tools.heal_scan_dates_2026_08 --evidence PATH [--defer-ambiguous] --apply

--apply refuses to run twice: it snapshots the DB to
trading_journal.pre_scan_date_heal_2026-08-11.db first and aborts if that
file already exists. All writes ride ONE transaction. Afterwards re-mature
outcomes against the corrected dates:
    python -m core.archive.forward_returns --min-age 0 --force
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.pipeline.market_calendar import (
    is_trading_session,
    normalize_session_date,
    previous_trading_session,
)

DB_PATH = os.path.join(_PROJECT_ROOT, "webapp", "backend", "trading_journal.db")
BACKUP_PATH = os.path.join(
    _PROJECT_ROOT, "webapp", "backend", "trading_journal.pre_scan_date_heal_2026-08-11.db"
)


def _non_trading_dates(cur) -> list[str]:
    """Non-trading dates carrying SCREENER rows (the nightly bug's victims).

    Seed/manual rows are exempt from the whole heal â€” one exists on a
    non-trading date (ST, seeded 2026-02-01, a Sunday): an operator hand-dating
    slip, surfaced for the operator rather than deleted."""
    dates = [r[0] for r in cur.execute(
        "SELECT DISTINCT scan_date FROM setup_archive WHERE source NOT IN ('seed','manual')")]
    return sorted(d for d in dates if not is_trading_session(normalize_session_date(d)))


def _effective_verdict(cohort: dict, defer_ambiguous: bool) -> str:
    """Map an evidence verdict to an action: 'prev' | 'stay' | 'defer'."""
    v = cohort["verdict"]
    if v == "prev":
        return "prev"
    if v == "stamp":
        return "stay"
    if v == "NO_EVIDENCE":
        if (cohort.get("advisory") or {}).get("advisory_verdict") == "prev":
            return "prev"
        sources = cohort.get("sources") or {}
        if sources and all(s in ("seed", "manual") for s in sources):
            return "stay"
        sys.exit(f"NO_EVIDENCE cohort with no advisory and non-seed rows: "
                 f"{cohort['scan_date']} {cohort['universe_type']}")
    if v == "AMBIGUOUS":
        if defer_ambiguous:
            return "defer"
        sys.exit(f"AMBIGUOUS cohort {cohort['scan_date']} {cohort['universe_type']} â€” "
                 "resolve the evidence or pass --defer-ambiguous to leave it untouched.")
    sys.exit(f"Unknown verdict {v!r} for {cohort['scan_date']} {cohort['universe_type']}")


def _plan(cur, evidence: dict, defer_ambiguous: bool):
    """Resolve cohorts into (purge_dates, shifts, merges, deferred).

    Ascending walk with an occupancy model: a 'prev' cohort may move only into
    a slot that is empty or was vacated by an earlier shift. A slot held by a
    staying/deferred cohort blocks the move â€” cascade-defer â€” unless the
    occupant is verdict 'stamp' for the SAME session the mover carries (two
    scans of one session): that pair MERGES.
    """
    purge_dates = _non_trading_dates(cur)
    # Coverage is demanded only for screener-bearing cohorts â€” seed/manual
    # rows are exempt from the heal entirely, so seed-only cohorts need no
    # evidence to be left alone.
    db_cohorts = {(d, u) for d, u in cur.execute(
        "SELECT DISTINCT scan_date, universe_type FROM setup_archive "
        "WHERE source NOT IN ('seed','manual')")
        if d not in purge_dates}
    evidenced = {(c["scan_date"], c["universe_type"]): c for c in evidence["cohorts"]}
    uncovered = sorted(db_cohorts - set(evidenced))
    if uncovered:
        sys.exit(f"Cohorts present in the DB but absent from the evidence: {uncovered}")

    actions = {key: _effective_verdict(c, defer_ambiguous) for key, c in evidenced.items()
               if key in db_cohorts}
    occupied = dict(actions)  # (date, universe) -> current action of the occupant
    shifts, merges, deferred = [], [], []
    for (d, u) in sorted(k for k, a in actions.items() if a == "prev"):
        c = evidenced[(d, u)]
        target = (c.get("target_date")
                  or (c.get("advisory") or {}).get("advisory_target_date")
                  or previous_trading_session(d).strftime("%Y-%m-%d"))
        occupant = occupied.get((target, u))
        if occupant is None:
            shifts.append((d, u, target))
            occupied.pop((d, u))
            occupied[(target, u)] = "shifted"
        elif occupant == "stay" and evidenced.get((target, u), {}).get("verdict") == "stamp" \
                and (evidenced[(target, u)].get("sources") or {}).get("screener"):
            merges.append((d, u, target))          # two scans of one true session
            occupied.pop((d, u))
        else:
            deferred.append((d, u, f"target {target} occupied by {occupant}"))
            # slot (d, u) stays occupied â€” anything shifting onto it defers too
    for (d, u), a in sorted(actions.items()):
        if a == "defer":
            deferred.append((d, u, "AMBIGUOUS (operator ruling pending)"))
    return purge_dates, shifts, merges, deferred


def _cohort_count(cur, d: str, u: str) -> int:
    n, = cur.execute("SELECT COUNT(*) FROM setup_archive WHERE scan_date=? AND universe_type=?",
                     (d, u)).fetchone()
    return n


def _move(cur, d: str, u: str, t: str, merge: bool) -> tuple[int, int, int, int]:
    """Move cohort (d,u) to t. Returns (dropped_dupes, shifted, verdicts, reviews).

    Seed/manual rows are exempt everywhere: their stamps are deliberate
    backdates (the evidence's 26 stamp-cohorts), never nightly-bug victims.

    Incumbent-wins on EVERY move, not only the flagged cohort merge: the
    UNIQUE(ticker, scan_date, universe_type) key means any occupant of the
    target key â€” a whole stamp-true cohort (the 2026-07-06 rescan) or a lone
    seed row sitting mid-range â€” blocks the mover, and the incumbent's row
    already carries outcomes matured on the correct date. The mover's copy of
    that key is a same-session duplicate and is dropped. `merge` only labels
    the planned cohort-level case for reporting.
    """
    src = "source NOT IN ('seed','manual')"
    cur.execute(
        f"DELETE FROM setup_archive WHERE scan_date=? AND universe_type=? AND {src} "
        "AND ticker IN (SELECT ticker FROM setup_archive WHERE scan_date=? AND universe_type=?)",
        (d, u, t, u))
    dropped = cur.rowcount
    cohort_tickers = [r[0] for r in cur.execute(
        f"SELECT ticker FROM setup_archive WHERE scan_date=? AND universe_type=? AND {src}",
        (d, u))]
    cur.execute(
        f"UPDATE setup_archive SET scan_date=? WHERE scan_date=? AND universe_type=? AND {src}",
        (t, d, u))
    shifted = cur.rowcount
    cur.execute("UPDATE read_verdicts SET scan_date=? WHERE scan_date=? AND universe_type=?",
                (t, d, u))
    verdicts = cur.rowcount
    reviews = 0
    if cohort_tickers:  # setup_reviews has no universe column â€” bind by ticker
        tq = ",".join("?" * len(cohort_tickers))
        cur.execute(
            f"UPDATE setup_reviews SET scan_date=? WHERE scan_date=? AND ticker IN ({tq})",
            [t, d, *cohort_tickers])
        reviews = cur.rowcount
    return dropped, shifted, verdicts, reviews


def main() -> None:
    ap = argparse.ArgumentParser(description="One-time scan_date heal (see module docstring)")
    ap.add_argument("--evidence", required=True, help="heal_evidence.json from the evidence pass")
    ap.add_argument("--defer-ambiguous", action="store_true",
                    help="leave AMBIGUOUS cohorts (and anything cascade-blocked) untouched")
    ap.add_argument("--apply", action="store_true", help="execute (default: dry run)")
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()

    with open(args.evidence, encoding="utf-8") as fh:
        evidence = json.load(fh)

    con = sqlite3.connect(args.db)
    con.execute("PRAGMA busy_timeout=30000")
    cur = con.cursor()
    total_before, = cur.execute("SELECT COUNT(*) FROM setup_archive").fetchone()
    purge_dates, shifts, merges, deferred = _plan(cur, evidence, args.defer_ambiguous)

    q = ",".join("?" * len(purge_dates))
    n_purge, = cur.execute(
        f"SELECT COUNT(*) FROM setup_archive WHERE scan_date IN ({q}) "
        "AND source NOT IN ('seed','manual')", purge_dates).fetchone()
    n_deferred_rows = sum(_cohort_count(cur, d, u) for d, u, _ in deferred)
    print(f"setup_archive rows: {total_before}")
    print(f"PURGE: {n_purge} rows on {len(purge_dates)} non-trading dates "
          f"({purge_dates[0]} .. {purge_dates[-1]})")
    print(f"SHIFT: {len(shifts)} cohorts | MERGE: {len(merges)} cohorts | "
          f"DEFER: {len(deferred)} cohorts ({n_deferred_rows} rows untouched)")
    for d, u, t in merges:
        print(f"  MERGE {d} [{u}] -> {t} (incumbent wins on key collision)")
    for d, u, why in deferred:
        print(f"  DEFER {d} [{u}]: {why}")

    if not args.apply:
        for d, u, t in shifts:
            print(f"  {d} [{u}] -> {t}  ({_cohort_count(cur, d, u)} rows)")
        print("\nDry run only. Re-run with --apply to execute.")
        con.close()
        return

    if os.path.exists(BACKUP_PATH):
        sys.exit(f"Backup already exists â€” refusing to run twice: {BACKUP_PATH}")
    backup_con = sqlite3.connect(BACKUP_PATH)
    with backup_con:
        con.backup(backup_con)
    backup_con.close()
    print(f"Backup written: {BACKUP_PATH}")

    n_dropped = n_shifted = n_verdicts = n_reviews = 0
    with con:  # ONE transaction â€” any failure rolls the whole heal back
        cur.execute(
            f"DELETE FROM setup_archive WHERE scan_date IN ({q}) "
            "AND source NOT IN ('seed','manual')", purge_dates)
        n_purged = cur.rowcount
        moves = sorted([(d, u, t, False) for d, u, t in shifts]
                       + [(d, u, t, True) for d, u, t in merges])
        for d, u, t, merge in moves:  # ascending: each target slot was vacated first
            dr, sh, vd, rv = _move(cur, d, u, t, merge)
            n_dropped += dr; n_shifted += sh; n_verdicts += vd; n_reviews += rv

    total_after, = cur.execute("SELECT COUNT(*) FROM setup_archive").fetchone()
    leftovers = _non_trading_dates(cur)
    dupes, = cur.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM setup_archive "
        "GROUP BY ticker, scan_date, universe_type HAVING COUNT(*) > 1)").fetchone()
    con.close()

    print(f"Purged {n_purged}; merged-out {n_dropped} same-session duplicates; "
          f"shifted {n_shifted} archive rows, {n_verdicts} read_verdicts, "
          f"{n_reviews} setup_reviews.")
    print(f"Rows after: {total_after} (expected {total_before - n_purged - n_dropped})")
    ok = True
    if total_after != total_before - n_purged - n_dropped:
        ok = False
        print("ROW-CONSERVATION CHECK FAILED")
    if leftovers:
        ok = False
        print(f"NON-TRADING DATES REMAIN: {leftovers}")
    if dupes:
        ok = False
        print(f"DUPLICATE (ticker, scan_date, universe_type) KEYS: {dupes}")
    if not ok:
        sys.exit("POST-CHECKS FAILED â€” restore from the backup and investigate.")
    print("Post-checks passed. Now re-mature outcomes against the corrected dates:")
    print("  python -m core.archive.forward_returns --min-age 0 --force")


if __name__ == "__main__":
    main()
