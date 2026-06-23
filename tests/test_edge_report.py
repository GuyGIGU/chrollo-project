import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.archive.analyze import matured_subset_summary, signal_edge, verdict_consistency
import tools.edge_report as edge_report_module


def test_matured_subset_summary_describes_only_populated_20d_rows():
    df = pd.DataFrame({
        "scan_date": ["2026-05-31", "2026-06-01", "2026-06-07", "2026-06-21"],
        "fwd_return_20d": [0.08, -0.03, 0.01, None],
        "spy_trend": ["BULLISH", "BULLISH", "NEUTRAL", "BULLISH"],
        "tier": ["S", "A", "S", "B"],
        "setup_type": ["LPS", "LPS", "REBOUND", "LPS"],
        "htf_w_reaccum": [0, 1, 0, 1],
        "htf_w_daily_nested": [0, 0, 0, 1],
        "score_traversal_quality": [None, 0.0, 6.0, 8.0],
    })

    summary = matured_subset_summary(df)

    assert summary["n"] == 3
    assert summary["total"] == 4
    assert summary["date_min"] == "2026-05-31"
    assert summary["date_max"] == "2026-06-07"
    assert summary["spy_trend"] == {"BULLISH": 2, "NEUTRAL": 1}
    assert summary["tier"] == {"S": 2, "A": 1}
    assert summary["setup_type"] == {"LPS": 2, "REBOUND": 1}
    assert summary["htf_tag_rows"] == 1
    assert summary["htf_value_rows"] == 3
    assert summary["traversal_quality_n"] == 2
    assert summary["traversal_quality_positive"] == 1


def test_matured_subset_summary_handles_zero_matured_rows():
    df = pd.DataFrame({
        "scan_date": ["2026-06-21"],
        "fwd_return_20d": [None],
        "spy_trend": ["BULLISH"],
    })

    summary = matured_subset_summary(df)

    assert summary["n"] == 0
    assert summary["date_min"] is None
    assert summary["spy_trend"] == {}


def test_verdict_consistency_confirms_only_same_direction_multi_target_edges():
    rows = [
        {
            "feature": "score_rs_bonus",
            "corr_by_target": {
                "durable_win": -0.31,
                "barrier_win": -0.22,
                "fwd_return_20d": -0.05,
            },
        },
        {
            "feature": "score_base_age",
            "corr_by_target": {
                "durable_win": 0.28,
                "fwd_return_20d": -0.26,
            },
        },
        {
            "feature": "score_adr",
            "corr_by_target": {
                "durable_win": 0.27,
                "fwd_return_20d": 0.04,
            },
        },
    ]

    out = {
        row["feature"]: row
        for row in verdict_consistency(rows, noise_floor=0.15)
    }

    assert out["score_rs_bonus"]["status"] == "confirmed"
    assert out["score_rs_bonus"]["direction"] == "harmful"
    assert out["score_base_age"]["status"] == "flip"
    assert out["score_base_age"]["direction"] == "mixed"
    assert out["score_adr"]["status"] == "insufficient"
    assert out["score_adr"]["direction"] is None


def test_verdict_consistency_ignores_untrustworthy_secondary_target():
    n = 30
    win = [1.0, 0.0] * (n // 2)
    fwd20 = [None] * 22 + [1.0, 0.0] * 4
    df = pd.DataFrame({
        "durable_win": win,
        "fwd_return_20d": fwd20,
        "score_box_tightness": win,
    })

    edge = signal_edge(df, targets=["durable_win", "fwd_return_20d"], min_n=8)
    row = next(r for r in edge["rows"] if r["feature"] == "score_box_tightness")
    result = verdict_consistency(
        [row],
        targets=["durable_win", "fwd_return_20d"],
        noise_floor=edge["noise_floor"],
    )[0]

    assert row["target_stats"]["durable_win"]["trustworthy"] is True
    assert row["target_stats"]["fwd_return_20d"]["n"] == 8
    assert row["target_stats"]["fwd_return_20d"]["trustworthy"] is False
    assert result["status"] == "insufficient"
    assert result["direction"] is None


def test_edge_report_prints_updater_count_as_archive_wide(monkeypatch, capsys):
    counts = iter([5, 7])
    called = {}

    monkeypatch.setattr(edge_report_module, "_populated_20d_count", lambda _source: next(counts))
    monkeypatch.setattr(edge_report_module, "update_forward_returns", lambda: 42)

    def fake_run(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(edge_report_module.analyze, "run", fake_run)

    edge_report_module.run_edge_report("20260629", source="screener", mature=True)

    out = capsys.readouterr().out
    assert "Forward-return maturation (screener report scope): fwd_return_20d 5 -> 7 (+2)" in out
    assert "updater touched 42 archive row(s) across all sources" in out
    assert called["source"] == "screener"
    assert called["md_path"] == str(Path("docs") / "edge_read_20260629.md")
