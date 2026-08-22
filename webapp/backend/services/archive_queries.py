"""Shared archive query and episode-grouping helpers."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func

from archive_models import SetupArchive
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE
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
    min_ta_grade: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    universe_type: Optional[str] = DEFAULT_UNIVERSE_TYPE,
):
    """Apply the shared setup_archive filters used by the list + episode views.

    ``universe_type`` defaults to ``'us_equities'`` so every equities read surface
    (/setups, /episodes, /missed-winners, calibration stats) excludes the ETF /
    sector screener rows that now share ``source='screener'`` — they are physically
    separate (3-col unique key) but would otherwise pool into the equities
    population and inflate counts / win-rate. Pass ``universe_type=None`` to query
    every universe."""
    if universe_type:
        q = q.filter(SetupArchive.universe_type == universe_type)
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
    # The grade's OWN filter (task 9): min_score keeps raw-sum semantics
    # FOREVER (the two scales are incommensurable); a ta_grade threshold
    # excludes pre-v2 NULL rows by SQL three-valued logic — deliberately
    # (an ungraded row can never satisfy a grade floor).
    if min_ta_grade is not None:
        q = q.filter(SetupArchive.ta_grade >= min_ta_grade)
    if date_from:
        q = q.filter(SetupArchive.scan_date >= date_from)
    if date_to:
        q = q.filter(SetupArchive.scan_date <= date_to)
    return q


def _archive_version(db, universe_type: Optional[str] = None) -> tuple[int, int]:
    """Coarse signature of the archive's grouping-relevant state. ticker /
    scan_date / setup_type are immutable after insert, so (max id, row count)
    fully captures whether episode membership could have changed.

    Scoped to ``universe_type`` when given so a grouping cached for one universe
    only invalidates when ITS OWN rows change. The signature was whole-table, so a
    commodities/ETF insert (the daily multi-universe scan) busted the cached
    us_equities grouping even though no equities row changed — forcing a full
    re-group on the next /episodes + /missed-winners request. ``None`` (the
    all-universes grouping) keeps the whole-table signature, which is correct."""
    q = db.query(func.max(SetupArchive.id), func.count(SetupArchive.id))
    if universe_type:
        q = q.filter(SetupArchive.universe_type == universe_type)
    mx, count = q.one()
    return (mx or 0, count or 0)


def _build_grouping(db, filters: dict):
    """Run the authoritative grouper (core.archive.episodes) over the filtered
    rows. Loads only the four identity columns the grouping needs."""
    from core.archive import episodes as ep_mod

    q = _apply_setup_filters(
        db.query(
            SetupArchive.id, SetupArchive.ticker,
            SetupArchive.scan_date, SetupArchive.setup_type,
            SetupArchive.universe_type,
        ),
        **filters,
    )
    return ep_mod.build_episodes(
        ep_mod.SetupRow(id=r.id, ticker=r.ticker, scan_date=r.scan_date,
                        setup_type=r.setup_type, universe_type=r.universe_type)
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


def _ta_grades_by_ids(db, ids) -> dict:
    """{row id: ta_grade} for the given ids (two columns only, chunked) —
    the episode view's CURRENT-grade lookup (each episode's latest member)."""
    ids = list(ids)
    out: dict = {}
    for start in range(0, len(ids), 900):
        chunk = ids[start:start + 900]
        for row_id, grade in (db.query(SetupArchive.id, SetupArchive.ta_grade)
                              .filter(SetupArchive.id.in_(chunk)).all()):
            out[row_id] = grade
    return out


def _grouped_episodes(db, filters: dict):
    """Episodes for the filtered archive, cached per (filter, archive-version).

    The cache key is derived from the *active* (non-None) filters, so it stays
    in lock-step with ``_apply_setup_filters`` automatically — there's no
    hand-maintained tuple to forget when a filter is added or renamed, and two
    callers with the same effective filter share one grouping.

    ``quality_label`` is the one filter that's mutable after insert (PATCH
    ``/setups/{id}/label``), so a grouping *selected by it* can go stale without
    ``(max_id, count)`` moving. Bypass the cache when it's in play. (A same-day
    upsert can also rewrite ``score``/``ta_grade`` in place, but it always
    REPLACES the day's row through the same writer — the stale window is one
    re-scan of the same day, accepted.) Every other filter keys on immutable
    identity columns and is safe to cache.
    """
    # Default the equities scope EXPLICITLY here (not only via _apply_setup_filters'
    # param default) so it lands in the cache key — otherwise the default
    # (us_equities) and an explicit universe_type=None (all universes) would both
    # key on the same empty signature and collide in _EPISODE_CACHE.
    filters = {**filters}
    filters.setdefault("universe_type", DEFAULT_UNIVERSE_TYPE)
    active = {k: v for k, v in filters.items() if v is not None}
    if "quality_label" in active:
        return _build_grouping(db, filters)
    cache_key = tuple(sorted(active.items()))
    version = _archive_version(db, filters.get("universe_type"))
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

    Scoped to ``us_equities`` because this serves the equities screener's
    saw-&-passed marker, which keys on the same equities episode the
    missed-winners / canonical path (also us_equities-default) does. Without the
    filter, a ticker present in two universes could resolve its first_seen to the
    ETF episode while missed-winners keyed on the equities episode — exactly the
    cross-surface disagreement this function exists to prevent.
    """
    from core.archive import episodes as ep_mod

    rows = db.query(
        SetupArchive.id, SetupArchive.ticker,
        SetupArchive.scan_date, SetupArchive.setup_type,
        SetupArchive.universe_type,
    ).filter(
        func.upper(SetupArchive.ticker) == ticker,
        SetupArchive.universe_type == DEFAULT_UNIVERSE_TYPE,
    ).all()
    if not rows:
        return None
    eps = ep_mod.build_episodes(
        ep_mod.SetupRow(id=r.id, ticker=r.ticker, scan_date=r.scan_date,
                        setup_type=r.setup_type, universe_type=r.universe_type)
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


# ── Manual-add row mapping ───────────────────────────────────────────────────
# The manual-add route maps a (seed) eval-result dict onto a SetupArchive row.
# Most columns are a flat ``result.get(col)`` pass-through; the rest are sourced
# elsewhere (sub-scores, coercions, market-context enrichment, the HTF / forward-
# return splats) and are passed by the route as ``overrides``. ``archive_row_from
# _result`` makes SetupArchive.__table__ the single source for the pass-through
# columns: a new flat column on the model flows through with no route edit.
#
# Columns the manual route does NOT source from ``result`` directly. These are
# either filled by the route's ``**fwd_returns`` splat (forward-return / triple-
# barrier outcomes, populated after the fact) or deliberately left NULL on a
# manual row (run-level context the single-ticker manual path does not compute:
# regime_*, scope_*, stage2_*, breadth/excess return, and a few engine internals).
# Frozen so a new model column can't silently start auto-filling here.
_MANUAL_UNMAPPED_COLUMNS = frozenset({
    # forward-return / triple-barrier outcomes (route passes **fwd_returns)
    "triggered", "trigger_date",
    "fwd_return_1d", "fwd_return_5d", "fwd_return_10d", "fwd_return_20d",
    "fwd_return_60d", "mfe_20d", "mae_20d", "mfe_60d", "mae_60d",
    "mfe_20d_date", "mae_20d_date", "r_multiple_20d", "r_multiple_60d",
    "trigger_volume_ratio", "days_to_trigger", "days_to_2_5r", "days_to_15pct",
    "days_to_stop", "barrier_label", "win_barrier",
    # deliberately NULL on a manual row (not computed on this path)
    "score_traversal_quality", "excess_return_6m", "breadth_pct",
    "bars_since_bc", "descent_length",
    "trav_last_support_frac", "trav_coil_floor_pos",
    "regime_state", "regime_breadth_50_pct", "regime_breadth_200_pct",
    "regime_distribution_days", "regime_spy_above_50", "regime_spy_above_200",
    "regime_spy_50d_slope_pct", "regime_qqq_above_50", "regime_qqq_above_200",
    "regime_qqq_50d_slope_pct",
    "scope_phase_a_date", "scope_phase_b_date", "scope_phase_d_date",
    "scope_phase_c_date", "scope_has_mini", "scope_confidence",
    "stage2_ma_stack_pass", "stage2_ma200_slope_1m_pct", "stage2_52w_low_pct",
    "stage2_trend_pass_count", "stage2_trend_pass",
})


def archive_row_from_result(result: dict, *, overrides: dict) -> dict:
    """Build SetupArchive(**kwargs) for a manually-added setup from an eval-result.

    Iterates ``SetupArchive.__table__.columns`` so the model is the single source
    of truth for the flat pass-through columns. For each column it takes, in order:
    the caller's ``overrides`` (special-cased values: identity, required fields,
    sub-scores, coercions, market context), else ``result.get(col)`` — except the
    auto-increment ``id`` and the ``_MANUAL_UNMAPPED_COLUMNS`` (filled by the
    route's ``**fwd_returns`` splat or intentionally left NULL).

    The route still passes its HTF / forward-return splats and ``overrides``
    explicitly; this only replaces the ~80-line block of identical ``col=result
    .get("col")`` lines, preserving the exact set of populated columns and values.
    """
    kwargs = dict(overrides)
    for column in SetupArchive.__table__.columns:
        name = column.name
        if name == "id" or name in kwargs or name in _MANUAL_UNMAPPED_COLUMNS:
            continue
        kwargs[name] = result.get(name)
    return kwargs
