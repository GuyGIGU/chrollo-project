"""
Cause-before-effect veto bite-proof - the live veto's regression net.

``CAUSE_BEFORE_EFFECT_VETO_ENABLED`` is live on main, but the veto shipped
without a regression guard: nothing reds if a future change silently defeats
it. The general negative corpus (``tools.negative_corpus``) only proves a frame
stays non-firing - it cannot tell "the veto suppressed this" from "some
unrelated gate did", so it could not guard the veto specifically.

This guard freezes the ONE frame where the veto is load-bearing - MIDD at its
census-defining reject session (the shelf ``tightness_ratio`` 0.957 minimum, the
whole reason the third AND-leg exists) - and asserts BOTH directions:

  * veto ON  -> the frame is REJECTED (``_evaluate_ticker`` returns None)
  * veto OFF -> the SAME frame FIRES

The bidirectional proof keeps the tripwire honest: a change that defeats the
veto reds the ON direction; a change that makes MIDD reject for an unrelated
reason (so this corpus would guard nothing) reds the OFF direction.

Self-contained negative fixture placed under ``tests/baselines/``
(PLAN-cause-before-effect.md Task 9, option b - EC-9 forbids the agent writing
a ``calibration_marks`` verdict, and the sealed ``docs/marks`` corpus is never
edited to manufacture a rejection). Hermetic on ``--check``: reads the frozen
parquet, never the network or the live cache.

Usage:
    python -m tools.cause_veto_corpus --build-fixture   # one-time, from the live cache
    python -m tools.cause_veto_corpus --check           # fail (exit 1) if the bite is gone
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

try:  # works under both `python -m tools.cause_veto_corpus` and `python tools/cause_veto_corpus.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path()

from config import settings
from engine_alpha.evaluation import EVAL_ERROR
from core.pipeline.screener import _evaluate_ticker
from tools import replay

_BASELINE_DIR = os.path.join(_PROJECT_ROOT, "tests", "baselines")
_FIXTURE_PARQUET = os.path.join(_BASELINE_DIR, "cause_veto_corpus.parquet")
_FIXTURE_META = os.path.join(_BASELINE_DIR, "cause_veto_corpus_meta.json")
_CACHE_PATH = os.path.join(_PROJECT_ROOT, settings.CACHE_FILENAME)

_FLAG = "CAUSE_BEFORE_EFFECT_VETO_ENABLED"

# Frozen market scalar for the breadth bonus - scoring-only, never a firing
# decision; any fixed value keeps the replay deterministic (matches the
# negative-corpus twin).
_FROZEN_BREADTH = 0.5

# The labeled corpus (the build recipe). Each case is a chart the veto - and
# ONLY the veto - suppresses at ``as_of``.
CASES: tuple[dict, ...] = (
    {"ticker": "MIDD", "as_of": "2026-07-17",
     "label": "cause-absent (MIDD class): box floats up through its own rails, "
              "loose shelf (tightness_ratio 0.957 = census min)",
     "evidence": "PLAN-cause-before-effect.md; project_cause_before_effect_veto.md; "
                 "flipped live 2026-07-20 (ed87029)"},
)


def _fires_off_rejects_on(ticker: str, df: pd.DataFrame, spy_6m: float,
                          breadth: float) -> tuple[object, object]:
    """Evaluate the frame with the veto OFF then ON, each in a self-restoring
    flag capture. Returns ``(result_off, result_on)`` - a dict/None/EVAL_ERROR
    for each."""
    with replay.flag_capture(**{_FLAG: False}):
        result_off = _evaluate_ticker(ticker, df, spy_6m, breadth)
    with replay.flag_capture(**{_FLAG: True}):
        result_on = _evaluate_ticker(ticker, df, spy_6m, breadth)
    return result_off, result_on


# ------------------------------------------------------------------
# Check (hermetic; reads only the committed fixture)
# ------------------------------------------------------------------
def _load_fixture() -> tuple[dict[str, pd.DataFrame], dict]:
    if not os.path.exists(_FIXTURE_PARQUET) or not os.path.exists(_FIXTURE_META):
        raise FileNotFoundError(
            "No cause-veto fixture - run `python -m tools.cause_veto_corpus "
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
    """Replay every frozen bite-proof frame BOTH directions through the real
    pipeline. Returns True iff, for every case, the veto ON rejects AND the
    veto OFF fires - a one-directional pass (either half wrong, or an
    EVAL_ERROR, or a missing frame) fails, because each removes the tripwire."""
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
        off, on = _fires_off_rejects_on(ticker, df, float(case["spy_6m_return"]),
                                        float(meta["breadth_pct"]))
        if off is EVAL_ERROR or on is EVAL_ERROR:
            ok = False
            lines.append(f"  {ticker}: EVAL_ERROR - the eval chain crashed on the bite-proof "
                         f"frame ({case['label']}); a crash proves nothing")
            continue
        if on is not None:
            ok = False
            lines.append(
                f"  {ticker}: FIRES with the veto ON (score={on.get('Score')}, "
                f"tier={on.get('Tier')}) - the veto NO LONGER BITES: {case['label']}"
            )
        if off is None:
            ok = False
            lines.append(
                f"  {ticker}: does NOT fire with the veto OFF - the frame now rejects for "
                f"some OTHER reason, so this case would guard nothing ({case['evidence']})"
            )

    print("=" * 64)
    print("  CAUSE-VETO BITE-PROOF - the live veto's regression net")
    print("=" * 64)
    if ok:
        print(f"all {len(cases)} case(s): veto ON rejects AND veto OFF fires - the veto bites.")
        print("PASS - the cause-before-effect veto still does its job.")
    else:
        for line in lines:
            print(line)
        print()
        print("FAIL - the veto's bite-proof no longer holds (see above).")
        print("If a change INTENTIONALLY re-stories one of these frames, re-eyeball it,")
        print("then rebuild or retire the case deliberately - never re-capture blindly.")
    return ok


# ------------------------------------------------------------------
# Fixture build (one-time; reads the live data cache, writes frozen files)
# ------------------------------------------------------------------
def build_fixture(cache_path: str = _CACHE_PATH) -> dict:
    """Freeze the bite-proof frames from the live data cache.

    Refuses to freeze a case unless BOTH directions hold at freeze time: the
    veto OFF fires and the veto ON rejects. A frame that does not fire with the
    veto off would guard nothing; a frame that still fires with it on is not a
    bite proof."""
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
        if len(df) < 300:
            problems.append(f"{ticker}: only {len(df)} bars at as_of={as_of}")
            continue
        spy_6m = float(spy.iloc[-1] / spy.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0)

        off, on = _fires_off_rejects_on(ticker, df, spy_6m, _FROZEN_BREADTH)
        if off is EVAL_ERROR or on is EVAL_ERROR:
            problems.append(f"{ticker}: EVAL_ERROR at as_of={as_of} - cannot freeze a crashing frame")
            continue
        if off is None:
            problems.append(f"{ticker}: does NOT fire with the veto OFF at as_of={as_of} "
                            "- guards nothing (pick an as_of where the veto is load-bearing)")
            continue
        if on is not None:
            problems.append(f"{ticker}: still FIRES with the veto ON at as_of={as_of} "
                            f"(score={on.get('Score')}, tier={on.get('Tier')}) - not a bite proof")
            continue

        frames[ticker] = df
        meta_cases.append({
            "ticker": ticker,
            "as_of": df.index[-1].date().isoformat(),
            "bars": len(df),
            "spy_6m_return": spy_6m,
            "fires_off_tier": off.get("Tier"),
            "fires_off_score": (float(off.get("Score"))
                                if off.get("Score") is not None else None),
            "label": case["label"],
            "evidence": case["evidence"],
        })

    if problems:
        raise RuntimeError(
            "Refusing to freeze the cause-veto corpus - unresolved cases:\n  "
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

    print(f"Built cause-veto corpus: {len(meta_cases)} bite-proof case(s) -> {_FIXTURE_PARQUET}")
    for c in meta_cases:
        print(f"  {c['ticker']}@{c['as_of']}: OFF fires {c['fires_off_tier']}/"
              f"{c['fires_off_score']}, ON rejects")
    return meta


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Cause-before-effect veto bite-proof guard.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--build-fixture", action="store_true",
                       help="Freeze the bite-proof frames from the live data cache")
    group.add_argument("--check", action="store_true",
                       help="Fail (exit 1) if the veto no longer bites (either direction)")
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
