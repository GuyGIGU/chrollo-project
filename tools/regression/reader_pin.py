"""
Reader pin - what the alpha reader SAYS about every committed fixture chart,
pinned field by field. Zero diffs is the fold acceptance.

The other guards cannot see a reading change that keeps the fires: the shadow
guard (``tools.regression.shadow_diff``) freezes nine canonical fields of the
FIRING tickers' last fire, the marks ratchet (``tools.regression.marks_corpus``)
compares FIRES, the junk gate pins FIRE DAYS. A change that rewrites every event,
moves a box an earlier read listed, or regrades a chart while every fire and
trigger stays put passes all three. This instrument reads the charts with the
reader itself (``engine_alpha.two_eyes.read`` - before the universe door and the
adapter, so a chart the door refuses is still read) and pins its record:

  * the boxes: role, R, S, the day each opened and the day each ended
  * the LPS: its first and last day, which box it was read against, its
    trigger and how it sat against the mini
  * the state word and the number that rides beside it
  * the events: the word, the day it points at and the price there
  * the grade: its letter and its score
  * the trail's STAGE words - never the sentences (a reworded sentence is not
    a reading change)

over three committed populations, each chart on its frame's last day:

  * the sealed marks-corpus frames (``tests/baselines/marks_corpus.parquet``,
    one per drawing, keyed ``TICKER:as_of``)
  * the 16 negative-corpus junk frames (``tests/baselines/negative_corpus.parquet``)
  * the 37 shadow-fixture frames (``tests/baselines/shadow_fixture.parquet``),
    including the ones that do not fire.

Prices are rounded to 2 decimals (the cent). Comparison is EXACT (NaN == NaN);
every chart records its frame's ``ohlcv_digest`` so a drifted parquet reads as
BASIS drift, named separately from reading drift (EC-12). The baseline is
stamped with the engine manifest hash and compared as an ADVISORY only: a
declared epoch rotates the hash on purpose, and the pin's verdict is about the
readings. A ruled reading change recaptures at its own seam commit (EC-29),
never mid-fold.

Hermetic: committed fixtures only - no network, no DB, no archive write.

Usage:
    python -m tools.regression.reader_pin --capture   # snapshot the reader's records as the baseline
    python -m tools.regression.reader_pin --check     # fail (exit 1) on any reading drift
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

try:  # works under both `python -m tools.regression.reader_pin` and `python tools/regression/reader_pin.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path

_PROJECT_ROOT = configure_path(backend=True)

from config import settings
from core.calibration.replay import load_sealed_fixture
from engine_alpha import two_eyes
from engine_alpha.freeze.manifest import manifest_hash

_BASELINE_DIR = os.path.join(_PROJECT_ROOT, "tests", "baselines")
_BASELINE_PATH = os.path.join(_BASELINE_DIR, "reader_pin_baseline.json")
_NEGATIVE_PARQUET = os.path.join(_BASELINE_DIR, "negative_corpus.parquet")
_NEGATIVE_META = os.path.join(_BASELINE_DIR, "negative_corpus_meta.json")
_SHADOW_PARQUET = os.path.join(_BASELINE_DIR, "shadow_fixture.parquet")
_SHADOW_SCALARS = os.path.join(_BASELINE_DIR, "shadow_fixture_scalars.json")


# ------------------------------------------------------------------
# Pure logic (unit-tested; no IO)
# ------------------------------------------------------------------
def jsonable(obj):
    """Recursively convert a value into a JSON-serializable twin without losing
    float precision (numpy scalars unwrap; NaN survives)."""
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [jsonable(v) for v in obj.tolist()]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return repr(obj)


def exact_equal(a, b) -> bool:
    """Exact equality with NaN == NaN (the one place == is wrong for floats
    here is NaN; everything else must match after the JSON round-trip)."""
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return False
        return all(exact_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(exact_equal(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def diff_paths(a, b, path: str = "", out: list | None = None, limit: int = 200) -> list[str]:
    """Human-readable list of paths where ``a`` (the baseline) and ``b`` (the
    current reading) differ."""
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else str(k)
            if k not in a:
                out.append(f"{p}: ONLY IN CURRENT = {b[k]!r}")
            elif k not in b:
                out.append(f"{p}: ONLY IN BASELINE = {a[k]!r}")
            elif not exact_equal(a[k], b[k]):
                if isinstance(a[k], (dict, list)) and isinstance(b[k], (dict, list)):
                    diff_paths(a[k], b[k], p, out, limit)
                else:
                    out.append(f"{p}: {a[k]!r} -> {b[k]!r}")
            if len(out) >= limit:
                break
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: list length {len(a)} -> {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                if not exact_equal(x, y):
                    diff_paths(x, y, f"{path}[{i}]", out, limit)
                if len(out) >= limit:
                    break
    elif not exact_equal(a, b):
        out.append(f"{path}: {a!r} -> {b!r}")
    return out


def _cents(value):
    return None if value is None else round(float(value), 2)


def _day(value):
    return None if value is None else value.isoformat()


def chart_record(read) -> dict:
    """One ``Read`` as the pinned record: the facts the reader said, prices to
    the cent, the trail as its stage words only."""
    boxes = [{"role": box.role, "R": _cents(box.resistance.price), "S": _cents(box.support.price),
              "opened": _day(box.opened_day), "end": _day(box.end_day)} for box in read.boxes]
    lps = read.lps
    grade = read.grade
    return {
        "as_of": _day(read.as_of),
        "failed": bool(read.failed),
        "refusal": read.refusal,
        "state": read.state,
        "state_days": None if read.state_days is None else int(read.state_days),
        "boxes": boxes,
        "lps": None if lps is None else {
            "start": _day(lps.start_day), "end": _day(lps.end_day), "against": lps.read_against,
            "trigger": _cents(lps.trigger_price), "how": lps.how},
        "events": [{"kind": e.kind, "day": _day(e.day), "price": _cents(e.price)} for e in read.events],
        "grade": None if grade is None else {"letter": grade.letter, "score": round(float(grade.score), 2)},
        "trail": [step.stage for step in read.trail],
    }


def diff_readings(current: dict, baseline: dict) -> tuple[bool, list[str]]:
    """Exact per-chart comparison, every difference named with its chart key.
    Basis drift (the bars moved) is named separately from reading drift (the
    words moved) - the repairs differ."""
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
            lines.append(f"  {pop}: charts NEW vs baseline (re-capture if intended): {', '.join(added)}")
        for key in sorted(set(base_pop) & set(cur_pop)):
            b, c = base_pop[key], cur_pop[key]
            if b.get("digest") != c.get("digest"):
                ok = False
                lines.append(f"  {pop}/{key}: BASIS DRIFT - the fixture frame's bars changed "
                             "(rebuild/verify the fixture; this is not a reading change)")
                continue
            if not exact_equal(b.get("reading"), c.get("reading")):
                ok = False
                for p in diff_paths(b.get("reading"), c.get("reading"), limit=10_000):
                    lines.append(f"  {pop}/{key}: {p}")
    return ok, lines


# ------------------------------------------------------------------
# Populations (hermetic; committed fixtures only)
# ------------------------------------------------------------------
def _load_parquet_frames(parquet_path: str, keys: list[str]) -> dict[str, pd.DataFrame]:
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


def ticker_of(key: str) -> str:
    """The ticker a population key names: ``ALB:2026-04-13`` (a drawing),
    ``BBVA@2026-06-05`` (a junk case frozen at a day), ``SWK`` (a shadow ticker)."""
    return key.split(":")[0].split("@")[0]


def run_pin() -> dict:
    """Read every chart in every population on its frame's last day; return the
    full pin snapshot."""
    from frame_store import ohlcv_digest

    populations: dict = {}
    for pop, frames in load_populations().items():
        charts: dict = {}
        for key in sorted(frames):
            df = frames[key]
            read = two_eyes.read(ticker_of(key), df)
            charts[key] = {"digest": ohlcv_digest(df), "reading": jsonable(chart_record(read))}
        populations[pop] = charts
    return {"populations": populations}


# ------------------------------------------------------------------
# Capture / check
# ------------------------------------------------------------------
def capture_baseline() -> dict:
    snapshot = run_pin()
    snapshot["captured_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    snapshot["engine_config_version"] = manifest_hash()
    snapshot["ruleset"] = settings.TWO_EYES_RULESET
    os.makedirs(_BASELINE_DIR, exist_ok=True)
    # LF forced: tests/baselines/*.json is .gitattributes-pinned to LF so byte
    # digests are checkout-independent; Windows text mode would write CRLF.
    with open(_BASELINE_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(snapshot, f, indent=1, allow_nan=True)
    n = {p: len(c) for p, c in snapshot["populations"].items()}
    fired = {p: sum(1 for c in charts.values() if c["reading"]["state"] == "fired")
             for p, charts in snapshot["populations"].items()}
    print(f"Captured reader pin -> {_BASELINE_PATH}")
    print(f"  charts: {n} | fired on the last day: {fired}")
    print(f"  engine_config_version: {snapshot['engine_config_version'][:16]}... | ruleset {snapshot['ruleset']}")
    return snapshot


def check_baseline() -> bool:
    if not os.path.exists(_BASELINE_PATH):
        print(f"No baseline at {_BASELINE_PATH} - run with --capture first.")
        return False
    with open(_BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    current = json.loads(json.dumps(run_pin(), allow_nan=True))
    ok, lines = diff_readings(current, baseline)

    print("=" * 64)
    print("  READER PIN - what the alpha reader says, chart by chart")
    print("=" * 64)
    n = {p: len(c) for p, c in baseline["populations"].items()}
    frozen_engine = baseline.get("engine_config_version", "?")
    print(f"populations: {n} | baseline engine: {frozen_engine[:16]}... | current engine: {manifest_hash()[:16]}...")
    if frozen_engine != manifest_hash():
        print("ADVISORY: the engine config epoch differs from the capture; the verdict below is about the "
              "readings, not the stamp (re-capture deliberately at the epoch's seam commit).")
    for line in lines:
        print(line)
    print()
    print("PASS - the reader says exactly what the baseline recorded." if ok
          else f"FAIL - {len(lines)} difference(s); see above. A fold must be zero-diff here; a ruled "
               "reading change recaptures at its own seam commit (EC-29), never mid-fold.")
    return ok


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="The alpha reader's records over the committed populations, pinned.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture", action="store_true", help="Snapshot the reader's records as the baseline")
    group.add_argument("--check", action="store_true", help="Fail (exit 1) if any reading drifted")
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
