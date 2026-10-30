"""
Negative-corpus precision gate - the junk charts' fire days are PINNED.

Sixteen charts the operator or a documented dissection labeled as junk are frozen
into a committed fixture (``tests/baselines/negative_corpus.parquet`` +
``negative_corpus_meta.json``) and replayed through the reader door
(``engine_alpha.reader.evaluate_ticker``) on every day of the fired-policy window
the marks ratchet grades (``core.calibration.replay.fired_window_walk``: the last
``FIRED_WINDOW_SESSIONS`` trading days ending at the frozen day, every clamp
named). The engine's other guards are one-directional: the shadow fixture
(``tools.regression.shadow_diff``) freezes only PREVIOUSLY-FIRING tickers, and
seed-recall (``core.archive.seed_recall``) can only fail on LOST winners - neither
reds when a change makes junk setups fire universe-wide.

The gate (decision E of the one-reader plan, Sat 31/10/2026): the days each junk
chart fires are pinned in ``tests/baselines/negative_corpus_baseline.json``
(``known_fires`` - every case, a silent chart with an empty list). ``--check``
FAILS on a fire on an UNPINNED day (a new fire day), on the silent chart firing
on any day, on a crash (``EVAL_ERROR``) on any day, and on a frame missing from
the parquet - each one removes a tripwire, so none may pass silently. A pinned
day that no longer fires is NAMED, not failed: good news is still a change to
look at, but the gate's teeth are for new junk fires. Re-pinning is a declared
seam (``--pin-known-fires``, recorded in ``docs/decisions.md`` with the cases
and days), never a routine recapture.

Hermetic: reads the frozen fixture parquet, never the network or the live cache.

Usage:
    python -m tools.regression.negative_corpus --build-fixture   # one-time, from the live data cache
    python -m tools.regression.negative_corpus --check           # fail (exit 1) on a new fire day, a crash, a missing frame
    python -m tools.regression.negative_corpus --pin-known-fires # a declared seam: pin today's fire days as KNOWN
    python -m tools.regression.negative_corpus --drop-case KEY   # a declared seam: a case leaves on the operator's ruling
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

try:  # works under both `python -m tools.regression.negative_corpus` and `python tools/regression/negative_corpus.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path

_PROJECT_ROOT = configure_path()

from config import settings
from engine_alpha.reader import evaluate_ticker as _evaluate_ticker
from engine_alpha.universe_door import apply_baseline_filters
from core.calibration.replay import (
    FIRED_WALK_MAX_SESSIONS,
    FIRED_WINDOW_SESSIONS,
    fired_window_walk,
)

_BASELINE_DIR = os.path.join(_PROJECT_ROOT, "tests", "baselines")
_FIXTURE_PARQUET = os.path.join(_BASELINE_DIR, "negative_corpus.parquet")
_FIXTURE_META = os.path.join(_BASELINE_DIR, "negative_corpus_meta.json")
_BASELINE_JSON = os.path.join(_BASELINE_DIR, "negative_corpus_baseline.json")
_CACHE_PATH = os.path.join(_PROJECT_ROOT, settings.CACHE_FILENAME)

# Frozen market scalar carried in the meta for the replay seam's call shape; the
# alpha reader reads neither it nor the SPY return. Any fixed value keeps the
# replay deterministic.
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
    # CHCT left this list on the operator's ruling of Sun 13/09/2026 ("The setups
    # is valid"), given on the pinned Thu 18/06/2026 window fire; the label was
    # the descent-tail gate's own name for it, never his words. Dropped through
    # ``--drop-case CHCT`` (see ``drop_case``).
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


def _key(case: dict) -> str:
    return case.get("key", case["ticker"])


# ------------------------------------------------------------------
# Check (hermetic; reads only the committed fixture)
# ------------------------------------------------------------------
def _load_fixture() -> tuple[dict[str, pd.DataFrame], dict]:
    if not os.path.exists(_FIXTURE_PARQUET) or not os.path.exists(_FIXTURE_META):
        raise FileNotFoundError(
            "No negative-corpus fixture - run `python -m tools.regression.negative_corpus "
            "--build-fixture` first (requires a populated data cache)."
        )
    data = pd.read_parquet(_FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    with open(_FIXTURE_META, "r", encoding="utf-8") as f:
        meta = json.load(f)
    level0 = set(data.columns.get_level_values(0))
    frames = {_key(c): data[_key(c)].dropna() for c in meta["cases"] if _key(c) in level0}
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
    """The pinned fire days - ``{case key: [ISO days]}`` - captured at a DECLARED
    seam by ``--pin-known-fires`` (first pinned Sun 13/09/2026 for the early-
    window fires of the old reader; re-pinned Sat 31/10/2026 as EVERY fire day of
    the alpha reader, 47 days over 15 charts, GOOD silent). A fire on a pinned
    day is reported as KNOWN and does not fail the gate; a fire on any OTHER
    day, a crash on any day, or a missing frame fails - the gate keeps its teeth
    in the only direction that matters (new junk fires). An absent file means
    nothing is pinned."""
    if not os.path.exists(_BASELINE_JSON):
        return {}
    with open(_BASELINE_JSON, "r", encoding="utf-8") as f:
        return json.load(f).get("known_fires", {})


def _case_walk(case: dict, df: pd.DataFrame, meta: dict) -> dict:
    """One case's window walk through the reader door."""
    return fired_window_walk(case["ticker"], df, float(case["spy_6m_return"]),
                             float(meta["breadth_pct"]), evaluate=_evaluate_ticker)


def walk_corpus() -> tuple[list[dict], dict]:
    """The REAL replay, paid once: ``(cases, {case key: walk | None})`` - None for
    a frame missing from the parquet."""
    frames, meta = _load_fixture()
    walks: dict = {}
    for case in meta["cases"]:
        df = frames.get(_key(case))
        walks[_key(case)] = None if df is None or df.empty else _case_walk(case, df, meta)
    return meta["cases"], walks


def judge(cases: list[dict], walks: dict, known: dict) -> tuple[bool, list[str], list[str]]:
    """The verdict on one replay: ``(ok, failures, notes)``.

    A failure: a frame missing, a crash on any day, a fire on an unpinned day
    (the silent chart firing is one: it has no pinned day). A note: each case's
    walked window, each pinned day that fired (KNOWN) and each pinned day that
    no longer fires (named, never failed)."""
    failures: list[str] = []
    notes: list[str] = []
    ok = bool(cases)
    for case in cases:
        key = _key(case)
        walk = walks.get(key)
        if walk is None:
            ok = False
            failures.append(f"  {key}: frame MISSING from fixture parquet - rebuild the fixture")
            continue
        notes.append(f"  {key}: {_window_line(walk)}")
        if walk["errors"]:
            ok = False
            days = ", ".join(e["day"] for e in walk["errors"])
            failures.append(f"  {key}: EVAL_ERROR on {days} - the eval chain crashed on a corpus "
                            f"frame ({case['label']}); a crash is not a clean rejection")
        pinned = list(known.get(key, []))
        fired = {f["day"] for f in walk["fires"]}
        old_fires = [f for f in walk["fires"] if f["day"] in pinned]
        new_fires = [f for f in walk["fires"] if f["day"] not in pinned]
        quiet = [day for day in pinned if day not in fired]
        if old_fires:
            notes.append(f"  {key}: KNOWN on {_fires_line({'fires': old_fires})}")
        if quiet:
            notes.append(f"  {key}: no longer fires on {', '.join(quiet)} - a pinned day went quiet; "
                         "look, then re-pin deliberately (--pin-known-fires)")
        if new_fires:
            ok = False
            failures.append(
                f"  {key}: FIRES on {_fires_line({'fires': new_fires})} - "
                f"labeled must-NOT-fire: {case['label']} [{case['evidence']}]"
            )
    return ok, failures, notes


def check_corpus() -> bool:
    """Replay every frozen junk frame through the reader door on the fired-policy
    window and judge it against the pinned fire days (``load_known_fires``).

    Returns True iff every case fires on pinned days only - a fire on an
    unpinned day, a crash on any day, or a missing frame fails. Pinned fires
    are printed as KNOWN and pinned days that went quiet are named, so neither
    is ever invisible.
    """
    cases, walks = walk_corpus()
    ok, failures, notes = judge(cases, walks, load_known_fires())

    print("=" * 64)
    print("  NEGATIVE-CORPUS PRECISION GUARD - the junk charts' fire days, pinned")
    print("=" * 64)
    print(f"fired-policy window: the last {FIRED_WINDOW_SESSIONS} trading days ending at "
          f"each frozen day (the marks ratchet's window); a fire on any UNPINNED day fails.")
    for line in notes:
        print(line)
    print()
    if ok:
        pinned_days = sum(len(v) for v in load_known_fires().values())
        print(f"all {len(cases)} labeled junk cases fire on their pinned days only "
              f"({pinned_days} pinned days); no new fire day, no crash.")
        print("PASS - precision held.")
    else:
        for line in failures:
            print(line)
        print()
        print("FAIL - a labeled must-NOT-fire case fires on a new day, crashed, or is missing.")
        print("If the fire is INTENDED (a deliberate reading change re-storied this chart),")
        print("re-eyeball the case, then pin it deliberately (--pin-known-fires, recorded in")
        print("docs/decisions.md) - never re-capture wholesale.")
    return ok


def pin_known_fires() -> dict:
    """Pin the CURRENT fire days of every case as KNOWN - a declared seam, never a
    routine recapture (record it in ``docs/decisions.md`` with the cases and
    days). Walks every case on the window with the real reader and writes
    ``{case key: [days]}`` for EVERY case, a silent one with an empty list, so
    the baseline says of each chart what it does. Refuses on any EVAL_ERROR and
    on a missing frame."""
    cases, walks = walk_corpus()
    known: dict[str, list[str]] = {}
    problems: list[str] = []
    for case in cases:
        key = _key(case)
        walk = walks[key]
        if walk is None:
            problems.append(f"{key}: frame MISSING from fixture parquet")
            continue
        if walk["errors"]:
            problems.append(f"{key}: EVAL_ERROR on " + ", ".join(e["day"] for e in walk["errors"]))
        known[key] = [f["day"] for f in walk["fires"]]
        print(f"  {key}: " + (f"pinned {_fires_line(walk)}" if walk["fires"] else "silent"))
    if problems:
        raise RuntimeError("Refusing to pin known fires:\n  " + "\n  ".join(problems))
    from engine_alpha.freeze.manifest import manifest_hash

    out = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine_config_version": manifest_hash(),
        "fired_policy": {"window_sessions": FIRED_WINDOW_SESSIONS,
                         "max_walk_sessions": FIRED_WALK_MAX_SESSIONS},
        "note": ("The fire days of the labeled junk charts under the reader of the capture day, every case, "
                 "pinned so the gate reds only on a NEW fire day (or a crash, or a missing frame); a silent "
                 "chart carries an empty list."),
        "known_fires": known,
    }
    os.makedirs(_BASELINE_DIR, exist_ok=True)
    # newline="\n": tests/baselines/*.json is .gitattributes-pinned to LF.
    with open(_BASELINE_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2)
    days = sum(len(v) for v in known.values())
    print(f"Pinned {days} fire days over {sum(1 for v in known.values() if v)} of {len(cases)} cases -> {_BASELINE_JSON}")
    return out


def drop_case(key: str) -> dict:
    """A case leaves the sealed fixture on the operator's ruling that the chart
    is NOT junk - the declared seam for a population change (``--drop-case``,
    first used for CHCT on Sun 13/09/2026: "The setups is valid", ruled on its
    pinned Thu 18/06/2026 window fire). A hand edit of the parquet leaves no
    trail, so this drops the frame's columns, the meta row and any pinned fire
    days TOGETHER and prints what left. Refuses when the key is still in
    ``CASES`` (the recipe and the fixture must agree: remove it from the recipe
    first, naming the ruling) or is not in the sealed meta."""
    if any(_key(c) == key for c in CASES):
        raise RuntimeError(f"Refusing to drop {key}: still in the build recipe (CASES) - "
                           "remove it there first, naming the ruling")
    if not os.path.exists(_FIXTURE_PARQUET) or not os.path.exists(_FIXTURE_META):
        raise FileNotFoundError("No negative-corpus fixture to drop a case from")
    with open(_FIXTURE_META, "r", encoding="utf-8") as f:
        meta = json.load(f)
    keys = [_key(c) for c in meta["cases"]]
    if key not in keys:
        raise RuntimeError(f"Refusing to drop {key}: not in the sealed fixture ({len(keys)} cases)")
    data = pd.read_parquet(_FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    if key in set(data.columns.get_level_values(0)):
        data = data.drop(columns=key, level=0)
    data.to_parquet(_FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    meta["cases"] = [c for c in meta["cases"] if _key(c) != key]
    with open(_FIXTURE_META, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=2)
    pins_dropped: list = []
    if os.path.exists(_BASELINE_JSON):
        with open(_BASELINE_JSON, "r", encoding="utf-8") as f:
            pins = json.load(f)
        if key in pins.get("known_fires", {}):
            pins_dropped = pins["known_fires"].pop(key)
            with open(_BASELINE_JSON, "w", encoding="utf-8", newline="\n") as f:
                json.dump(pins, f, indent=2)
    print(f"Dropped {key} from the negative corpus: {len(meta['cases'])} cases remain; "
          f"pinned fire days removed: {pins_dropped or 'none'}. Record the ruling in docs/decisions.md.")
    return {"dropped": key, "cases": len(meta["cases"]), "pins_dropped": pins_dropped}


# ------------------------------------------------------------------
# Fixture build (one-time; reads the live data cache, writes frozen files)
# ------------------------------------------------------------------
def build_fixture(cache_path: str = _CACHE_PATH) -> dict:
    """Freeze the labeled corpus from the live data cache.

    Refuses to freeze a case the reader CRASHES on on any day of its
    fired-policy window. A case that fires is frozen and its fire days are
    printed: they are pinned afterwards by ``--pin-known-fires`` (the gate
    pins fire days, it no longer demands silence). Records each case's walked
    window and the window policy it was read under, and whether each frame
    passes the baseline filters: a case should be judged on STRUCTURE, not on
    the universe gate.
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
        key = _key(case)
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
        print(f"  {key}: " + (f"fires on {_fires_line(walk)}" if walk["fires"] else "silent")
              + f" ({_window_line(walk)})")

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
        # The engine the cases were frozen under: stamped at every rebuild so
        # junk evidence is cohortable.
        "engine_config_version": manifest_hash(),
        # The window policy every case was read under - the replay seam's
        # constants, never re-typed here.
        "fired_policy": {"window_sessions": FIRED_WINDOW_SESSIONS,
                         "max_walk_sessions": FIRED_WALK_MAX_SESSIONS},
        "cases": meta_cases,
    }
    with open(_FIXTURE_META, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=2)

    print(f"Built negative corpus: {len(meta_cases)} labeled junk cases -> {_FIXTURE_PARQUET}")
    baseline_passing = sum(1 for c in meta_cases if c["baseline_pass_at_freeze"])
    print(f"  {baseline_passing}/{len(meta_cases)} pass baseline at freeze (live structural tripwires)")
    print("  now pin the fire days: python -m tools.regression.negative_corpus --pin-known-fires")
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
                       help="Pin the current fire days of every case as KNOWN (a declared seam; record it in decisions.md)")
    group.add_argument("--drop-case", metavar="KEY",
                       help="Drop one case from the sealed fixture on the operator's ruling (a declared seam; "
                            "remove it from CASES first and record the ruling in decisions.md)")
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
        elif args.drop_case is not None:
            drop_case(args.drop_case)
    except (FileNotFoundError, RuntimeError) as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
