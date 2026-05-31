"""
Purge uncurated rows from setup_archive.

Deletes every setup whose source is not 'seed' or 'manual' — i.e. the
auto-scanner output that historically piled up. The archive is meant to
be a hand-picked regression suite, not a scan log.

Usage:
    python -m core.archive.purge            # dry run, prints what would go
    python -m core.archive.purge --apply    # actually delete
"""
from __future__ import annotations

import argparse
import os
import sys

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.append(_BACKEND_DIR)


def purge(apply: bool = False) -> dict[str, int]:
    from sqlalchemy import func
    from sqlalchemy.orm import sessionmaker

    from archive_models import SetupArchive
    from database import make_sqlite_engine

    db_path = os.path.join(_BACKEND_DIR, "trading_journal.db")
    engine = make_sqlite_engine(db_path)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()

    counts = dict(
        session.query(SetupArchive.source, func.count(SetupArchive.id))
        .group_by(SetupArchive.source)
        .all()
    )
    print("Current row counts by source:")
    for src, n in sorted(counts.items(), key=lambda kv: (kv[0] or "")):
        print(f"  {src or '(null)'}: {n}")

    q = session.query(SetupArchive).filter(~SetupArchive.source.in_(["seed", "manual"]))
    target_count = q.count()

    if not apply:
        print(f"\nDry run: would delete {target_count} rows (source not in seed/manual).")
        print("Re-run with --apply to actually delete.")
        session.close()
        return {"would_delete": target_count}

    deleted = q.delete(synchronize_session=False)
    session.commit()
    session.close()
    print(f"\nDeleted {deleted} rows.")
    return {"deleted": deleted}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually perform the deletion")
    args = parser.parse_args()
    purge(apply=args.apply)
