"""Unit pins for ``tools.research.build_universe_returns._validate_out`` — the output-path
guard that stops the universe-returns builder from clobbering a protected file.

``_validate_out`` is pure path-string logic (no filesystem writes): it REFUSES
(``SystemExit``) the live trading journal, the read-only as-traded price cache and
its ``cache_meta.json`` sidecar, anything under ``webapp/backend``, and any
non-``.parquet`` output; it ACCEPTS a normal scratch ``*.parquet`` outside those.
These tests touch neither the live DB nor the cache — they only assert the guard's
accept/refuse verdict on path strings.
"""
import os
import sys

import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from tools.research.build_universe_returns import _validate_out


# ── refusals (each raises SystemExit) ────────────────────────────────────────
@pytest.mark.parametrize("name", [
    "trading_journal.db",
    "TRADING_JOURNAL.DB",       # case-insensitive: basename is lowered first
    "Trading_Journal.DB",
])
def test_refuses_trading_journal_any_case(name, tmp_path):
    with pytest.raises(SystemExit):
        _validate_out(str(tmp_path / name))


@pytest.mark.parametrize("name", [
    "market_data_cache_5y.parquet",   # the as-traded price cache basename
    "MARKET_DATA_CACHE_5Y.PARQUET",   # case-insensitive
    "cache_meta.json",                # the cache metadata sidecar
    "CACHE_META.JSON",
])
def test_refuses_price_cache_and_meta(name, tmp_path):
    with pytest.raises(SystemExit):
        _validate_out(str(tmp_path / name))


def test_refuses_path_under_webapp_backend():
    # A .parquet name is fine, but the webapp/backend read-only zone is not — the
    # backend check fires before the extension check.
    under_backend = ROOT / "webapp" / "backend" / "scratch.parquet"
    with pytest.raises(SystemExit):
        _validate_out(str(under_backend))


def test_refuses_non_parquet_extension(tmp_path):
    with pytest.raises(SystemExit):
        _validate_out(str(tmp_path / "universe_returns.csv"))


# ── acceptance (a normal scratch parquet outside the protected set) ──────────
def test_accepts_normal_scratch_parquet(tmp_path):
    out = tmp_path / "universe_returns.parquet"
    result = _validate_out(str(out))
    # Returns the absolute path; no exception raised.
    assert result == os.path.abspath(str(out))
    assert result.lower().endswith(".parquet")
    assert os.path.basename(result) == "universe_returns.parquet"
