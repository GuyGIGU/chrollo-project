"""The Home edge tile measures ONE reader at a time (his word Mon 12/10/2026, option A).

The archive holds two readers' fires since the flip of Sat 10/10/2026. Their letters are
different verdicts (an old S and a new S are not one grade), so the tile's headline and
tiers measure the reader that wrote the latest scan, and the other reader's fires ride
under them as one baseline line, never pooled. The split happens BEFORE the episode
collapse, so a base the old engine first saw on a Friday and the new reader on the
Monday is the new reader's own first sighting too.

In-memory data only, never the live archive.
"""
import sqlite3
import sys

import pandas as pd

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "webapp" / "backend"))

from core.backtest import loader  # noqa: E402
from domains.archive import edge  # noqa: E402


def _row(id_, ticker, day, *, new, tier="S", mfe=0.10, source="screener"):
    return {"id": id_, "ticker": ticker, "scan_date": day, "setup_type": "LPS",
            "universe_type": "us_equities", "source": source, "tier": tier,
            "mfe_20d": mfe, "mfe_to_date": mfe, "barrier_label": None,
            "two_eyes_has_mini": (0 if new else None)}


def _archive(rows):
    con = sqlite3.connect(":memory:")
    pd.DataFrame(rows).to_sql("setup_archive", con, index=False)
    return con


def test_a_base_both_readers_saw_is_an_episode_for_each():
    """Fri 09/10 the old engine, Mon 12/10 the new reader, one base: collapsed first,
    the Monday would be the old engine's continuation and the new reader would own
    nothing."""
    con = _archive([_row(1, "AAA", "2026-10-09", new=False),
                    _row(2, "AAA", "2026-10-12", new=True)])
    by_reader = loader.load_episodes_by_reader(con=con)
    assert list(by_reader[loader.READER_OLD]["id"]) == [1]
    assert list(by_reader[loader.READER_NEW]["id"]) == [2]


def test_an_archive_without_the_new_family_is_the_old_readers():
    df = pd.DataFrame({"id": [1, 2]})
    assert set(loader.reader_of_rows(df)) == {loader.READER_OLD}


def _tile(monkeypatch, rows):
    con = _archive(rows)
    monkeypatch.setattr(edge, "load_episodes_by_reader",
                        lambda **kw: loader.load_episodes_by_reader(con=con, **kw))
    monkeypatch.setattr(edge, "load_calibration_setups", lambda: pd.DataFrame())
    return edge._compute()


def _old_and_new():
    # The old engine: 4 fires, 2 of them +40%. The new reader: 2 fires, none +25%.
    old = [_row(i, f"O{i}", "2026-10-09", new=False, mfe=m)
           for i, m in enumerate((0.45, 0.50, 0.05, 0.05), start=1)]
    new = [_row(10 + i, f"N{i}", "2026-10-12", new=True, tier="A", mfe=0.05) for i in (1, 2)]
    return old + new


def test_the_headline_and_tiers_are_the_current_reader_alone(monkeypatch):
    tile = _tile(monkeypatch, _old_and_new())
    assert tile["reader"] == "new" and tile["reader_since"] == "2026-10-12"
    assert tile["n_unbiased"] == 2
    assert set(tile["by_tier"]) == {"A"}, "an old engine's S may not sit among the new grades"
    assert [b["rate"] for b in tile["tail"]["bands"]] == [0.0, 0.0]


def test_the_other_reader_is_one_baseline_line(monkeypatch):
    base = _tile(monkeypatch, _old_and_new())["baseline"]
    assert base["reader"] == "old" and base["n"] == 4
    assert (base["first_scan"], base["last_scan"]) == ("2026-10-09", "2026-10-09")
    assert [b["rate"] for b in base["tail"]["bands"]] == [0.5, 0.5]


def test_switched_back_the_old_engine_is_current_again(monkeypatch):
    rows = _old_and_new() + [_row(20, "LATE", "2026-10-13", new=False)]
    tile = _tile(monkeypatch, rows)
    assert tile["reader"] == "old" and tile["baseline"]["reader"] == "new"


def test_on_a_shared_scan_day_the_reader_that_wrote_last_is_current(monkeypatch):
    """The flip: both readers wrote rows for Fri 09/10/2026. The day ties; the row
    written last says which reader is running, whichever order the readers are listed in."""
    old_last = [_row(1, "N1", "2026-10-09", new=True), _row(2, "O1", "2026-10-09", new=False)]
    assert _tile(monkeypatch, old_last)["reader"] == "old"
    new_last = [_row(1, "O1", "2026-10-09", new=False), _row(2, "N1", "2026-10-09", new=True)]
    assert _tile(monkeypatch, new_last)["reader"] == "new"


def test_hand_picked_rows_count_in_neither_reader(monkeypatch):
    rows = _old_and_new() + [_row(30, "SEED", "2026-10-14", new=True, source="seed")]
    tile = _tile(monkeypatch, rows)
    assert tile["reader_since"] == "2026-10-12" and tile["n_unbiased"] == 2
