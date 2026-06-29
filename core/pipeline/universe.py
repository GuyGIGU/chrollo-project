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

import json
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

    Three universes, all driven by the same engine:
    - ``us_stocks``      — the existing NASDAQ common-stock scan (byte-identical default).
    - ``us_sectors``     — the 11 SPDR sector ETFs + broad-market indices.
    - ``commodities_etf``— curated commodity + thematic/industry ETFs.

    The ETF universes draw from curated CSVs (``ticker_source="csv"``: no NASDAQ FTP
    pull, no admission gate) and own their cache / artifact / context filenames so
    they never collide with US-Stocks. Their ``index_symbols`` only gate which
    members are skipped from evaluation as pure regime benchmarks; the broad-market
    regime/breadth sourcing for these small universes is handled separately (Task 4).
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
    us_sectors = Universe(
        key="us_sectors",
        label="US Sectors + Market",
        universe_type="us_sectors",
        ticker_source="csv",
        ticker_csv=os.path.join(_config_dir(), "tickers_us_sectors.csv"),
        cache_filename="market_data_cache_5y_us_sectors.parquet",
        cache_meta_filename="cache_meta_us_sectors.json",
        market_context_filename="market_context_us_sectors.json",
        artifact_filename="screener_data_us_sectors.json",
        index_symbols=("SPY", "QQQ"),
    )
    commodities_etf = Universe(
        key="commodities_etf",
        label="Commodities + ETFs",
        universe_type="commodities_etf",
        ticker_source="csv",
        ticker_csv=os.path.join(_config_dir(), "tickers_commodities_etf.csv"),
        cache_filename="market_data_cache_5y_commodities_etf.parquet",
        cache_meta_filename="cache_meta_commodities_etf.json",
        market_context_filename="market_context_commodities_etf.json",
        artifact_filename="screener_data_commodities_etf.json",
        index_symbols=(),
    )
    return {u.key: u for u in (us_stocks, us_sectors, commodities_etf)}


_DRILLDOWN_MAP_FILENAME = "commodity_equity_map.json"


def drilldown_map() -> dict[str, list[str]]:
    """Curated commodity/thematic-ETF -> related-equity basket (read at call time).

    Returns an empty dict if the file is missing or malformed; the leading
    ``_comment`` key (and any other underscore-prefixed key) is dropped. Used by
    the top-down drill-down so a firing commodity/thematic ETF can resolve to the
    equities it represents. Sector SPDRs are NOT here — they drill via the
    existing ``sector_etf`` mapping carried on each stock setup.
    """
    path = os.path.join(_config_dir(), _DRILLDOWN_MAP_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for key, value in raw.items():
        if key.startswith("_") or not isinstance(value, list):
            continue
        out[str(key).upper()] = [str(v).strip().upper() for v in value if str(v).strip()]
    return out


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
