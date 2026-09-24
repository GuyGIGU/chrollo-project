import json
import sys

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from core.archive import seed_recall
from core.archive.seed_recall import (
    _baseline_payload,
    filter_ignored_seeds,
    match_seeds,
    summarize_fresh_results,
    summarize_recall,
)


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


def test_summarize_fresh_results_matches_report_shape():
    seeds = [("AAA", "2026-03-13"), ("BBB", "2026-03-14"), ("CCC", "2026-03-15")]
    results = {
        ("AAA", "2026-03-13"): {"scan_date": "2026-03-10", "tier": "S", "score": 90.0},
        ("BBB", "2026-03-14"): None,
    }
    s, hits, misses, ignored = summarize_fresh_results(
        seeds,
        results,
        {("CCC", "2026-03-15"): "bad vendor history"},
    )

    assert s["fired"] == 1
    assert s["missed"] == 1
    assert s["ignored"] == 1
    assert hits == [{
        "ticker": "AAA",
        "trigger_date": "2026-03-13",
        "scan_date": "2026-03-10",
        "tier": "S",
        "score": 90.0,
    }]
    assert misses == [{"ticker": "BBB", "trigger_date": "2026-03-14"}]
    assert ignored == [{
        "ticker": "CCC",
        "trigger_date": "2026-03-15",
        "reason": "bad vendor history",
    }]


def test_baseline_payload_records_basis_and_sorts_rows():
    summary = {
        "recall": 0.5,
        "fired": 1,
        "missed": 1,
        "total": 2,
        "raw_total": 3,
        "ignored": 1,
    }
    misses = [
        {"ticker": "ZZZ", "trigger_date": "2026-03-15"},
        {"ticker": "AAA", "trigger_date": "2026-03-15"},
    ]
    ignored = [{"ticker": "BBB", "trigger_date": "2026-01-01", "reason": "bad vendor history"}]

    payload = _baseline_payload(summary, misses, ignored, basis="fresh")

    assert payload["basis"] == "fresh"
    assert payload["misses"] == [
        {"ticker": "AAA", "trigger_date": "2026-03-15"},
        {"ticker": "ZZZ", "trigger_date": "2026-03-15"},
    ]
    assert payload["ignored_seeds"] == ignored


def test_check_baseline_delegates_to_fresh_guard_for_fresh_baseline(tmp_path, monkeypatch):
    baseline_path = tmp_path / "seed_recall_baseline.json"
    baseline_path.write_text('{"basis": "fresh"}', encoding="utf-8")
    calls = []

    def fake_fresh_check(baseline_path):
        calls.append(baseline_path)
        return True

    monkeypatch.setattr(seed_recall, "fresh_check_baseline", fake_fresh_check)

    assert seed_recall.check_baseline(db_path="unused.db", baseline_path=str(baseline_path)) is True
    assert calls == [str(baseline_path)]


def test_summarize_empty():
    s = summarize_recall([], [])
    assert s["total"] == 0 and s["raw_total"] == 0
    assert s["recall"] == 0.0 and s["score_median"] is None


# ------------------------------------------------------------------
# Hermetic-fixture rebuild guard (council review 2026-08-22, Leach F7):
# --build-fixture is a one-command baseline recapture, so an EXISTING
# fixture refuses to be overwritten without the explicit --reseal-fixture
# seam flag (EC-29), and every build stamps a population sidecar.
# ------------------------------------------------------------------
def _tiny_frames():
    idx = pd.date_range("2026-01-02", periods=5, freq="B")
    frame = pd.DataFrame({"Open": 1.0, "High": 1.1, "Low": 0.9,
                          "Close": 1.0, "Volume": 100.0}, index=idx)
    spy = pd.Series(1.0, index=idx)
    return {"AAA": frame}, spy


def test_build_fixture_refuses_to_overwrite_without_reseal(tmp_path, monkeypatch):
    import core.archive.seed as seed_mod

    fixture = tmp_path / "fixture.parquet"
    fixture.write_bytes(b"frozen")

    def _no_network(active):
        raise AssertionError("the refusal must fire BEFORE any download")

    monkeypatch.setattr(seed_mod, "_download_seed_data", _no_network)
    with pytest.raises(RuntimeError, match="EC-29"):
        seed_recall.build_hermetic_fixture(fixture_path=str(fixture))
    assert fixture.read_bytes() == b"frozen"   # ground truth untouched


def test_build_fixture_reseal_rebuilds_and_stamps_population(tmp_path, monkeypatch):
    import core.archive.seed as seed_mod

    fixture = tmp_path / "fixture.parquet"
    fixture.write_bytes(b"old")
    frames, spy = _tiny_frames()
    monkeypatch.setattr(seed_mod, "_download_seed_data",
                        lambda active: (frames, spy))

    frozen = seed_recall.build_hermetic_fixture(fixture_path=str(fixture),
                                                reseal=True)
    assert set(frozen) == {"AAA", "SPY"}
    assert fixture.read_bytes() != b"old"      # the deliberate reseal landed

    meta = json.loads((tmp_path / "fixture.parquet.meta.json")
                      .read_text(encoding="utf-8"))
    assert meta["seed_tickers"] == ["AAA"]     # the covered ticker set
    assert meta["frozen_at"]                   # the freeze date
    assert "missing_tickers" in meta


def test_build_fixture_first_build_needs_no_flag(tmp_path, monkeypatch):
    import core.archive.seed as seed_mod

    fixture = tmp_path / "fresh" / "fixture.parquet"   # no fixture yet
    frames, spy = _tiny_frames()
    monkeypatch.setattr(seed_mod, "_download_seed_data",
                        lambda active: (frames, spy))

    seed_recall.build_hermetic_fixture(fixture_path=str(fixture))
    assert fixture.exists()
    assert (tmp_path / "fresh" / "fixture.parquet.meta.json").exists()


def test_reseal_flag_alone_is_a_usage_error(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["seed_recall", "--reseal-fixture"])
    with pytest.raises(SystemExit):
        seed_recall.main()
