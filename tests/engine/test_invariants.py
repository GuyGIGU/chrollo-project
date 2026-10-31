"""Manifest invariants (the engine-freeze track).

The frozen-config manifest (engine_alpha/stamp.py): determinism, ops-knob exclusion, the
"a listed key vanished" guard, and provenance completeness — every setting the reader's eval path reads
is hashed into engine_config_version. The old engine's geometry invariants (support under resistance,
phases in order, the zigzag's alternation) left with that engine on Sat 31/10/2026; the alpha reader's
record is pinned chart by chart in tests/engine/test_two_eyes_*.py and by tools.regression.reader_pin.

All offline; touches no DB.
"""
from __future__ import annotations

import pytest

import config.settings as settings


# ── Frozen-config manifest contract ──────────────────────────────────────────
def test_manifest_hash_is_deterministic():
    from engine_alpha.stamp import manifest_hash

    h1 = manifest_hash()
    h2 = manifest_hash()
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) == 64
    int(h1, 16)  # valid hex


def test_manifest_includes_engine_excludes_ops():
    from engine_alpha.stamp import collect_manifest

    m = collect_manifest()
    # representative engine constants are present
    for key in ("MIN_PRICE", "ALPHA_RULESET", "DAILY_STRUCTURE_PERIOD",
                "ADR_WINDOW", "RS_LOOKBACK_BARS", "ALPHA_NUMBERS"):
        assert key in m, f"engine constant {key} missing from manifest"
    # ops / observability knobs are excluded
    for key in ("MARKET_DATA_PROVIDER", "YAHOO_RATE_LIMIT_PER_SEC",
                "ARCHIVE_LIVE_SCANS", "DASHBOARD_CHART_DAYS",
                "SCAN_SCHEDULE_HOUR_ET", "QUARANTINE_ENABLED"):
        assert key not in m, f"ops knob {key} leaked into manifest"


def test_manifest_raises_when_listed_key_vanishes(monkeypatch):
    """The contract must not silently rot: a listed key that no longer exists
    on settings raises, rather than dropping silently from the hash."""
    import engine_alpha.stamp as mod

    monkeypatch.setattr(
        mod, "ENGINE_SETTINGS_KEYS",
        mod.ENGINE_SETTINGS_KEYS + ("DEFINITELY_NOT_A_SETTING_XYZ",),
    )
    with pytest.raises(KeyError):
        mod.collect_manifest()


def test_manifest_json_is_canonical_sorted():
    """manifest_json is stable, sorted, and round-trips to collect_manifest."""
    import json

    from engine_alpha.stamp import collect_manifest, manifest_json

    js = manifest_json()
    parsed = json.loads(js)
    assert parsed == collect_manifest()
    # keys are sorted in the serialized form
    keys = list(parsed.keys())
    assert keys == sorted(keys)


# Ops / observability knobs that the engine EVAL PATH legitimately reads but
# which must NOT churn the engine config version (they change how data is
# fetched/serialized, never a detector decision). Enumerated by reading the
# current reads across the scanned files; kept small and explicit so a NEW
# score-affecting setting cannot hide behind a blanket exclusion. Mirror of
# manifest.py's DELIBERATELY EXCLUDED block for the eval-path subset:
#   SPY_SYMBOL   — market-context fetch symbol (screener.py)
#   PARQUET_ENGINE — cache (de)serialization engine (screener.py)
#   SECTOR_RANKING_ETFS — the SPDR sector-ETF universe the (dark, advisory)
#       sector-ranking read ranks; a symbol SET like INDEX_SYMBOLS, not a
#       computed-value tuning knob (core/regime/sector_ranking.py)
ALLOWED_OPS_EXCLUSIONS = frozenset(
    {"SPY_SYMBOL", "PARQUET_ENGINE", "SECTOR_RANKING_ETFS"})

# The engine's decision-making eval path. Every ``settings.NAME`` read here can
# move which setups fire / how they are graded / what a fire carries — the
# hashable engine identity — EXCEPT the ops knobs enumerated above.
# engine_alpha/ is GLOBBED whole (every module, see _engine_eval_path_sources), not
# hand-listed: a new stage is covered the day it lands and cannot be forgotten
# here (the reader reads its numbers from engine_alpha.numbers, never settings — a
# settings read inside it would surface here first). The pipeline conductor stays explicit. The Lane-C entry modules (scan_context /
# advisory) DELEGATE their tuning reads to helper modules, so those helpers are
# listed too — else a lookback/lag knob read one import-hop away escapes the scan
# (the engine-α second-pass audit gap, 2026-07-06).
_ENGINE_EVAL_PATH_MODULES = (
    "core.pipeline.screening.screener",
    "core.regime.scan_context",
    "core.regime.rs_line",
    "core.regime.sector_ranking",
    "core.fundamentals.advisory",
    "core.fundamentals.metrics",
)


def _engine_eval_path_sources():
    """Source files of the engine eval path: the explicit conductor modules
    plus EVERY ``engine_alpha/**/*.py`` (globbed recursively)."""
    import importlib
    from pathlib import Path

    import engine_alpha

    paths = [Path(importlib.import_module(m).__file__)
             for m in _ENGINE_EVAL_PATH_MODULES]
    reader_files = sorted(Path(engine_alpha.__file__).parent.rglob("*.py"))
    # A non-recursive glob once matched only __init__.py and silently emptied
    # this guard. Keep it from going vacuous.
    assert len(reader_files) >= 15, reader_files
    return paths + reader_files


def test_every_scoring_settings_symbol_is_in_manifest():
    """Provenance completeness: EVERY ``settings.NAME`` the engine eval path reads
    must be in ``ENGINE_SETTINGS_KEYS`` and hashed into engine_config_version —
    unless it is one of the explicitly enumerated ops-only exclusions.

    The eval path (the door + the adapter + the universe door + the screener +
    ALL of engine_alpha/) is the layer that decides which setups fire,
    how they are graded and what a fire carries — every constant it touches
    changes archived output and MUST bump the manifest hash. This static-source
    scan (over the ``settings.NAME``, ``getattr(settings, "NAME")``, and
    ``_flag("NAME")`` advisory-helper read forms) makes a future flag/knob unable
    to silently escape provenance: add a read in any scanned module and this
    fails until the name is either added to the allow-list or declared an ops
    exclusion. (Regression guard for the since-retired CANDLE_SPREAD_AWARE /
    PUZZLE_SCORE_ENABLED / SOS_*_BOX omissions and the Lane-C ``_flag()``
    indirection seam.)
    """
    import re

    from engine_alpha.stamp import ENGINE_SETTINGS_KEYS

    # Union settings reads across the whole eval path, matching both the direct
    # attribute form (``settings.NAME``) and the string-literal getattr form
    # (``getattr(settings, "NAME")`` / single-quoted). The scan is over raw
    # source text (comments included, deliberately): a comment naming
    # ``settings.X`` either documents a real nearby read or should be reworded.
    pat_attr = re.compile(r"settings\.([A-Z][A-Z0-9_]+)")
    pat_getattr = re.compile(r"getattr\(\s*settings\s*,\s*['\"]([A-Z][A-Z0-9_]+)['\"]")
    # Indirection seam: the ``_flag("NAME")`` advisory-path helper (Lane-C reads
    # in core/regime + core/fundamentals).
    pat_flag = re.compile(r"_flag\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]")
    referenced: set[str] = set()
    for src_path in _engine_eval_path_sources():
        src = src_path.read_text(encoding="utf-8")
        referenced |= set(pat_attr.findall(src))
        referenced |= set(pat_getattr.findall(src))
        referenced |= set(pat_flag.findall(src))
    assert referenced, "scanner found no settings.<NAME> reads on the eval path"

    # Every read must be either provenance-hashed OR an explicit ops exclusion —
    # nothing may silently fall between the two.
    unaccounted = sorted(referenced - set(ENGINE_SETTINGS_KEYS) - ALLOWED_OPS_EXCLUSIONS)
    assert not unaccounted, (
        "score/structure-affecting settings read by the engine eval path "
        f"({', '.join(_ENGINE_EVAL_PATH_MODULES)} + engine_alpha/**) are absent from "
        "engine_alpha.stamp.ENGINE_SETTINGS_KEYS (so flipping them would change "
        "engine output WITHOUT bumping engine_config_version, corrupting archive "
        f"provenance): {unaccounted}. Add them to the manifest allow-list, or, if "
        "one is genuinely an ops-only knob, to ALLOWED_OPS_EXCLUSIONS with a reason."
    )

    # The exclusion set must not rot: every declared ops exclusion has to actually
    # be read somewhere on the eval path (else it is stale) and must NOT also be in
    # the manifest (that would be a contradictory double-listing).
    stale_exclusions = sorted(ALLOWED_OPS_EXCLUSIONS - referenced)
    assert not stale_exclusions, (
        f"ALLOWED_OPS_EXCLUSIONS lists names no longer read on the eval path: "
        f"{stale_exclusions}. Remove them."
    )
    double_listed = sorted(ALLOWED_OPS_EXCLUSIONS & set(ENGINE_SETTINGS_KEYS))
    assert not double_listed, (
        f"names are BOTH ops-excluded and in the manifest allow-list: {double_listed}. "
        "Pick one."
    )

    # Every referenced symbol must actually EXIST on settings — a stale name in
    # the eval path (or the regex) would otherwise mask a real gap.
    for name in referenced:
        assert hasattr(settings, name), (
            f"the eval path reads settings.{name} which does not exist on "
            "config.settings"
        )


# Boolean settings that are default-OFF but ADOPTED engine identity, not pending
# dark flags — exempt from the flag-ledger requirement (they belong to the frozen
# config, tracked in the manifest, with no "decision pending").
_LEDGER_EXEMPT_OFF_BOOLS = frozenset({
    "DATA_DIVIDEND_ADJUSTED",   # as-traded price regime (adopted 2026-07-02)
})


def _ledger_dark_flags() -> dict:
    """Parse docs/flag_ledger.md's Dark-flags table -> {flag_name: kill_by}.

    Reads the first backticked NAME token of each row of the Dark table, plus the
    row's last cell (the kill-by date). The table ENDS at the next "## " heading:
    the sections below it carry tables of their own whose rows also open with a
    backticked flag name (the final-method fate table, 2026-09-20), and reading
    those as dark rows makes this guard fail on a cell that was never a date."""
    import re
    from _paths import REPO_ROOT

    text = (REPO_ROOT / "docs" / "flag_ledger.md"
            ).read_text(encoding="utf-8")
    start = text.index("## Dark flags")
    end = text.index("\n## ", start + 1)
    out: dict = {}
    for line in text[start:end].splitlines():
        line = line.strip()
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        m = re.search(r"`([A-Z][A-Z0-9_]+)`", cells[0])
        if m:
            out[m.group(1)] = cells[-1]
    return out


def test_flag_ledger_matches_the_default_off_engine_flags():
    """Machine-enforce the flag-ledger's "never silently carried" promise.

    (a) Every flag in the Dark table names a REAL setting that is STILL off (a
    flipped or deleted flag belongs in Retired, not Dark) and carries a dated
    kill-by. (b) Every default-off boolean setting is EITHER a Dark-table row or
    an explicitly adopted exemption — so a flag cannot be added / removed /
    flipped in settings.py with the ledger never noticing. Closes the seam the
    engine-alpha council audit flagged (2026-07-06)."""
    from datetime import date

    from config import settings

    dark = _ledger_dark_flags()
    assert dark, "parsed no flags from the flag-ledger Dark table"

    for name, kill_by in dark.items():
        assert hasattr(settings, name), (
            f"flag-ledger Dark table lists `{name}`, not a config.settings symbol")
        val = getattr(settings, name)
        assert val is False, (
            f"`{name}` is in the Dark (decision-pending) table but is not off "
            f"({val!r}); a flipped or deleted flag belongs in the Retired section")
        try:
            date.fromisoformat(kill_by)
        except ValueError:
            raise AssertionError(
                f"`{name}` has no dated kill-by (got {kill_by!r}); every dark flag "
                "carries a YYYY-MM-DD kill-by so it is never silently carried")

    off_bools = {n for n in dir(settings)
                 if not n.startswith("_") and getattr(settings, n) is False}
    unlisted = sorted(off_bools - set(dark) - _LEDGER_EXEMPT_OFF_BOOLS)
    assert not unlisted, (
        f"default-off boolean settings with no flag-ledger Dark row: {unlisted}. "
        "Add a Dark-table row (name + blocking decision + kill-by), or — if it is "
        "adopted engine identity, not a pending flag — add it to "
        "_LEDGER_EXEMPT_OFF_BOOLS with a reason.")
