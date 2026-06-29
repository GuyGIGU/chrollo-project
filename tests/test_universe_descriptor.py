"""Byte-parity lock for the Universe descriptor.

Task 1 of the multi-universe screener threads a ``Universe`` descriptor through
the scan path. The US-Stocks descriptor MUST resolve to the exact literals the
pipeline used before, so routing the existing scan through it changes nothing.
These tests pin that equality so a future edit to the descriptor can't silently
move the US-Stocks artifact/cache/ticker paths.
"""
from __future__ import annotations

import os

import pytest

from config import settings
from core.pipeline import tickers as tickers_mod
from core.pipeline.cache import _cache_paths
from core.pipeline.universe import (
    DEFAULT_UNIVERSE_KEY,
    Universe,
    default_universe,
    resolve_universe,
    universe_keys,
)


def _norm(path: str) -> str:
    return os.path.normpath(path)


def test_default_universe_matches_current_literals():
    u = default_universe()
    assert u.key == DEFAULT_UNIVERSE_KEY == "us_stocks"
    assert u.cache_filename == settings.CACHE_FILENAME
    assert u.cache_meta_filename == settings.CACHE_META_FILENAME
    assert u.market_context_filename == settings.MARKET_CONTEXT_FILENAME
    assert tuple(u.index_symbols) == tuple(settings.INDEX_SYMBOLS)
    assert _norm(u.ticker_csv) == _norm(tickers_mod._default_ticker_csv_path())


def test_cache_paths_default_unchanged():
    # The historical hardcoded tuple: project root + the two settings filenames.
    legacy_root = _norm(
        os.path.join(os.path.dirname(os.path.abspath(tickers_mod.__file__)), "..", "..")
    )
    expected = (
        os.path.join(legacy_root, settings.CACHE_FILENAME),
        os.path.join(legacy_root, settings.CACHE_META_FILENAME),
    )
    # None (back-compat), the descriptor, and the legacy literal all agree.
    assert _cache_paths(None) == _cache_paths(default_universe()) == expected


def test_artifact_path_default_is_screener_data_json():
    assert default_universe().artifact_path().endswith(
        os.path.join("output", "screener_data.json")
    )


def test_resolve_universe_is_a_closed_set():
    assert resolve_universe(None) == default_universe()
    assert resolve_universe("us_stocks").key == "us_stocks"
    u = default_universe()
    assert resolve_universe(u) is u  # a Universe passes through unchanged
    # Unknown keys (incl. path-traversal attempts) are rejected, never resolved
    # to a filesystem path.
    with pytest.raises(ValueError):
        resolve_universe("../../etc/passwd")
    with pytest.raises(ValueError):
        resolve_universe("commodities_etf")  # not registered until Task 2


def test_default_key_is_registered():
    assert DEFAULT_UNIVERSE_KEY in universe_keys()


def test_universe_is_frozen():
    u = default_universe()
    with pytest.raises(Exception):
        u.key = "mutated"  # frozen dataclass
    assert isinstance(u, Universe)
