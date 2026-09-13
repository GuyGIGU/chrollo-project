"""
Negative-corpus precision gate - proves labeled must-NOT-fire charts STAY
non-firing.

The engine's other guards are one-directional: the shadow fixture
(``tools.shadow_diff``) freezes only PREVIOUSLY-FIRING tickers, and seed-recall
(``core.archive.seed_recall``) can only fail on LOST winners - neither reds when
a change makes junk setups fire universe-wide. This guard closes that gap for
the prime directive (accurate detection of visually TIGHT structure): it
freezes OHLCV for operator/dissection-labeled must-NOT-fire cases into a
committed fixture and fails when ANY of them starts firing.

Each case carries its label (the documented junk class) and evidence pointer,
and is verified non-firing against the live engine AT FREEZE TIME -
``--build-fixture`` refuses to freeze a case the current engine fires on. Both
the build refusal and ``--check`` grade the SAME fired-policy WINDOW the marks
ratchet grades (``tools.replay.fired_window_walk``: the last
``FIRED_WINDOW_SESSIONS`` trading days ending at the frozen day, every clamp
named): a junk chart that fires on ANY day of that window fails. One day per
frame was blind to a fire that moves a day earlier or later (final method,
build step 1, operator ruling 2026-09-13). Cases
whose junk structure has scrolled out of the live 2y read window are frozen
with an ``as_of`` trim back to their dissection era, chosen so the frame PASSES
the baseline universe filters and rejects on STRUCTURE - a case that fails
baseline would be dead weight (it could never fire regardless of detector
code and would guard nothing).

An EVAL_ERROR on a corpus frame FAILS the gate (unlike the shadow guard, which
drops it): the corpus documents "the engine cleanly rejects this junk", and a
crash is neither a rejection nor a fire - it silently removes the tripwire.

Hermetic: reads the frozen fixture parquet, never the network or the live cache.

Usage:
    python -m tools.negative_corpus --build-fixture   # one-time, from the live data cache
    python -m tools.negative_corpus --check           # fail (exit 1) if any case fires on an unpinned window day
    python -m tools.negative_corpus --pin-known-fires # a declared seam: pin today's early-window fires as KNOWN
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

try:  # works under both `python -m tools.negative_corpus` and `python tools/negative_corpus.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path()

from config import settings
from engine_alpha.evaluation import apply_baseline_filters
from core.pipeline.screener import _evaluate_ticker
from tools.replay import (
    FIRED_WALK_MAX_SESSIONS,
    FIRED_WINDOW_SESSIONS,
    fired_window_walk,
)

_BASELINE_DIR = os.path.join(_PROJECT_ROOT, "tests", "baselines")
_FIXTURE_PARQUET = os.path.join(_BASELINE_DIR, "negative_corpus.parquet")
_FIXTURE_META = os.path.join(_BASELINE_DIR, "negative_corpus_meta.json")
_BASELINE_JSON = os.path.join(_BASELINE_DIR, "negative_corpus_baseline.json")
_CACHE_PATH = os.path.join(_PROJECT_ROOT, settings.CACHE_FILENAME)

# Frozen market scalar for the breadth bonus - scoring-only, never a firing
# decision; any fixed value keeps the replay deterministic.
_FROZEN_BREADTH = 0.5

# ─────────────────────────────────────────────────────────────────────────────
# The labeled corpus (the build recipe). Each case is a chart the operator or a
# documented dissection labeled as junk the screener must NOT surface.
#   as_of: None = freeze the frame as-is; else trim to this end date so the
#          junk structure is in-window AND the frame passes baseline (verified
#          at build - see module docstring).
#   label: the junk class; evidence: where the labeling is documented.
# Verified non-firing + baseline-passing on the live engine 2026-07-03
# (as-traded cache of 2026-07-02). Dropped from the candidate list: DBD at the
# live edge (fires legitimately on a NEWER base - frozen at its dissection era
# instead) and WDI (fails baseline at every probed as-traded date - dead weight).
# ─────────────────────────────────────────────────────────────────────────────
CASES: tuple[dict, ...] = (
    # Descent-tail dead-space: support rail abandoned early, coil in dead space
    # above it (config/settings.py DESCENT_TAIL_* rationale, validated 2026-06-19).
    {"ticker": "CHCT", "as_of": None,
     "label": "descent-tail dead-space",
     "evidence": "settings.DESCENT_TAIL_GATE_ENABLED comment; operator dissection 2026-06-19"},
    {"ticker": "DGII", "as_of": None,
     "label": "descent-tail dead-space",
     "evidence": "settings.DESCENT_TAIL_GATE_ENABLED comment; operator dissection 2026-06-19"},
    # Limb-traversal dead-space: wide box whose swings never travel rail-to-rail
    # (settings.TRAVERSAL_MIN_DENSITY rationale: BMRN 5/111 = 0.045, 2026-06-15).
    {"ticker": "BMRN", "as_of": None,
     "label": "limb-traversal dead-space",
     "evidence": "settings.TRAVERSAL_MIN_DENSITY comment (BMRN density 0.045); 2026-06-15"},
    {"ticker": "FRPH", "as_of": None,
     "label": "limb-traversal dead-space",
     "evidence": "settings.TRAVERSAL_MIN_DENSITY rationale; ranking-A dissection 2026-06-15"},
    # Rescue-markup run-ups: vertical launches off support elected as "LPS" via
    # the rising_support_shelf rescue (settings.LPS_RESCUE_MAX_ADVANCE_BOX
    # rationale, validated 2026-06-26; SPCB is the documented borderline).
    {"ticker": "OHI", "as_of": None,
     "label": "rescue-markup run-up",
     "evidence": "settings.LPS_RESCUE_MAX_ADVANCE_BOX comment (OHI +6.6% launch, 2026-06)"},
    {"ticker": "AEF", "as_of": "2026-06-12",
     "label": "rescue-markup run-up",
     "evidence": "settings.LPS_RESCUE_MAX_ADVANCE_BOX comment (OHI/AEF/NVT/SPCB drop set)"},
    # NVT left this list on the operator's ruling of Thu 10/09/2026 ("correct but would grade low"): a correct low-grade fire is not junk.
    {"ticker": "SPCB", "as_of": None,
     "label": "wide/volatile spread",
     "evidence": "settings.LPS_RESCUE_MAX_ADVANCE_BOX comment (lone borderline to eyeball); operator ruling 2026-07-17 (spread/width/volatility/volume)"},
    # Change-C reject set, relabeled to the operator's dictated honest reasons
    # (2026-07-17 rulings; "dead-space" is reserved for the rail-placement
    # diagnostic, never a junk-chart catch-all).
    {"ticker": "KWR", "as_of": None,
     "label": "no valid setup at the frame",
     "evidence": "docs/segmentation_research.md Change C (DBD/RLGT/KWR/FLG reject); operator ruling 2026-07-17"},
    {"ticker": "DBD", "as_of": "2026-06-07",
     "label": "mis-framed range - rails no longer in force",
     "evidence": "docs/segmentation_research.md Change C; trimmed to era (fires on a NEWER base at the 2026-07 live edge); operator ruling 2026-07-17"},
    {"ticker": "RLGT", "as_of": None,
     "label": "trend-continuation, not a base",
     "evidence": "docs/segmentation_research.md Change C (DBD/RLGT/KWR/FLG reject); operator ruling 2026-07-17"},
    {"ticker": "FLG", "as_of": None,
     "label": "trend-continuation dips, not a base",
     "evidence": "docs/segmentation_research.md Change C (DBD/RLGT/KWR/FLG reject); operator ruling 2026-07-17"},
    {"ticker": "BBVA", "as_of": None,
     "label": "worked-equilibrium dead-space (Change C demotion set)",
     "evidence": "docs/segmentation_research.md Change C (BBVA/ABEV/COLM -> A)"},
    {"ticker": "ABEV", "as_of": "2026-06-15",
     "label": "worked-equilibrium dead-space (Change C demotion set)",
     "evidence": "docs/segmentation_research.md Change C; fired B at 2026-05-15, rejects from 2026-06-15 on as-traded data"},
    {"ticker": "COLM", "as_of": None,
     "label": "worked-equilibrium dead-space (Change C demotion set)",
     "evidence": "docs/segmentation_research.md Change C (BBVA/ABEV/COLM -> A)"},
    # Dividend-adjustment artifacts: income names whose fires existed only on
    # the dividend-adjusted series (as-traded cutover, commit 3b4c808).
    {"ticker": "GOOD", "as_of": None,
     "label": "dividend-adjustment artifact",
     "evidence": "as-traded price cutover 3b4c808 (passed baseline only on adjusted data)"},
    {"ticker": "ENIC", "as_of": None,
     "label": "dividend-adjustment artifact",
     "evidence": "as-traded price cutover 3b4c808 (passed baseline only on adjusted data)"},
    # Incomplete throwback (the OVERSHOOT_R rescope admission class): an LPS
    # shelf above R claims the cause below is COMPLETE, but the base barely
    # existed — 20-bar minimum, 2 full traversals (vs CTOS's 50-bar,
    # 10-traversal cause). Operator eyeball on the full-package render
    # 2026-07-17: "BBVA is just incomplete... nothing really going on".
    # Frozen from the shadow-fixture frame the rescope fired on (edge
    # 2026-06-05); ``key`` disambiguates from the Change-C BBVA case above.
    {"ticker": "BBVA", "key": "BBVA@2026-06-05", "as_of": "2026-06-05",
     "label": "incomplete throwback (immature 20-bar cause)",
     "evidence": "operator eyeball 2026-07-17; solve-the-engine flip #3 shadow admission; matured-cause floor in lps.py rescope"},
)


# ------------------------------------------------------------------
# Check (hermetic; reads only the committed fixture)
# ------------------------------------------------------------------
def _load_fixture() -> tuple[dict[str, pd.DataFrame], dict]:
    if not os.path.exists(_FIXTURE_PARQUET) or not os.path.exists(_FIXTURE_META):
        raise FileNotFoundError(
            "No negative-corpus fixture - run `python -m tools.negative_corpus "
            "--build-fixture` first (requires a populated data cache)."
        )
    data = pd.read_parquet(_FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    with open(_FIXTURE_META, "r", encoding="utf-8") as f:
        meta = json.load(f)
    level0 = set(data.columns.get_level_values(0))
    frames = {c.get("key", c["ticker"]): data[c.get("key", c["ticker"])].dropna()
              for c in meta["cases"] if c.get("key", c["ticker"]) in level0}
    return frames, meta


def _fires_line(walk: dict) -> str:
    """Every fire day of one window walk, with score and tier."""
    return ", ".join(
        f"{f['day']} (score={float(f['result'].get('Score') or 0):.1f}, tier={f['result'].get('Tier')})"
        for f in walk["fires"])


def _window_line(walk: dict) -> str:
    first, last = walk["window"] if walk["window"] else ("?", "?")
    note = f"; clamp: {walk['clamp_note']}" if walk["clamp_note"] else ""
    return f"window {first} .. {last}, {walk.get('evaluated', '?')} days evaluated{note}"


def load_known_fires() -> dict:
    """The pinned early-window fires - ``{case key: [ISO days]}`` - captured at
    a DECLARED seam by ``--pin-known-fires`` (first pinned Sun 13/09/2026, build
    step 1 of the final method: 9 of 17 cases fired on an earlier day of their
    window under the engine of that day, none on the frozen day; those days are
    the operator's-eye queue, recorded in ``docs/decisions.md``). A fire on a
    pinned day is reported as KNOWN and does not fail the gate; a fire on any
    OTHER day, a crash on any day, or a missing frame still fails - the gate
    keeps its teeth in the only direction that matters (new junk fires). An
    absent file means nothing is pinned."""
    if not os.path.exists(_BASELINE_JSON):
        return {}
    with open(_BASELINE_JSON, "r", encoding="utf-8") as f:
        return json.load(f).get("known_fires", {})


def _case_walk(case: dict, df: pd.DataFrame, meta: dict, frozen_day_only: bool) -> dict:
    """One case's window walk; with ``frozen_day_only`` only the frame's final
    day is kept (the pre-2026-09-13 one-day read, still used for the dark
    flag-ON replays whose junk exposure is graded on the frozen day)."""
    walk = fired_window_walk(case["ticker"], df, float(case["spy_6m_return"]),
                             float(meta["breadth_pct"]), evaluate=_evaluate_ticker)
    if frozen_day_only:
        final_day = df.index[-1].date().isoformat()
        walk["fires"] = [f for f in walk["fires"] if f["day"] == final_day]
        walk["errors"] = [e for e in walk["errors"] if e["day"] == final_day]
    return walk


def check_corpus(*, frozen_day_only: bool = False) -> bool:
    """Replay every frozen must-NOT-fire frame through the real pipeline on
    the fired-policy window (``tools.replay.fired_window_walk``).

    Returns True iff every case still cleanly rejects on EVERY day of its
    window that is not a pinned KNOWN fire day (``load_known_fires``). A case
    that FIRES on an unpinned day, a case whose eval CRASHES (EVAL_ERROR) on
    any day, and a case whose frame is missing from the parquet all fail -
    each removes a tripwire, so none may pass silently. Pinned fires are
    printed as KNOWN so they are never invisible. The report names each
    case's walked window and any clamp. ``frozen_day_only`` grades the
    frame's final day alone with no pins (the dark flag-ON replays).
    """
    frames, meta = _load_fixture()
    cases = meta["cases"]
    known = {} if frozen_day_only else load_known_fires()

    lines: list[str] = []
    windows: list[str] = []
    known_lines: list[str] = []
    ok = True
    if not cases:
        return False

    for case in cases:
        ticker = case["ticker"]
        key = case.get("key", ticker)
        df = frames.get(key)
        if df is None or df.empty:
            ok = False
            lines.append(f"  {key}: frame MISSING from fixture parquet - rebuild the fixture")
            continue
        walk = _case_walk(case, df, meta, frozen_day_only)
        windows.append(f"  {key}: {_window_line(walk)}")
        if walk["errors"]:
            ok = False
            days = ", ".join(e["day"] for e in walk["errors"])
            lines.append(f"  {key}: EVAL_ERROR on {days} - the eval chain crashed on a corpus "
                         f"frame ({case['label']}); a crash is not a clean rejection")
        pinned = set(known.get(key, []))
        old_fires = [f for f in walk["fires"] if f["day"] in pinned]
        new_fires = [f for f in walk["fires"] if f["day"] not in pinned]
        if old_fires:
            known_lines.append(f"  {key}: KNOWN on {_fires_line({'fires': old_fires})} - "
                               "pinned, awaiting the operator's eye")
        if new_fires:
            ok = False
            lines.append(
                f"  {key}: FIRES on {_fires_line({'fires': new_fires})} - "
                f"labeled must-NOT-fire: {case['label']} [{case['evidence']}]"
            )

    print("=" * 64)
    print("  NEGATIVE-CORPUS PRECISION GUARD - must-NOT-fire cases")
    print("=" * 64)
    if frozen_day_only:
        print("frozen day only: each case graded on its frame's final day (no pins).")
    else:
        print(f"fired-policy window: the last {FIRED_WINDOW_SESSIONS} trading days ending at "
              f"each frozen day (the marks ratchet's window); a fire on any UNPINNED day fails.")
    for line in windows:
        print(line)
    if known_lines:
        print(f"known early-window fires, pinned by --pin-known-fires ({len(known_lines)} cases):")
        for line in known_lines:
            print(line)
    print()
    if ok:
        print(f"all {len(cases)} labeled junk cases still cleanly reject on every "
              f"{'frozen day' if frozen_day_only else 'unpinned window day'}.")
        print("PASS - precision held.")
    else:
        for line in lines:
            print(line)
        print()
        print("FAIL - a labeled must-NOT-fire case no longer cleanly rejects.")
        print("If the fire is INTENDED (a deliberate recall change re-storied this")
        print("chart), re-eyeball the case, then remove/re-freeze it deliberately -")
        print("never re-capture wholesale.")
    return ok


def pin_known_fires() -> dict:
    """Pin the CURRENT early-window fires as KNOWN - a declared seam, never a
    routine recapture (record it in ``docs/decisions.md`` with the cases and
    days). Walks every case on the window with the real engine and writes
    ``{case key: [days]}`` for the cases that fire. Refuses on any EVAL_ERROR
    and on a fire on a case's FINAL day (that day is the fixture's own
    verified-non-firing premise; such a case must be re-eyeballed and
    removed or re-frozen instead)."""
    frames, meta = _load_fixture()
    known: dict[str, list[str]] = {}
    problems: list[str] = []
    for case in meta["cases"]:
        key = case.get("key", case["ticker"])
        df = frames.get(key)
        if df is None or df.empty:
            problems.append(f"{key}: frame MISSING from fixture parquet")
            continue
        walk = _case_walk(case, df, meta, frozen_day_only=False)
        final_day = df.index[-1].date().isoformat()
        if walk["errors"]:
            problems.append(f"{key}: EVAL_ERROR on " + ", ".join(e["day"] for e in walk["errors"]))
        if any(f["day"] == final_day for f in walk["fires"]):
            problems.append(f"{key}: FIRES on its frozen day {final_day} - not pinnable, re-eyeball it")
        early = [f for f in walk["fires"] if f["day"] != final_day]
        if early:
            known[key] = [f["day"] for f in early]
            print(f"  {key}: pinned {_fires_line({'fires': early})}")
    if problems:
        raise RuntimeError("Refusing to pin known fires:\n  " + "\n  ".join(problems))
    from engine_alpha.freeze.manifest import manifest_hash

    out = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine_config_version": manifest_hash(),
        "fired_policy": {"window_sessions": FIRED_WINDOW_SESSIONS,
                         "max_walk_sessions": FIRED_WALK_MAX_SESSIONS},
        "note": ("Early-window fires of labeled junk under the engine of the capture day, pinned so "
                 "the gate reds only on NEW fire days; each pinned day awaits the operator's eye."),
        "known_fires": known,
    }
    os.makedirs(_BASELINE_DIR, exist_ok=True)
    with open(_BASELINE_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Pinned known early-window fires for {len(known)} of {len(meta['cases'])} cases -> {_BASELINE_JSON}")
    return out


# ------------------------------------------------------------------
# Fixture build (one-time; reads the live data cache, writes frozen files)
# ------------------------------------------------------------------
def build_fixture(cache_path: str = _CACHE_PATH) -> dict:
    """Freeze the labeled corpus from the live data cache.

    Refuses to freeze a case the current engine FIRES on (or crashes on) on
    ANY day of its fired-policy window - the gate's premise is that every
    frozen frame is verified non-firing across the window the check grades.
    Records each case's walked window and the window policy it was verified
    under. Also records whether each frame passes the baseline filters: a
    case should reject on STRUCTURE, not on the universe gate.
    """
    if not os.path.exists(cache_path):
        raise FileNotFoundError(
            f"Data cache not found at {cache_path} - run a real scan first "
            "(`python run_screener.py`) so the parquet exists."
        )
    data = pd.read_parquet(cache_path, engine=settings.PARQUET_ENGINE)
    level0 = set(data.columns.get_level_values(0))
    spy_close = data[settings.SPY_SYMBOL]["Close"].dropna()

    frames: dict[str, pd.DataFrame] = {}
    meta_cases: list[dict] = []
    problems: list[str] = []
    for case in CASES:
        ticker, as_of = case["ticker"], case["as_of"]
        key = case.get("key", ticker)
        if key in frames:
            problems.append(f"{key}: duplicated in CASES")
            continue
        if ticker not in level0:
            problems.append(f"{ticker}: not in the data cache")
            continue
        df = data[ticker].dropna()
        spy = spy_close
        if as_of:
            df = df.loc[:as_of]
            spy = spy_close.loc[:as_of]
        if len(df) < 200:
            problems.append(f"{ticker}: only {len(df)} bars at as_of={as_of}")
            continue
        spy_6m = float(spy.iloc[-1] / spy.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0)

        walk = fired_window_walk(ticker, df, spy_6m, _FROZEN_BREADTH,
                                 evaluate=_evaluate_ticker)
        if walk["errors"]:
            days = ", ".join(e["day"] for e in walk["errors"])
            problems.append(f"{ticker}: EVAL_ERROR on {days} ({_window_line(walk)}) - "
                            "cannot freeze a crashing frame")
            continue
        if walk["fires"]:
            problems.append(
                f"{ticker}: FIRES on {_fires_line(walk)} ({_window_line(walk)}) - "
                "not freezable as a must-NOT-fire case"
            )
            continue

        baseline_pass = apply_baseline_filters(df) is not None
        if not baseline_pass:
            # Freezable but weak: it can never fire regardless of detector code.
            print(f"  WARNING {ticker}: fails baseline at as_of={as_of} - guards nothing "
                  "structural; pick an as_of where baseline passes.")
        frames[key] = df
        entry = {
            "ticker": ticker,
            "as_of": df.index[-1].date().isoformat(),
            "bars": len(df),
            "spy_6m_return": spy_6m,
            "baseline_pass_at_freeze": baseline_pass,
            "window": walk["window"],
            "label": case["label"],
            "evidence": case["evidence"],
        }
        if key != ticker:
            entry["key"] = key
        meta_cases.append(entry)

    if problems:
        raise RuntimeError(
            "Refusing to freeze the negative corpus - unresolved cases:\n  "
            + "\n  ".join(problems)
        )

    os.makedirs(_BASELINE_DIR, exist_ok=True)
    combined = pd.concat(frames, axis=1)  # MultiIndex columns: (ticker, field)
    combined.to_parquet(_FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    from engine_alpha.freeze.manifest import manifest_hash

    meta = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "breadth_pct": _FROZEN_BREADTH,
        # The engine the cases were verified non-firing against (Rail Program
        # Task 2): stamped at every rebuild so junk evidence is cohortable.
        "engine_config_version": manifest_hash(),
        # The window policy every case was verified non-firing under - the
        # replay seam's constants, never re-typed here.
        "fired_policy": {"window_sessions": FIRED_WINDOW_SESSIONS,
                         "max_walk_sessions": FIRED_WALK_MAX_SESSIONS},
        "cases": meta_cases,
    }
    with open(_FIXTURE_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"Built negative corpus: {len(meta_cases)} verified must-NOT-fire cases -> {_FIXTURE_PARQUET}")
    baseline_passing = sum(1 for c in meta_cases if c["baseline_pass_at_freeze"])
    print(f"  {baseline_passing}/{len(meta_cases)} pass baseline at freeze (live structural tripwires)")
    return meta


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Negative-corpus precision guard for the screener.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--build-fixture", action="store_true",
                       help="Freeze the labeled must-NOT-fire cases from the live data cache")
    group.add_argument("--check", action="store_true",
                       help="Fail (exit 1) if any frozen case fires on an unpinned window day or crashes")
    group.add_argument("--pin-known-fires", action="store_true",
                       help="Pin the current early-window fires as KNOWN (a declared seam; record it in decisions.md)")
    ap.add_argument("--cache", default=_CACHE_PATH,
                    help="Path to the market data cache parquet (build only)")
    args = ap.parse_args()

    try:
        if args.build_fixture:
            build_fixture(cache_path=args.cache)
        elif args.check:
            sys.exit(0 if check_corpus() else 1)
        elif args.pin_known_fires:
            pin_known_fires()
    except (FileNotFoundError, RuntimeError) as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
