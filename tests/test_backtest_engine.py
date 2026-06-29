"""Tests for the standalone-edge backtest harness (core/backtest + tools).

All tests build a small IN-MEMORY / temp sqlite fixture archive — the production
DB is never touched. They verify:
  * read-only loader + episode collapse (REUSES core.archive.episodes)
  * MFE/MAE + barrier distributions sliced by tier/setup_type (MFE headline)
  * null-model: defers honestly without a universe dataset; computes a
    deterministic, seeded edge + bootstrap CI WITH one; detects a real edge
  * multiple-testing haircut (BH-FDR + Bonferroni) math
  * abnormal-return-vs-SPY
  * IS/OOS graceful degradation (absent / single / multi config version)
  * the end-to-end CLI run() over a fixture DB
"""
from __future__ import annotations

import os
import sqlite3
import sys

import numpy as np
import pandas as pd
import pytest

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.backtest import edge_report, is_oos, null_model, stats
from core.backtest.loader import collapse_to_episodes, load_archive, load_episodes


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
def _build_fixture_df(with_config: bool = False) -> pd.DataFrame:
    """A small archive with: one persisting base (AAA over 3 consecutive days),
    distinct setups, two tiers, two setup types, a win/loss/timeout mix."""
    base_cols = dict(
        id=[],
        ticker=[],
        scan_date=[],
        setup_type=[],
        tier=[],
        source=[],
        score=[],
        mfe_20d=[],
        mae_20d=[],
        mfe_60d=[],
        mae_60d=[],
        fwd_return_20d=[],
        fwd_return_60d=[],
        r_multiple_20d=[],
        r_multiple_60d=[],
        barrier_label=[],
    )
    rows = [
        # AAA: persisting base — 3 consecutive scans => ONE episode (first-seen anchor).
        dict(id=1, ticker="AAA", scan_date="2026-04-01", setup_type="LPS", tier="S",
             source="screener", score=90, mfe_20d=0.20, mae_20d=-0.03, mfe_60d=0.30,
             mae_60d=-0.04, fwd_return_20d=0.15, fwd_return_60d=0.25,
             r_multiple_20d=3.0, r_multiple_60d=4.0, barrier_label="win"),
        dict(id=2, ticker="AAA", scan_date="2026-04-02", setup_type="LPS", tier="S",
             source="screener", score=91, mfe_20d=0.19, mae_20d=-0.02, mfe_60d=0.29,
             mae_60d=-0.03, fwd_return_20d=0.14, fwd_return_60d=0.24,
             r_multiple_20d=2.9, r_multiple_60d=3.9, barrier_label="win"),
        dict(id=3, ticker="AAA", scan_date="2026-04-03", setup_type="LPS", tier="S",
             source="screener", score=92, mfe_20d=0.18, mae_20d=-0.02, mfe_60d=0.28,
             mae_60d=-0.03, fwd_return_20d=0.13, fwd_return_60d=0.23,
             r_multiple_20d=2.8, r_multiple_60d=3.8, barrier_label="win"),
        # BBB: distinct, a loss
        dict(id=4, ticker="BBB", scan_date="2026-04-01", setup_type="LPS", tier="A",
             source="screener", score=70, mfe_20d=0.02, mae_20d=-0.15, mfe_60d=0.03,
             mae_60d=-0.20, fwd_return_20d=-0.10, fwd_return_60d=-0.12,
             r_multiple_20d=-1.0, r_multiple_60d=-1.0, barrier_label="loss"),
        # CCC: REBOUND, a timeout
        dict(id=5, ticker="CCC", scan_date="2026-04-02", setup_type="REBOUND", tier="A",
             source="screener", score=65, mfe_20d=0.05, mae_20d=-0.05, mfe_60d=0.06,
             mae_60d=-0.06, fwd_return_20d=0.01, fwd_return_60d=0.02,
             r_multiple_20d=0.5, r_multiple_60d=0.6, barrier_label="timeout"),
        # DDD: REBOUND, a win, distinct day
        dict(id=6, ticker="DDD", scan_date="2026-04-03", setup_type="REBOUND", tier="S",
             source="screener", score=88, mfe_20d=0.25, mae_20d=-0.04, mfe_60d=0.35,
             mae_60d=-0.05, fwd_return_20d=0.20, fwd_return_60d=0.30,
             r_multiple_20d=3.5, r_multiple_60d=5.0, barrier_label="win"),
        # EEE: still maturing — no outcomes yet
        dict(id=7, ticker="EEE", scan_date="2026-06-25", setup_type="LPS", tier="B",
             source="screener", score=60, mfe_20d=None, mae_20d=None, mfe_60d=None,
             mae_60d=None, fwd_return_20d=None, fwd_return_60d=None,
             r_multiple_20d=None, r_multiple_60d=None, barrier_label=None),
    ]
    df = pd.DataFrame(rows)
    if with_config:
        df["engine_config_version"] = [
            "cfgA", "cfgA", "cfgA", "cfgA", "cfgA", "cfgB", "cfgB"
        ]
    return df


def _write_fixture_db(df: pd.DataFrame, path: str) -> None:
    con = sqlite3.connect(path)
    df.to_sql("setup_archive", con, index=False, if_exists="replace")
    con.close()


@pytest.fixture
def fixture_df():
    return _build_fixture_df()


@pytest.fixture
def fixture_db(tmp_path):
    path = os.path.join(str(tmp_path), "fixture.db")
    _write_fixture_db(_build_fixture_df(), path)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Loader + episode collapse
# ─────────────────────────────────────────────────────────────────────────────
def test_load_archive_in_memory_connection():
    con = sqlite3.connect(":memory:")
    _build_fixture_df().to_sql("setup_archive", con, index=False)
    df = load_archive(con=con)
    assert len(df) == 7
    con.close()


def test_collapse_persisting_base_to_one_episode(fixture_df):
    ep = collapse_to_episodes(fixture_df)
    # AAA's 3 consecutive rows collapse to ONE (its first-seen id=1).
    assert (ep["ticker"] == "AAA").sum() == 1
    aaa = ep[ep["ticker"] == "AAA"].iloc[0]
    assert int(aaa["id"]) == 1
    assert int(aaa["episode_scan_count"]) == 3
    # 7 raw rows -> 5 episodes (AAA collapses 3->1).
    assert len(ep) == 5


def test_source_filter(fixture_df):
    con = sqlite3.connect(":memory:")
    df2 = fixture_df.copy()
    df2.loc[df2["ticker"] == "BBB", "source"] = "seed"
    df2.to_sql("setup_archive", con, index=False)
    live = load_archive(con=con, source="screener")
    assert "BBB" not in set(live["ticker"])
    con.close()


def test_load_episodes_end_to_end(fixture_db):
    ep = load_episodes(db_path=fixture_db)
    assert len(ep) == 5
    assert "episode_scan_count" in ep.columns


def test_loader_opens_readonly(fixture_db):
    """The read-only URI connection must reject writes (DB never mutated)."""
    from core.backtest.loader import _connect_readonly
    con = _connect_readonly(fixture_db)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("UPDATE setup_archive SET tier='X'")
    con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Edge report — MFE headline + slices
# ─────────────────────────────────────────────────────────────────────────────
def test_edge_block_headline_is_mfe(fixture_df):
    ep = collapse_to_episodes(fixture_df)
    block = edge_report.edge_block(ep)
    # 5 episodes, but only 4 have mfe_20d (EEE is unmatured).
    assert block["headline_mfe_n"] == 4
    # Median of [0.20(AAA), 0.02(BBB), 0.05(CCC), 0.25(DDD)] = 0.125
    assert block["headline_mfe_median"] == pytest.approx(0.125, abs=1e-9)


def test_barrier_distribution(fixture_df):
    ep = collapse_to_episodes(fixture_df)
    bar = edge_report.barrier_distribution(ep)
    # episodes: AAA win, BBB loss, CCC timeout, DDD win, EEE unlabelled
    assert bar["counts"] == {"win": 2, "loss": 1, "timeout": 1}
    assert bar["n_labelled"] == 4
    assert bar["n_unlabelled"] == 1
    assert bar["win_rate"] == pytest.approx(0.5)


def test_slice_by_tier_and_type(fixture_df):
    ep = collapse_to_episodes(fixture_df)
    report = edge_report.build_edge_report(ep)
    assert set(report["by_tier"].keys()) >= {"S", "A"}
    assert set(report["by_setup_type"].keys()) == {"LPS", "REBOUND"}
    # tier S episodes (AAA, DDD) both winners -> headline median = (0.20+0.25)/2
    assert report["by_tier"]["S"]["headline_mfe_median"] == pytest.approx(0.225)


def test_describe_nan_safe():
    d = edge_report.describe(pd.Series([np.nan, np.nan]))
    assert d["n"] == 0 and d["median"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Null model
# ─────────────────────────────────────────────────────────────────────────────
def test_null_model_defers_without_universe(fixture_df):
    ep = collapse_to_episodes(fixture_df)
    res = null_model.run_null_model(ep, universe_returns=None)
    assert res.available is False
    assert "universe_returns" in res.reason
    # still reports how many screener rows it would have used
    assert res.n_screener == 4


def test_null_model_missing_columns_defers(fixture_df):
    ep = collapse_to_episodes(fixture_df)
    bad = pd.DataFrame({"scan_date": ["2026-04-01"], "ticker": ["ZZZ"]})  # no metric
    res = null_model.run_null_model(ep, universe_returns=bad)
    assert res.available is False
    assert "missing required column" in res.reason


def _universe(metric_mean: float, seed: int = 0) -> pd.DataFrame:
    """A synthetic eligible universe with a controllable mean MFE per day."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in ["2026-04-01", "2026-04-02", "2026-04-03"]:
        for i in range(40):
            rows.append({"scan_date": d, "ticker": f"U{i}_{d}",
                         "mfe_20d": float(rng.normal(metric_mean, 0.05))})
    return pd.DataFrame(rows)


def test_null_model_detects_positive_edge(fixture_df):
    """Screener median MFE (~0.125, with two 0.20+ winners) should beat a
    universe whose names average ~0.0."""
    ep = collapse_to_episodes(fixture_df)
    uni = _universe(metric_mean=0.0, seed=7)
    res = null_model.run_null_model(ep, uni, n_draws=500, n_bootstrap=500, seed=1)
    assert res.available is True
    assert res.edge > 0
    assert res.p_value < 0.5
    assert res.ci_low is not None and res.ci_high is not None


def test_null_model_deterministic(fixture_df):
    ep = collapse_to_episodes(fixture_df)
    uni = _universe(metric_mean=0.05, seed=3)
    a = null_model.run_null_model(ep, uni, n_draws=300, n_bootstrap=300, seed=42)
    b = null_model.run_null_model(ep, uni, n_draws=300, n_bootstrap=300, seed=42)
    assert a.edge == b.edge
    assert a.ci_low == b.ci_low and a.ci_high == b.ci_high
    assert a.p_value == b.p_value


def test_null_model_no_day_overlap_defers(fixture_df):
    ep = collapse_to_episodes(fixture_df)
    uni = _universe(metric_mean=0.0, seed=0)
    uni["scan_date"] = "2099-01-01"  # no overlap with screener days
    res = null_model.run_null_model(ep, uni)
    assert res.available is False
    assert "overlap" in res.reason


# ─────────────────────────────────────────────────────────────────────────────
# Multiple-testing haircut
# ─────────────────────────────────────────────────────────────────────────────
def test_bonferroni_haircut():
    entries = stats.multiple_testing_haircut(
        {"a": 0.01, "b": 0.04, "c": 0.20}, alpha=0.05, method="bonferroni"
    )
    by = {e.label: e for e in entries}
    assert by["a"].p_adjusted == pytest.approx(0.03)   # 0.01 * 3
    assert by["b"].p_adjusted == pytest.approx(0.12)   # 0.04 * 3
    assert by["a"].significant is True
    assert by["b"].significant is False


def test_bh_fdr_haircut_monotone():
    entries = stats.multiple_testing_haircut(
        {"a": 0.001, "b": 0.01, "c": 0.03, "d": 0.5}, alpha=0.05, method="fdr_bh"
    )
    # sorted ascending by raw p; adjusted p must be non-decreasing
    adj = [e.p_adjusted for e in entries]
    assert adj == sorted(adj)
    by = {e.label: e for e in entries}
    assert by["a"].significant is True


def test_haircut_carries_none_pvalues():
    entries = stats.multiple_testing_haircut({"a": 0.01, "b": None}, method="fdr_bh")
    by = {e.label: e for e in entries}
    assert by["b"].significant is False
    assert np.isnan(by["b"].p_adjusted)


def test_haircut_unknown_method_raises():
    with pytest.raises(ValueError):
        stats.multiple_testing_haircut({"a": 0.01}, method="nope")


# ─────────────────────────────────────────────────────────────────────────────
# Abnormal return vs SPY
# ─────────────────────────────────────────────────────────────────────────────
def test_abnormal_return_median():
    # setups beat SPY by +0.05 each
    val = stats.abnormal_return([0.10, 0.20, 0.15], [0.05, 0.15, 0.10])
    assert val == pytest.approx(0.05)


def test_abnormal_return_empty():
    assert stats.abnormal_return([], []) is None


def test_abnormal_return_frame():
    df = pd.DataFrame({"mfe_20d": [0.10, 0.20], "spy_20d": [0.05, 0.05]})
    out = stats.abnormal_return_frame(df, "mfe_20d", "spy_20d")
    assert out["n"] == 2
    assert out["abnormal_median"] == pytest.approx(0.10)
    assert out["reason"] is None


def test_abnormal_return_frame_missing_col():
    df = pd.DataFrame({"mfe_20d": [0.10]})
    out = stats.abnormal_return_frame(df, "mfe_20d", "spy_20d")
    assert out["n"] == 0 and out["reason"]


# ─────────────────────────────────────────────────────────────────────────────
# IS/OOS split
# ─────────────────────────────────────────────────────────────────────────────
def test_is_oos_absent_column_degrades(fixture_df):
    ep = collapse_to_episodes(fixture_df)  # no engine_config_version
    split = is_oos.split_is_oos(ep)
    assert split.available is False
    assert "no 'engine_config_version'" in split.reason
    assert len(split.is_index) == len(ep)  # whole frame is in-sample
    assert len(split.oos_index) == 0


def test_is_oos_single_version_degrades():
    df = _build_fixture_df()
    df["engine_config_version"] = "only_one"
    ep = collapse_to_episodes(df)
    split = is_oos.split_is_oos(ep)
    assert split.available is False
    assert split.n_versions == 1


def test_is_oos_multi_version_splits():
    ep = collapse_to_episodes(_build_fixture_df(with_config=True))
    split = is_oos.split_is_oos(ep)
    assert split.available is True
    assert split.n_versions == 2
    # cfgA seen earliest -> in-sample; cfgB latest -> out-of-sample
    assert split.is_versions == ("cfgA",)
    assert split.oos_versions == ("cfgB",)
    assert len(split.oos_index) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end CLI
# ─────────────────────────────────────────────────────────────────────────────
def test_cli_run_over_fixture_db(fixture_db, tmp_path):
    from tools import backtest_engine
    json_out = os.path.join(str(tmp_path), "report.json")
    result = backtest_engine.run(db_path=fixture_db, json_path=json_out)
    assert result["composition"]["n"] == 5
    assert result["edge"]["overall"]["headline_mfe_n"] == 4
    # null model defers (no universe injected)
    assert result["null_model"]["overall"]["available"] is False
    # IS/OOS degrades (fixture has no config column)
    assert result["is_oos"]["available"] is False
    assert os.path.exists(json_out)


def test_cli_run_with_universe(fixture_db):
    from tools import backtest_engine
    uni = _universe(metric_mean=0.0, seed=11)
    # The CLI run() signature accepts an injected universe_returns; verify that
    # the null model is computed (not deferred) when a universe is supplied.
    result = backtest_engine.run(db_path=fixture_db, universe_returns=uni, seed=5)
    assert result["null_model"]["overall"]["available"] is True
    assert result["null_model"]["overall"]["edge"] is not None
    # the haircut should now have at least the 'overall' slice to correct
    assert result["haircut"]["computed"] is True


def test_cli_abnormal_defers_without_spy(fixture_db):
    from tools import backtest_engine
    result = backtest_engine.run(db_path=fixture_db)
    assert result["abnormal_vs_spy"]["available"] is False


def test_cli_abnormal_computes_with_spy_col(tmp_path):
    """When a per-row same-window SPY return column exists, abnormal return
    computes (machinery wired through the CLI)."""
    from tools import backtest_engine
    df = _build_fixture_df()
    df["spy_20d"] = 0.05  # SPY made +5% in each window
    path = os.path.join(str(tmp_path), "fixture_spy.db")
    _write_fixture_db(df, path)
    result = backtest_engine.run(db_path=path, spy_col="spy_20d")
    ab = result["abnormal_vs_spy"]
    assert ab["available"] is True
    # 4 matured episodes: MFE_20d [0.20, 0.02, 0.05, 0.25] minus 0.05 -> median 0.075
    assert ab["abnormal_median"] == pytest.approx(0.075, abs=1e-9)
