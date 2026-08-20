"""Watchlist candle endpoint (router + service), EC-22 mold: real handlers
against REAL parquet panels written to tmp_path in the pipeline's cache shape
— never a mocked read, never the live cache, never a booted app. The ONE
monkeypatched boundary is cache-path resolution (Universe.cache_paths), so
the actual pruned-column read path that has produced real defects (forming
bars, absent sessions, torn files) is what runs.

Pins: EC-22 (every closed-set verdict value produced by the real producer),
EC-27 (every refusing leg distinguishable — bad ticker vs over-cap vs each
degrade verdict), EC-28 (no engine-read material on this wire), EC-6
(degrades are named 200s, never raises), the exact envelope key-set snapshot
(the FLAG_OFF_WIRE_KEYS tradition), and the router Literal vocabularies ==
service tuples so the two cannot drift.
"""
from __future__ import annotations

import os
import sys
import typing
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from core.pipeline import universe as universe_mod  # noqa: E402
from routers import candles as candles_router  # noqa: E402
from routers.calibration import require_same_app  # noqa: E402
from services import watchlist_candles as wc  # noqa: E402

# ── fixtures ────────────────────────────────────────────────────────────────

# 10 business days, 2026-01-05 (Mon) … 2026-01-16 (Fri): two complete
# W-FRI weekly buckets and one forming monthly bucket — hand-reasonable.
DAYS = 10
START = "2026-01-05"


def _ohlcv(days=DAYS, base=10.0):
    """Deterministic float64 OHLCV whose weekly aggregates are hand-derivable
    (dyadic fractions — exact in binary, no rounding surprises)."""
    idx = pd.bdate_range(START, periods=days, name="Date")
    step = np.arange(days, dtype="float64")
    return pd.DataFrame({
        "Open": base + step,
        "High": base + step + 0.5,
        "Low": base + step - 0.5,
        "Close": base + step + 0.25,
        "Volume": 1000.0 + step,
    }, index=idx)


def _write_panel(path: Path, frames: dict):
    """A multi-ticker panel in the pipeline's cache shape: (ticker, field)
    MultiIndex columns over a Date-named DatetimeIndex."""
    panel = pd.concat(frames, axis=1)
    panel.to_parquet(path)


@pytest.fixture()
def panels(monkeypatch, tmp_path):
    """Redirect every universe's cache paths into tmp_path (the ONE allowed
    monkeypatch seam) and reset the service's identity-keyed caches."""
    def fake_cache_paths(self):
        d = tmp_path / self.key
        d.mkdir(exist_ok=True)
        return (str(d / "panel.parquet"), str(d / "meta.json"))

    monkeypatch.setattr(universe_mod.Universe, "cache_paths", fake_cache_paths)
    monkeypatch.setattr(wc, "_frame_cache", OrderedDict())
    monkeypatch.setattr(wc, "_panel_tickers_cache", {})
    return tmp_path


def _paths(tmp_path, key):
    d = tmp_path / key
    d.mkdir(exist_ok=True)
    return d / "panel.parquet", d / "meta.json"


def _seed_default(tmp_path, frames=None, meta='{"price_series": "as_traded", "last_modified": "2026-01-16T22:00:00+00:00"}'):
    panel, meta_path = _paths(tmp_path, "us_stocks")
    _write_panel(panel, frames if frames is not None else {"TAA": _ohlcv()})
    meta_path.write_text(meta, encoding="utf-8")


# ── the served happy path, hand-reasoned (EC-17 spirit: real cascade) ──────

def test_served_ticker_returns_hand_reasoned_dwm(panels):
    _seed_default(panels)
    env = wc.ticker_candles("TAA")

    assert env["status"] == "ok"
    assert env["universe"] == "us_stocks"
    assert env["source"] == "cache"
    assert env["price_series"] == "as_traded"
    assert env["last_bar_date"] == "2026-01-16"

    daily = env["frames"]["daily"]
    weekly = env["frames"]["weekly"]
    monthly = env["frames"]["monthly"]
    assert [len(f["candles"]) for f in (daily, weekly, monthly)] == [10, 2, 1]

    # Daily bar 1 exactly as the shared builder serializes it.
    assert daily["candles"][0] == {
        "time": "2026-01-05", "open": 10.0, "high": 10.5,
        "low": 9.5, "close": 10.25}
    assert daily["volumes"][0]["value"] == 1000.0
    assert daily["volumes"][0]["color"] == "rgba(38,166,154,0.5)"  # close>=open

    # Weekly bucket 1 aggregates that week's daily extremes BY HAND:
    # sessions 0-4 → open=first, high=max, low=min, close=last, vol=sum.
    assert weekly["candles"][0] == {
        "time": "2026-01-09", "open": 10.0, "high": 14.5,
        "low": 9.5, "close": 14.25}
    assert weekly["volumes"][0]["value"] == 5010.0

    # Forming marks resolved server-side: both weeks END on the last traded
    # session (Fri) → complete; the January bucket's ME label (01-31) lies
    # beyond it → forming.
    assert daily["forming_last_bar"] is False
    assert weekly["forming_last_bar"] is False
    assert monthly["candles"][0]["time"] == "2026-01-31"
    assert monthly["forming_last_bar"] is True


# ── every degrade verdict produced by the real producer (EC-22) ────────────

def test_unknown_ticker_degrades_named(panels):
    _seed_default(panels)
    env = wc.ticker_candles("ZZZ")
    assert env["status"] == "unknown_ticker"
    assert env["universe"] is None
    assert env["last_bar_date"] is None
    for frame in env["frames"].values():
        assert frame == {"status": "empty", "forming_last_bar": None,
                         "candles": [], "volumes": []}


def test_missing_cache_degrades_no_cache(panels):
    # No panel file written anywhere.
    env = wc.ticker_candles("TAA")
    assert env["status"] == "no_cache"


def test_torn_panel_degrades_no_cache(panels):
    # Garbage bytes where every universe's panel should be — the mid-rewrite
    # window. Must be a named 200-style verdict, never a raise (EC-6).
    for universe in universe_mod.all_universes():
        panel, _meta = _paths(panels, universe.key)
        panel.write_bytes(b"this is not a parquet file")
    env = wc.ticker_candles("TAA")
    assert env["status"] == "no_cache"


def test_torn_panel_beside_readable_panel_stays_retryable(panels):
    # ONE universe torn mid-rewrite while another is readable and denies
    # membership: the failed schema read can never certify absence, so the
    # RETRYABLE verdict must win — never the terminal "unknown_ticker"
    # (_aggregate_status's precedence contract).
    _seed_default(panels)  # us_stocks readable, holds only TAA
    for universe in universe_mod.all_universes():
        if universe.key == "us_stocks":
            continue
        panel, _meta = _paths(panels, universe.key)
        panel.write_bytes(b"this is not a parquet file")
    env = wc.ticker_candles("ZZZ")
    assert env["status"] == "no_cache"


def test_all_nan_history_degrades_no_drawable_bars(panels):
    dead = _ohlcv() * np.nan
    _seed_default(panels, frames={"TAA": _ohlcv(), "TDD": dead})
    env = wc.ticker_candles("TDD")
    assert env["status"] == "no_drawable_bars"
    assert env["universe"] is None


def test_non_default_universe_resolves(panels):
    # TBB lives ONLY in the sectors panel — the deterministic registry-order
    # search must find it there (a real branch, not a hypothetical).
    _seed_default(panels)
    sector_panel, _meta = _paths(panels, "us_sectors")
    _write_panel(sector_panel, {"TBB": _ohlcv(base=50.0)})
    env = wc.ticker_candles("TBB")
    assert env["status"] == "ok"
    assert env["universe"] == "us_sectors"
    assert env["frames"]["daily"]["candles"][0]["open"] == 50.0


def test_pinned_universe_is_tried_first(panels):
    # The same ticker in TWO panels with different values: the supplied pin
    # key (EC-37) decides which panel serves.
    _seed_default(panels, frames={"TAA": _ohlcv(base=10.0)})
    sector_panel, _meta = _paths(panels, "us_sectors")
    _write_panel(sector_panel, {"TAA": _ohlcv(base=99.0)})
    pinned = wc.ticker_candles("TAA", "us_sectors")
    assert pinned["universe"] == "us_sectors"
    assert pinned["frames"]["daily"]["candles"][0]["open"] == 99.0
    unpinned = wc.ticker_candles("TAA")
    assert unpinned["universe"] == "us_stocks"
    assert unpinned["frames"]["daily"]["candles"][0]["open"] == 10.0


def test_unknown_pin_key_degrades_into_search(panels):
    _seed_default(panels)
    env = wc.ticker_candles("TAA", "retired_universe")
    assert env["status"] == "ok"
    assert env["universe"] == "us_stocks"


# ── the card-grid batch ────────────────────────────────────────────────────

def test_batch_mixed_isolates_verdicts(panels):
    _seed_default(panels)
    out = wc.batch_candles(["TAA", "ZZZ"])
    assert out["tickers"]["TAA"]["status"] == "ok"
    assert out["tickers"]["ZZZ"] == {
        "status": "unknown_ticker", "candles": [], "volumes": []}
    # The batch's daily bars are the SAME builder's output as the full
    # envelope's daily frame (the over-cap window parity is pinned in
    # test_candle_parity.py against the 1700-bar frame).
    env = wc.ticker_candles("TAA")
    assert out["tickers"]["TAA"]["candles"] == env["frames"]["daily"]["candles"]


def test_batch_produces_every_degrade_verdict(panels):
    # EC-22 for the batch itself: no_drawable_bars and no_cache from the
    # REAL batch producer, not vicariously through the single route.
    dead = _ohlcv() * np.nan
    _seed_default(panels, frames={"TAA": _ohlcv(), "TDD": dead})
    out = wc.batch_candles(["TDD"])
    assert out["tickers"]["TDD"]["status"] == "no_drawable_bars"

    for universe in universe_mod.all_universes():
        panel, _meta = _paths(panels, universe.key)
        panel.write_bytes(b"this is not a parquet file")
    wc._frame_cache.clear()
    wc._panel_tickers_cache.clear()
    out = wc.batch_candles(["TDD"])
    assert out["tickers"]["TDD"]["status"] == "no_cache"


def test_batch_and_single_agree_on_a_dual_listed_name(panels):
    # The review's finding 5: a name whose FIRST panel holds it but has no
    # drawable rows must keep walking (exactly like the single route) — the
    # two surfaces may never file different verdicts for one ticker.
    dead = _ohlcv() * np.nan
    _seed_default(panels, frames={"TAA": _ohlcv(), "TDL": dead})
    sector_panel, _meta = _paths(panels, "us_sectors")
    _write_panel(sector_panel, {"TDL": _ohlcv(base=70.0)})

    env = wc.ticker_candles("TDL")
    out = wc.batch_candles(["TDL"])
    assert env["status"] == "ok"
    assert env["universe"] == "us_sectors"
    assert out["tickers"]["TDL"]["status"] == "ok"
    assert out["tickers"]["TDL"]["candles"] == env["frames"]["daily"]["candles"]


def test_member_read_failure_is_retryable_not_dead_history(panels):
    # EC-27: the member-but-read-failed leg must file the RETRYABLE verdict.
    # Construct the exact race: the identity-cached schema still says the
    # ticker is a member, but the data read hits garbage — same byte size +
    # same mtime_ns, so the identity check cannot see the rewrite.
    _seed_default(panels)
    wc.ticker_candles("TAA")  # primes the schema cache under this identity
    panel, _meta = _paths(panels, "us_stocks")
    stat = panel.stat()
    panel.write_bytes(b"x" * stat.st_size)
    os.utime(panel, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    wc._frame_cache.clear()  # force the data read; keep the schema cache

    env = wc.ticker_candles("TAA")
    assert env["status"] == "no_cache"  # never "no_drawable_bars"
    out = wc.batch_candles(["TAA"])
    assert out["tickers"]["TAA"]["status"] == "no_cache"


def test_panel_rewrite_invalidates_the_frame_cache(panels):
    # The identity design's whole reason to exist: a rewritten panel must
    # serve NEW values on the next request, never yesterday's frames.
    _seed_default(panels)
    first = wc.ticker_candles("TAA")
    assert first["frames"]["daily"]["candles"][0]["open"] == 10.0
    _seed_default(panels, frames={"TAA": _ohlcv(base=55.0)})
    second = wc.ticker_candles("TAA")
    assert second["frames"]["daily"]["candles"][0]["open"] == 55.0


def test_batch_route_drops_bad_grammar_and_dedupes(panels):
    _seed_default(panels)
    out = candles_router.get_batch_candles("taa, bad!!x, taa, 1NUM")
    assert list(out["tickers"].keys()) == ["TAA"]


def test_batch_route_refuses_over_cap_loudly(panels):
    tickers = ",".join(f"T{i}" for i in range(candles_router.BATCH_MAX_TICKERS + 1))
    with pytest.raises(HTTPException) as err:
        candles_router.get_batch_candles(tickers)
    assert err.value.status_code == 400
    assert err.value.detail["class"] == "too_many_tickers"


def test_batch_route_threads_pins_per_ticker(panels):
    # EC-37 reaches the batch: the same ticker in two panels serves from its
    # PINNED panel, exactly like the single route's ?universe=.
    _seed_default(panels, frames={"TAA": _ohlcv(base=10.0)})
    sector_panel, _meta = _paths(panels, "us_sectors")
    _write_panel(sector_panel, {"TAA": _ohlcv(base=99.0)})
    out = candles_router.get_batch_candles("TAA", pins="TAA:us_sectors")
    assert out["tickers"]["TAA"]["candles"][0]["open"] == 99.0
    # Malformed pairs and unknown keys degrade into the search, never raise.
    out = candles_router.get_batch_candles("TAA", pins="garbage,TAA:retired")
    assert out["tickers"]["TAA"]["candles"][0]["open"] == 10.0


# ── the flat-panel fallback (single-level columns) ─────────────────────────

def test_flat_panel_serves_and_degrades_honestly(panels):
    # A single-level panel (no ticker tuples) is served whole; its verdicts
    # must keep the closed vocabulary's meanings — a held-but-cleaned-away
    # name is dead history, not "unknown".
    flat = _ohlcv(base=30.0)
    flat_panel, _meta = _paths(panels, "us_stocks")
    flat.to_parquet(flat_panel)
    env = wc.ticker_candles("TFF")
    assert env["status"] == "ok"
    assert env["frames"]["daily"]["candles"][0]["open"] == 30.0

    (flat * np.nan).to_parquet(flat_panel)
    wc._frame_cache.clear()
    wc._panel_tickers_cache.clear()
    env = wc.ticker_candles("TFF")
    assert env["status"] == "no_drawable_bars"


# ── boundary + guard (EC-27: each refusing leg distinguishable) ────────────

def test_malformed_ticker_refused_by_the_folded_validator(panels):
    with pytest.raises(HTTPException) as err:
        candles_router.get_ticker_candles("bad ticker!", None)
    assert err.value.status_code == 400
    assert err.value.detail["class"] == "bad_ticker"


def test_both_routes_carry_the_same_app_guard():
    for route in candles_router.router.routes:
        deps = [d.dependency for d in route.dependencies]
        assert require_same_app in deps, route.path


# ── wire-contract pins ─────────────────────────────────────────────────────

# The exact envelope key sets. Changing the candle wire contract means
# editing these tuples deliberately in the same change — never drifting past
# them (the FLAG_OFF_WIRE_KEYS tradition).
ENVELOPE_KEYS = ("cache_last_modified", "frames", "last_bar_date",
                 "price_series", "source", "status", "ticker", "universe")
FRAME_KEYS = ("candles", "forming_last_bar", "status", "volumes")
BATCH_TICKER_KEYS = ("candles", "status", "volumes")


def test_envelope_key_set_snapshot(panels):
    _seed_default(panels)
    env = wc.ticker_candles("TAA")
    assert tuple(sorted(env)) == ENVELOPE_KEYS
    assert tuple(env["frames"]) == ("daily", "weekly", "monthly")
    for frame in env["frames"].values():
        assert tuple(sorted(frame)) == FRAME_KEYS
    batch = wc.batch_candles(["TAA"])
    assert tuple(sorted(batch["tickers"]["TAA"])) == BATCH_TICKER_KEYS


def test_ok_ticker_never_carries_an_empty_frame(panels):
    # The narrowed FrameOut claim, pinned: "empty" co-occurs only with a
    # non-ok ticker status — the resampler yields at least one bucket for
    # any nonempty cleaned frame, so a servable ticker fills all three.
    _seed_default(panels)
    env = wc.ticker_candles("TAA")
    assert env["status"] == "ok"
    assert all(f["status"] == "ok" for f in env["frames"].values())


def test_no_engine_read_material_on_this_wire(panels):
    # EC-28: rails/LPS/structure verdicts ride ONLY the scan artifact. The
    # envelope's closed key set (above) is the structural guarantee; this
    # spells the promise out against the obvious names.
    _seed_default(panels)
    env = wc.ticker_candles("TAA")
    for forbidden in ("R", "S", "weekly_box", "monthly_box", "sub_scores",
                      "lps_len", "base_len"):
        assert forbidden not in env


def test_router_literals_match_service_vocabularies():
    assert typing.get_args(
        candles_router.TickerStatus) == wc.TICKER_STATUSES
    assert typing.get_args(candles_router.FrameStatus) == wc.FRAME_STATUSES
    out_fields = candles_router.TickerCandlesOut.model_fields
    assert typing.get_args(out_fields["status"].annotation) == wc.TICKER_STATUSES
