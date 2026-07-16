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
``--build-fixture`` refuses to freeze a case the current engine fires on. Cases
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
    python -m tools.negative_corpus --check           # fail (exit 1) if any case fires
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
from engine_alpha.evaluation import EVAL_ERROR, apply_baseline_filters
from core.pipeline.screener import _evaluate_ticker

_BASELINE_DIR = os.path.join(_PROJECT_ROOT, "tests", "baselines")
_FIXTURE_PARQUET = os.path.join(_BASELINE_DIR, "negative_corpus.parquet")
_FIXTURE_META = os.path.join(_BASELINE_DIR, "negative_corpus_meta.json")
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
    {"ticker": "NVT", "as_of": "2026-06-26",
     "label": "rescue-markup run-up",
     "evidence": "settings.LPS_RESCUE_MAX_ADVANCE_BOX comment (OHI/AEF/NVT/SPCB drop set)"},
    {"ticker": "SPCB", "as_of": None,
     "label": "rescue-markup run-up (borderline +0.234)",
     "evidence": "settings.LPS_RESCUE_MAX_ADVANCE_BOX comment (lone borderline to eyeball)"},
    # Worked-equilibrium dead-space: the pre-Change-C S/A fires on wide,
    # dead-space or mid-churn boxes (docs/segmentation_research.md, Change C).
    {"ticker": "KWR", "as_of": None,
     "label": "worked-equilibrium dead-space",
     "evidence": "docs/segmentation_research.md Change C (DBD/RLGT/KWR/FLG reject)"},
    {"ticker": "DBD", "as_of": "2026-06-07",
     "label": "worked-equilibrium dead-space",
     "evidence": "docs/segmentation_research.md Change C; trimmed to era (fires on a NEWER base at the 2026-07 live edge)"},
    {"ticker": "RLGT", "as_of": None,
     "label": "worked-equilibrium dead-space",
     "evidence": "docs/segmentation_research.md Change C (DBD/RLGT/KWR/FLG reject)"},
    {"ticker": "FLG", "as_of": None,
     "label": "worked-equilibrium dead-space",
     "evidence": "docs/segmentation_research.md Change C (DBD/RLGT/KWR/FLG reject)"},
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
    frames = {c["ticker"]: data[c["ticker"]].dropna()
              for c in meta["cases"] if c["ticker"] in level0}
    return frames, meta


def check_corpus() -> bool:
    """Replay every frozen must-NOT-fire frame through the real pipeline.

    Returns True iff every case still cleanly rejects. A case that FIRES, a
    case whose eval CRASHES (EVAL_ERROR), and a case whose frame is missing
    from the parquet all fail - each removes a tripwire, so none may pass
    silently.
    """
    frames, meta = _load_fixture()
    cases = meta["cases"]

    lines: list[str] = []
    ok = True
    if not cases:
        return False

    for case in cases:
        ticker = case["ticker"]
        df = frames.get(ticker)
        if df is None or df.empty:
            ok = False
            lines.append(f"  {ticker}: frame MISSING from fixture parquet - rebuild the fixture")
            continue
        result = _evaluate_ticker(ticker, df, float(case["spy_6m_return"]),
                                  float(meta["breadth_pct"]))
        if result is EVAL_ERROR:
            ok = False
            lines.append(f"  {ticker}: EVAL_ERROR - the eval chain crashed on a corpus frame "
                         f"({case['label']}); a crash is not a clean rejection")
        elif result is not None:
            ok = False
            lines.append(
                f"  {ticker}: FIRES (score={result.get('Score')}, tier={result.get('Tier')}) - "
                f"labeled must-NOT-fire: {case['label']} [{case['evidence']}]"
            )

    print("=" * 64)
    print("  NEGATIVE-CORPUS PRECISION GUARD - must-NOT-fire cases")
    print("=" * 64)
    if ok:
        print(f"all {len(cases)} labeled junk cases still cleanly reject.")
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


# ------------------------------------------------------------------
# Fixture build (one-time; reads the live data cache, writes frozen files)
# ------------------------------------------------------------------
def build_fixture(cache_path: str = _CACHE_PATH) -> dict:
    """Freeze the labeled corpus from the live data cache.

    Refuses to freeze a case the current engine FIRES on (or crashes on) - the
    gate's premise is that every frozen frame is verified non-firing at freeze
    time. Also records whether each frame passes the baseline filters: a case
    should reject on STRUCTURE, not on the universe gate.
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
        if ticker in frames:
            problems.append(f"{ticker}: duplicated in CASES")
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

        result = _evaluate_ticker(ticker, df, spy_6m, _FROZEN_BREADTH)
        if result is EVAL_ERROR:
            problems.append(f"{ticker}: EVAL_ERROR at as_of={as_of} - cannot freeze a crashing frame")
            continue
        if result is not None:
            problems.append(
                f"{ticker}: FIRES at as_of={as_of} (score={result.get('Score')}, "
                f"tier={result.get('Tier')}) - not freezable as a must-NOT-fire case"
            )
            continue

        baseline_pass = apply_baseline_filters(df) is not None
        if not baseline_pass:
            # Freezable but weak: it can never fire regardless of detector code.
            print(f"  WARNING {ticker}: fails baseline at as_of={as_of} - guards nothing "
                  "structural; pick an as_of where baseline passes.")
        frames[ticker] = df
        meta_cases.append({
            "ticker": ticker,
            "as_of": df.index[-1].date().isoformat(),
            "bars": len(df),
            "spy_6m_return": spy_6m,
            "baseline_pass_at_freeze": baseline_pass,
            "label": case["label"],
            "evidence": case["evidence"],
        })

    if problems:
        raise RuntimeError(
            "Refusing to freeze the negative corpus - unresolved cases:\n  "
            + "\n  ".join(problems)
        )

    os.makedirs(_BASELINE_DIR, exist_ok=True)
    combined = pd.concat(frames, axis=1)  # MultiIndex columns: (ticker, field)
    combined.to_parquet(_FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    meta = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "breadth_pct": _FROZEN_BREADTH,
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
                       help="Fail (exit 1) if any frozen case fires or crashes")
    ap.add_argument("--cache", default=_CACHE_PATH,
                    help="Path to the market data cache parquet (build only)")
    args = ap.parse_args()

    try:
        if args.build_fixture:
            build_fixture(cache_path=args.cache)
        elif args.check:
            sys.exit(0 if check_corpus() else 1)
    except (FileNotFoundError, RuntimeError) as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
