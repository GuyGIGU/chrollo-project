"""Unit tests for the HTF (higher-timeframe) structure-context layer.

These cover the deterministic plumbing — resampling, the window-override context
manager, the Stage-2 read, field derivation, and guards. Whether the box-tolerant
walk finds real boxes on real charts is a calibration question exercised by
tools/htf_audit.py, not asserted here.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "webapp" / "backend"
for _p in (str(_ROOT), str(_BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import settings
from core.structure import htf
from core.structure.bricks import EquilibriumBox


def _daily(n=600, lo=20.0, hi=80.0, start="2022-01-03"):
    """A clean rising daily OHLCV frame with a DatetimeIndex (Stage-2 'up')."""
    idx = pd.bdate_range(start, periods=n)
    close = np.linspace(lo, hi, n)
    return pd.DataFrame({
        "Open": close,
        "High": close + 0.5,
        "Low": close - 0.5,
        "Close": close,
        "Volume": np.full(n, 2_000_000.0),
    }, index=idx)


def _box(R=110.0, S=100.0, box_width=0.1):
    return EquilibriumBox(
        S=S, R=R, start_bar=0, base_len=30, box_width=box_width, quality=1.0,
        r_touches=3, s_touches=3, breach_days=0, r_anchor_bar=0, s_anchor_bar=0,
        n_full_traversals=2, traversal_density=0.5,
    )


# ── window-override context manager ──────────────────────────────────────────

def test_timeframe_windows_applies_and_restores():
    before = settings.MIN_BASE_DAYS
    with htf.timeframe_windows("weekly"):
        assert settings.MIN_BASE_DAYS == settings.HTF_WEEKLY_WINDOWS["MIN_BASE_DAYS"]
        assert settings.LPS_LENGTH_MAX == settings.HTF_WEEKLY_WINDOWS["LPS_LENGTH_MAX"]
    assert settings.MIN_BASE_DAYS == before


def test_timeframe_windows_restores_on_exception():
    before = settings.AR_MAX_BARS
    with pytest.raises(RuntimeError):
        with htf.timeframe_windows("monthly"):
            assert settings.AR_MAX_BARS == settings.HTF_MONTHLY_WINDOWS["AR_MAX_BARS"]
            raise RuntimeError("boom")
    assert settings.AR_MAX_BARS == before


def test_timeframe_windows_leaves_ratio_thresholds_untouched():
    # Scale-invariant ratios must NOT be in the presets (they keep daily values).
    for preset in (settings.HTF_WEEKLY_WINDOWS, settings.HTF_MONTHLY_WINDOWS):
        assert "MAX_BOX_WIDTH" not in preset
        assert "MIN_BOUNDARY_RESPECT_PCT" not in preset
        assert "LPS_PULLBACK_PROFILE_MIN" not in preset


# ── resampling ───────────────────────────────────────────────────────────────

def test_resample_weekly_and_monthly_shapes():
    df = _daily(520)
    wk = htf.resample_ohlc(df, "weekly")
    mo = htf.resample_ohlc(df, "monthly")
    assert wk is not None and mo is not None
    assert len(wk) < len(df) and len(mo) < len(wk)
    assert list(wk.columns) == ["Open", "High", "Low", "Close", "Volume"]
    # OHLC aggregation is sane: weekly High >= weekly Close everywhere.
    assert (wk["High"] >= wk["Close"]).all()


def test_resample_non_datetime_index_is_handled():
    df = _daily(60).reset_index(drop=True)  # RangeIndex, not parseable to dates
    assert htf.resample_ohlc(df, "weekly") is None


def test_resample_unknown_timeframe_raises():
    with pytest.raises(ValueError):
        htf.resample_ohlc(_daily(60), "hourly")


# ── Stage-2 read ─────────────────────────────────────────────────────────────

def test_stage2_true_on_clean_uptrend():
    wk = htf.resample_ohlc(_daily(600), "weekly")
    out = htf.htf_stage2(wk)
    assert out["stage2"] is True
    assert out["trend_state"] == "up"


def test_stage2_unknown_on_short_history():
    wk = htf.resample_ohlc(_daily(40), "weekly")
    out = htf.htf_stage2(wk)
    assert out["stage2"] is False
    assert out["trend_state"] == "unknown"


# ── read_htf_context field set + derivation ──────────────────────────────────

def test_context_returns_complete_prefixed_field_set():
    out = htf.read_htf_context(_daily(600), "weekly")
    expected = {"htf_w_" + k for k in
                ("stage2", "trend_state", "in_consol", "phase",
                 "box_r", "box_s", "box_width", "reaccum", "daily_nested")}
    assert set(out) == expected


def test_context_empty_on_short_history_but_keys_present():
    out = htf.read_htf_context(_daily(10), "monthly")
    assert out["htf_m_in_consol"] is False
    assert out["htf_m_phase"] is None
    assert set(out) == {"htf_m_" + k for k in
                        ("stage2", "trend_state", "in_consol", "phase",
                         "box_r", "box_s", "box_width", "reaccum", "daily_nested")}


def test_context_derives_box_fields_and_nesting(monkeypatch):
    # Force the walk to return a known box so we test the derivation, not detection.
    monkeypatch.setattr(htf, "_read_htf_structure",
                        lambda df, atr: {"box": _box(R=110, S=100), "spring": None,
                                         "lps": object(), "phase": "D", "root": None})
    out = htf.read_htf_context(_daily(600), "weekly", daily_box=(105.0, 102.0))
    assert out["htf_w_in_consol"] is True
    assert out["htf_w_phase"] == "D"
    assert out["htf_w_box_r"] == 110.0 and out["htf_w_box_s"] == 100.0
    assert out["htf_w_reaccum"] is True              # stage-2 up AND in a box
    assert out["htf_w_daily_nested"] is True          # daily [102,105] inside HTF [100,110]


def test_context_not_nested_when_daily_box_escapes(monkeypatch):
    monkeypatch.setattr(htf, "_read_htf_structure",
                        lambda df, atr: {"box": _box(R=110, S=100), "spring": None,
                                         "lps": None, "phase": "B", "root": None})
    out = htf.read_htf_context(_daily(600), "weekly", daily_box=(115.0, 108.0))
    assert out["htf_w_phase"] == "B"
    assert out["htf_w_daily_nested"] is False


def test_context_disabled_flag(monkeypatch):
    monkeypatch.setattr(settings, "HTF_CONTEXT_ENABLED", False)
    out = htf.read_htf_context(_daily(600), "weekly")
    assert out["htf_w_in_consol"] is False
    assert out["htf_w_stage2"] is False


def test_context_never_raises_on_garbage():
    out = htf.read_htf_context(pd.DataFrame({"foo": [1, 2, 3]}), "weekly")
    assert out["htf_w_in_consol"] is False


# ── archive mapping (live + seed) ────────────────────────────────────────────

def test_htf_archive_values_live_and_seed_mapping():
    assert len(htf.HTF_COLUMNS) == 18
    live_row = {"_htf_w_stage2": True, "_htf_w_phase": "D",
                "_htf_w_box_width": 0.1, "_htf_w_daily_nested": None}
    out = htf.htf_archive_values(live_row.get, prefixed=True)
    assert set(out) == set(htf.HTF_COLUMNS)
    assert out["htf_w_stage2"] == 1            # bool -> 0/1
    assert out["htf_w_phase"] == "D"           # text passthrough
    assert out["htf_w_box_width"] == 0.1       # float passthrough
    assert out["htf_w_daily_nested"] is None   # None stays None
    seed_out = htf.htf_archive_values({"htf_m_reaccum": False}.get, prefixed=False)
    assert seed_out["htf_m_reaccum"] == 0


def test_orm_model_has_htf_columns():
    from archive_models import SetupArchive
    for col in htf.HTF_COLUMNS:
        assert hasattr(SetupArchive, col), f"ORM missing {col}"
