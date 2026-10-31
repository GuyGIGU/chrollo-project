"""The version stamp: the hash of every number that can move a read, the night's ``engine_config_version``.

``collect_manifest`` gathers a hand-curated allow-list of ``config.settings`` names (the ops knobs stay out, so a
fetch or cache tweak never churns the version) and every upper-case name of ``engine_alpha/numbers.py``;
``manifest_hash`` is its sha256. Settings are read lazily inside the function; a listed name that vanished raises.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

# The allow-list: every setting that can change a read. To freeze a new one, add its name here and accept the new hash.
ENGINE_SETTINGS_KEYS: tuple[str, ...] = (
    # The price series' regime (every read's provenance)
    "DATA_DIVIDEND_ADJUSTED",
    # The gate's floors (engine_alpha/gate.py) and the market-cap floor on the fires
    "MIN_PRICE",
    "MIN_VOLUME_50D",
    "MIN_YEARLY_RETURN",
    "MIN_MARKET_CAP",
    # The reader: its hand-bumped ruleset string, the daily window its stock facts are read on, the ADR window
    # (the reader's own numbers ride as the ALPHA_NUMBERS block below)
    "ALPHA_RULESET",
    "DAILY_STRUCTURE_PERIOD",
    "ADR_WINDOW",
    # Relative strength against SPY: the lookback of the excess-return read (the seed's and the scan's SPY 6m)
    "RS_LOOKBACK_BARS",
    # The advisory flags and their knobs: each moves an archived advisory value, so it rotates the stamp
    "FUNDAMENTALS_ENABLED",
    "FUNDAMENTALS_EARNINGS_HISTORY_LIMIT",
    "FUNDAMENTALS_FILING_LAG_DAYS",
    # The fundamentals sheet and the fundamental grade: display and archive only, but each knob moves the archived grade
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

# DELIBERATELY EXCLUDED, the ops knobs: data source and cache, ARCHIVE_LIVE_SCANS, fetch tuning, rate limit and
# quarantine, the market-context fetch (SPY_SYMBOL, INDEX_SYMBOLS, SECTOR_RANKING_ETFS), REGIME_*, DASHBOARD_*,
# the scheduler and alerts. None of them moves a read; tests/engine/test_invariants.py holds the list.


def _canonical(value: Any) -> Any:
    """A settings value in JSON-native form: tuples and lists to lists, dict keys to strings; scalars pass through."""
    if isinstance(value, tuple):
        return [_canonical(v) for v in value]
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    return value


def collect_manifest() -> Dict[str, Any]:
    """The canonical manifest, a plain dict: ``ENGINE_SETTINGS_KEYS`` read lazily off ``config.settings``, plus the
    reader's numbers as ``ALPHA_NUMBERS``. Raises ``KeyError`` when a listed name is gone from settings."""
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
            + " — update engine_alpha/stamp.ENGINE_SETTINGS_KEYS deliberately "
            "(a rename/removal changes the engine contract)."
        )

    # the reader reads its numbers here, not in settings: without this block a tuned number would keep the version
    from engine_alpha import numbers

    manifest["ALPHA_NUMBERS"] = {
        name: _canonical(value)
        for name, value in vars(numbers).items() if name.isupper()}
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
        prog="python -m engine_alpha.stamp",
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
