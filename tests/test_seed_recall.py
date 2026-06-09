import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.archive.seed_recall import filter_ignored_seeds, match_seeds, summarize_recall


def _row(ticker, scan_date, tier="S", score=80.0):
    return {"ticker": ticker, "scan_date": scan_date, "tier": tier, "score": score}


def test_hit_when_archived_scan_in_window():
    # seed fired ~5 days before trigger → archived row within -10/+3 window
    seeds = [("AAA", "2026-03-13")]
    rows = [_row("AAA", "2026-03-09")]
    hits, misses = match_seeds(seeds, rows)
    assert len(hits) == 1 and not misses
    assert hits[0]["scan_date"] == "2026-03-09"
    assert hits[0]["tier"] == "S"


def test_miss_when_no_row_in_window():
    seeds = [("AAA", "2026-03-13")]
    rows = [_row("AAA", "2026-01-01")]   # far outside -10/+3
    hits, misses = match_seeds(seeds, rows)
    assert not hits
    assert misses == [{"ticker": "AAA", "trigger_date": "2026-03-13"}]


def test_miss_when_ticker_absent():
    hits, misses = match_seeds([("AAA", "2026-03-13")], [_row("BBB", "2026-03-10")])
    assert not hits and len(misses) == 1


def test_window_boundaries_inclusive():
    seeds = [("AAA", "2026-03-13")]
    assert match_seeds(seeds, [_row("AAA", "2026-03-03")])[0]   # exactly -10
    assert match_seeds(seeds, [_row("AAA", "2026-03-16")])[0]   # exactly +3
    # one day past each edge → miss
    assert not match_seeds(seeds, [_row("AAA", "2026-03-02")])[0]
    assert not match_seeds(seeds, [_row("AAA", "2026-03-17")])[0]


def test_duplicate_seeds_collapsed():
    seeds = [("AAA", "2026-03-13"), ("AAA", "2026-03-13")]
    hits, misses = match_seeds(seeds, [_row("AAA", "2026-03-10")])
    assert len(hits) + len(misses) == 1   # counted once


def test_filter_ignored_seeds_excludes_bad_data_with_reason():
    seeds = [("AAA", "2026-03-13"), ("BBB", "2026-03-14"), ("BBB", "2026-03-14")]
    active, ignored = filter_ignored_seeds(
        seeds,
        {("BBB", "2026-03-14"): "bad vendor history"},
    )
    assert active == [("AAA", "2026-03-13")]
    assert ignored == [{
        "ticker": "BBB",
        "trigger_date": "2026-03-14",
        "reason": "bad vendor history",
    }]


def test_same_ticker_two_distinct_triggers_matched_independently():
    seeds = [("AAA", "2026-01-20"), ("AAA", "2026-03-20")]
    rows = [_row("AAA", "2026-03-18")]   # only the March base was re-detected
    hits, misses = match_seeds(seeds, rows)
    assert {h["trigger_date"] for h in hits} == {"2026-03-20"}
    assert {m["trigger_date"] for m in misses} == {"2026-01-20"}


def test_summarize_recall_counts_and_distribution():
    hits = [
        {"ticker": "A", "trigger_date": "2026-03-13", "scan_date": "2026-03-10", "tier": "S", "score": 90.0},
        {"ticker": "B", "trigger_date": "2026-03-14", "scan_date": "2026-03-11", "tier": "A", "score": 70.0},
    ]
    misses = [{"ticker": "C", "trigger_date": "2026-03-15"}]
    s = summarize_recall(hits, misses)
    assert s["total"] == 3 and s["fired"] == 2 and s["missed"] == 1
    assert abs(s["recall"] - 2 / 3) < 1e-9
    assert s["tier_dist"] == {"S": 1, "A": 1}
    assert s["score_min"] == 70.0 and s["score_max"] == 90.0


def test_summarize_recall_reports_ignored_without_penalizing_recall():
    hits = [{"ticker": "A", "trigger_date": "2026-03-13", "scan_date": "2026-03-10", "tier": "S", "score": 90.0}]
    misses = [{"ticker": "B", "trigger_date": "2026-03-15"}]
    ignored = [{"ticker": "C", "trigger_date": "2026-03-16", "reason": "bad vendor history"}]
    s = summarize_recall(hits, misses, ignored)
    assert s["total"] == 2 and s["raw_total"] == 3 and s["ignored"] == 1
    assert abs(s["recall"] - 0.5) < 1e-9


def test_summarize_empty():
    s = summarize_recall([], [])
    assert s["total"] == 0 and s["raw_total"] == 0
    assert s["recall"] == 0.0 and s["score_median"] is None
