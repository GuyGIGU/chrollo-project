"""Geometry & manifest invariants (Lane A — engine-freeze track).

These are PROPERTY tests, not example tests: they assert structural invariants
that must hold for *every* Structure / swing skeleton the engine emits, over the
committed shadow fixture (real OHLC for the recently-firing tickers, offline).
They tolerate None / empty — the engine is free not to fire — and only assert
when a structure exists. That makes them robust to calibration changes (they
never force a particular fire) while still catching a geometry regression
(support above resistance, phases out of order, a NaN level, a broken zigzag).

Plus a focused contract test for the frozen-config manifest
(engine_alpha/freeze/manifest.py): determinism, ops-knob exclusion, and the
"a listed key vanished" guard.

All offline. Reuses the shadow fixture + conftest fixtures; touches no DB.
"""
from __future__ import annotations

import math

import pytest

import config.settings as settings
from engine_alpha.evaluation import _prepare_eval_frame
from engine_alpha.structure.narrative.reader import read_structure
from engine_alpha.structure.metrics.pivots import _build_zigzag, _find_pivots
from engine_alpha.structure.phases.segmentation import segment_swings


# ── Shared fixture: real Structures over the committed shadow fixture ─────────
# Frozen coverage baseline (measured 2026-08-22 over the committed fixture):
# 37 tickers -> 33 structures, 0 dropped at prep/ATR. A committed deterministic
# fixture can never legitimately produce a skip (the suite's own "fail LOUDLY,
# never skip" doctrine — tests/test_regression_guards.py), so the module FAILS
# below the floor instead of going green-by-skip, and any NEW prep/ATR drop is
# a coverage erosion the shadow guard cannot see. Re-measure both numbers only
# at a deliberate fixture recapture (EC-29 flip/seam commit), never mid-build.
_MIN_FIXTURE_STRUCTURES = 30
_FIXTURE_DROPPED_BASELINE = 0


def _structures_from_fixture():
    """Return ``(structures, dropped)``: (ticker, df, Structure) triples for
    every fixture ticker that produces a non-None Structure, plus the count of
    tickers lost to a prep refusal or a missing/broken ATR sample. A None
    Structure is NOT a drop — the engine is free not to fire. Built once,
    module-scoped, so the parquet read + ATR compute happen a single time.
    """
    from tools.shadow_diff import _load_fixture

    frames, _scalars = _load_fixture()
    out = []
    dropped = 0
    for ticker, df in frames.items():
        prep = _prepare_eval_frame(df)
        if prep is None:
            dropped += 1
            continue
        daily = prep["df"]
        try:
            atr = float(daily.iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET]["ATR_10"])
        except (KeyError, IndexError, ValueError):
            dropped += 1
            continue
        structure = read_structure(daily, atr)
        if structure is None:
            continue
        out.append((ticker, daily, structure))
    return out, dropped


@pytest.fixture(scope="module")
def fixture_structures():
    structures, dropped = _structures_from_fixture()
    assert len(structures) >= _MIN_FIXTURE_STRUCTURES, (
        f"shadow fixture yielded {len(structures)} structures "
        f"(< {_MIN_FIXTURE_STRUCTURES}): the geometry battery lost its "
        "subjects — a committed fixture can never legitimately skip"
    )
    assert dropped == _FIXTURE_DROPPED_BASELINE, (
        f"{dropped} fixture ticker(s) silently dropped at prep/ATR "
        f"(frozen baseline: {_FIXTURE_DROPPED_BASELINE}) — the geometry "
        "module's coverage eroded without a deliberate fixture recapture"
    )
    return structures


# ── Geometry invariants on emitted Structures ────────────────────────────────
def test_support_below_resistance(fixture_structures):
    """Vertical invariant: the support rail is strictly below resistance."""
    for ticker, _df, s in fixture_structures:
        assert s.S < s.R, f"{ticker}: S ({s.S}) not below R ({s.R})"


def test_levels_are_finite(fixture_structures):
    """No NaN / inf in the emitted price levels (R, S) or box width."""
    for ticker, _df, s in fixture_structures:
        for name in ("R", "S", "box_width"):
            val = float(getattr(s, name))
            assert math.isfinite(val), f"{ticker}: {name} not finite ({val})"
        # The vertical view recomposes the levels — it must be finite too.
        for name in ("R", "S", "box_height"):
            val = float(s.vertical[name])
            assert math.isfinite(val), f"{ticker}: vertical[{name}] not finite ({val})"


def test_phase_ordering_monotone(fixture_structures):
    """Time invariant: A -> B opens in chronological order.

      climax_bar <= ar_bar <= phase_b_start_bar <= phase_b_end_bar

    The root swing climax precedes its automatic reaction, the box opens at /
    after the AR low, and Phase B cannot end before it starts. The state machine
    builds these sequentially, so the bars must never go backwards (equality is
    allowed for a degenerate zero-length phase).

    NOTE: phase_d_start_bar is asserted separately (test_phase_d_after_b_start).
    phase_b_end_bar and phase_d_start_bar are TWO DIFFERENT boundary semantics —
    phase_b_end_bar is the LPS start (terminator='lps') or spring tip, while
    phase_d_start_bar is the right-side region resolved from support-test
    evidence, which legitimately begins EARLIER than the LPS. So B_end vs D_start
    is intentionally NOT a monotone pair and must not be asserted as one.
    """
    for ticker, _df, s in fixture_structures:
        bars = [
            ("climax_bar", s.climax_bar),
            ("ar_bar", s.ar_bar),
            ("phase_b_start_bar", s.phase_b_start_bar),
            ("phase_b_end_bar", s.phase_b_end_bar),
        ]
        for (an, av), (bn, bv) in zip(bars, bars[1:]):
            assert av <= bv, (
                f"{ticker}: phase order broken {an}={av} > {bn}={bv}"
            )


def test_phase_d_after_b_start(fixture_structures):
    """Phase D (the right-side region) opens at or after Phase B opens — it is a
    later region of the same base, never before the box began."""
    for ticker, _df, s in fixture_structures:
        assert s.phase_b_start_bar <= s.phase_d_start_bar, (
            f"{ticker}: phase_d_start {s.phase_d_start_bar} precedes "
            f"phase_b_start {s.phase_b_start_bar}"
        )


def test_phase_bars_in_range(fixture_structures):
    """Every phase boundary bar indexes a real bar of the daily frame."""
    for ticker, df, s in fixture_structures:
        n = len(df)
        for name in (
            "climax_bar", "ar_bar", "phase_b_start_bar",
            "phase_b_end_bar", "phase_d_start_bar",
        ):
            bar = int(getattr(s, name))
            assert 0 <= bar < n, f"{ticker}: {name}={bar} out of range [0,{n})"


def test_spring_tip_inside_phase_b(fixture_structures):
    """The spring tip sits inside Phase B (at/after B opens, at/before B ends).
    When a spring terminates B (terminator='spring'), the tip ends B, so it must
    not precede phase_b_start_bar nor exceed phase_b_end_bar."""
    for ticker, _df, s in fixture_structures:
        if s.spring is None:
            continue
        tip = getattr(s.spring, "tip_bar", None)
        if tip is None:
            continue
        assert s.phase_b_start_bar <= int(tip) <= s.phase_b_end_bar, (
            f"{ticker}: spring tip {tip} outside B window "
            f"[{s.phase_b_start_bar}, {s.phase_b_end_bar}]"
        )


# ── Swing-skeleton invariant: strict pivot (peak/valley) alternation ─────────
def _zigzag_for(df):
    n = len(df)
    order = (settings.PIVOT_ORDER_LONG if n >= settings.PIVOT_ORDER_THRESHOLD
             else settings.PIVOT_ORDER_SHORT)
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    peaks, valleys = _find_pivots(highs, lows, order)
    if not peaks or not valleys:
        return []
    return _build_zigzag(peaks, valleys, highs, lows)


def test_zigzag_strict_kind_alternation(fixture_structures):
    """The swing skeleton's pivots strictly alternate peak/valley.

    This is the canonical "strict pivot alternation" guarantee of _build_zigzag
    (consecutive same-type pivots are merged to the more extreme one). It is the
    structural property — NOT the derived swing `direction` sign, which can
    legitimately repeat across a zero-displacement swing.
    """
    checked = 0
    for ticker, df, _s in fixture_structures:
        zz = _zigzag_for(df)
        if len(zz) < 2:
            continue
        kinds = [p[1] for p in zz]
        for i in range(len(kinds) - 1):
            assert kinds[i] != kinds[i + 1], (
                f"{ticker}: zigzag kinds not alternating at {i}: "
                f"{kinds[i]} == {kinds[i + 1]}"
            )
        checked += 1
    assert checked > 0, "no zigzags with >=2 pivots in the fixture"


def test_zigzag_bars_non_decreasing(fixture_structures):
    """Zigzag pivots are ordered in time (non-decreasing bar index).

    NOT strictly increasing: a single wide outside bar can be BOTH a local high
    (peak) and a local low (valley), so the same bar index appears twice with
    different kinds. Time must never run backwards, but a tie at one bar is real.
    """
    for ticker, df, _s in fixture_structures:
        zz = _zigzag_for(df)
        bars = [p[0] for p in zz]
        for i in range(len(bars) - 1):
            assert bars[i] <= bars[i + 1], (
                f"{ticker}: zigzag bars decreasing at {i}: "
                f"{bars[i]} > {bars[i + 1]}"
            )


def test_segment_swings_alternation_on_ramp(_ramp_frame):
    """On a clean synthetic zig-zag ramp, segment_swings emits alternating-sign
    swings — the well-behaved case the conftest fixture is built for."""
    df = _ramp_frame([100.0, 120.0, 105.0, 130.0, 110.0, 140.0])
    # Synthetic flat-OHLC ramp; ATR is a small positive constant.
    seg = segment_swings(df, atr_val=1.0)
    dirs = [s["direction"] for s in seg.get("swings", [])]
    assert len(dirs) >= 2
    for i in range(len(dirs) - 1):
        assert dirs[i] != dirs[i + 1], f"ramp swings not alternating: {dirs}"


# ── Frozen-config manifest contract ──────────────────────────────────────────
def test_manifest_hash_is_deterministic():
    from engine_alpha.freeze.manifest import manifest_hash

    h1 = manifest_hash()
    h2 = manifest_hash()
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) == 64
    int(h1, 16)  # valid hex


def test_manifest_includes_engine_excludes_ops():
    from engine_alpha.freeze.manifest import collect_manifest

    m = collect_manifest()
    # representative engine constants are present
    for key in ("MAX_BOX_WIDTH", "STRUCTURE_ATR_SAMPLE_OFFSET", "TIER_S_STRUCT",
                "LPS_PULLBACK_PROFILE_MIN", "DAILY_STRUCTURE_PERIOD"):
        assert key in m, f"engine constant {key} missing from manifest"
    # ops / observability knobs are excluded
    for key in ("MARKET_DATA_PROVIDER", "YAHOO_RATE_LIMIT_PER_SEC",
                "ARCHIVE_LIVE_SCANS", "DASHBOARD_CHART_DAYS",
                "SCAN_SCHEDULE_HOUR_ET", "QUARANTINE_ENABLED"):
        assert key not in m, f"ops knob {key} leaked into manifest"


def test_manifest_raises_when_listed_key_vanishes(monkeypatch):
    """The contract must not silently rot: a listed key that no longer exists
    on settings raises, rather than dropping silently from the hash."""
    import engine_alpha.freeze.manifest as mod

    monkeypatch.setattr(
        mod, "ENGINE_SETTINGS_KEYS",
        mod.ENGINE_SETTINGS_KEYS + ("DEFINITELY_NOT_A_SETTING_XYZ",),
    )
    with pytest.raises(KeyError):
        mod.collect_manifest()


def test_manifest_json_is_canonical_sorted():
    """manifest_json is stable, sorted, and round-trips to collect_manifest."""
    import json

    from engine_alpha.freeze.manifest import collect_manifest, manifest_json

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
# move which setups fire / how they score / where phase boundaries land — the
# hashable engine identity — EXCEPT the ops knobs enumerated above.
# core/structure/ is GLOBBED (every module, see _engine_eval_path_sources), not
# hand-listed: a new detector file is covered the day it lands and cannot be
# forgotten here. The scoring/pipeline conductors stay explicit. The Lane-C
# entry modules (scan_context / advisory) DELEGATE their tuning reads to helper
# modules, so those helpers are listed too — else a lookback/lag knob read one
# import-hop away escapes the scan (the engine-α second-pass audit gap, 2026-07-06).
_ENGINE_EVAL_PATH_MODULES = (
    "engine_alpha.scoring.scoring",
    "engine_alpha.scoring.taxonomy",
    "engine_alpha.evaluation",
    "core.pipeline.screening.screener",
    "core.regime.scan_context",
    "core.regime.rs_line",
    "core.regime.sector_ranking",
    "core.fundamentals.advisory",
    "core.fundamentals.metrics",
)


def _engine_eval_path_sources():
    """Source files of the engine eval path: the explicit conductor modules
    plus EVERY ``engine_alpha/structure/**/*.py`` (globbed recursively)."""
    import importlib
    from pathlib import Path

    import engine_alpha.structure

    paths = [Path(importlib.import_module(m).__file__)
             for m in _ENGINE_EVAL_PATH_MODULES]
    structure_files = sorted(Path(engine_alpha.structure.__file__).parent.rglob("*.py"))
    # The detectors live in subpackages; a non-recursive glob once matched only
    # __init__.py and silently emptied this guard. Keep it from going vacuous.
    assert len(structure_files) >= 30, structure_files
    return paths + structure_files


def test_every_scoring_settings_symbol_is_in_manifest():
    """Provenance completeness: EVERY ``settings.NAME`` the engine eval path reads
    must be in ``ENGINE_SETTINGS_KEYS`` and hashed into engine_config_version —
    unless it is one of the explicitly enumerated ops-only exclusions.

    The eval path (scoring + evaluation + screener + ALL of core/structure/) is
    the layer that decides which setups fire, how they score/rank, and where
    phase boundaries land — every score/structure-affecting constant it touches
    changes archived output and MUST bump the manifest hash. This static-source
    scan (over the ``settings.NAME``, ``getattr(settings, "NAME")``, and
    ``_flag("NAME")`` advisory-helper read forms) PLUS a runtime introspection of
    the scoring taxonomy ``REGISTRY`` (each ``TermSpec``'s ``cap_setting`` /
    ``producer`` partition, resolved at call time and invisible to any
    source regex) makes a future score-affecting flag/weight unable to silently
    escape provenance: add a read in any scanned module — or a registry term whose
    cap is read only via ``TermSpec.cap()`` — and this
    fails until the name is either added to the allow-list or declared an ops
    exclusion. (Regression guard for the since-retired CANDLE_SPREAD_AWARE /
    PUZZLE_SCORE_ENABLED / SOS_*_BOX omissions, the Lane-C ``_flag()`` indirection
    seam, and the positional-``TermSpec`` registry seam; the scoring / regime /
    fundamentals eval modules and all of core/structure/ are scanned.)
    """
    import re

    from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS

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
    # The scoring taxonomy resolves each term's point cap + gate flag by settings
    # ATTRIBUTE NAME through getattr at call time (``TermSpec.cap``).
    # ``TermSpec`` is built positionally, so a source regex over the registry cannot
    # see those names; introspect the registry object itself so a term whose cap /
    # flag is read ONLY via the registry (e.g. a future 0-100 normalization divisor)
    # still cannot escape the manifest.
    from engine_alpha.scoring.taxonomy import REGISTRY as _score_registry
    for _term in _score_registry:
        referenced.add(_term.cap_setting)
    assert referenced, "scanner found no settings.<NAME> reads on the eval path"

    # Every read must be either provenance-hashed OR an explicit ops exclusion —
    # nothing may silently fall between the two.
    unaccounted = sorted(referenced - set(ENGINE_SETTINGS_KEYS) - ALLOWED_OPS_EXCLUSIONS)
    assert not unaccounted, (
        "score/structure-affecting settings read by the engine eval path "
        f"({', '.join(_ENGINE_EVAL_PATH_MODULES)} + engine_alpha/structure/**) are absent from "
        "engine_alpha.freeze.manifest.ENGINE_SETTINGS_KEYS (so flipping them would change "
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

    Reads the first backticked NAME token of each row between the "## Dark flags"
    heading and "## Retired", plus the row's last cell (the kill-by date)."""
    import re
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "docs" / "flag_ledger.md"
            ).read_text(encoding="utf-8")
    start = text.index("## Dark flags")
    end = text.index("## Retired", start)
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
