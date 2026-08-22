"""The archive chart route's bounded `glance` variant (Finviz plan Task 11).

A hover-size chart cannot show 370 bars, and the archive is the ONE glance path
that reaches the vendor whose rate bucket the nightly scans depend on. So the
variant trims the RESPONSE while leaving the provider window byte-identical —
same call, same market-data cache key, so a hover followed by a click never
costs two pulls for the same name.

The trim is the dangerous part, and these tests exist for one specific lie: the
payload's r_anchor/s_anchor are offsets from the BOX START, which the frontend
reconstructs as len(candles) - 1 - forward_bars - base_len + 1 and clamps at
zero. A window shorter than the box makes that clamp silently pin the box to bar
zero, painting the rails and the grey root swing on the wrong bars — a chart
that misreports the structure rather than declining to draw it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
from routers import archive_browse  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

SCAN_DATE = "2026-06-01"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    sess = sessionmaker(bind=engine)()
    yield sess
    sess.close()
    engine.dispose()


def _frame(bars: int, last_day: str = "2026-07-01") -> pd.DataFrame:
    """A daily OHLCV frame ending `last_day`, business days back."""
    index = pd.bdate_range(end=pd.Timestamp(last_day), periods=bars)
    return pd.DataFrame(
        {
            "Open": [10.0 + i * 0.01 for i in range(bars)],
            "High": [10.5 + i * 0.01 for i in range(bars)],
            "Low": [9.5 + i * 0.01 for i in range(bars)],
            "Close": [10.2 + i * 0.01 for i in range(bars)],
            "Volume": [1_000 + i for i in range(bars)],
        },
        index=index,
    )


def _setup(db, **kw):
    row = archive_models.SetupArchive(
        ticker=kw.pop("ticker", "NVDA"),
        scan_date=kw.pop("scan_date", SCAN_DATE),
        tier=kw.pop("tier", "A"),
        setup_type=kw.pop("setup_type", "VCP"),
        score=kw.pop("score", 71.0),
        base_length=kw.pop("base_length", 40),
        lps_length=kw.pop("lps_length", 6),
        r_level=kw.pop("r_level", 11.0),
        s_level=kw.pop("s_level", 9.0),
        current_price=kw.pop("current_price", 10.2),
        **kw,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def provider(monkeypatch):
    """Record every provider call so 'the window never changes' is provable."""
    calls = []
    frame = {"df": _frame(400)}

    def fake_daily_candle_frame(ticker, days, start=None, end=None, auto_adjust=True):
        calls.append({"ticker": ticker, "start": start, "end": end,
                      "auto_adjust": auto_adjust, "days": days})
        return frame["df"]

    import services.market_data as market_data

    monkeypatch.setattr(market_data, "daily_candle_frame", fake_daily_candle_frame)
    return {"calls": calls, "frame": frame}


def _chart(db, setup_id, glance=False):
    return archive_browse.get_setup_chart(setup_id, glance=glance, db=db)


# --- the budget itself -------------------------------------------------------

def test_budget_always_covers_the_whole_box_plus_context():
    """Derived from the setup, never a constant: live archive base lengths run
    to 433 bars (median 37, p99 196), so any fixed cap mis-frames the tail."""
    for base, lps in [(0, 0), (37, 5), (130, 10), (196, 12), (433, 20)]:
        budget = archive_browse.glance_bar_budget(base, lps)
        assert budget >= base + lps, f"box of {base}+{lps} must fit in {budget}"
        assert budget >= 130, "a tiny box still gets a readable window"

    # Nulls are the real archive's shape for boxless rows, not a hypothetical.
    assert archive_browse.glance_bar_budget(None, None) == 130


# --- the trim ----------------------------------------------------------------

def test_glance_trims_the_response_but_never_the_provider_window(db, provider):
    row = _setup(db, base_length=40, lps_length=6)

    full = _chart(db, row.id)
    glance = _chart(db, row.id, glance=True)

    assert len(glance["candles"]) < len(full["candles"])
    assert len(glance["candles"]) == len(glance["volumes"])

    # ONE window shape for both calls -> one market-data cache key -> a hover
    # followed by a click costs a single vendor pull.
    assert len(provider["calls"]) == 2
    assert provider["calls"][0] == provider["calls"][1]


def test_glance_keeps_the_box_and_the_forward_bars_whole(db, provider):
    """The trim takes from the OLD end only. Both base_len and forward_bars are
    anchored to the right edge, so the box cannot move under them."""
    row = _setup(db, base_length=40, lps_length=6)

    full = _chart(db, row.id)
    glance = _chart(db, row.id, glance=True)

    assert glance["forward_bars"] == full["forward_bars"]
    assert glance["base_len"] == full["base_len"]
    # The kept bars are a suffix of the full series — same bars, fewer of them.
    assert glance["candles"] == full["candles"][-len(glance["candles"]):]
    assert glance["volumes"] == full["volumes"][-len(glance["volumes"]):]

    # The box start the frontend reconstructs must land at the same DATE in both.
    def box_start_date(payload):
        index = len(payload["candles"]) - 1 - payload["forward_bars"] - payload["base_len"] + 1
        assert index > 0, "a clamped-to-zero box start is the bug this guards"
        return payload["candles"][index]["time"]

    assert box_start_date(glance) == box_start_date(full)


def test_a_box_longer_than_the_floor_widens_the_window(db, provider):
    """A 300-bar base must not be cropped to a 130-bar window."""
    row = _setup(db, base_length=300, lps_length=10)
    glance = _chart(db, row.id, glance=True)

    assert len(glance["candles"]) >= 300 + 10
    index = len(glance["candles"]) - 1 - glance["forward_bars"] - glance["base_len"] + 1
    assert index >= 0


def test_a_history_shorter_than_the_budget_is_served_whole(db, provider):
    provider["frame"]["df"] = _frame(60)
    row = _setup(db, base_length=20, lps_length=3)

    full = _chart(db, row.id)
    glance = _chart(db, row.id, glance=True)

    assert glance["candles"] == full["candles"]


# --- the envelope stays put --------------------------------------------------

def test_the_unparameterized_call_is_unchanged(db, provider):
    """Every top-level key is load-bearing — useArchiveChart stores the raw JSON
    and ArchiveTab spreads it straight into ScreenerModal."""
    row = _setup(db)
    full = _chart(db, row.id)

    assert set(full) == {
        "candles", "volumes", "base_len", "R", "S", "lps_len", "lps_offset",
        "r_anchor", "s_anchor", "tier", "setup", "forward_bars",
        "annotations",
    }  # the legacy raw score left this envelope at the 2026-08-23 retirement


def test_glance_answers_with_the_same_keys_and_the_same_rescaled_levels(db, provider):
    """The trim is a slice, not a different payload: the R/S adjustment rescale
    must survive it or the rails float off the base."""
    row = _setup(db)
    full = _chart(db, row.id)
    glance = _chart(db, row.id, glance=True)

    assert set(glance) == set(full)
    for key in ("R", "S", "tier", "setup", "r_anchor", "s_anchor", "annotations"):
        assert glance[key] == full[key]


def test_a_missing_setup_still_404s_on_the_glance_path(db, provider):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as err:
        _chart(db, 9999, glance=True)
    assert err.value.status_code == 404
