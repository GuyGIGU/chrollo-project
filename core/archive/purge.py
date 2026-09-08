"""
Purge stray rows from setup_archive — SAFE BY DEFAULT.

By default this deletes only stray/test rows (source NOT in
seed/manual/screener). The live ``source='screener'`` rows are the unbiased
edge-measurement record (the engine-validation pivot): deleting them throws
away forward-return outcomes that are still accruing and resets the
measurement clock to zero. They are PROTECTED unless you pass the explicit
``--include-live`` flag, which prints a loud warning first.

Usage:
    python -m core.archive.purge                         # dry run, stray rows only
    python -m core.archive.purge --apply                 # delete stray rows
    python -m core.archive.purge --include-live --apply  # ALSO delete live
                                                          # screener rows (destructive!)
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

from core.archive.db_path import archive_db_path  # noqa: E402  (needs the path above)


# Sources that are NEVER deleted by default. 'screener' is the live unbiased
# edge-measurement record; removing it discards accruing forward returns and
# resets the measurement clock, so it is protected unless --include-live is set.
_PROTECTED_SOURCES = ["seed", "manual", "screener"]


def purge(apply: bool = False, include_live: bool = False) -> dict[str, int]:
    from sqlalchemy import func
    from sqlalchemy.orm import sessionmaker

    from archive_models import SetupArchive
    from database import make_sqlite_engine

    db_path = archive_db_path()
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

    # Always protect seed/manual; protect live 'screener' rows unless the caller
    # explicitly opts in via --include-live. NULL/stray sources are deletable —
    # SQL `~col.in_(...)` excludes NULL, so match those rows explicitly.
    from sqlalchemy import or_

    protected = ["seed", "manual"] if include_live else _PROTECTED_SOURCES
    q = session.query(SetupArchive).filter(
        or_(SetupArchive.source.is_(None), ~SetupArchive.source.in_(protected))
    )
    target_count = q.count()
    scope = "incl. LIVE screener rows" if include_live else "stray rows only; live screener PROTECTED"

    if include_live:
        live_n = counts.get("screener", 0)
        print(
            f"\n!!  --include-live set: this will delete the {live_n} live 'screener' "
            "rows - the unbiased edge-measurement record. Forward returns still "
            "accruing on them are lost and the measurement clock resets to zero."
        )

    if not apply:
        print(f"\nDry run: would delete {target_count} rows ({scope}).")
        print("Re-run with --apply to actually delete.")
        session.close()
        return {"would_delete": target_count}

    deleted = q.delete(synchronize_session=False)
    session.commit()
    session.close()
    print(f"\nDeleted {deleted} rows ({scope}).")
    return {"deleted": deleted}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually perform the deletion")
    parser.add_argument(
        "--include-live",
        action="store_true",
        help="ALSO delete live source='screener' rows (destructive: resets the edge clock)",
    )
    args = parser.parse_args()
    purge(apply=args.apply, include_live=args.include_live)
