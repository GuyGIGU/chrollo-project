"""
Setup episodes — collapse a persisting setup's daily re-flags into one event.

The screener re-flags the same base every day it persists, so the raw archive
holds many *continuation* rows for one logical setup. Treating each as an
independent outcome would badly inflate win-rate / expectancy (a base that sits
15 days and then runs would count as 15 winners). An **episode** groups those
rows into a single event anchored to its **first-seen** row — which is also the
correct entry date for forward returns.

Definition (a "gap-and-islands" grouping):
    Rows with the same ``ticker`` and ``setup_type`` whose consecutive
    ``scan_date``s are no more than ``MAX_GAP_TRADING_DAYS`` apart belong to one
    episode. A larger gap starts a new episode — the base broke and re-formed
    weeks later, which is a genuinely new setup.

This module is deliberately dependency-light (stdlib + numpy, both already core
deps) and free of SQLAlchemy/pandas so it stays trivially unit-testable. Callers
adapt their own rows (ORM objects, DataFrame rows, dicts) into ``SetupRow``.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

# Max trading-day gap between consecutive scans that still counts as the same
# persisting base. 4 tolerates a long weekend plus a couple of missed/holiday
# scans without merging two genuinely separate basing attempts.
MAX_GAP_TRADING_DAYS = 4


@dataclass(frozen=True)
class SetupRow:
    """Minimal projection of a setup_archive row needed to form episodes."""

    id: int
    ticker: str
    scan_date: str        # ISO "YYYY-MM-DD" — sorts and diffs chronologically
    setup_type: str


@dataclass(frozen=True)
class Episode:
    """One logical setup, spanning one or more consecutive daily re-flags."""

    ticker: str
    setup_type: str
    canonical_id: int       # id of the first-seen row — the entry anchor
    first_seen: str         # earliest scan_date in the episode
    last_seen: str          # latest scan_date in the episode
    member_ids: tuple[int, ...]

    @property
    def scan_count(self) -> int:
        """How many daily scans flagged this setup (1 = caught once)."""
        return len(self.member_ids)


def _trading_day_gap(earlier: str, later: str) -> int:
    """Business days between two ISO dates (weekends excluded).

    Used as a holiday-agnostic proxy for trading days; the gap tolerance
    absorbs the handful of market holidays a pure business-day count misses.
    """
    return int(np.busday_count(earlier, later))


def build_episodes(
    rows: Iterable[SetupRow],
    max_gap_trading_days: int = MAX_GAP_TRADING_DAYS,
) -> list[Episode]:
    """Group rows into episodes. Order of the input does not matter.

    Returns one ``Episode`` per logical setup, each anchored to its first-seen
    row. The ``setup_archive`` unique constraint is (ticker, scan_date), so a
    given (ticker, setup_type) group has at most one row per date.
    """
    groups: dict[tuple[str, str], list[SetupRow]] = defaultdict(list)
    for row in rows:
        groups[(row.ticker, row.setup_type)].append(row)

    episodes: list[Episode] = []
    for (ticker, setup_type), members in groups.items():
        members.sort(key=lambda r: r.scan_date)

        run: list[SetupRow] = []
        for row in members:
            gap_too_wide = (
                run and _trading_day_gap(run[-1].scan_date, row.scan_date) > max_gap_trading_days
            )
            if gap_too_wide:
                episodes.append(_make_episode(ticker, setup_type, run))
                run = []
            run.append(row)
        if run:
            episodes.append(_make_episode(ticker, setup_type, run))

    return episodes


def _make_episode(ticker: str, setup_type: str, run: list[SetupRow]) -> Episode:
    """Build an Episode from a date-sorted run of same-base rows."""
    return Episode(
        ticker=ticker,
        setup_type=setup_type,
        canonical_id=run[0].id,
        first_seen=run[0].scan_date,
        last_seen=run[-1].scan_date,
        member_ids=tuple(r.id for r in run),
    )


def canonical_ids(episodes: Iterable[Episode]) -> set[int]:
    """The set of first-seen row ids — i.e. one row per episode.

    Filtering an archive query to these ids de-duplicates continuation rows for
    correct stats and a one-row-per-setup table view.
    """
    return {ep.canonical_id for ep in episodes}


def episode_by_member_id(episodes: Iterable[Episode]) -> dict[int, Episode]:
    """Map every member row id to its episode (for enriching a row with its
    episode span, e.g. a 'seen 4 scans' badge)."""
    index: dict[int, Episode] = {}
    for ep in episodes:
        for member_id in ep.member_ids:
            index[member_id] = ep
    return index
