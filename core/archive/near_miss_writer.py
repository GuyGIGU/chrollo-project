"""Near-miss cohort writer — persists ruled refusal rows (lane Task 9).

One batched pass per scan night over the rows the deferred phase produced
(``engine_alpha.structure.near_miss.deferred_rows``): in-memory dedup on the
framing identity, per-ticker + global caps (every drop COUNTED — a silent
cap reads as "covered everything"), then the R-EPISODE upsert (operator
ruling 2026-07-26 axis 3): a new identity inserts with ``first_seen`` =
tonight (the forward-return clock anchor); a re-observed identity bumps
``last_seen`` / ``nights_seen`` / ``fired_any_night`` and touches NOTHING
else — the margin vector stays the FIRST refusal's evidence.

Error split (the plan's Leach row): no blanket try/except around the
collector — programmer errors surface; ONE narrow logged catch wraps the
flush/commit, because an archive failure must never kill the night's picks.
ONE session, autoflush off, one commit (the "database is locked" lesson).

The ``enable`` pass-through mirrors ``archive_scan_results``: test scans and
replays never pollute the cohort unless a caller explicitly opts in.
"""
from __future__ import annotations

import logging
import os
import sys

_PROJECT_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.append(_BACKEND_DIR)

log = logging.getLogger("chrollo.archive.near_miss")

# EC-19 write-time leg vocabulary — must match the model CHECK and the ruled
# T-COARSE-8 taxonomy exactly (the fresh-DB CHECK cannot retrofit onto the
# live DB; THIS assertion is the live DB's guard).
_FAILING_LEGS = ("width", "window", "respect_share", "respect_run", "crash",
                 "occupancy", "traversal_count", "traversal_density")
_POOLS = ("strict", "rescued", "band")


def _failing_leg_label(value) -> str:
    """The single stamping point of the cohort's failing-leg label (EC-19)."""
    label = str(value)
    if label not in _FAILING_LEGS:
        raise ValueError(
            f"unknown failing-leg label {value!r} — the cohort's closed set "
            f"is {'/'.join(_FAILING_LEGS)}")
    return label


def _pool_label(value) -> str:
    label = str(value)
    if label not in _POOLS:
        raise ValueError(
            f"unknown near-miss pool label {value!r} — the closed set is "
            f"{'/'.join(_POOLS)}")
    return label


def _ensure_table(engine) -> None:
    """Create-on-fresh + ADD-only model diff, so a standalone scan process
    (no backend boot) still lands every model column (the Task-9
    generalization: the new table is covered AT BIRTH)."""
    from sqlalchemy import inspect, text

    from archive_models import NearMissArchive

    NearMissArchive.__table__.create(bind=engine, checkfirst=True)
    inspector = inspect(engine)
    existing = {col["name"] for col in inspector.get_columns("near_miss_archive")}
    with engine.begin() as conn:
        for column in NearMissArchive.__table__.columns:
            if column.primary_key or column.name in existing:
                continue
            try:
                conn.execute(text(
                    f"ALTER TABLE near_miss_archive ADD COLUMN "
                    f"{column.name} {column.type}"))
            except Exception as exc:
                # Idempotency vs a concurrently booting backend's own ensure
                # pass — the startup runner's exact predicate (review
                # 2026-07-26 finding 5; both siblings already tolerate this).
                message = str(exc).lower()
                if "duplicate column" in message or "already exists" in message:
                    continue
                raise


def archive_near_miss_rows(rows: list[dict], *, universe_type: str,
                           enable: bool = False) -> dict:
    """Persist one night's ruled near-miss rows. Returns the counter dict
    (inserted / recurred / dedup_dropped / ticker_cap_dropped /
    global_cap_dropped / flush_error) — every bound is visible."""
    counters = {"inserted": 0, "recurred": 0, "dedup_dropped": 0,
                "ticker_cap_dropped": 0, "global_cap_dropped": 0,
                "flush_error": 0}
    if not enable or not rows:
        return counters

    from config import settings  # lazy: the backend-cwd config shadow (AP-3)

    # Deterministic writer order regardless of the worker pool's completion
    # order — WHICH episodes the caps drop (and so where the R-EPISODE clock
    # anchors) must reproduce on identical data (review 2026-07-26 finding 15).
    rows = sorted(rows, key=lambda r: (
        r["ticker"], r["r_anchor_date"], r["s_anchor_date"],
        r["r_level"], r["s_level"]))

    # In-memory dedup on the framing identity (two consultations of one
    # framing may both survive into rows only across ticker boundaries by
    # construction, but the writer owns its own invariant).
    seen: set = set()
    deduped: list[dict] = []
    for row in rows:
        key = (row["ticker"], universe_type, row["r_level"], row["s_level"],
               row["r_anchor_date"], row["s_anchor_date"])
        if key in seen:
            counters["dedup_dropped"] += 1
            continue
        seen.add(key)
        deduped.append(row)

    per_ticker: dict[str, int] = {}
    capped: list[dict] = []
    ticker_cap = settings.NEAR_MISS_WRITER_TICKER_CAP
    global_cap = settings.NEAR_MISS_WRITER_GLOBAL_CAP
    for row in deduped:
        n = per_ticker.get(row["ticker"], 0)
        if n >= ticker_cap:
            counters["ticker_cap_dropped"] += 1
            continue
        if len(capped) >= global_cap:
            counters["global_cap_dropped"] += 1
            continue
        per_ticker[row["ticker"]] = n + 1
        capped.append(row)

    import database
    from archive_models import NearMissArchive
    from engine_alpha.freeze.manifest import manifest_hash
    from sqlalchemy.exc import OperationalError

    try:
        _ensure_table(database.engine)
    except OperationalError:
        # Locked DB / disk error during the ensure DDL: operational, counted,
        # never the night's scan (review 2026-07-26 finding 5).
        log.exception("near-miss table-ensure failed; night's rows dropped")
        counters["flush_error"] = len(capped)
        return counters
    engine_version = manifest_hash()

    session = database.SessionLocal()
    session.autoflush = False
    try:
        for row in capped:
            existing = session.query(NearMissArchive).filter_by(
                ticker=row["ticker"], universe_type=universe_type,
                r_level=row["r_level"], s_level=row["s_level"],
                r_anchor_date=row["r_anchor_date"],
                s_anchor_date=row["s_anchor_date"],
            ).one_or_none()
            if existing is not None:
                # R-EPISODE re-observation: counters only, never the record.
                if row["scan_date"] > (existing.last_seen or ""):
                    existing.last_seen = row["scan_date"]
                    existing.nights_seen = int(existing.nights_seen or 1) + 1
                    if row["fired_night"]:
                        existing.fired_any_night = 1
                counters["recurred"] += 1
                continue
            margins = row["margins"]
            session.add(NearMissArchive(
                ticker=row["ticker"], universe_type=universe_type,
                r_level=row["r_level"], s_level=row["s_level"],
                r_anchor_date=row["r_anchor_date"],
                s_anchor_date=row["s_anchor_date"],
                first_seen=row["scan_date"], last_seen=row["scan_date"],
                nights_seen=1,
                fired_first_night=int(row["fired_night"]),
                fired_any_night=int(row["fired_night"]),
                pool=_pool_label(row["pool"]),
                kill_stage=str(row["kill_stage"]),
                failing_leg=_failing_leg_label(row["failing_leg"]),
                lane_ruleset=str(row["lane_ruleset"]),
                engine_config_version=engine_version,
                judged_n=int(row["judged_n"]),
                window_start_date=row["window_start_date"],
                window_end_date=row["window_end_date"],
                nm_width=float(margins["width"]),
                nm_window=(int(margins["window"])
                           if "window" in margins else None),
                nm_respect_share=int(margins["respect_share"]),
                nm_respect_run=int(margins["respect_run"]),
                nm_crash=float(margins["crash"]),
                nm_r_touches=int(margins["r_touches"]),
                nm_s_touches=int(margins["s_touches"]),
                nm_r_touch_thirds=int(margins["r_touch_thirds"]),
                nm_s_touch_thirds=int(margins["s_touch_thirds"]),
                nm_lower_dwell=int(margins["lower_dwell"]),
                nm_upper_dwell=int(margins["upper_dwell"]),
                nm_mid_dwell=int(margins["mid_dwell"]),
                nm_coverage=int(margins["coverage"]),
                nm_traversal_count=int(margins["traversal_count"]),
                nm_traversal_density=float(margins["traversal_density"]),
                episode_profile=row.get("episode_profile") or None,
                would_be_trigger=float(row["would_be_trigger"]),
                scan_close=float(row["scan_close"]),
            ))
            counters["inserted"] += 1
        try:
            session.commit()
        except Exception:
            # The ONE narrow operational catch: an archive flush failure is
            # logged and counted, never allowed to kill the night's picks.
            log.exception("near-miss cohort flush failed; rows dropped")
            session.rollback()
            counters["flush_error"] = counters["inserted"] + counters["recurred"]
            counters["inserted"] = 0
            counters["recurred"] = 0
    except OperationalError:
        # Locked DB / disk error on an upsert probe: the whole batch degrades
        # to a counted drop (nothing committed). Row-content programmer errors
        # (the EC-19 label refusals, missing keys) still surface — the split
        # the module header promises (review 2026-07-26 finding 5).
        log.exception("near-miss cohort DB phase failed; rows dropped")
        session.rollback()
        counters["flush_error"] = len(capped)
        counters["inserted"] = 0
        counters["recurred"] = 0
    finally:
        session.close()
    return counters
