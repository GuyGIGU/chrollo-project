"""A read that fell over is said as a failed read, never as "no setup" (council review 2026-10-09, finding 3).

Under the new reader the door RAISES when the reader refuses a chart (a trading day missing from the middle of its
history refused 27 charts on Thu 08/10/2026). The seed's re-read caught every ValueError as "no setup", so the
manual add answered "screener did not fire ... no valid LPS at that date" for a chart that was never read, and the
winners seed dropped the date without counting it.

Real route handler against a real throwaway SQLite database, the download monkeypatched at its source; never the
live DB, never a booted app.
"""
import sys

import pandas as pd
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
import database  # noqa: E402
from domains.archive.actions import add_setup_manually  # noqa: E402
from domains.archive.schemas import ManualSetupIn  # noqa: E402

#: One of his own drawn charts (sealed fixture bars, ALB to Mon 13/04/2026): a chart the universe door admits, so
#: the read runs and refuses the hole. A flat made-up chart never reaches the read (the door says "not scanned").
CHART = "ALB:2026-04-13"
SCAN_DATE = "2026-04-13"


def _chart_with_a_hole():
    """His chart with one trading day deleted from the middle: the new reader's frame contract refuses it."""
    from core.calibration.replay import load_sealed_fixture

    frames, _ = load_sealed_fixture()
    df = frames[CHART]
    return df.drop(df.index[len(df) // 2])


def test_the_seeds_re_read_says_a_failed_read_instead_of_no_setup():
    from core.archive import seed
    from engine_alpha import gate

    with pytest.raises(gate.ReadFailed, match="missing from the middle"):
        seed._evaluate_at_date(_chart_with_a_hole())


def test_the_manual_add_says_the_read_failed_and_why(monkeypatch):
    import core.pipeline.market_data.downloads as downloads

    engine = database.make_sqlite_engine(":memory:")
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    monkeypatch.setattr(downloads, "_batched_download", lambda tickers, params, label: _chart_with_a_hole())
    try:
        with pytest.raises(HTTPException) as caught:
            add_setup_manually(ManualSetupIn(ticker="AAA", scan_date=SCAN_DATE), db)
    finally:
        db.close()
        engine.dispose()
    assert caught.value.status_code == 422
    assert "the read failed" in caught.value.detail and "missing from the middle" in caught.value.detail
    assert "did not fire" not in caught.value.detail


def test_the_seeds_window_counts_its_failed_reads_and_says_so():
    """The seed's own walk (verify-2 of the fix run: the loop was run by no test). Every day of the window reads
    his chart with its hole, so every day is a failed read: none fires, and the words say the read FAILED."""
    import pandas as pd

    from core.archive import seed

    best, day, failed = seed._best_day(_chart_with_a_hole(), pd.Timestamp(SCAN_DATE), None)
    assert best is None and day is None
    assert failed and all("missing from the middle" in f for f in failed)
    words = seed._window_words("ALB", SCAN_DATE, best, failed)
    assert f"read FAILED on {len(failed)} of its days" in words and "did not fire" not in words


def test_any_other_error_still_skips_the_day_as_before(monkeypatch):
    """Only a refused read is told apart: a plain error on a day is skipped as it always was ("did not fire")."""
    import pandas as pd

    from core.archive import seed
    from engine_alpha import gate

    def broken(*args, **kwargs):
        raise ValueError("some other fault")

    monkeypatch.setattr(gate, "run_eval_chain", broken)
    best, day, failed = seed._best_day(_chart_with_a_hole(), pd.Timestamp(SCAN_DATE), None)
    assert (best, day, failed) == (None, None, [])
    assert seed._window_words("ALB", SCAN_DATE, best, failed).endswith("screener did not fire in -10/+3d window.")
