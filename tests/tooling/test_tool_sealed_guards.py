"""EC-14 refusal legs for the five tools whose user-supplied write paths
(--json / --capture / --out) went around the ONE sealed-output guard
(council review 2026-08-20). Each leg exercises the tool's own
path-validation seam only — the heavy pass behind it is stubbed to fail
the test if reached, proving the refusal fires PRE-FLIGHT."""
import os
import sys

import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from tools.research import backtest_engine, build_universe_returns  # noqa: E402
from tools.regression import fold_parity  # noqa: E402
from tools.research import full_package_render  # noqa: E402
from tools.audits import provider_parity  # noqa: E402

SEALED = os.path.join(str(ROOT), "docs", "marks", "evil_report.json")


def _backtest(sealed, monkeypatch):
    monkeypatch.setattr(backtest_engine, "load_episodes",
                        lambda *a, **k: pytest.fail("guard fired after the archive load"))
    backtest_engine.run(json_path=sealed)


def _fold(sealed, monkeypatch):
    monkeypatch.setattr(fold_parity, "run_full",
                        lambda: pytest.fail("guard fired after the fixture run"))
    monkeypatch.setattr(sys, "argv", ["fold_parity", "--capture", sealed])
    fold_parity.main()


def _provider(sealed, monkeypatch):
    monkeypatch.setattr(provider_parity, "resolve_source",
                        lambda *a: pytest.fail("guard fired after the fetch"))
    provider_parity.run_snapshot("cache", None, sealed)


def _render(sealed, monkeypatch):
    # --out is a PNG DIRECTORY here: the sealed dir itself must refuse.
    monkeypatch.setattr(full_package_render.pd, "read_parquet",
                        lambda *a, **k: pytest.fail("guard fired after the cache load"))
    full_package_render.render(["AAPL"], window=0, out_dir=os.path.dirname(sealed),
                               show_events=True, show_macro=False, cache=None)


def _universe(sealed, monkeypatch):
    build_universe_returns._validate_out(sealed)


@pytest.mark.parametrize("entry", [_backtest, _fold, _provider, _render, _universe],
                         ids=["backtest_engine", "fold_parity", "provider_parity",
                              "full_package_render", "build_universe_returns"])
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
