"""Shared pytest fixtures for the core-logic test suite.

These are the frame-builder helpers that were previously redefined verbatim
across the (now split) ``test_core_logic.py`` modules. They are exposed as
factory fixtures: each fixture returns the builder function, so a test consumes
it by naming the fixture in its signature and calling it exactly as before
(e.g. ``_flat_ohlc(120)``). The builder bodies are unchanged.

It also redirects the backend database away from the operator's live archive
for the whole session — see the module-scope block below.
"""

import os
import shutil
import sys
import tempfile

import pandas as pd
import pytest

# ── the live archive is OFF LIMITS to the suite ────────────────────────────
# `import main` runs initialize_database() at import scope, and three test
# modules import main in a subprocess with cwd=webapp/backend. Left alone that
# migrates webapp/backend/trading_journal.db (12,507 archived setups) and its
# orphaned-run reconcile rewrites any in-flight scan row to status='failed' —
# observed in the operator's archive. Point the whole session at a throwaway
# file instead. This runs at conftest IMPORT time, before pytest collects any
# test module, so a module-scope `import database` already sees it; children
# inherit it through os.environ. tests/integration/test_db_isolation.py is the guard.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="chrollo-test-db-")
os.environ["CHROLLO_DB_PATH"] = os.path.join(_TEST_DB_DIR, "trading_journal.db")

# ...and the STRUCTURAL half. The line above only protects call sites that READ
# the override; this refuses the live path at the sqlite driver itself, so it
# covers all ten front doors at once — including any new one somebody adds. It
# refuses rather than redirects: a test that reaches the archive is a defect to
# surface, not to paper over. Proven against a decoy path in
# tests/integration/test_db_isolation.py, never against the real one (register row 18).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from live_archive_guard import install as _install_live_archive_guard  # noqa: E402
from core.archive.db_path import DEFAULT_DB_PATH as _LIVE_DB_PATH  # noqa: E402

_install_live_archive_guard(_LIVE_DB_PATH)


@pytest.fixture(scope="session", autouse=True)
def _discard_the_throwaway_database():
    yield
    # Return the pooled SQLite handles first: on Windows an open handle keeps
    # the file undeletable and the directory would survive every run.
    db = sys.modules.get("database")
    if db is not None:
        db.engine.dispose()
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


@pytest.fixture
def _contraction_frame():
    """Build an OHLCV frame from a list of close levels (±0.5 High/Low band)."""
    def _build(levels, volumes):
        return pd.DataFrame({
            "High": [c + 0.5 for c in levels],
            "Low": [c - 0.5 for c in levels],
            "Close": list(levels),
            "Volume": list(volumes),
        })
    return _build


@pytest.fixture
def _lps_behavior_frame():
    def _build(highs, lows, closes=None):
        closes = closes or lows
        return pd.DataFrame([
            {
                "High": high,
                "Low": low,
                "Close": close,
                "Spread": high - low,
                "Volume": 500,
                "Vol_50": 1000,
            }
            for high, low, close in zip(highs, lows, closes)
        ])
    return _build


@pytest.fixture
def _ramp_frame():
    """Build a degenerate OHLC frame (High==Low==Close) that linearly ramps
    between the given pivot prices, so the zigzag pivots land predictably."""
    def _build(pivot_prices, bars_per_leg=6):
        prices = [float(pivot_prices[0])]
        for k in range(1, len(pivot_prices)):
            p0, p1 = float(pivot_prices[k - 1]), float(pivot_prices[k])
            for b in range(1, bars_per_leg + 1):
                prices.append(p0 + (p1 - p0) * b / bars_per_leg)
        return pd.DataFrame({"High": prices, "Low": prices, "Close": prices, "Open": prices})
    return _build


@pytest.fixture
def _cand():
    """Build a Phase-B candidate tuple (only combined [0] and cand_start [9]
    drive selection; the rest are placeholders)."""
    def _build(combined, cand_start, box_width=0.1):
        return (combined, 100.0, 90.0, box_width, 5, 5, 0, 10, 5, cand_start)
    return _build


@pytest.fixture
def _osc_frame():
    """OHLC frame with High/Low a fixed band around each close."""
    def _build(closes, band=1.0):
        return pd.DataFrame({
            "High": [c + band for c in closes],
            "Low": [c - band for c in closes],
            "Close": list(closes),
        })
    return _build


@pytest.fixture
def _flat_frame():
    """High == Low == Close, so a swing's amplitude is the raw close move (no
    band inflation) — needed to exercise genuinely sub-threshold reversals."""
    def _build(closes):
        return pd.DataFrame({"High": list(closes), "Low": list(closes), "Close": list(closes)})
    return _build


@pytest.fixture
def _flat_ohlc():
    """Uniform OHLC frame; callers mutate specific rows for region tests."""
    def _build(n, *, high=101.0, low=99.0, close=100.0, volume=1000.0):
        return pd.DataFrame([
            {"Open": close, "High": high, "Low": low, "Close": close, "Volume": volume}
            for _ in range(n)
        ])
    return _build


@pytest.fixture
def _scope_df():
    """A length-n OHLC-ish frame with a DatetimeIndex (Low + High are read)."""
    def _build(n=30, low=100.0):
        idx = pd.date_range("2026-01-01", periods=n, freq="D")
        return pd.DataFrame({"Low": [low] * n, "High": [low + 1.0] * n}, index=idx)
    return _build
