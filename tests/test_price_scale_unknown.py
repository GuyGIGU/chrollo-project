"""The split-rescale guard must ABSTAIN, not claim "same scale" (council 2026-09-07 #15).

``_price_scale_factor`` used to return 1.0 whenever the implied factor fell
outside ``[0.2, 5.0]`` — the affirmative claim that the stored scan-time
absolutes and the freshly downloaded series are on the same scale. A 10-for-1
split, or the 1-for-10 reverse splits routine among the sub-$5 names this
screener scans, then graded ``triggered``, ``barrier_label``, ``days_to_*`` and
the R-multiples against a trigger and a stop an order of magnitude wrong, and the
row entered the edge record looking clean.

It now has three outcomes — agree (1.0), a usable factor, and UNKNOWN (None) —
and on unknown both callers leave every column derived from a stored absolute
NULL. Hermetic: no network, throwaway sqlite (the pass must never open the live
journal in a test).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
import database  # noqa: E402
from core.archive import forward_returns as fr  # noqa: E402
from core.archive import near_miss_outcomes as nmo  # noqa: E402
from core.archive import near_miss_writer as nmw  # noqa: E402
from core.archive.outcomes import HORIZON_BARS  # noqa: E402
from core.pipeline.market_data import downloads as dl  # noqa: E402


# ── the three outcomes ────────────────────────────────────────────────────────
def test_price_scale_factor_has_three_outcomes():
    # AGREE — same scale (and float noise snaps to exactly 1.0).
    assert fr._price_scale_factor(100.0, 100.0) == 1.0
    assert fr._price_scale_factor(100.02, 100.0) == 1.0

    # A USABLE factor — a 2-for-1 split is inside the plausible band.
    assert fr._price_scale_factor(50.0, 100.0) == pytest.approx(0.5)

    # UNKNOWN — 10-for-1 and 1-for-10 reverse both fall outside it. These are
    # the cases that used to answer 1.0, i.e. "there was no split".
    assert fr._price_scale_factor(10.0, 100.0) is None      # 10-for-1
    assert fr._price_scale_factor(100.0, 10.0) is None      # 1-for-10 reverse


def test_rescaled_refuses_to_pass_an_absolute_through_an_unknown_scale():
    assert fr._rescaled(10.5, None) is None
    assert fr._rescaled(10.5, 1.0) == 10.5
    assert fr._rescaled(10.5, 2.0) == 21.0


# ── the fires pass ────────────────────────────────────────────────────────────
def _flat_frame(level: float, periods: int, start) -> pd.DataFrame:
    idx = pd.bdate_range(start=pd.Timestamp(start), periods=periods)
    return pd.DataFrame(
        {"Open": level, "High": level * 1.02, "Low": level * 0.99,
         "Close": level, "Volume": 1e6},
        index=idx,
    )


def test_forward_returns_leaves_absolute_derived_columns_null_on_an_unknown_scale(
        tmp_path, monkeypatch):
    """A 1-for-10 reverse split: the archived scan close is 10.0, the freshly
    downloaded scan bar is 100.0. The stored trigger (10.5) and stop (9.0) are on
    the OLD scale, so on the new series every bar towers over the trigger — the
    old guard called that a day-1 trigger and a graded barrier outcome.

    The row is seeded with exactly that wrong verdict so this pins that the
    columns are WRITTEN null, not merely left unwritten with the stale value.
    """
    eng = create_engine(f"sqlite:///{tmp_path / 'fires.db'}")
    monkeypatch.setattr(database, "engine", eng)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=eng))
    monkeypatch.setattr(database, "make_sqlite_engine", lambda _p: eng)
    archive_models.SetupArchive.metadata.create_all(bind=eng)

    scan_date = (datetime.today() - timedelta(days=120)).strftime("%Y-%m-%d")
    session = sessionmaker(bind=eng, autoflush=False)()
    session.add(archive_models.SetupArchive(
        ticker="RVRS", scan_date=scan_date, setup_type="LPS", tier="A", score=1.0,
        source="screener", universe_type="us_equities",
        current_price=10.0,          # stored scan close, PRE reverse split
        trigger_price=10.5, s_level=9.0,
        # the wrongly-graded verdict a previous pass wrote
        triggered=1, trigger_date=scan_date, days_to_trigger=1,
        trigger_volume_ratio=1.4, r_multiple_20d=3.0, r_multiple_60d=3.0,
        barrier_label="win", win_barrier="r_target", days_to_2_5r=1,
        days_to_15pct=2, days_to_stop=None,
    ))
    session.commit()
    session.close()

    frame = _flat_frame(100.0, 90, pd.Timestamp(scan_date) - pd.Timedelta(days=5))
    monkeypatch.setattr(dl, "_batched_download", lambda t, p, l: {"sentinel": True})
    monkeypatch.setattr(fr, "_ticker_frame",
                        lambda raw, ticker: frame if ticker == "RVRS"
                        else pd.DataFrame())

    assert fr.update_forward_returns(min_age_days=0, force=True) == 1

    db = sessionmaker(bind=eng)()
    row = db.query(archive_models.SetupArchive).one()
    for column in fr._SCALE_DEPENDENT_NULLS:
        assert getattr(row, column) is None, (
            f"{column} was graded against an unexplainable price scale"
        )
    # The ratio metrics read only the FRESH close, so they stay valid and filled.
    assert row.fwd_return_20d is not None
    assert row.mfe_20d is not None
    db.close()


# ── the near-miss lane ────────────────────────────────────────────────────────
_MARGINS = {"width": 0.17, "respect_share": 1, "respect_run": 9,
            "crash": 0.25, "r_touches": 2, "s_touches": 1,
            "r_touch_thirds": 0, "s_touch_thirds": 0,
            "lower_dwell": -1, "upper_dwell": 3, "mid_dwell": 4,
            "coverage": 1, "traversal_count": 0, "traversal_density": 0.02}


def test_near_miss_never_records_never_triggered_on_an_unknown_scale(
        tmp_path, monkeypatch):
    """A 10-for-1 split: the archived scan close is 242.0, the fresh scan bar is
    24.2. The stored would-be trigger (250.0) towers over every fresh bar, and the
    row has matured past the horizon — so the old guard fell into the matured
    branch and stamped ``triggered = 0``, "it never triggered". On the correct
    scale the trigger is 25.0 and a forward bar tags 25.3: it DID trigger.
    """
    eng = create_engine(f"sqlite:///{tmp_path / 'lane.db'}")
    monkeypatch.setattr(database, "engine", eng)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=eng))
    monkeypatch.setattr(database, "make_sqlite_engine", lambda _path: eng)

    first_seen = (datetime.today() - timedelta(days=150)).strftime("%Y-%m-%d")
    row = {"ticker": "SPLT", "scan_date": first_seen, "r_level": 250.0,
           "s_level": 225.0, "r_anchor_date": "2026-01-05",
           "s_anchor_date": "2026-01-12", "window_start_date": "2026-01-05",
           "window_end_date": first_seen, "pool": "strict",
           "kill_stage": "occupancy", "failing_leg": "occupancy",
           "judged_n": 28, "fired_night": 0, "episode_profile": "S+ S+ R^",
           "margins": dict(_MARGINS), "would_be_trigger": 250.0,
           "scan_close": 242.0, "lane_ruleset": "2026-07-26.A"}
    assert nmw.archive_near_miss_rows(
        [row], universe_type="us_equities", enable=True)["inserted"] == 1

    # Post-split series: flat at 24.2 with one forward bar tagging 25.3, and
    # enough forward bars that the row is matured (the branch that asserts 0).
    idx = pd.bdate_range(pd.Timestamp(first_seen) - pd.Timedelta(days=4),
                         periods=HORIZON_BARS + 10)
    scan_ts = idx[idx <= pd.Timestamp(first_seen)][-1]
    closes = np.full(len(idx), 24.2)
    highs = np.full(len(idx), 24.5)
    fwd_positions = np.flatnonzero(idx > scan_ts)
    assert len(fwd_positions) >= HORIZON_BARS
    highs[fwd_positions[2]] = 25.3     # a real touch of the rescaled trigger
    frame = pd.DataFrame({"Open": closes, "High": highs, "Low": closes - 0.4,
                          "Close": closes, "Volume": np.full(len(idx), 1e6)},
                         index=idx)

    monkeypatch.setattr(dl, "_batched_download", lambda t, p, l: {"sentinel": True})
    monkeypatch.setattr(fr, "_ticker_frame",
                        lambda raw, ticker: frame if ticker == "SPLT"
                        else pd.DataFrame())

    assert nmo.update_near_miss_outcomes(min_age_days=5, force=True) == 1

    db = database.SessionLocal()
    stored = db.query(archive_models.NearMissArchive).one()
    assert stored.triggered is None, "an unknown scale was recorded as a verdict"
    assert stored.trigger_date is None
    # The elapsed metrics ride the fresh close and still land.
    assert stored.bars_to_date is not None
    db.close()
