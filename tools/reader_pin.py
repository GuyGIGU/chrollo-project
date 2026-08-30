"""
Reader-vocabulary pin - proves a fold/rename did NOT rewrite what the rail-event
readers SAY about a chart (PLAN-one-event-map Task 2).

The other guards cannot see this program's failure mode. ``tools.shadow_diff``
freezes nine canonical fields; ``tools.marks_corpus`` compares FIRES;
``tools.fold_parity`` captures the full ``_evaluate_ticker`` result dict - which
carries the episode sentence and tape but provably NOT the puzzle event list,
the role labels, or the inner-box position (the three surfaces the ONE-Event-Map
fold renames), and collapses every non-firing ticker to one ``__REJECT__``
token. A fold that kept every fire and score identical while rewriting every
event would pass all of them. This instrument pins the readers themselves, at
per-event grain, on real bars from three committed populations:

  * the 33 sealed marks-corpus frames  (``tests/baselines/marks_corpus.parquet``)
  * the 18 negative-corpus junk frames (``tests/baselines/negative_corpus.parquet``)
  * the 37 shadow-fixture frames       (``tests/baselines/shadow_fixture.parquet``)
    - including the 5 that REJECT, the population every other guard is blind to.

Basis: a fixed MECHANICAL window per chart - the frame's last ``PIN_WINDOW_BARS``
bars, rails at the window's High/Low extremes, ATR via the shared instrument
enrichment (``tools.replay.enrich_marked_frame`` at ``MARK_ATR_OFFSET``). This is
deliberately NOT the operator's drawn rails and NOT the engine's election: a pin
must not move when an unrelated program legally moves an election, and drawn
rails live in the editable calibration DB (a gate may not depend on a population
the operator grows daily). Reader fidelity to the DRAWN rails is census
evidence (``CORRESPONDENCE-REPORT.md``), not this gate's job; this gate answers
exactly one question - same inputs, same words.

Surfaces pinned per chart (public reader contracts only):
  * ``read_rail_episodes`` + ``episode_sequence_stats``  (the episode layer)
  * ``read_box_events``                                  (the puzzle event list)
  * ``read_role_labels``                                 (the role-label layer)
  * ``find_spring`` / ``find_lps``                       (the bricks the two
    surfaces above consume, pinned so a drift names its layer)
plus a fixed numeric grid through ``inner_box.mini_consolidation_position``
(the dark position attribute - band values AND refusal legs stated literally).

There is NO rename-mapping mode here BY DESIGN (unlike ``fold_parity
--mapping``): the readers' emitted keys and vocabulary values are stored/wire
history (conventions AP-12 / the Leach freeze - "the fold renames code, never
cells"), so on these surfaces zero diffs is the only acceptable fold outcome.
A legitimate vocabulary seam (e.g. the ruled Task-6 position-tolerance change)
recaptures deliberately at that seam commit per EC-29 - never mid-fold.

Comparison is EXACT (NaN == NaN) via the fold_parity comparators; the baseline
is committed and stamped with the engine manifest hash, and every chart records
its window's ``ohlcv_digest`` so a drifted parquet reads as BASIS drift (named
separately), never as silent reading drift (EC-12).

Hermetic: committed fixtures only - no network, no DB, no archive write (EC-46).

Usage:
    python -m tools.reader_pin --capture   # snapshot reader outputs as baseline
    python -m tools.reader_pin --check     # fail (exit 1) on any reading drift
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

try:  # works under both `python -m tools.reader_pin` and `python tools/reader_pin.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path(backend=True)

from tools.fold_parity import diff_paths, exact_equal, jsonable
from tools.replay import MARK_ATR_OFFSET, enrich_marked_frame, load_sealed_fixture

from engine_alpha.freeze.manifest import manifest_hash
from engine_alpha.structure.bricks import find_lps, find_spring
from engine_alpha.structure.box_events import read_box_events
from engine_alpha.structure.event_map import (
    episode_sequence_stats,
    read_rail_episodes,
    read_role_labels,
)
from engine_alpha.structure.inner_box import mini_consolidation_position

_BASELINE_DIR = os.path.join(_PROJECT_ROOT, "tests", "baselines")
_BASELINE_PATH = os.path.join(_BASELINE_DIR, "reader_pin_baseline.json")
_NEGATIVE_PARQUET = os.path.join(_BASELINE_DIR, "negative_corpus.parquet")
_NEGATIVE_META = os.path.join(_BASELINE_DIR, "negative_corpus_meta.json")
_SHADOW_PARQUET = os.path.join(_BASELINE_DIR, "shadow_fixture.parquet")
_SHADOW_SCALARS = os.path.join(_BASELINE_DIR, "shadow_fixture_scalars.json")

# The fixed mechanical window (bars from the frame end). ~6 months of sessions:
# long enough for multi-wave structure, short enough that every fixture frame
# covers it. Changing it is a deliberate re-capture event, never a tuning knob.
PIN_WINDOW_BARS = 120

# Behavior pin for mini_consolidation_position: literal inputs -> literal
# expected band, INCLUDING the refusal legs (None, never a fabricated band).
# These values were reasoned from the function's stated conventions
# (inner_box.py: inclusive comparisons, ceiling evaluated first, refuse on
# unusable input) - NOT copied from a run. Band rows re-derived at the
# 2026-08-30 rail-area seam commit (MINI_POSITION_TOL_ATR 1.0 -> 0.5, the
# ruled +/-0.50-ATR area; EC-29); the refusal rows never move.
POSITION_GRID: tuple[tuple[dict, object], ...] = (
    ({"inner_r": 9.5, "inner_s": 8.0, "parent_r": 10.0, "parent_s": 5.0, "atr_val": 1.0},
     "at_ceiling"),      # inner top exactly AT parent_r - 0.5*ATR (inclusive tie)
    ({"inner_r": 9.0, "inner_s": 5.5, "parent_r": 10.0, "parent_s": 5.0, "atr_val": 1.0},
     "on_support"),      # ceiling band (from 9.5) misses; support tie at 5.5 holds
    ({"inner_r": 6.2, "inner_s": 5.8, "parent_r": 10.0, "parent_s": 5.0, "atr_val": 1.0},
     "mid_range"),       # 5.8 > 5.5: outside both 0.5-ATR bands
    ({"inner_r": 12.0, "inner_s": 10.0, "parent_r": 20.0, "parent_s": 5.0, "atr_val": 1.0},
     "mid_range"),       # tall box: neither band reaches the middle
    ({"inner_r": 19.0, "inner_s": 17.5, "parent_r": 20.0, "parent_s": 5.0, "atr_val": 0.0},
     None),              # non-positive ATR -> refused, never fabricated
    ({"inner_r": float("nan"), "inner_s": 8.0, "parent_r": 10.0, "parent_s": 5.0,
      "atr_val": 1.0},
     None),              # non-finite input -> refused
    ({"inner_r": None, "inner_s": 8.0, "parent_r": 10.0, "parent_s": 5.0, "atr_val": 1.0},
     None),              # missing input -> refused
)


# ------------------------------------------------------------------
# Pure logic (unit-tested; no IO)
# ------------------------------------------------------------------
def pin_window(frame: pd.DataFrame):
    """The fixed mechanical basis for one chart: ``(window, R, S, atr)``.

    Window = the enriched frame's last ``PIN_WINDOW_BARS`` bars; rails at the
    window extremes; ATR at the shared ``MARK_ATR_OFFSET``. Returns None when
    the basis is underivable (too few bars / no finite ATR) - recorded
    honestly, never guessed.
    """
    if frame is None or frame.empty:
        return None
    enriched = enrich_marked_frame(frame)
    window = enriched.iloc[-PIN_WINDOW_BARS:]
    if len(window) < MARK_ATR_OFFSET + 1:
        return None
    atr = window["ATR_10"].iloc[-MARK_ATR_OFFSET]
    if pd.isna(atr) or float(atr) <= 0:
        return None
    r = float(window["High"].max())
    s = float(window["Low"].min())
    if not (math.isfinite(r) and math.isfinite(s)) or r - s <= 0:
        return None
    return window, r, s, float(atr)


def read_chart(frame: pd.DataFrame) -> dict:
    """Every pinned reader surface on one chart's mechanical basis.

    The box handed to the readers is the duck-typed contract the bricks
    already accept (start_bar/base_len/R/S + the anchor bars find_lps reads);
    spring and lps are detected ONCE and INJECTED into the role labels so the
    label layer describes the same bricks the event list carries.
    """
    basis = pin_window(frame)
    if basis is None:
        return {"basis": None}
    window, r, s, atr = basis
    box = SimpleNamespace(start_bar=0, base_len=len(window), R=r, S=s,
                          r_anchor_bar=0, s_anchor_bar=0)

    spring = find_spring(window, box, atr)
    lps = find_lps(window, box, atr)
    episodes = read_rail_episodes(window, r, s, atr)
    return {
        "basis": {
            "window_start": window.index[0].date().isoformat(),
            "window_end": window.index[-1].date().isoformat(),
            "bars": len(window),
            "R": r, "S": s, "atr": atr,
        },
        "episodes": episodes,
        "episode_stats": episode_sequence_stats(episodes),
        "box_events": read_box_events(window, box, atr),
        "role_labels": read_role_labels(window, box, atr, spring=spring, lps=lps),
        "spring": None if spring is None else {
            "tip_bar": int(spring.tip_bar), "recovery_bar": int(spring.recovery_bar),
            "undercut_atr": float(spring.undercut_atr),
        },
        "lps": None if lps is None else {
            "start_bar": int(lps.start_bar), "end_bar": int(lps.end_bar),
            "low_bar": int(lps.low_bar), "swing_type": lps.swing_type,
        },
    }


def diff_readings(current: dict, baseline: dict) -> tuple[bool, list[str]]:
    """Exact per-chart comparison. Basis drift (the bars moved) is named
    separately from reading drift (the words moved) - the repairs differ."""
    lines: list[str] = []
    ok = True

    for pop in sorted(set(baseline["populations"]) | set(current["populations"])):
        base_pop = baseline["populations"].get(pop, {})
        cur_pop = current["populations"].get(pop, {})
        missing = sorted(set(base_pop) - set(cur_pop))
        added = sorted(set(cur_pop) - set(base_pop))
        if missing:
            ok = False
            lines.append(f"  {pop}: charts MISSING vs baseline: {', '.join(missing)}")
        if added:
            ok = False
            lines.append(f"  {pop}: charts NEW vs baseline (re-capture if intended): "
                         f"{', '.join(added)}")
        for key in sorted(set(base_pop) & set(cur_pop)):
            b, c = base_pop[key], cur_pop[key]
            if b.get("window_digest") != c.get("window_digest"):
                ok = False
                lines.append(f"  {pop}/{key}: BASIS DRIFT - the fixture window's bars "
                             "changed (rebuild/verify the fixture; this is not a "
                             "reading change)")
                continue
            if not exact_equal(b.get("reading"), c.get("reading")):
                ok = False
                for p in diff_paths(b.get("reading"), c.get("reading"), limit=6):
                    lines.append(f"  {pop}/{key}: {p}")

    if not exact_equal(current["position_grid"], baseline["position_grid"]):
        ok = False
        for p in diff_paths(baseline["position_grid"], current["position_grid"], limit=10):
            lines.append(f"  position_grid: {p}")
    return ok, lines


# ------------------------------------------------------------------
# Populations (hermetic; committed fixtures only)
# ------------------------------------------------------------------
def _load_parquet_frames(parquet_path: str, keys: list[str]) -> dict[str, pd.DataFrame]:
    from config import settings
    data = pd.read_parquet(parquet_path, engine=settings.PARQUET_ENGINE)
    level0 = set(data.columns.get_level_values(0))
    return {k: data[k].dropna() for k in keys if k in level0}


def load_populations() -> dict[str, dict[str, pd.DataFrame]]:
    """The three committed populations, keyed exactly as their owners key them."""
    marks_frames, _baseline = load_sealed_fixture()

    with open(_NEGATIVE_META, "r", encoding="utf-8") as f:
        neg_meta = json.load(f)
    neg_keys = [c.get("key", c["ticker"]) for c in neg_meta["cases"]]
    junk_frames = _load_parquet_frames(_NEGATIVE_PARQUET, neg_keys)

    with open(_SHADOW_SCALARS, "r", encoding="utf-8") as f:
        shadow_scalars = json.load(f)
    shadow_frames = _load_parquet_frames(_SHADOW_PARQUET, shadow_scalars["tickers"])

    return {"marks": marks_frames, "junk": junk_frames, "shadow": shadow_frames}


def run_pin() -> dict:
    """Read every chart in every population; return the full pin snapshot."""
    from frame_store import ohlcv_digest

    populations: dict = {}
    for pop, frames in load_populations().items():
        charts: dict = {}
        for key in sorted(frames):
            reading = read_chart(frames[key])
            basis = reading.pop("basis")
            if basis is None:
                charts[key] = {"window_digest": None, "reading": None,
                               "note": "basis underivable (too few bars / no ATR)"}
                continue
            window = enrich_marked_frame(frames[key]).iloc[-PIN_WINDOW_BARS:]
            charts[key] = {
                "window_digest": ohlcv_digest(window),
                "basis": jsonable(basis),
                "reading": jsonable(reading),
            }
        populations[pop] = charts

    grid = [{"inputs": jsonable(inputs),
             "position": mini_consolidation_position(**inputs)}
            for inputs, _expected in POSITION_GRID]
    return {"populations": populations, "position_grid": grid}


def _verify_position_grid() -> list[str]:
    """The literal expected values, asserted at capture AND check time - the
    grid's truth does not depend on the baseline file."""
    problems = []
    for inputs, expected in POSITION_GRID:
        got = mini_consolidation_position(**inputs)
        if got != expected:
            problems.append(f"  position_grid: {inputs} -> {got!r}, expected {expected!r}")
    return problems


# ------------------------------------------------------------------
# Capture / check
# ------------------------------------------------------------------
def capture_baseline() -> dict:
    grid_problems = _verify_position_grid()
    if grid_problems:
        raise RuntimeError(
            "Refusing to capture - mini_consolidation_position disagrees with its "
            "stated-literal grid (fix the engine or re-rule the grid at a seam "
            "commit):\n" + "\n".join(grid_problems))
    snapshot = run_pin()
    snapshot["captured_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    snapshot["engine_config_version"] = manifest_hash()
    snapshot["pin_window_bars"] = PIN_WINDOW_BARS
    os.makedirs(_BASELINE_DIR, exist_ok=True)
    with open(_BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=1, allow_nan=True)
    n = {p: len(c) for p, c in snapshot["populations"].items()}
    print(f"Captured reader pin -> {_BASELINE_PATH}")
    print(f"  charts: {n} | position grid: {len(snapshot['position_grid'])} rows")
    print(f"  engine_config_version: {snapshot['engine_config_version'][:16]}...")
    return snapshot


def check_baseline() -> bool:
    if not os.path.exists(_BASELINE_PATH):
        print(f"No baseline at {_BASELINE_PATH} - run with --capture first.")
        return False
    with open(_BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    current = json.loads(json.dumps(run_pin(), allow_nan=True))
    ok, lines = diff_readings(current, baseline)
    grid_problems = _verify_position_grid()
    if grid_problems:
        ok = False
        lines.extend(grid_problems)

    print("=" * 64)
    print("  READER-VOCABULARY PIN - what the rail readers say, per event")
    print("=" * 64)
    n = {p: len(c) for p, c in baseline["populations"].items()}
    print(f"populations: {n} | baseline engine: "
          f"{baseline.get('engine_config_version', '?')[:16]}... | "
          f"current engine: {manifest_hash()[:16]}...")
    for line in lines:
        print(line)
    print()
    print("PASS - every reader says exactly what the baseline recorded." if ok
          else "FAIL - a reader's output drifted; see above. A fold must be "
               "zero-diff here; a deliberate vocabulary seam recaptures at its "
               "own seam commit (EC-29), never mid-fold.")
    return ok


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="Per-event reader-vocabulary pin over the committed populations.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture", action="store_true",
                       help="Snapshot current reader outputs as the baseline")
    group.add_argument("--check", action="store_true",
                       help="Fail (exit 1) if any reader output drifted")
    args = ap.parse_args()

    try:
        if args.capture:
            capture_baseline()
        elif args.check:
            sys.exit(0 if check_baseline() else 1)
    except (FileNotFoundError, RuntimeError) as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
