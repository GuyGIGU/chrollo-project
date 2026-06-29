"""Universe descriptor — the single source of truth for *which* market a scan
covers and *where* its artifacts live.

The screener engine runs over any ticker list unchanged; everything ELSE about a
scan (ticker source, market-data cache, output artifact, regime/index set,
archive tag) used to be a scattered set of hardcoded literals living in five
different modules. This module folds those co-travelling literals into one
immutable :class:`Universe` descriptor, so adding a universe becomes one registry
entry rather than six coordinated edits — and the read side and write side can
never disagree about where a universe's artifact lives.

The US-Stocks descriptor resolves to the EXACT current literals, so routing the
existing scan through the descriptor is byte-parity-preserving by construction
(locked by ``tests/test_universe_descriptor.py``).

Two discipline points baked in here:
- **Paths anchor to the project root, never cwd** — a universe key resolves to a
  fixed file under the repo, so a stray working directory can't redirect one
  universe's writes onto another's artifact.
- **Settings are read at call time, never import time** — to stay clear of the
  config-vs-cwd shadowing trap (the backend cwd shadows the repo-root ``config``
  package), the registry is rebuilt per call rather than materialized on import.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from config import settings


def _project_root() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    )


def _config_dir() -> str:
    return os.path.normpath(os.path.join(_project_root(), "config"))


@dataclass(frozen=True)
class Universe:
    """One scannable market: its identity, ticker source, and artifact paths.

    Filename fields are bare names; the ``*_path`` accessors anchor them under the
    project root, so a universe can only ever resolve to a fixed file in the data
    directory.
    """

    key: str                        # API/URL token; closed-set member
    label: str                      # human label, e.g. "US Stocks"
    universe_type: str              # archive tag (used from Task 3), e.g. "us_equities"
    ticker_source: str              # "nasdaq" (FTP common-stock dump) | "csv" (curated)
    ticker_csv: str                 # absolute path to this universe's ticker CSV
    cache_filename: str             # market-data parquet (bare name)
    cache_meta_filename: str        # cache metadata json (bare name)
    market_context_filename: str    # regime/breadth context json (bare name)
    artifact_filename: str          # dashboard payload json (bare name)
    index_symbols: tuple[str, ...]  # regime index symbols carried with the panel

    def cache_paths(self) -> tuple[str, str]:
        """(market-data parquet, cache-meta json) anchored under the project root."""
        root = _project_root()
        return (
            os.path.join(root, self.cache_filename),
            os.path.join(root, self.cache_meta_filename),
        )

    def artifact_path(self) -> str:
        """Dashboard payload JSON path (``output/<artifact_filename>``)."""
        return os.path.join(_project_root(), "output", self.artifact_filename)

    def market_context_path(self) -> str:
        """Regime/breadth context cache path, anchored under the project root."""
        return os.path.join(_project_root(), self.market_context_filename)


DEFAULT_UNIVERSE_KEY = "us_stocks"


def _build_registry() -> dict[str, "Universe"]:
    """Construct the universe registry (settings read here, at call time).

    Only US-Stocks is registered today; the two ETF universes are added in a later
    step as additional entries — no other code changes when they land.
    """
    us_stocks = Universe(
        key=DEFAULT_UNIVERSE_KEY,
        label="US Stocks",
        universe_type="us_equities",
        ticker_source="nasdaq",
        ticker_csv=os.path.join(_config_dir(), "tickers.csv"),
        cache_filename=settings.CACHE_FILENAME,
        cache_meta_filename=settings.CACHE_META_FILENAME,
        market_context_filename=settings.MARKET_CONTEXT_FILENAME,
        artifact_filename="screener_data.json",
        index_symbols=tuple(getattr(settings, "INDEX_SYMBOLS", [settings.SPY_SYMBOL])),
    )
    return {us_stocks.key: us_stocks}


def universe_keys() -> tuple[str, ...]:
    """The closed set of known universe keys (the allowlist)."""
    return tuple(_build_registry().keys())


def default_universe() -> "Universe":
    """The US-Stocks universe — the byte-identical default for every call site."""
    return _build_registry()[DEFAULT_UNIVERSE_KEY]


def resolve_universe(universe: "Universe | str | None") -> "Universe":
    """Resolve a :class:`Universe`, a key string, or ``None`` to a descriptor.

    ``None`` resolves to the default (US-Stocks), so every existing call site is
    unchanged. An unrecognized key raises ``ValueError`` — a universe value can
    never become an arbitrary filesystem path (closed-set allowlist).
    """
    if universe is None:
        return default_universe()
    if isinstance(universe, Universe):
        return universe
    registry = _build_registry()
    try:
        return registry[universe]
    except KeyError:
        raise ValueError(
            f"unknown universe {universe!r}; known: {', '.join(registry)}"
        ) from None
