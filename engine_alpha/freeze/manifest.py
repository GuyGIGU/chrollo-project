"""Frozen-config manifest — the hashable identity of the engine's constants.

The engine's computed output is a pure function of (market data, engine
constants, detector code). This module canonicalises the *constants* half: an
EXPLICIT allow-list of every value in ``config.settings`` that can move a
detector decision (which setups fire, how they score/rank, where the phase
boundaries land), gathered into a sorted dict whose sha256 is the engine config
version. An archived signal stamped with that hash can later be traced to the
exact config that produced it, and a freeze + backtest can assert the config
hasn't silently drifted. ONE non-settings block rides along, for the same
reason — it decides what the DATA MEANS, so it rotates the version like any
weight: the reader's own numbers (``engine_alpha/two_eyes_numbers.py``), which
the reader reads instead of settings.

The old engine's knobs (config/engine.py, config/scoring.py) left this list when
that engine retired (Sat 31/10/2026, the operator's word): the hash rotated once,
a declared epoch, and ``TWO_EYES_RULESET`` bumped to ``two-eyes-0.12.0-one-reader``.

Design rules (deliberate, audited):

  * The allow-list is HAND-CURATED, not a ``dir(settings)`` sweep. That is the
    whole point: it draws the line between "engine identity" (in) and "ops
    noise" (out — data source, cache, fetch tuning, rate-limit, quarantine,
    scheduler, dashboard, regime observability, ARCHIVE_LIVE_SCANS) so that an
    ops tweak never churns the engine version, and so the contract is auditable.
  * Settings are read LAZILY inside the function (import in-body), never at
    module import. The backend runs with cwd=webapp/backend which shadows the
    repo-root ``config`` package; a module-level import would risk binding the
    wrong module at import time. (See project_config_collision.)
  * A listed key that has VANISHED from settings raises ``KeyError`` — the
    contract cannot silently rot when a constant is renamed/removed. New
    settings are simply absent from the manifest until added to the allow-list
    on purpose.

Pure, read-only. No engine math, no I/O beyond the CLI's stdout.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

# ─────────────────────────────────────────────────────────────────────────────
# ENGINE-RELEVANT CONSTANTS (the manifest allow-list).
#
# Every name here is a setting that can change a detector decision. Grouped to
# mirror config/settings.py sections for auditability. To add a constant to the
# frozen contract, add its name here (and accept the new hash + re-baseline).
# ─────────────────────────────────────────────────────────────────────────────
ENGINE_SETTINGS_KEYS: tuple[str, ...] = (
    # Phase 0 — price-series regime (every read's provenance)
    "DATA_DIVIDEND_ADJUSTED",
    # The universe door (engine_alpha/universe_door.py) and the market-cap floor on the fires
    "MIN_PRICE",
    "MIN_VOLUME_50D",
    "MIN_YEARLY_RETURN",
    "MIN_MARKET_CAP",
    # The reader: its hand-bumped ruleset string, the daily window its stock facts are read on, the ADR window
    # (the reader's own numbers ride as the TWO_EYES_METHOD_NUMBERS block below)
    "TWO_EYES_RULESET",
    "DAILY_STRUCTURE_PERIOD",
    "ADR_WINDOW",
    # Relative strength against SPY: the lookback of the excess-return read (the seed's and the scan's SPY 6m)
    "RS_LOOKBACK_BARS",
    # Lane-C advisory/enrichment flags + tuning knobs (default-off + byte-identical off, read via
    # _flag()/getattr on the advisory path). Registered so the consumption wave that wires them into
    # score/archive rotates engine_config_version from day one — and so a lookback/lag tweak that changes an
    # archived advisory value cannot slip the hash. (SECTOR_RANKING_ETFS is the ranked symbol SET,
    # ops-excluded like INDEX_SYMBOLS — see below.)
    "FUNDAMENTALS_ENABLED",
    "FUNDAMENTALS_EARNINGS_HISTORY_LIMIT",
    "FUNDAMENTALS_FILING_LAG_DAYS",
    # The fundamentals sheet + the fundamental grade (2026-10-12): display and
    # archive only, but each knob moves an archived value (the grade), so it
    # rotates the stamp like the lag above. SEC_CONTACT is a data source:
    # ops-excluded (see the list below).
    "FUND_SHEET_QUARTERS",
    "FUND_GRADE_EPS_GROWTH_MIN",
    "FUND_GRADE_SALES_GROWTH_MIN",
    "FUND_GRADE_BEATS_MIN",
    "FUND_GRADE_REACTION_RANGES",
    "FUND_GRADE_REACTION_VOLUME",
    "FUND_GRADE_SBC_MAX",
    "FUND_GRADE_MIN_CHECKS",
    "FUND_GRADE_LETTERS",
    "FUND_FLAG_UNUSUAL_SHARE",
    "FUND_FLAG_SHARE_DROP",
    "FUND_FLAG_ACQUISITION_SHARE",
    "RS_LINE_ENABLED",
    "RS_LINE_NEW_HIGH_LOOKBACK",
    "SECTOR_RANKING_ENABLED",
    "SECTOR_RANKING_LOOKBACKS",
    "RS_RATING_LOOKBACK",
)

# ─────────────────────────────────────────────────────────────────────────────
# DELIBERATELY EXCLUDED (ops / observability knobs).
#
# Documented for auditability only — NOT used by collect_manifest. These move
# how data is fetched/cached/scheduled or are pure observability, never a
# detector decision. Changing one must NOT churn the engine version.
#   data source / cache:  MARKET_DATA_PROVIDER, SEC_CONTACT, CACHE_FILENAME, PARQUET_*,
#                         DOWNLOAD_PERIOD, TICKER_* admission/skiplist, ...
#   archiving:            ARCHIVE_LIVE_SCANS
#   fetch tuning:         TTL_*, FULL_REFRESH_*, INCREMENTAL_*, *_REPAIR_*,
#                         MARKET_DATA_MIN_LATEST_COVERAGE, SPLIT_PROBE_*,
#                         MARKET_DATA_EVALUATE_MAX_LAG_SESSIONS,
#                         ABSENT_SESSION_LEDGER_MAX,
#                         PROVIDER_ABSENT_SESSION_MAX_COVERAGE
#   rate limit / quarantine:  YAHOO_RATE_LIMIT_*, YAHOO_DOWNLOAD_WORKERS,
#                         QUARANTINE_*
#   market-context fetch: SPY_SYMBOL, INDEX_SYMBOLS, SECTOR_RANKING_ETFS,
#                         MARKET_CONTEXT_TTL_*
#   regime observability: REGIME_* (state is observability-only, not a gate)
#   dashboard:            DASHBOARD_*
#   scheduler / alerts:   SCAN_SCHEDULE_*, FORWARD_RETURNS_MIN_AGE_DAYS,
#                         ALERT_*
# ─────────────────────────────────────────────────────────────────────────────


def _canonical(value: Any) -> Any:
    """Coerce a settings value into a JSON-canonical form.

    Tuples/lists -> list; dicts -> dict with sorted keys is handled by
    json.dumps(sort_keys=True), so we only need to make containers JSON-native.
    Scalars (int/float/bool/str/None) pass through unchanged.
    """
    if isinstance(value, tuple):
        return [_canonical(v) for v in value]
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    return value


def collect_manifest() -> Dict[str, Any]:
    """Return the canonical engine-config manifest (a plain dict).

    Reads ``config.settings`` lazily and pulls exactly ``ENGINE_SETTINGS_KEYS``.
    Raises ``KeyError`` if any listed key is missing from settings — the frozen
    contract must not silently rot when a constant is renamed or removed.
    """
    from config import settings

    manifest: Dict[str, Any] = {}
    missing: list[str] = []
    for key in ENGINE_SETTINGS_KEYS:
        if not hasattr(settings, key):
            missing.append(key)
            continue
        manifest[key] = _canonical(getattr(settings, key))
    if missing:
        raise KeyError(
            "frozen-config manifest references settings that no longer exist: "
            + ", ".join(sorted(missing))
            + " — update engine_alpha/freeze/manifest.ENGINE_SETTINGS_KEYS deliberately "
            "(a rename/removal changes the engine contract)."
        )

    # The reader's own numbers (two-eyes-reader task 7): the reader reads them
    # from two_eyes_numbers, not settings, so without this block a tuned number
    # would change the reading and keep the version. The numbers live OUTSIDE the
    # package (a module with no imports): this stamp runs on every night's
    # payload and archive write, and importing them from inside the package would
    # run its door, which loads every stage (council review 2026-10-09, finding 1).
    from engine_alpha import two_eyes_numbers

    manifest["TWO_EYES_METHOD_NUMBERS"] = {
        name: _canonical(value)
        for name, value in vars(two_eyes_numbers).items() if name.isupper()}
    return manifest


def manifest_json() -> str:
    """Canonical JSON serialization of the manifest (sorted keys, stable)."""
    return json.dumps(collect_manifest(), sort_keys=True, separators=(",", ":"))


def manifest_hash() -> str:
    """sha256 hex digest of the canonical manifest — the engine config version."""
    return hashlib.sha256(manifest_json().encode("utf-8")).hexdigest()


def _main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m engine_alpha.freeze.manifest",
        description="Print the frozen engine-config manifest or its hash.",
    )
    parser.add_argument(
        "--hash",
        action="store_true",
        help="print only the sha256 manifest hash (the engine config version)",
    )
    args = parser.parse_args(argv)

    if args.hash:
        print(manifest_hash())
    else:
        print(json.dumps(collect_manifest(), sort_keys=True, indent=2))
        print(f"\n# engine_config_version (sha256): {manifest_hash()}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_main(sys.argv[1:]))
