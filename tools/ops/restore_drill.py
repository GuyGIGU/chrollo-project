"""Restore drill for the Chrollo nightly backup - proves the newest snapshot restores.

Usage:
    python tools\\ops\\restore_drill.py [--root PATH] [--live-db PATH]

Finds the newest snapshot under --root (default %USERPROFILE%\\ChrolloBackups),
copies its trading_journal.db to a temp dir (a real restore, just not in place),
opens the copy READ-ONLY, runs PRAGMA integrity_check, and compares row counts of
the key tables against the live database. Prints PASS/FAIL and exits 0/1.

Run it monthly, and after any change to the backup script. It never writes to the
live database or to the snapshots.
"""
import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta

try:  # works under both `python -m tools.ops.restore_drill` and `python tools/ops/restore_drill.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path

REPO = configure_path()
KEY_TABLES = ("setup_archive", "trade_logs", "executions")
STAMP_FORMAT = "%Y-%m-%d_%H%M"  # snapshot dir names, e.g. 2026-07-02_2030
MAX_AGE = timedelta(hours=48)   # older than this = the nightly task is not running


def ro_uri(path):
    return "file:" + os.path.abspath(path).replace("\\", "/") + "?mode=ro"


def table_counts(db_path, problems, label):
    """Row counts for KEY_TABLES via a read-only connection; None if unreadable."""
    try:
        conn = sqlite3.connect(ro_uri(db_path), uri=True)
    except sqlite3.Error as exc:
        problems.append("%s could not be opened read-only: %s" % (label, exc))
        return None
    counts = {}
    try:
        for table in KEY_TABLES:
            try:
                counts[table] = conn.execute(
                    "SELECT count(*) FROM " + table).fetchone()[0]
            except sqlite3.Error as exc:
                counts[table] = None
                problems.append("%s: table %s unreadable (%s)" % (label, table, exc))
    finally:
        conn.close()
    return counts


def latest_snapshot(root):
    best = None
    for name in os.listdir(root):
        full = os.path.join(root, name)
        if not os.path.isdir(full):
            continue
        try:
            stamp = datetime.strptime(name, STAMP_FORMAT)
        except ValueError:
            continue  # not a snapshot dir
        if best is None or stamp > best[0]:
            best = (stamp, full)
    return best


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=os.path.join(
        os.environ.get("USERPROFILE", os.path.expanduser("~")), "ChrolloBackups"))
    parser.add_argument("--live-db", default=os.path.join(
        REPO, "webapp", "backend", "trading_journal.db"))
    args = parser.parse_args()

    print("Chrollo restore drill")
    problems = []

    if not os.path.isdir(args.root):
        print("FAIL: snapshot root not found: %s" % args.root)
        return 1
    found = latest_snapshot(args.root)
    if found is None:
        print("FAIL: no snapshot directories under %s" % args.root)
        return 1
    stamp, snap_dir = found
    age = datetime.now() - stamp
    print("  snapshot: %s  (age %.1f h)" % (snap_dir, age.total_seconds() / 3600))
    if age > MAX_AGE:
        problems.append(
            "latest snapshot is %.1f h old - the nightly backup task is not running"
            % (age.total_seconds() / 3600))

    snap_db = os.path.join(snap_dir, "trading_journal.db")
    if not os.path.exists(snap_db):
        print("FAIL: snapshot has no trading_journal.db: %s" % snap_dir)
        return 1

    # Restore = copy the snapshot db to a fresh location and open that copy.
    tmp = tempfile.mkdtemp(prefix="chrollo_restore_drill_")
    try:
        restored = os.path.join(tmp, "trading_journal.db")
        shutil.copy2(snap_db, restored)

        conn = sqlite3.connect(ro_uri(restored), uri=True)
        try:
            verdict = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
        print("  restored to temp, integrity_check: %s" % verdict)
        if verdict != "ok":
            problems.append("integrity_check on the restored copy: %s" % verdict)

        restored_counts = table_counts(restored, problems, "restored copy")
        # Live-side hiccups are printed but do not fail the drill - its job is to
        # judge the snapshot, and the live db may be mid-write or the service down.
        live_counts = None
        if os.path.exists(args.live_db):
            live_notes = []
            live_counts = table_counts(args.live_db, live_notes, "live db")
            for note in live_notes:
                print("  note: " + note)
            if live_counts is None:
                print("  note: count comparison skipped")
        else:
            print("  note: live db not found at %s - count comparison skipped"
                  % args.live_db)

        for table in KEY_TABLES:
            snap_n = (restored_counts or {}).get(table)
            live_n = (live_counts or {}).get(table)
            line = "  %-14s snapshot=%s" % (table, snap_n)
            if live_n is not None:
                line += "  live=%s" % live_n
                if snap_n is not None and live_n is not None:
                    if snap_n == 0 and live_n > 0:
                        problems.append("%s is EMPTY in the snapshot but has %d live rows"
                                        % (table, live_n))
                    elif snap_n > live_n:
                        line += "  (live shrank since snapshot - archive purge?)"
                    elif live_n > snap_n:
                        line += "  (delta %d, added since snapshot)" % (live_n - snap_n)
            print(line)

        snap_uploads = os.path.join(snap_dir, "uploads")
        live_uploads = os.path.join(os.path.dirname(args.live_db), "uploads")
        count_files = lambda d: sum(len(f) for _, _, f in os.walk(d)) if os.path.isdir(d) else 0
        print("  uploads: snapshot=%d files  live=%d files"
              % (count_files(snap_uploads), count_files(live_uploads)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if problems:
        print("FAIL:")
        for p in problems:
            print("  - " + p)
        return 1
    print("PASS: latest snapshot restores cleanly and matches the live database shape")
    return 0


if __name__ == "__main__":
    sys.exit(main())
