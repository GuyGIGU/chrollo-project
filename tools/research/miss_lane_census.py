"""Miss-lane flip census — fleet exposure of the two dark miss-program lanes.

The flip instrument for `CONTRACTION_RESCUE_ENABLED` and
`SMA50_DIP_EXCEPTION_ENABLED` (docs/miss_program_2026-08.md): over the live
5-year cache at its LAST session, replay every universe ticker through the
real per-ticker pipeline and answer the two questions each flip ask names:

* **the contraction rescue** — how many tickers that currently read NOTHING
  convert to fires through the full-refusal re-walk, and what do they look
  like (tier, rails, admitting sentence) for the operator's eyeball;
* **the 50-day dip exception** — how many `sma50` universe refusals enter
  chart reading through the exception, and how many of those FIRE (entering
  the detector is not a pick; the fire count is the exposure);
* **the bottoming-base lane** (2026-08-29) — how many `sma200` refusals with
  the 50-day reclaimed enter, and how many FIRE;
* **the ceiling-rest LPS exception** (2026-08-29) — how many current
  no-reads convert through the sanctioned straddle, and — the drift leg —
  whether ANY currently-firing ticker's canonical read moves with it armed
  (the completion-form analogue of the shadow guard, at fleet scale).

Attribution is by construction: a ticker's baseline refusal reason routes it
to exactly the lane(s) that could reach it (an `sma50` universe refusal to
the door leg — then door+rescue for the residue; a chart-read refusal to the
rescue leg; any other universe refusal to neither). Baseline fires are
counted and never re-evaluated — the rescue cannot touch them by
construction, and that invariant is pinned in tests, not re-measured here.

Read-only everywhere: flags toggle through ``tools.calibration.replay.flag_capture``
(self-restoring), nothing writes to the archive, and the output is a sidecar
JSON + stdout summary.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.research.miss_lane_census [--limit N] [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import pandas as pd

try:  # works under both `python -m tools.research.miss_lane_census` and `python tools/research/miss_lane_census.py`
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

_PROJECT_ROOT = configure_path()

from config import settings  # noqa: E402
from engine_alpha.evaluation import (  # noqa: E402
    EVAL_ERROR,
    apply_baseline_filters_with_reason,
)
from core.pipeline.screening.screener import _evaluate_ticker  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from tools.calibration.replay import flag_capture  # noqa: E402

_CACHE = os.path.join(_PROJECT_ROOT, settings.CACHE_FILENAME)

# Frozen replay scalars (scoring-only inputs), the replay seam's convention.
_BREADTH = 0.5
_SPY_6M = 0.0


def _fire_row(ticker, result, lane):
    return {
        "ticker": ticker,
        "lane": lane,
        "tier": result.get("Tier"),
        "score": round(float(result.get("Score", 0.0)), 1),
        "elected_pool": result.get("_elected_pool"),
        "profile": result.get("_story_admission_profile"),
        "resistance": result.get("Resistance"),
        "support": result.get("Support"),
    }


def run(limit=None, json_out=None):
    if json_out:
        refuse_sealed_output(json_out)
    data = pd.read_parquet(_CACHE, engine=settings.PARQUET_ENGINE)
    tickers = sorted(set(data.columns.get_level_values(0)))
    skip = {settings.SPY_SYMBOL, *getattr(settings, "INDEX_SYMBOLS", [])}
    tickers = [t for t in tickers if t not in skip]
    if limit:
        tickers = tickers[:int(limit)]

    counts = {
        "tickers": 0, "fires_off": 0, "eval_error": 0,
        "universe_refused_other": 0, "universe_refused_sma50": 0,
        "universe_refused_sma200": 0,
        "door_admitted": 0, "door_fires": 0, "door_rescue_fires": 0,
        "bottoming_admitted": 0, "bottoming_fires": 0,
        "read_refused": 0, "rescue_fires": 0, "ceiling_fires": 0,
        "fires_ceiling_drift": 0,
    }
    conversions = []
    drifted = []
    t0 = time.time()
    session = None
    for i, ticker in enumerate(tickers):
        # Heartbeat on the unconditional path — every classification leg below
        # ends in continue, so anywhere later only fires on one leg (council
        # review 2026-08-30, Fowler).
        if (i + 1) % 250 == 0:
            print(f"  ... {i + 1}/{len(tickers)} "
                  f"({time.time() - t0:.0f}s) {counts}", flush=True)
        df = data[ticker].dropna()
        if df.empty:
            continue
        counts["tickers"] += 1
        if session is None or df.index[-1] > session:
            session = df.index[-1]

        off = _evaluate_ticker(ticker, df, _SPY_6M, _BREADTH)
        if off is EVAL_ERROR:
            counts["eval_error"] += 1
            continue
        if isinstance(off, dict):
            counts["fires_off"] += 1
            # The ceiling-rest DRIFT leg: a completion-form change is the one
            # lane class that can move an EXISTING fire's read. Fleet-scale
            # canonical comparison, the shadow guard's yardstick.
            from tools.regression import shadow_diff  # noqa: PLC0415
            with flag_capture(LPS_CEILING_REST_ENABLED=True):
                on = _evaluate_ticker(ticker, df, _SPY_6M, _BREADTH)
            if (not isinstance(on, dict)
                    or shadow_diff.canonical_fields(on)
                    != shadow_diff.canonical_fields(off)):
                counts["fires_ceiling_drift"] += 1
                drifted.append(ticker)
            continue

        _, reason = apply_baseline_filters_with_reason(df)
        if reason is not None and reason[0] == "sma200":
            counts["universe_refused_sma200"] += 1
            with flag_capture(BOTTOMING_BASE_LANE_ENABLED=True):
                base2, _r2 = apply_baseline_filters_with_reason(df)
                if base2 is None:
                    continue                    # 50d not reclaimed / later leg
                counts["bottoming_admitted"] += 1
                bot = _evaluate_ticker(ticker, df, _SPY_6M, _BREADTH)
            if isinstance(bot, dict):
                counts["bottoming_fires"] += 1
                conversions.append(_fire_row(ticker, bot, "bottoming"))
            continue
        if reason is not None and reason[0] != "sma50":
            counts["universe_refused_other"] += 1
            continue

        if reason is not None:                      # the sma50 door leg
            counts["universe_refused_sma50"] += 1
            with flag_capture(SMA50_DIP_EXCEPTION_ENABLED=True):
                base2, _r2 = apply_baseline_filters_with_reason(df)
                if base2 is None:
                    continue                        # dip test / later leg refused
                counts["door_admitted"] += 1
                door = _evaluate_ticker(ticker, df, _SPY_6M, _BREADTH)
            if isinstance(door, dict):
                counts["door_fires"] += 1
                conversions.append(_fire_row(ticker, door, "door"))
                continue
            with flag_capture(SMA50_DIP_EXCEPTION_ENABLED=True,
                              CONTRACTION_RESCUE_ENABLED=True):
                both = _evaluate_ticker(ticker, df, _SPY_6M, _BREADTH)
            if isinstance(both, dict):
                counts["door_rescue_fires"] += 1
                conversions.append(_fire_row(ticker, both, "door+rescue"))
            continue

        counts["read_refused"] += 1                 # the rescue leg
        with flag_capture(CONTRACTION_RESCUE_ENABLED=True):
            on = _evaluate_ticker(ticker, df, _SPY_6M, _BREADTH)
        if isinstance(on, dict):
            counts["rescue_fires"] += 1
            conversions.append(_fire_row(ticker, on, "rescue"))
        # The ceiling-rest leg, independent of the rescue: the sanctioned
        # straddle can complete an LPS on a box that already elects.
        with flag_capture(LPS_CEILING_REST_ENABLED=True):
            ceil = _evaluate_ticker(ticker, df, _SPY_6M, _BREADTH)
        if isinstance(ceil, dict):
            counts["ceiling_fires"] += 1
            conversions.append(_fire_row(ticker, ceil, "ceiling"))

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "cache_last_session": str(session)[:10] if session is not None else None,
        # FULL manifest hash in the persisted sidecar (EC-46; truncation only
        # ever on stdout) so the flip evidence exact-matches an engine epoch.
        "engine_manifest": manifest_hash(),
        "counts": counts,
        "fires_ceiling_drifted": drifted,
        "conversions": sorted(conversions,
                              key=lambda r: (-(r["score"] or 0), r["ticker"])),
    }
    print("=" * 64)
    print("  MISS-LANE FLIP CENSUS - fleet exposure at the cache edge")
    print("=" * 64)
    print(f"session {report['cache_last_session']}   "
          f"engine {report['engine_manifest']}...")
    for k, v in counts.items():
        print(f"  {k:>24}: {v}")
    print(f"  conversions: {len(conversions)} "
          f"(rescue {counts['rescue_fires']}, door {counts['door_fires']}, "
          f"door+rescue {counts['door_rescue_fires']}, "
          f"bottoming {counts['bottoming_fires']}, "
          f"ceiling {counts['ceiling_fires']})")
    if drifted:
        print(f"  ceiling-rest drift on current fires: {drifted}")
    for r in report["conversions"]:
        print(f"    {r['ticker']:<6} [{r['lane']}] tier {r['tier']} "
              f"score {r['score']} pool {r['elected_pool']} "
              f"{(r['profile'] or '')[:60]}")
    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
        print(f"wrote {json_out}")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", default=None, help="first N tickers only (smoke)")
    ap.add_argument("--json", default=None, help="sidecar report path")
    a = ap.parse_args()
    run(a.limit, a.json)


if __name__ == "__main__":
    main()
