"""
Operator-marks acceptance gate (Event Map) - proves operator-marked MUST-fire
setups fire while their marked entry windows are live, and ratchets progress.

This is the must-FIRE sibling of ``tools.negative_corpus`` (must-NOT-fire) and
the acceptance harness for the Event Map plan (PLAN-event-tape.md, Task 1): the
corpus files under ``docs/marks/`` are the operator's ground-truth dissections
(EC-7: immutable test specs - a failing case is fixed in the ENGINE, never by
editing a mark, widening a window, or reinterpreting trigger rules), and each
setup is replayed point-in-time through the SAME per-ticker evaluation the
nightly screener runs, entirely offline from a committed fixture.

The matcher: a setup is a HIT when the pipeline fires on ANY session inside its
marked entry window(s) - each window runs from an LPS start to its trigger
(inclusive); a null trigger gets ``NULL_TRIGGER_GRACE_SESSIONS`` sessions past
the LPS end ("by the trigger"); a second entry (``lps2`` / ``last_support`` +
``trigger_alt``) contributes its own window. These semantics FREEZE with the
baseline: changing them is an EC-7 event, not a tuning knob.

The baseline is a RATCHET, verified at freeze time:
  * every HIT is pinned forever - a pinned setup that stops firing FAILS;
  * every MISS carries the build-order stage expected to convert it
    (``STAGE_TAGS``) - an expected miss that starts firing also FAILS, loudly,
    until the baseline is deliberately re-frozen (strict-xfail semantics: a
    silent behavior change is never good news until a human looks).

The FULL replay walks every window session (~150 evals, minutes) - too slow for
the default suite, so it is the dedicated CI / per-stage acceptance step
(``python -m tools.marks_corpus --check``), like the hermetic seed-recall gate.
``tests/test_marks_corpus.py`` keeps the plumbing honest on every pytest run.

Usage:
    python -m tools.marks_corpus --build-fixture   # one-time, from the live data cache
    python -m tools.marks_corpus --check           # fail (exit 1) on any ratchet break
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone

import pandas as pd

try:  # works under both `python -m tools.marks_corpus` and `python tools/marks_corpus.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path()

from config import settings
from core.pipeline.evaluation import EVAL_ERROR
from core.pipeline.screener import _evaluate_ticker

# The shared replay layer owns fixture paths + loading (Task 6 fold).
# No dual-form fallback needed: configure_path() above already put the repo
# root on sys.path, so `tools.replay` resolves under both documented
# invocations (band_rails_ab imports it the same way).
from tools.replay import (
    BASELINE_DIR as _BASELINE_DIR,
    SEALED_BASELINE_JSON as _BASELINE_JSON,
    SEALED_FIXTURE_PARQUET as _FIXTURE_PARQUET,
    load_sealed_fixture,
)

# The operator-marks corpus files (EC-7: append-only ground truth under docs/marks/).
CORPUS_FILES: tuple[str, ...] = (
    os.path.join(_PROJECT_ROOT, "docs", "marks", "part2_2026-07.json"),
)

_CACHE_PATH = os.path.join(_PROJECT_ROOT, settings.CACHE_FILENAME)

# Frozen market scalar for the breadth bonus - scoring-only, never a firing
# decision; any fixed value keeps the replay deterministic (negative-corpus twin).
_FROZEN_BREADTH = 0.5

# "By the trigger" grace when a setup has no trigger mark: the entry window runs
# this many sessions past the LPS end. Frozen with the baseline (EC-7).
NULL_TRIGGER_GRACE_SESSIONS = 2

# Build-order stage expected to convert each known miss (PLAN-event-tape.md
# ratchet). Verified at freeze time: the replayed miss-set must equal this key
# set exactly, so the baseline can never freeze an unexplained miss.
STAGE_TAGS: dict[str, str] = {
    "WTS": "holding-shelf-lps",
    "DRTS": "holding-shelf-lps",
    "PBT": "holding-shelf-lps",
    "BODI": "band-vs-excursion",
    "EGBN": "under-investigation",
}

# Corpus schema: every key a setup may carry. An unrecognized key FAILS the
# load (a typo'd mark silently skipped would shrink the acceptance set).
_REQUIRED_KEYS = ("ticker", "source", "lps", "rails_drawn")
_ALLOWED_KEYS = frozenset({
    "ticker", "setup", "source", "notes",
    "bc", "bc_source", "ar", "ar_source",
    "lps", "lps_source", "lps2", "trigger", "trigger_source", "trigger_alt",
    "last_supper", "last_support", "springs", "sos", "shakeout_dates",
    "consolidation_start", "root_swing", "rails_drawn", "rails_source",
})
_DATE_SPAN_KEYS = ("lps", "lps2", "last_supper", "last_support",
                   "consolidation_start", "root_swing", "sos")
_DATE_LIST_KEYS = ("springs", "shakeout_dates")
_DATE_SCALAR_KEYS = ("bc", "ar", "trigger", "trigger_alt")


def _parse_date(value: str, ctx: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"marks corpus: {ctx} is not an ISO date: {value!r}")


def setup_key(setup: dict) -> str:
    """Stable identity: ticker plus the optional setup label (NGL has two)."""
    label = setup.get("setup")
    return f"{setup['ticker']}:{label}" if label else setup["ticker"]


def load_corpus(paths: tuple[str, ...] = CORPUS_FILES) -> list[dict]:
    """Load + validate every marks file. LOUD on any malformed mark - a skipped
    mark would silently shrink the acceptance set (EC-7)."""
    setups: list[dict] = []
    seen: set[str] = set()
    for path in paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"marks corpus file missing: {path}")
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        if not isinstance(doc.get("setups"), list) or not doc["setups"]:
            raise ValueError(f"marks corpus: {path} has no 'setups' list")
        for raw in doc["setups"]:
            ctx = f"{os.path.basename(path)}::{raw.get('ticker', '?')}"
            unknown = set(raw) - _ALLOWED_KEYS
            if unknown:
                raise ValueError(f"marks corpus: {ctx} has unrecognized keys {sorted(unknown)} "
                                 "- extend _ALLOWED_KEYS deliberately, never skip")
            for key in _REQUIRED_KEYS:
                if key not in raw:
                    raise ValueError(f"marks corpus: {ctx} missing required key '{key}'")
            for key in _DATE_SPAN_KEYS:
                if raw.get(key) is not None:
                    span = raw[key]
                    if not (isinstance(span, list) and len(span) == 2):
                        raise ValueError(f"marks corpus: {ctx}.{key} must be a [start, end] pair")
                    lo, hi = (_parse_date(v, f"{ctx}.{key}") for v in span)
                    if lo > hi:
                        raise ValueError(f"marks corpus: {ctx}.{key} start after end")
            for key in _DATE_LIST_KEYS:
                for v in raw.get(key) or []:
                    _parse_date(v, f"{ctx}.{key}")
            for key in _DATE_SCALAR_KEYS:
                if raw.get(key) is not None:
                    _parse_date(raw[key], f"{ctx}.{key}")
            rails = raw["rails_drawn"]
            if not (isinstance(rails, dict) and {"R", "S"} <= set(rails)):
                raise ValueError(f"marks corpus: {ctx}.rails_drawn needs R and S")
            key = setup_key(raw)
            if key in seen:
                raise ValueError(f"marks corpus: duplicate setup key {key!r}")
            seen.add(key)
            setups.append(raw)
    return setups


def corpus_sha256(paths: tuple[str, ...] = CORPUS_FILES) -> str:
    """One digest over every corpus file, in listed order - the EC-7 seal."""
    h = hashlib.sha256()
    for path in paths:
        with open(path, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def eval_windows(setup: dict) -> list[tuple[date, date]]:
    """The marked entry window(s) - see module docstring. Frozen semantics."""
    lps_start = _parse_date(setup["lps"][0], "lps[0]")
    lps_end = _parse_date(setup["lps"][1], "lps[1]")
    windows: list[tuple[date, date, int]] = []  # (start, end, grace_sessions)
    if setup.get("trigger"):
        windows.append((lps_start, _parse_date(setup["trigger"], "trigger"), 0))
    else:
        windows.append((lps_start, lps_end, NULL_TRIGGER_GRACE_SESSIONS))

    second_start = second_end = None
    grace = 0
    if setup.get("lps2"):
        second_start = _parse_date(setup["lps2"][0], "lps2[0]")
        second_end, grace = _parse_date(setup["lps2"][1], "lps2[1]"), NULL_TRIGGER_GRACE_SESSIONS
    if setup.get("last_support"):
        second_start = _parse_date(setup["last_support"][0], "last_support[0]")
        if second_end is None:
            second_end, grace = _parse_date(setup["last_support"][1], "last_support[1]"), NULL_TRIGGER_GRACE_SESSIONS
    if setup.get("trigger_alt"):
        alt = _parse_date(setup["trigger_alt"], "trigger_alt")
        if second_start is not None:
            second_end, grace = alt, 0
        elif alt > windows[0][1]:
            second_start, second_end, grace = windows[0][1], alt, 0
    if second_start is not None and second_end is not None:
        windows.append((second_start, second_end, grace))

    # Windows whose alt trigger sits inside the first window collapse away.
    merged: list[tuple[date, date, int]] = []
    for w in windows:
        if merged and w[0] >= merged[0][0] and w[1] <= merged[0][1]:
            continue
        merged.append(w)
    return [(s, e, g) for s, e, g in merged]


def _window_sessions(df: pd.DataFrame, windows) -> list[pd.Timestamp]:
    """The frame's actual trading sessions inside each window (+ grace bars)."""
    sessions: list[pd.Timestamp] = []
    for start, end, grace in windows:
        inside = df.index[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
        sessions.extend(inside)
        if grace and len(inside):
            after = df.index[df.index > pd.Timestamp(end)][:grace]
            sessions.extend(after)
    return sorted(set(sessions))


# ------------------------------------------------------------------
# Check (hermetic; reads only the committed fixture + baseline)
# ------------------------------------------------------------------
def _load_fixture() -> tuple[dict[str, pd.DataFrame], dict]:
    # Preserved name: the implementation moved DOWN into the shared replay
    # layer (Task 6) so the gate and the instruments load the same fixture.
    return load_sealed_fixture()


def _replay_setup(setup: dict, df: pd.DataFrame, spy_6m: float) -> dict:
    """Replay one setup's window sessions; return {status, first_fire|reason}."""
    ticker = setup["ticker"]
    sessions = _window_sessions(df, eval_windows(setup))
    if not sessions:
        return {"status": "error", "reason": "no frame sessions inside the marked windows"}
    for ts in sessions:
        sliced = df.loc[:ts]
        if len(sliced) < 200:
            continue
        result = _evaluate_ticker(ticker, sliced, spy_6m, _FROZEN_BREADTH)
        if result is EVAL_ERROR:
            return {"status": "error",
                    "reason": f"EVAL_ERROR at {ts.date()} - a crash is neither a hit nor a miss"}
        if result is not None:
            return {"status": "hit", "first_fire": ts.date().isoformat(),
                    "tier": result.get("Tier"), "score": result.get("Score")}
    return {"status": "miss"}


def check_corpus() -> bool:
    """Full ratchet check: corpus seal, pinned hits still hit, expected misses
    still miss. ANY deviation fails - improvements included, until the baseline
    is deliberately re-frozen with the stage's acceptance evidence."""
    frames, baseline = _load_fixture()
    setups = load_corpus()

    lines: list[str] = []
    ok = True

    seal = corpus_sha256()
    if seal != baseline.get("corpus_sha256"):
        ok = False
        lines.append(
            "  CORPUS SEAL BROKEN: docs/marks/ content differs from the frozen baseline.\n"
            "  EC-7: marks are immutable test specs - fix the engine, never the marks.\n"
            "  If this change IS an operator-sanctioned correction, re-freeze deliberately:\n"
            "  `python -m tools.marks_corpus --build-fixture`."
        )

    by_key = {s["key"]: s for s in baseline["setups"]}
    for setup in setups:
        key = setup_key(setup)
        pinned = by_key.get(key)
        if pinned is None:
            ok = False
            lines.append(f"  {key}: in the corpus but not in the baseline - re-freeze deliberately")
            continue
        df = frames.get(setup["ticker"])
        if df is None or df.empty:
            ok = False
            lines.append(f"  {key}: frame MISSING from fixture parquet - rebuild the fixture")
            continue
        got = _replay_setup(setup, df, float(pinned["spy_6m_return"]))
        if got["status"] == "error":
            ok = False
            lines.append(f"  {key}: {got['reason']}")
        elif pinned["status"] == "hit" and got["status"] == "miss":
            ok = False
            lines.append(f"  {key}: PINNED HIT REGRESSED - fired at freeze "
                         f"({pinned.get('first_fire')}), now silent in its marked window")
        elif pinned["status"] == "miss" and got["status"] == "hit":
            ok = False
            lines.append(
                f"  {key}: EXPECTED MISS NOW FIRES ({got['first_fire']}, tier {got.get('tier')}) - "
                f"stage '{pinned.get('stage')}' may have converted it. Good news is still a "
                "ratchet break: verify the stage's acceptance evidence, then re-freeze."
            )

    missing = set(by_key) - {setup_key(s) for s in setups}
    if missing:
        ok = False
        lines.append(f"  baseline setups vanished from the corpus: {sorted(missing)} (EC-7)")

    print("=" * 64)
    print("  OPERATOR-MARKS ACCEPTANCE GUARD - must-fire setups (Event Map)")
    print("=" * 64)
    if ok:
        hits = sum(1 for s in baseline["setups"] if s["status"] == "hit")
        print(f"ratchet held: {hits}/{len(baseline['setups'])} pinned hits still fire; "
              "every expected miss still misses.")
        print("PASS")
    else:
        for line in lines:
            print(line)
        print()
        print("FAIL - the marks ratchet broke (see above).")
    return ok


# ------------------------------------------------------------------
# Fixture build (one-time / per-stage re-freeze; reads the live data cache)
# ------------------------------------------------------------------
def build_fixture(cache_path: str = _CACHE_PATH) -> dict:
    """Freeze frames + the ratchet baseline from the live cache.

    Refuses to freeze when the replayed miss-set differs from STAGE_TAGS -
    every frozen miss must carry the build-order stage expected to convert it,
    and a pinned hit that does not actually fire is a broken freeze, not a
    baseline.
    """
    if not os.path.exists(cache_path):
        raise FileNotFoundError(
            f"Data cache not found at {cache_path} - run a real scan first "
            "(`python run_screener.py`) so the parquet exists."
        )
    setups = load_corpus()
    data = pd.read_parquet(cache_path, engine=settings.PARQUET_ENGINE)
    level0 = set(data.columns.get_level_values(0))
    spy_close = data[settings.SPY_SYMBOL]["Close"].dropna()

    frames: dict[str, pd.DataFrame] = {}
    baseline_setups: list[dict] = []
    problems: list[str] = []
    for setup in setups:
        key, ticker = setup_key(setup), setup["ticker"]
        if ticker not in level0:
            problems.append(f"{key}: not in the data cache")
            continue
        windows = eval_windows(setup)
        last_end = max(w[1] for w in windows)
        # Freeze through the last window end + grace room; full history before it
        # (the pipeline applies its own live structure trim internally).
        df_full = data[ticker].dropna()
        cutoff_idx = df_full.index[df_full.index <= pd.Timestamp(last_end)]
        if not len(cutoff_idx):
            problems.append(f"{key}: no bars at/before window end {last_end}")
            continue
        pos = df_full.index.get_loc(cutoff_idx[-1])
        df = df_full.iloc[: pos + 1 + NULL_TRIGGER_GRACE_SESSIONS]
        if len(df) < 200:
            problems.append(f"{key}: only {len(df)} bars through {last_end}")
            continue
        prior = frames.get(ticker)
        if prior is None or len(df) > len(prior):
            frames[ticker] = df  # one frame per ticker, longest window wins (NGL x2)

        spy = spy_close.loc[: df.index[-1]]
        spy_6m = float(spy.iloc[-1] / spy.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0)
        got = _replay_setup(setup, df, spy_6m)
        if got["status"] == "error":
            problems.append(f"{key}: {got['reason']}")
            continue
        stage = STAGE_TAGS.get(key.split(":")[0])
        if got["status"] == "miss" and stage is None:
            problems.append(f"{key}: replays as a MISS but has no STAGE_TAGS entry - "
                            "every frozen miss must name its converting stage")
            continue
        if got["status"] == "hit" and stage is not None:
            problems.append(f"{key}: replays as a HIT but STAGE_TAGS expects a miss - "
                            "remove the stale tag deliberately")
            continue
        entry = {"key": key, "ticker": ticker, "status": got["status"],
                 "windows": [[w[0].isoformat(), w[1].isoformat()] for w in windows],
                 "spy_6m_return": spy_6m, "bars": len(df)}
        if got["status"] == "hit":
            entry.update({"first_fire": got["first_fire"], "tier": got.get("tier")})
        else:
            entry["stage"] = stage
        baseline_setups.append(entry)
        print(f"  {key}: {got['status'].upper()}"
              + (f" (first fire {got['first_fire']}, tier {got.get('tier')})"
                 if got["status"] == "hit" else f" (stage: {stage})"), flush=True)

    if problems:
        raise RuntimeError("Refusing to freeze the marks corpus - unresolved setups:\n  "
                           + "\n  ".join(problems))

    os.makedirs(_BASELINE_DIR, exist_ok=True)
    combined = pd.concat(frames, axis=1)  # MultiIndex columns: (ticker, field)
    combined.to_parquet(_FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    baseline = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "breadth_pct": _FROZEN_BREADTH,
        "corpus_sha256": corpus_sha256(),
        "null_trigger_grace_sessions": NULL_TRIGGER_GRACE_SESSIONS,
        "setups": baseline_setups,
    }
    with open(_BASELINE_JSON, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)

    hits = sum(1 for s in baseline_setups if s["status"] == "hit")
    print(f"Built marks corpus: {hits} pinned hits / "
          f"{len(baseline_setups) - hits} staged misses -> {_FIXTURE_PARQUET}")
    return baseline


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Operator-marks acceptance guard (Event Map).")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--build-fixture", action="store_true",
                       help="Freeze corpus frames + the ratchet baseline from the live data cache")
    group.add_argument("--check", action="store_true",
                       help="Fail (exit 1) on any ratchet break (regressed hit, converted miss, corpus edit)")
    ap.add_argument("--cache", default=_CACHE_PATH,
                    help="Path to the market data cache parquet (build only)")
    args = ap.parse_args()

    try:
        if args.build_fixture:
            build_fixture(cache_path=args.cache)
        elif args.check:
            sys.exit(0 if check_corpus() else 1)
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
