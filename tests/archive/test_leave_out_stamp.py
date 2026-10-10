"""A bad night is left out of the winner report and the edge read BY ITS STAMP.

Go-live plan task 7. After the flip, a bad first night keeps its rows (the
evidence is never deleted), but the two studies that judge the engine must be
able to read the archive as if that night had never been written. Every row
carries the engine stamp that wrote it (`engine_config_version`), so the
studies take one stamp to leave out, by name: the full hash, or its first 8+
characters as the flag ledger prints them.

The rows are left out BEFORE the re-flags are collapsed to episodes: a setup
first seen on the bad night anchors on its first GOOD night, not on a row
that no longer counts.
"""
from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

from _paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "webapp" / "backend"))

BAD = "cdb7ee2d98a8aab687c04a70a7ddc41c2271fa7286517ac61ab4dde3da4836d1"
GOOD = "8cae6fd9415f92220ee5d7cb0b7e98dfd9a576fe49dadcac535f0f08f2482e6c"


def _rows() -> pd.DataFrame:
    """AAA: first seen on the BAD night, held two good nights after it.
    BBB: a bad-night-only fire. CCC: a good-night fire."""
    def row(i, ticker, day, stamp, mfe):
        return dict(id=i, ticker=ticker, scan_date=day, setup_type="LPS", tier="S",
                    source="screener", score=90, engine_config_version=stamp,
                    mfe_to_date=mfe, mae_to_date=-0.02, ret_to_date=mfe / 2,
                    bars_to_date=20, mfe_20d=mfe, mae_20d=-0.02, mfe_60d=mfe,
                    mae_60d=-0.02, fwd_return_20d=mfe / 2, fwd_return_60d=mfe / 2,
                    r_multiple_20d=1.0, r_multiple_60d=1.0, barrier_label="win",
                    abnormal_ret_to_date=mfe / 2)
    return pd.DataFrame([
        row(1, "AAA", "2026-10-12", BAD, 0.30),
        row(2, "AAA", "2026-10-13", GOOD, 0.20),
        row(3, "AAA", "2026-10-14", GOOD, 0.10),
        row(4, "BBB", "2026-10-12", BAD, 0.90),
        row(5, "CCC", "2026-10-13", GOOD, 0.05),
    ])


def _db(tmp_path) -> str:
    """The archive built through the backend's own model (every column the
    report reads exists), holding the five rows above."""
    import archive_models
    import database
    from sqlalchemy.orm import sessionmaker

    path = os.path.join(str(tmp_path), "archive.db")
    engine = database.make_sqlite_engine(path)
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    columns = {c.name for c in archive_models.SetupArchive.__table__.columns}
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        for row in _rows().to_dict("records"):
            session.add(archive_models.SetupArchive(
                **{k: v for k, v in row.items() if k in columns}))
        session.commit()
    finally:
        session.close()
        engine.dispose()
    return path


# --------------------------------------------------------------------------- #
# The one helper both studies use                                             #
# --------------------------------------------------------------------------- #
def test_the_full_stamp_and_its_short_form_both_name_the_night():
    from core.archive.analyze_features import leave_out_stamp

    for name in (BAD, BAD[:8]):
        kept, n_out = leave_out_stamp(_rows(), name)
        assert n_out == 2
        assert sorted(kept["id"]) == [2, 3, 5]
        assert BAD not in set(kept["engine_config_version"])


def test_a_name_shorter_than_eight_characters_is_refused():
    """'c' or 'cd' could name several stamps; the report must not guess."""
    from core.archive.analyze_features import leave_out_stamp

    with pytest.raises(ValueError, match="8"):
        leave_out_stamp(_rows(), BAD[:7])


def test_a_stamp_no_row_carries_leaves_every_row():
    from core.archive.analyze_features import leave_out_stamp

    kept, n_out = leave_out_stamp(_rows(), "0123456789abcdef")
    assert n_out == 0
    assert len(kept) == 5


# --------------------------------------------------------------------------- #
# The edge read                                                               #
# --------------------------------------------------------------------------- #
def test_the_edge_read_leaves_the_night_out_before_episodes(tmp_path):
    from tools.research import backtest_engine

    path = _db(tmp_path)
    whole = backtest_engine.run(db_path=path)
    assert whole["composition"]["n"] == 3          # AAA, BBB, CCC episodes

    left = backtest_engine.run(db_path=path, leave_out_stamp=BAD[:8])
    assert left["composition"]["n"] == 2           # BBB was a bad-night-only fire
    assert left["left_out_stamp"] == {"stamp": BAD[:8], "rows": 2}
    # AAA now anchors on its first GOOD night (mfe 0.20), not the bad one (0.30)
    assert left["edge"]["headline"]["headline_mfe_median"] == pytest.approx(0.125)


def test_the_edge_read_takes_the_flag_on_its_command_line(tmp_path, monkeypatch):
    from tools.research import backtest_engine

    seen = {}
    monkeypatch.setattr(backtest_engine, "run", lambda **kw: seen.update(kw))
    monkeypatch.setattr("sys.argv", ["backtest_engine", "--db", _db(tmp_path),
                                     "--leave-out-stamp", BAD[:8]])
    backtest_engine.main()
    assert seen["leave_out_stamp"] == BAD[:8]


# --------------------------------------------------------------------------- #
# The winner report                                                           #
# --------------------------------------------------------------------------- #
def test_the_winner_report_leaves_the_night_out_and_says_so(tmp_path, monkeypatch, capsys):
    from core.archive import analyze

    monkeypatch.setattr(analyze, "_DB_PATH", _db(tmp_path))
    analyze.run(leave_out_stamp=BAD[:8])
    report = capsys.readouterr().out
    assert f"Left out engine stamp {BAD[:8]}: 2 rows" in report
    assert "Episode dedup: 3 raw rows -> 2 episodes" in report


def test_the_winner_report_takes_the_flag_on_its_command_line(monkeypatch):
    from core.archive import analyze

    seen = {}
    monkeypatch.setattr(analyze, "run", lambda **kw: seen.update(kw))
    monkeypatch.setattr("sys.argv", ["analyze", "--leave-out-stamp", BAD[:8]])
    analyze.main()
    assert seen["leave_out_stamp"] == BAD[:8]


def test_without_the_flag_the_winner_report_is_unchanged(tmp_path, monkeypatch, capsys):
    from core.archive import analyze

    monkeypatch.setattr(analyze, "_DB_PATH", _db(tmp_path))
    analyze.run()
    report = capsys.readouterr().out
    assert "Left out engine stamp" not in report
    assert "Episode dedup: 5 raw rows -> 3 episodes" in report
