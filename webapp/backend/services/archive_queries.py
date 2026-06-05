"""Shared archive query and episode-grouping helpers."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func

from archive_models import SetupArchive
from services.episode_cache import VersionedCache

# Caches the expensive episode grouping per (filter, archive-version) so
# repeated requests do not rebuild it over the whole table.
_EPISODE_CACHE = VersionedCache()


def _apply_setup_filters(
    q,
    *,
    tier: Optional[str] = None,
    setup_type: Optional[str] = None,
    source: Optional[str] = None,
    quality_label: Optional[str] = None,
    min_score: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Apply the shared setup_archive filters used by the list + episode views."""
    if tier:
        q = q.filter(SetupArchive.tier == tier.upper())
    if setup_type:
        q = q.filter(SetupArchive.setup_type == setup_type.upper())
    if source:
        sources = [s.strip() for s in source.split(",") if s.strip()]
        if len(sources) == 1:
            q = q.filter(SetupArchive.source == sources[0])
        elif sources:
            q = q.filter(SetupArchive.source.in_(sources))
    if quality_label:
        q = q.filter(SetupArchive.quality_label == quality_label)
    if min_score is not None:
        q = q.filter(SetupArchive.score >= min_score)
    if date_from:
        q = q.filter(SetupArchive.scan_date >= date_from)
    if date_to:
        q = q.filter(SetupArchive.scan_date <= date_to)
    return q


def _archive_version(db) -> tuple[int, int]:
    """Coarse signature of the archive's grouping-relevant state. ticker /
    scan_date / setup_type are immutable after insert, so (max id, row count)
    fully captures whether episode membership could have changed."""
    mx, count = db.query(func.max(SetupArchive.id), func.count(SetupArchive.id)).one()
    return (mx or 0, count or 0)


def _build_grouping(db, filters: dict):
    """Run the authoritative grouper (core.archive.episodes) over the filtered
    rows. Loads only the four identity columns the grouping needs."""
    from core.archive import episodes as ep_mod

    q = _apply_setup_filters(
        db.query(
            SetupArchive.id, SetupArchive.ticker,
            SetupArchive.scan_date, SetupArchive.setup_type,
        ),
        **filters,
    )
    return ep_mod.build_episodes(
        ep_mod.SetupRow(id=r.id, ticker=r.ticker, scan_date=r.scan_date, setup_type=r.setup_type)
        for r in q.all()
    )


def _rows_by_ids(db, ids) -> dict:
    """Fetch full SetupArchive rows for the given ids, chunked to stay under
    SQLite's bound-parameter limit."""
    ids = list(ids)
    out: dict = {}
    for start in range(0, len(ids), 900):
        chunk = ids[start:start + 900]
        for row in db.query(SetupArchive).filter(SetupArchive.id.in_(chunk)).all():
            out[row.id] = row
    return out


def _grouped_episodes(db, filters: dict):
    """Episodes for the filtered archive, cached per (filter, archive-version).

    The cache key is derived from the *active* (non-None) filters, so it stays
    in lock-step with ``_apply_setup_filters`` automatically — there's no
    hand-maintained tuple to forget when a filter is added or renamed, and two
    callers with the same effective filter share one grouping.

    ``quality_label`` is the one filter that's mutable after insert (PATCH
    ``/setups/{id}/label``), so a grouping *selected by it* can go stale without
    ``(max_id, count)`` moving. Bypass the cache when it's in play; every other
    filter keys on immutable identity columns and is safe to cache.
    """
    active = {k: v for k, v in filters.items() if v is not None}
    if "quality_label" in active:
        return _build_grouping(db, filters)
    cache_key = tuple(sorted(active.items()))
    version = _archive_version(db)
    return _EPISODE_CACHE.get_or_compute(cache_key, version, lambda: _build_grouping(db, filters))


def _canonical_setups(db, **filters) -> list:
    """Full SetupArchive rows collapsed to one per episode (the first-seen
    canonical row) — the same de-duplication the episode table applies, so
    aggregate stats aren't inflated by a base's daily continuation re-flags.
    Rows are fetched fresh, so forward returns / labels are never stale."""
    eps = _grouped_episodes(db, filters)
    row_by_id = _rows_by_ids(db, [ep.canonical_id for ep in eps])
    return [row_by_id[ep.canonical_id] for ep in eps if ep.canonical_id in row_by_id]


def _latest_episode_first_seen(db, ticker: str) -> Optional[str]:
    """First-seen (entry-anchor) date of a ticker's most-recent episode.

    A live screener card has no scan_date of its own, but a 'saw & passed'
    mark from the screener must land on the SAME (ticker, first_seen) key the
    archive episode table and the missed-winners report key on — otherwise the
    two surfaces disagree and a passed winner buckets as 'never engaged'.
    Resolving to the latest episode's first-seen keeps them in lock-step.
    Returns None if the ticker has never been archived (nothing to mark yet).
    """
    from core.archive import episodes as ep_mod

    rows = db.query(
        SetupArchive.id, SetupArchive.ticker,
        SetupArchive.scan_date, SetupArchive.setup_type,
    ).filter(func.upper(SetupArchive.ticker) == ticker).all()
    if not rows:
        return None
    eps = ep_mod.build_episodes(
        ep_mod.SetupRow(id=r.id, ticker=r.ticker, scan_date=r.scan_date, setup_type=r.setup_type)
        for r in rows
    )
    if not eps:
        return None
    return max(eps, key=lambda e: e.last_seen).first_seen


def _episode_context(db, **filters):
    """Shared episode view used by the episodes + missed-winners endpoints.

    Returns ``(episodes, canonical-row-by-id, saw-&-passed key set)``. The
    grouping is cached (see ``_grouped_episodes``); only the canonical row of
    each episode is then fetched — fresh, so forward returns / labels are never
    stale. Both callers use only each episode's canonical row.
    """
    from models import SetupReview

    eps = _grouped_episodes(db, filters)
    row_by_id = _rows_by_ids(db, [ep.canonical_id for ep in eps])
    passed_notes = {
        (rv.ticker, rv.scan_date): rv.note
        for rv in db.query(SetupReview).filter(SetupReview.verdict == "passed").all()
    }
    return eps, row_by_id, passed_notes


def _episode_key(ticker: str, setup_type: str, first_seen: str) -> str:
    """Stable logical setup key shared by archive rows and UI state."""
    return f"{ticker.upper()}|{setup_type.upper()}|{first_seen}"
