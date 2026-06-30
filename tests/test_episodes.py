import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.archive.episodes import (
    SetupRow,
    build_episodes,
    canonical_ids,
    episode_by_member_id,
)


def _row(id, ticker, scan_date, setup_type="LPS"):
    return SetupRow(id=id, ticker=ticker, scan_date=scan_date, setup_type=setup_type)


def test_single_scan_is_one_episode():
    eps = build_episodes([_row(1, "AAA", "2026-05-31")])
    assert len(eps) == 1
    assert eps[0].canonical_id == 1
    assert eps[0].scan_count == 1


def test_same_ticker_in_two_universes_forms_two_episodes():
    """Fix ⑤: the same ticker+setup_type in two universes is TWO distinct setups —
    an ETF and a like-named stock must never merge into one episode."""
    eps = build_episodes([
        SetupRow(id=1, ticker="XLE", scan_date="2026-06-01", setup_type="LPS", universe_type="us_equities"),
        SetupRow(id=2, ticker="XLE", scan_date="2026-06-02", setup_type="LPS", universe_type="commodities_etf"),
    ])
    assert len(eps) == 2
    assert {e.canonical_id for e in eps} == {1, 2}


def test_consecutive_days_collapse_into_one_episode():
    eps = build_episodes([
        _row(1, "AAA", "2026-06-01"),
        _row(2, "AAA", "2026-06-02"),
        _row(3, "AAA", "2026-06-03"),
    ])
    assert len(eps) == 1
    ep = eps[0]
    assert ep.scan_count == 3
    assert ep.canonical_id == 1          # first-seen is the entry anchor
    assert ep.first_seen == "2026-06-01"
    assert ep.last_seen == "2026-06-03"
    assert ep.member_ids == (1, 2, 3)


def test_weekend_gap_stays_one_episode():
    # Fri -> Mon is a single trading-day gap; must not split.
    eps = build_episodes([
        _row(1, "AAA", "2026-05-29"),   # Friday
        _row(2, "AAA", "2026-06-01"),   # Monday
    ])
    assert len(eps) == 1
    assert eps[0].scan_count == 2


def test_large_gap_splits_into_two_episodes():
    # A multi-week gap = the base broke and re-formed: two separate setups.
    eps = build_episodes([
        _row(1, "AAA", "2026-05-04"),
        _row(2, "AAA", "2026-05-05"),
        _row(9, "AAA", "2026-06-01"),
    ])
    assert len(eps) == 2
    by_first = {ep.first_seen: ep for ep in eps}
    assert by_first["2026-05-04"].member_ids == (1, 2)
    assert by_first["2026-06-01"].member_ids == (9,)


def test_different_setup_types_do_not_merge():
    eps = build_episodes([
        _row(1, "AAA", "2026-06-01", setup_type="LPS"),
        _row(2, "AAA", "2026-06-02", setup_type="REBOUND"),
    ])
    assert len(eps) == 2


def test_different_tickers_are_separate():
    eps = build_episodes([
        _row(1, "AAA", "2026-06-01"),
        _row(2, "BBB", "2026-06-01"),
    ])
    assert len(eps) == 2


def test_unordered_input_still_anchors_to_earliest():
    eps = build_episodes([
        _row(3, "AAA", "2026-06-03"),
        _row(1, "AAA", "2026-06-01"),
        _row(2, "AAA", "2026-06-02"),
    ])
    assert len(eps) == 1
    assert eps[0].canonical_id == 1
    assert eps[0].first_seen == "2026-06-01"


def test_gap_tolerance_is_configurable():
    rows = [_row(1, "AAA", "2026-06-01"), _row(2, "AAA", "2026-06-08")]  # 5 trading days
    assert len(build_episodes(rows, max_gap_trading_days=4)) == 2   # splits
    assert len(build_episodes(rows, max_gap_trading_days=5)) == 1   # merges


def test_canonical_ids_picks_one_row_per_episode():
    eps = build_episodes([
        _row(1, "AAA", "2026-06-01"),
        _row(2, "AAA", "2026-06-02"),
        _row(5, "BBB", "2026-06-01"),
    ])
    assert canonical_ids(eps) == {1, 5}


def test_episode_by_member_id_maps_every_row():
    eps = build_episodes([
        _row(1, "AAA", "2026-06-01"),
        _row(2, "AAA", "2026-06-02"),
    ])
    index = episode_by_member_id(eps)
    assert index[1] is index[2]          # both rows point at the same episode
    assert index[2].canonical_id == 1


def test_malformed_date_does_not_crash_grouping():
    # A bad scan_date must not 500 the whole endpoint — it should degrade to its
    # own (singleton) episode rather than raising out of np.busday_count.
    eps = build_episodes([
        _row(1, "AAA", "2026-06-01"),
        _row(2, "AAA", "2026-06-02"),
        _row(3, "AAA", ""),              # malformed — would raise unguarded
    ])
    # All three rows are still accounted for across the resulting episodes.
    all_members = {mid for ep in eps for mid in ep.member_ids}
    assert all_members == {1, 2, 3}
    # The bad row didn't merge into the clean run.
    assert any(ep.member_ids == (3,) for ep in eps)
