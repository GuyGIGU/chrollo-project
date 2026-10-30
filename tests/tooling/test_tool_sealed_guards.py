"""EC-14 refusal legs for the tools whose user-supplied write paths
(--json / --capture / --out) went around the ONE sealed-output guard
(council review 2026-08-20). Each leg exercises the tool's own
path-validation seam only — the heavy pass behind it is stubbed to fail
the test if reached, proving the refusal fires PRE-FLIGHT. The two
signal-edge tools (backtest_exits --json, backtest_backfill --db) took the
same guard when they were ported onto the domain layout (2026-09-24)."""
import os
import sys

import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from tools.research import backtest_backfill, backtest_engine, backtest_exits, build_universe_returns  # noqa: E402
from tools.audits import provider_parity  # noqa: E402

SEALED = os.path.join(str(ROOT), "docs", "marks", "evil_report.json")


def _backtest(sealed, monkeypatch):
    monkeypatch.setattr(backtest_engine, "load_episodes",
                        lambda *a, **k: pytest.fail("guard fired after the archive load"))
    backtest_engine.run(json_path=sealed)


def _provider(sealed, monkeypatch):
    monkeypatch.setattr(provider_parity, "resolve_source",
                        lambda *a: pytest.fail("guard fired after the fetch"))
    provider_parity.run_snapshot("cache", None, sealed)


def _universe(sealed, monkeypatch):
    build_universe_returns._validate_out(sealed)


def _exits(sealed, monkeypatch):
    monkeypatch.setattr(backtest_exits, "load_episodes",
                        lambda *a, **k: pytest.fail("guard fired after the archive load"))
    backtest_exits.run_exits(db_path=None, cache_path=None, ladder=[(3.0, 1.0)],
                             json_path=sealed)


def _backfill(sealed, monkeypatch):
    # --db is the scratch archive the backfill WRITES: a sealed path must refuse.
    monkeypatch.setattr(backtest_backfill.pd, "read_parquet",
                        lambda *a, **k: pytest.fail("guard fired after the cache load"))
    backtest_backfill.run_backfill(db_path=sealed)


@pytest.mark.parametrize("entry", [_backtest, _provider, _universe, _exits, _backfill],
                         ids=["backtest_engine", "provider_parity", "build_universe_returns",
                              "backtest_exits", "backtest_backfill"])
def test_user_supplied_write_paths_refuse_the_sealed_dirs(entry, monkeypatch):
    with pytest.raises(ValueError, match="sealed"):
        entry(SEALED, monkeypatch)
    assert not os.path.exists(SEALED)


def test_validate_out_keeps_its_own_refusals_on_top(tmp_path):
    # The shared guard runs FIRST (EC-3: sealed knowledge lives in one place);
    # the tool's extra DB/cache/backend refusals still bite behind it.
    assert build_universe_returns._validate_out(str(tmp_path / "u.parquet"))
    with pytest.raises(SystemExit, match="trading_journal.db"):
        build_universe_returns._validate_out(str(tmp_path / "trading_journal.db"))
