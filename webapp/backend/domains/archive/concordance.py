"""The read-verdict concordance reader (TA-grade build task 14).

The grade's future ground-truth harvest: every operator verdict LEFT-joined
to the archive on the exact identity triple (ticker, scan_date,
universe_type).

Contract (both flags ruled/reviewed before the first calibration consumes
this):
  * ORPHANS ARE SURFACED, never dropped (operator-ruled 2026-08-05: a
    verdict on a scan that never reached the archive — cache-mode abort,
    AP-9 readable-but-never-archived — is accepted evidence).
  * VERSION MISMATCHES ARE FLAGGED (council 2026-08-05 finding 6):
    setup_archive upserts in place, so a same-day re-scan under a rotated
    manifest replaces the narrative the operator actually judged — a
    calibration that pairs the verdict with the replaced row would be
    grading fiction.
  * The GRADE channel rides along (grade_verdict — 'read right, grade
    wrong' separable from a reading error), with the row's stored score /
    tier / ta_grade so the harvest can split the two error kinds.
"""
from __future__ import annotations


def read_verdict_concordance(db) -> dict:
    from archive_models import SetupArchive
    from models import ReadVerdict

    verdicts = (db.query(ReadVerdict)
                .order_by(ReadVerdict.scan_date.desc(), ReadVerdict.ticker)
                .all())
    rows = []
    orphans = 0
    version_mismatches = 0
    for v in verdicts:
        row = (db.query(SetupArchive)
               .filter(SetupArchive.ticker == v.ticker,
                       SetupArchive.scan_date == v.scan_date,
                       SetupArchive.universe_type == v.universe_type)
               .first())
        archived = row is not None
        version_match = None
        if archived and v.engine_config_version and row.engine_config_version:
            version_match = (
                v.engine_config_version == row.engine_config_version)
        entry = {
            "ticker": v.ticker,
            "scan_date": v.scan_date,
            "universe_type": v.universe_type,
            "verdict": v.verdict,
            "grade_verdict": v.grade_verdict,
            "note": v.note,
            "archived": archived,
            "orphan": not archived,
            "verdict_engine_config_version": v.engine_config_version,
            "archived_engine_config_version": (
                row.engine_config_version if archived else None),
            "version_match": version_match,
            "score": row.score if archived else None,
            "tier": row.tier if archived else None,
            "ta_grade": row.ta_grade if archived else None,
        }
        if entry["orphan"]:
            orphans += 1
        if version_match is False:
            version_mismatches += 1
        rows.append(entry)
    return {
        "rows": rows,
        "n": len(rows),
        "orphans": orphans,
        "version_mismatches": version_mismatches,
    }
