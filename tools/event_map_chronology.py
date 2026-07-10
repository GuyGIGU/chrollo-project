"""Event Map chronology battery — Beck's truncate-and-relabel guard at corpus scale.

For every operator-marked setup (``docs/marks/*.json``), step the evaluation cut
session by session through the marked LPS window and trigger (±margin), run the
REAL election at each cut (``_prepare_eval_frame`` → ``_resolve_structure_context``),
and label each cut's frame with the Event Map role layer fed that cut's elected
bricks. The causality contract (specs/event-map-causality-contract.md §7) is then
asserted on EMITTED labels only:

  * within a run of consecutive cuts that elect the SAME box (identical rounded
    rails + start date), every election-independent label committed by the
    earlier cut (``knowable`` inside it) must appear IDENTICALLY at the later
    cut — labels may arrive as bars print, but never mutate or vanish;
  * election-dependent labels (spring / lps) are frame-scoped by design and are
    reported, not asserted;
  * an election flip between cuts legitimately re-frames the whole read — it is
    reported as info and starts a new comparison run.

Labels are compared DATE-anchored (bars → session dates) because the live
two-year trim slides the frame's left edge between cuts (the contract's
left-edge rule made testable).

Hermetic: replays the committed marks fixture (tests/baselines/marks_corpus.parquet),
no network. Runtime ~2-4 minutes (dozens of real elections) — a dedicated step
like ``tools.marks_corpus --check``, not part of the default suite.

Usage:
    python -m tools.event_map_chronology            # report
    python -m tools.event_map_chronology --check    # exit 1 on any violation
"""
from __future__ import annotations

import sys

import pandas as pd

try:
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path()

from core.pipeline.evaluation import _prepare_eval_frame, _resolve_structure_context
from core.structure.event_map import read_role_labels
from tools.marks_corpus import _load_fixture, eval_windows, load_corpus, setup_key

# Sessions added on each side of the marked windows so the battery watches the
# labels as the story approaches, crosses, and leaves the marked entry.
_MARGIN_BEFORE = 3
_MARGIN_AFTER = 2


def _cut_positions(frame: pd.DataFrame, setup: dict) -> list[int]:
    windows = eval_windows(setup)
    if not windows:
        return []
    first = pd.Timestamp(min(w[0] for w in windows))
    last = pd.Timestamp(max(w[1] for w in windows))
    idx = frame.index
    inside = [i for i, ts in enumerate(idx) if first <= ts <= last]
    if not inside:
        return []
    lo = max(0, inside[0] - _MARGIN_BEFORE)
    hi = min(len(idx) - 1, inside[-1] + _MARGIN_AFTER)
    return list(range(lo, hi + 1))


def _labels_at_cut(frame: pd.DataFrame, pos: int):
    """(box_identity, committed_sigs, info) at one cut — or (None, None, reason)."""
    sliced = frame.iloc[: pos + 1]
    prepared = _prepare_eval_frame(sliced)
    if prepared is None:
        return None, None, "baseline"
    df, latest = prepared["df"], prepared["latest"]
    try:
        ctx = _resolve_structure_context(df, latest)
    except (KeyError, ValueError, IndexError, TypeError,
            ZeroDivisionError, AttributeError):
        return None, None, "eval-error"
    if ctx is None:
        return None, None, "no-structure"
    structure = ctx["structure"]
    box = structure.box
    atr = float(ctx["atr_for_zone"])
    roles = read_role_labels(df, box, atr,
                             spring=structure.spring, lps=structure.lps)

    dates = df.index
    identity = (round(float(box.R), 4), round(float(box.S), 4),
                str(dates[int(box.start_bar)].date()))

    def _d(bar: int) -> str:
        return str(dates[max(0, min(int(bar), len(dates) - 1))].date())

    committed = {}
    extras = {"election": [], "in_progress": 0}
    for lbl in roles["labels"]:
        if lbl["election_dependent"]:
            extras["election"].append((lbl["role"], _d(lbl["anchor_bar"])))
            continue
        if lbl["in_progress"]:
            extras["in_progress"] += 1
            continue
        sig = (lbl["role"], lbl["rail"], _d(lbl["describes"][0]),
               _d(lbl["describes"][1]), _d(lbl["anchor_bar"]),
               lbl["resolution"])
        committed[sig] = _d(lbl["knowable_bar"])
    return identity, committed, extras


def run(check: bool = False) -> bool:
    frames, _baseline = _load_fixture()
    setups = load_corpus()

    ok = True
    print("=" * 68)
    print("  EVENT MAP CHRONOLOGY - truncate-and-relabel over the marks corpus")
    print("=" * 68)
    for setup in setups:
        key = setup_key(setup)
        frame = frames.get(setup["ticker"])
        if frame is None or frame.empty:
            print(f"{key}: frame missing from fixture - rebuild it")
            ok = False
            continue
        positions = _cut_positions(frame.dropna(), setup)
        if not positions:
            print(f"{key}: marked window not inside the fixture frame")
            ok = False
            continue

        prev = None            # (pos, identity, committed)
        flips = 0
        structureless = 0
        violations: list[str] = []
        for pos in positions:
            identity, committed, extras = _labels_at_cut(frame.dropna(), pos)
            if identity is None:
                structureless += 1
                prev = None
                continue
            if prev is not None and prev[1] == identity:
                prev_pos, _, prev_committed = prev
                cut_date = str(frame.dropna().index[prev_pos].date())
                for sig, know in prev_committed.items():
                    got = committed.get(sig)
                    if got is None:
                        violations.append(
                            f"cut {cut_date}: committed label vanished at the "
                            f"next cut: {sig} (knowable {know})")
                    elif got != know:
                        violations.append(
                            f"cut {cut_date}: knowable date moved for {sig}: "
                            f"{know} -> {got}")
            elif prev is not None:
                flips += 1
            prev = (pos, identity, committed)

        n_cuts = len(positions)
        if violations:
            ok = False
            print(f"{key}: FAIL ({len(violations)} violations over {n_cuts} cuts)")
            for v in violations[:6]:
                print(f"    {v}")
        else:
            print(f"{key}: ok ({n_cuts} cuts, {structureless} structureless, "
                  f"{flips} election flips)")

    print()
    print("PASS - committed labels never mutated or vanished within a stable election."
          if ok else "FAIL - the tape re-wrote history; see violations above.")
    return ok


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="Truncate-and-relabel chronology battery over the marks corpus.")
    ap.add_argument("--check", action="store_true",
                    help="Exit 1 if any committed label mutated or vanished.")
    args = ap.parse_args()
    ok = run(check=args.check)
    if args.check:
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
