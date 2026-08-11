"""Pipeline wiring above the evaluation twin (review 2026-07-26 finding 10).

The lane could die invisibly ABOVE the twin with the suite green: the worker
selection + three-tuple unpack + sink/stats accumulation in
``_evaluate_frames``, scan_job's gate condition and archive call sites, and
the ordering that keeps the dashboard artifact ahead of the lane write.
These tests make each seam able to go red. Hermetic: the process pool is
replaced with an inline executor (a settings monkeypatch cannot cross a real
process boundary), and scan_job's collaborators are stubbed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from core.pipeline import scan_job as sj
from core.pipeline import screener as scr
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE
from tools.marks_corpus import _FROZEN_BREADTH
from tools.marks_corpus import _load_fixture as _load_marks_fixture
from tools.replay import fixture_frame

pytestmark = pytest.mark.regression


class _InlineFuture:
    def __init__(self, fn, *args):
        self._result = fn(*args)

    def result(self):
        return self._result


class _InlinePool:
    def __init__(self, max_workers=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def submit(self, fn, *args):
        return _InlineFuture(fn, *args)


def test_evaluate_frames_fills_the_sink_under_the_flag(monkeypatch):
    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", True)
    monkeypatch.setattr(scr, "ProcessPoolExecutor", _InlinePool)
    monkeypatch.setattr(scr, "as_completed", lambda futures: list(futures))

    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "EGBN:2026-01-15")
    sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
        :pd.Timestamp("2026-01-15")]

    sink = {"rows": [], "stats": {}}
    results, errored = scr._evaluate_frames(
        {e["ticker"]: sliced}, float(e["spy_6m_return"]), _FROZEN_BREADTH,
        near_miss_sink=sink)
    assert errored == 0
    # The three-tuple was unpacked — a fire result is a dict, never a tuple.
    assert all(isinstance(r, dict) for r in results)
    assert sink["rows"], "the sink stayed empty on the frame the e2e proves ruled"
    assert sink["stats"].get("records", 0) > 0
    assert all(r["ticker"] == e["ticker"] and r["scan_date"] == "2026-01-15"
               for r in sink["rows"])


def _stub_scan_job(monkeypatch, calls, fresh: bool):
    monkeypatch.setattr(settings, "ARCHIVE_LIVE_SCANS", True)
    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", True)

    def _fake_screener(mode="download", universe=None, near_miss_sink=None):
        assert near_miss_sink is not None, "the gate condition dropped the sink"
        near_miss_sink["rows"].append({"ticker": "EGBN"})
        near_miss_sink["stats"]["records"] = 3
        # An empty DataFrame, not {}: the panel slot is typed pd.DataFrame and
        # scan_job now reads its last bar for the session stamp.
        return pd.DataFrame(), pd.DataFrame(), [], {}

    def _fake_writer(rows, *, universe_type, enable=False):
        calls.append(("writer", len(rows), universe_type, enable))
        return {"inserted": len(rows), "recurred": 0, "dedup_dropped": 0,
                "ticker_cap_dropped": 0, "global_cap_dropped": 0,
                "flush_error": 0}

    from core.archive import near_miss_writer as nmw
    monkeypatch.setattr(sj, "run_screener", _fake_screener)
    monkeypatch.setattr(sj, "_passes_archive_freshness",
                        lambda *a, **k: fresh)
    monkeypatch.setattr(sj, "generate_dashboard",
                        lambda *a, **k: calls.append("dashboard"))
    monkeypatch.setattr(sj, "_maybe_build_health_board", lambda *a, **k: None)
    monkeypatch.setattr(nmw, "archive_near_miss_rows", _fake_writer)


def test_scan_job_archives_the_sink_on_the_fresh_empty_path(monkeypatch):
    calls: list = []
    _stub_scan_job(monkeypatch, calls, fresh=True)
    res = sj.run_scan_and_export(mode="download")
    assert res.n_setups == 0
    writer_calls = [c for c in calls if isinstance(c, tuple)]
    assert writer_calls == [("writer", 1, DEFAULT_UNIVERSE_TYPE, True)]
    # The empty artifact writes FIRST — a lane escape can never cost it
    # (review finding 5's ordering, pinned here).
    assert calls.index("dashboard") < calls.index(writer_calls[0])


def test_scan_job_says_so_when_the_lane_rows_drop(monkeypatch, capsys):
    calls: list = []
    _stub_scan_job(monkeypatch, calls, fresh=False)
    res = sj.run_scan_and_export(mode="cache")
    assert res.n_setups == 0
    assert not any(isinstance(c, tuple) for c in calls)   # writer never reached
    out = capsys.readouterr().out
    assert "Near-miss lane: 1 row(s) skipped (cache-mode partial coverage)" in out
