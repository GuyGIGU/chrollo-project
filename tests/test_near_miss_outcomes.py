"""Near-miss maturation pass (near-miss lane Task 10) — hermetic.

The pass delegates to core.archive.outcomes (one MFE meaning), anchors the
clock at FIRST refusal, applies the split-rescale guard to the would-be
trigger, and re-touches only still-maturing rows inside the age cap. No
network: the batched download and per-ticker frames are faked; the DB is a
throwaway sqlite file (make_sqlite_engine is patched — the pass must never
open the live journal in a test).
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
from core.pipeline.market_data import downloads as dl  # noqa: E402

pytestmark = pytest.mark.regression

_MARGINS = {"width": 0.17, "respect_share": 1, "respect_run": 9,
            "crash": 0.25, "r_touches": 2, "s_touches": 1,
            "r_touch_thirds": 0, "s_touch_thirds": 0,
            "lower_dwell": -1, "upper_dwell": 3, "mid_dwell": 4,
            "coverage": 1, "traversal_count": 0, "traversal_density": 0.02}


def test_maturation_fills_elapsed_outcomes_and_the_trigger_touch(
        tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'lane.db'}")
    monkeypatch.setattr(database, "engine", eng)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=eng))
    monkeypatch.setattr(database, "make_sqlite_engine", lambda _path: eng)

    first_seen = (datetime.today() - timedelta(days=40)).strftime("%Y-%m-%d")
    row = {"ticker": "EGBN", "scan_date": first_seen, "r_level": 25.0,
           "s_level": 22.5, "r_anchor_date": "2026-05-01",
           "s_anchor_date": "2026-05-08", "window_start_date": "2026-05-01",
           "window_end_date": first_seen, "pool": "strict",
           "kill_stage": "occupancy", "failing_leg": "occupancy",
           "judged_n": 28, "fired_night": 0, "episode_profile": "S+ S+ R^",
           "margins": dict(_MARGINS), "would_be_trigger": 25.0,
           "scan_close": 24.2, "lane_ruleset": "2026-07-26.A"}
    counters = nmw.archive_near_miss_rows([row], universe_type="us_equities",
                                          enable=True)
    assert counters["inserted"] == 1

    # A 12-forward-bar frame: the would-be trigger (25.0) is touched on the
    # THIRD forward bar; the scan-day close matches the stored scale (x1).
    idx = pd.bdate_range(pd.Timestamp(first_seen) - pd.Timedelta(days=4),
                         periods=16)
    scan_ts = idx[idx <= pd.Timestamp(first_seen)][-1]
    closes = np.full(len(idx), 24.2)
    highs = np.full(len(idx), 24.5)
    fwd_positions = np.flatnonzero(idx > scan_ts)
    highs[fwd_positions[2]] = 25.3            # bar 3 forward: trigger touch
    closes[fwd_positions[-1]] = 26.0          # last forward close: +7.4%
    frame = pd.DataFrame({"Open": closes, "High": highs,
                          "Low": closes - 0.4, "Close": closes,
                          "Volume": np.full(len(idx), 1e6)}, index=idx)

    monkeypatch.setattr(dl, "_batched_download",
                        lambda tickers, params, label: {"sentinel": True})
    monkeypatch.setattr(fr, "_ticker_frame",
                        lambda raw, ticker: frame if ticker == "EGBN"
                        else pd.DataFrame())

    updated = nmo.update_near_miss_outcomes(min_age_days=5)
    assert updated == 1

    db = database.SessionLocal()
    stored = db.query(archive_models.NearMissArchive).one()
    n_fwd = len(fwd_positions)
    assert stored.triggered == 1
    assert stored.trigger_date == str(idx[fwd_positions[2]])[:10]
    assert stored.bars_to_date == n_fwd
    assert stored.mfe_to_date == pytest.approx((25.3 - 24.2) / 24.2, abs=1e-4)
    assert stored.ret_to_date == pytest.approx((26.0 - 24.2) / 24.2, abs=1e-4)
    assert stored.abnormal_ret_to_date is None      # no SPY frame supplied
    db.close()

    # Still-maturing re-touch: a second run re-selects it (bars < horizon)…
    assert nmo.update_near_miss_outcomes(min_age_days=5) == 1
    # …but a matured row (bars_to_date >= horizon) drops out of the query.
    db = database.SessionLocal()
    stored = db.query(archive_models.NearMissArchive).one()
    stored.bars_to_date = 60
    db.commit()
    db.close()
    assert nmo.update_near_miss_outcomes(min_age_days=5) == 0


def _boundary_row(ticker, days_old):
    first_seen = (datetime.today() - timedelta(days=days_old)).strftime("%Y-%m-%d")
    return {"ticker": ticker, "scan_date": first_seen, "r_level": 25.0,
            "s_level": 22.5, "r_anchor_date": "2026-05-01",
            "s_anchor_date": "2026-05-08", "window_start_date": "2026-05-01",
            "window_end_date": first_seen, "pool": "strict",
            "kill_stage": "occupancy", "failing_leg": "occupancy",
            "judged_n": 28, "fired_night": 0, "episode_profile": "S+",
            "margins": dict(_MARGINS), "would_be_trigger": 25.0,
            "scan_close": 24.2, "lane_ruleset": "2026-07-26.A"}


def test_maturation_selection_boundaries(tmp_path, monkeypatch):
    """min-age and age-cap boundaries pinned by which tickers reach the
    download (review 2026-07-26 finding 10): exactly-at-min-age is IN,
    fresher is OUT, beyond the age cap is OUT unless --force. Rows are built
    relative to today, so the outcome is deterministic on any run date."""
    eng = create_engine(f"sqlite:///{tmp_path / 'lane.db'}")
    monkeypatch.setattr(database, "engine", eng)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=eng))
    monkeypatch.setattr(database, "make_sqlite_engine", lambda _path: eng)

    rows = [_boundary_row("ATCUTOFF", 5),
            _boundary_row("TOOFRESH", 4),
            _boundary_row("ANCIENT", fr.FORWARD_RETURN_MAX_SCAN_AGE_DAYS + 1)]
    counters = nmw.archive_near_miss_rows(rows, universe_type="us_equities",
                                          enable=True)
    assert counters["inserted"] == 3

    seen: dict = {}

    def _fake_dl(tickers, params, label):
        seen["tickers"] = sorted(tickers)
        return {}

    monkeypatch.setattr(dl, "_batched_download", _fake_dl)
    monkeypatch.setattr(fr, "_ticker_frame", lambda raw, t: pd.DataFrame())

    nmo.update_near_miss_outcomes(min_age_days=5)
    assert seen["tickers"] == sorted(["ATCUTOFF", fr.SPY_TICKER])

    nmo.update_near_miss_outcomes(min_age_days=5, force=True)
    assert "ANCIENT" in seen["tickers"]           # --force re-admits the aged
    assert "TOOFRESH" not in seen["tickers"]      # min-age holds even forced


def test_lane_maturation_is_contained_and_named(monkeypatch, capsys):
    """A lane-only maturation failure returns -1 and prints — it can never
    own the shared fires-maturation run's status (review finding 6); and the
    __main__ seam is pinned to call the CONTAINED wrapper (finding 10)."""
    def _boom(**_kw):
        raise RuntimeError("download pathology")
    monkeypatch.setattr(nmo, "update_near_miss_outcomes", _boom)
    assert fr.run_near_miss_maturation(min_age_days=5) == -1
    out = capsys.readouterr().out
    assert "Near-miss maturation FAILED" in out

    monkeypatch.setattr(nmo, "update_near_miss_outcomes",
                        lambda min_age_days, force=False: 7)
    assert fr.run_near_miss_maturation(min_age_days=5) == 7

    src = Path(fr.__file__).read_text(encoding="utf-8")
    assert "run_near_miss_maturation(min_age_days=args.min_age" in src
