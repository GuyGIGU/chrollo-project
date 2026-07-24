"""Shared point-in-time replay layer (Calibration at Scale, Task 6).

ONE home for the jobs every mark-replay tool repeats, so the sealed-corpus
GATE (``tools.marks_corpus``) and
the agreement harness (Task 9) all measure through the same lens — four
slightly different definitions of "what the engine saw" would turn every
agreement number into an argument about tooling:

* ``resolve_frame`` — the faithful raw frame for a ticker with its source
  named honestly ("corpus fixture" first, calibration fixture when Task 7
  lands, else "5y cache"). A tool that silently replays a mark on rolled
  live data produces reports nobody can distrust in time.
* ``prepared_frame`` / ``snapped_election`` — the live-twin point-in-time
  prep (``_prepare_eval_frame`` + the ATR snapshot) and the day-snapped
  structure capture (elections are day-sensitive: BODI's flag-ON pair exists
  2026-04-15 and dies 04-16), folded out of the A/B renderer.
* ``flag_capture`` — the ONE self-restoring engine-flag toggle for
  rule-variant batches; a leaked flag mid-batch silently poisons every
  subsequent measurement in the run.

Gate vs instrument: this layer is shared UNDERNEATH the tools; verdict
logic, baselines and ratchets stay with their owners (EC-9 spirit).
Read-only: nothing live imports it.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager

import pandas as pd

try:  # works under both `python -m tools.x` and `python tools/x.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path()

from config import settings
from core.pipeline.downloads import _trim_to_period
from engine_alpha.evaluation import _prepare_eval_frame_with_reason
from engine_alpha.structure.narrative import read_structure

# Sealed-corpus fixture paths (written by `tools.marks_corpus --build-fixture`,
# read by every replay consumer). The corpus tool aliases these.
BASELINE_DIR = os.path.join(_PROJECT_ROOT, "tests", "baselines")
SEALED_FIXTURE_PARQUET = os.path.join(BASELINE_DIR, "marks_corpus.parquet")
SEALED_BASELINE_JSON = os.path.join(BASELINE_DIR, "marks_corpus_baseline.json")


def load_sealed_fixture() -> tuple[dict[str, pd.DataFrame], dict]:
    """The committed sealed-corpus frames + ratchet baseline (hermetic)."""
    if not os.path.exists(SEALED_FIXTURE_PARQUET) or not os.path.exists(SEALED_BASELINE_JSON):
        raise FileNotFoundError(
            "No marks-corpus fixture - run `python -m tools.marks_corpus "
            "--build-fixture` first (requires a populated data cache)."
        )
    data = pd.read_parquet(SEALED_FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    with open(SEALED_BASELINE_JSON, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    level0 = set(data.columns.get_level_values(0))
    frames = {t: data[t].dropna() for t in level0}
    return frames, baseline


def fixture_frame(frames: dict, key: str, ticker: str | None = None):
    """The sealed-fixture frame for one baseline setup, or None.

    Digest-graduated setups (Guided List, 2026-07-24) freeze under their FULL
    setup key — two marks on one ticker are two distinct drawn bases — while
    legacy setups freeze under the bare ticker. The ONE lookup every fixture
    consumer shares (gate, chronology battery, election tests)."""
    df = frames.get(key)
    if df is not None:
        return df
    return frames.get(ticker if ticker is not None else key.split(":")[0])


_LIVE_PANEL: pd.DataFrame | None = None


def _live_panel() -> pd.DataFrame:
    """The live 5y cache, loaded ONCE per process and sliced per ticker —
    never re-read per unit of work (the A/B tool's old per-mark reload does
    not generalize to a harness over hundreds of marks)."""
    global _LIVE_PANEL
    if _LIVE_PANEL is None:
        _LIVE_PANEL = pd.read_parquet(settings.CACHE_FILENAME,
                                      engine=settings.PARQUET_ENGINE)
    return _LIVE_PANEL


def resolve_frame(ticker: str, *, sealed: dict | None = None):
    """(raw_frame, source_label) for ``ticker``, or (None, reason).

    Source order and labels are decided HERE, once: the sealed corpus fixture
    (pass a preloaded dict to avoid re-reading it per call), then the live 5y
    cache. FROZEN calibration frames are deliberately NOT resolved here —
    their policy is frozen-or-refuse (a mark must never silently replay on
    fallback data), and ``webapp.backend.frame_store.load_frame`` (digest-
    resolved) is their one door; the agreement harness goes through it.
    """
    if sealed is None:
        try:
            sealed, _ = load_sealed_fixture()
        except FileNotFoundError:
            sealed = {}
    raw = sealed.get(ticker)
    if raw is not None:
        return raw, "corpus fixture"
    panel = _live_panel()
    if ticker not in set(panel.columns.get_level_values(0)):
        return None, "not in corpus fixture nor cache"
    return panel[ticker].dropna(), "5y cache"


def prepared_frame_with_reason(
    raw: pd.DataFrame, as_of,
) -> tuple[tuple[pd.DataFrame, float] | None, tuple[str, dict] | None]:
    """The faithful live-twin frame at one eval date, reasoned: slice to
    ``as_of``, run the ONE reasoned prep (baseline filters -> 2y trim -> ATR
    columns), take the live ATR snapshot. Returns ``((df, atr), None)`` on
    pass or ``(None, (gate, samples))`` naming the FIRST failing universe
    gate (Move 4 — a refusal is a named operational outcome, never a bare
    silence). The reasonless ``prepared_frame`` derives from this."""
    prep, reason = _prepare_eval_frame_with_reason(raw.loc[:pd.Timestamp(as_of)])
    if prep is None:
        return None, reason
    df = prep["df"]
    atr = float(df.iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET]["ATR_10"])
    return (df, atr), None


def prepared_frame(raw: pd.DataFrame, as_of) -> tuple[pd.DataFrame, float] | None:
    """The faithful live-twin frame at one eval date (reason discarded)."""
    prep, _ = prepared_frame_with_reason(raw, as_of)
    return prep


def refusal_scan(raw: pd.DataFrame, sessions) -> list[tuple[str, str]]:
    """Named universe-prep refusals across ``sessions`` — one ``(session ISO,
    gate slug)`` per refused session, in walk order. The reason vocabulary is
    the baseline gate's frozen first-fail contract (bars, price, vol50, sma50,
    sma200, yoy). Inert evidence only: produced for harness reports; no
    election, gate, or scoring path may ever branch on it."""
    out: list[tuple[str, str]] = []
    for ts in sessions:
        prep, reason = prepared_frame_with_reason(raw, ts)
        if prep is None and reason is not None:
            out.append((pd.Timestamp(ts).strftime("%Y-%m-%d"), reason[0]))
    return out


@contextmanager
def flag_capture(**overrides):
    """Toggle engine flags for one capture, guaranteed restored — even on a
    crash mid-capture. Refuses unknown flag names loudly: a typo'd override
    that silently does nothing measures the wrong engine.

    ALL names are validated before ANY flag is set — a typo in the second
    name of a multi-flag override must not leave the first one flipped with
    the restoring finally never entered."""
    for name in overrides:
        if not hasattr(settings, name):
            raise AttributeError(f"flag_capture: settings.{name} does not exist")
    prior = {name: getattr(settings, name) for name in overrides}
    try:
        for name, value in overrides.items():
            setattr(settings, name, value)
        yield
    finally:
        for name, value in prior.items():
            setattr(settings, name, value)


def read_structure_under(df: pd.DataFrame, atr: float, overrides: dict):
    """One structure read under the given flag overrides (self-restoring)."""
    with flag_capture(**overrides):
        return read_structure(df, atr)


# The ONE day-snap policy: how far a replay may walk back from a requested
# eval day when nothing elects there. Every instrument (A/B render, agreement
# harness) imports THIS value; changing it is a deliberate re-freeze event.
SNAP_BACK_SESSIONS = 5


def snapped_election(raw: pd.DataFrame, span_end, variants: list[dict],
                     *, snap_back: int = SNAP_BACK_SESSIONS):
    """The reads at the last session <= ``span_end`` where ANY variant elects
    a structure — or, when none elects there, the most recent prior session
    (within ``snap_back``) where one does. Elections are day-sensitive; the
    A/B must show the read where it EXISTS, with the snap named honestly.

    Returns ``((df, atr, [structure per variant]), eval_ts, snapped_k)`` or
    ``None`` when the prep refuses every candidate session. ``snapped_k`` is
    0 on the requested day; callers word their own note from it.
    """
    idx = raw.index[raw.index <= pd.Timestamp(span_end)]
    first = None
    for k, ts in enumerate(reversed(idx[-(snap_back + 1):])):
        prep = prepared_frame(raw, ts)
        if prep is None:
            continue
        df, atr = prep
        reads = [read_structure_under(df, atr, v) for v in variants]
        if first is None:
            first = ((df, atr, reads), ts, k)
        if any(s is not None for s in reads):
            return (df, atr, reads), ts, k
    return first


# ------------------------------------------------------------------
# The ONE fired-policy window (pops-up-live acceptance bar)
# ------------------------------------------------------------------
# Owned by the replay seam so the agreement harness (--fired) and the
# marks-corpus ratchet grade the SAME criterion — one scoreboard, one ground
# truth. Moved here verbatim from tools/calibration_harness.py 2026-07-24
# (Guided List graduation, PLAN-guided-list-gap-breach Task 1); the harness
# re-exports for report stamping. Changing any of these values or the window
# semantics is a deliberate re-freeze event, never a tuning knob.
FIRED_WINDOW_SESSIONS = 10   # default backward window ending at the mark's as-of
FIRED_EVENT_TAIL_SESSIONS = 5    # sessions walked past each marked-LPS end
FIRED_WALK_MAX_SESSIONS = 40     # hard cap per mark; oldest kept, clamp named


def full_live_basis(frozen: pd.DataFrame, ts) -> bool:
    """Does ``frozen.loc[:ts]`` contain the FULL trailing daily-structure
    window the nightly scan evaluated at ``ts``? The live eval trims the 5y
    cache to ``DAILY_STRUCTURE_PERIOD`` behind each session and the root walk
    is left-edge-sensitive, so a slice the trim cannot cut is thinner than
    live — unless the frame the trim cannot cut even at its END is simply the
    ticker's full (young-listing) history, in which case live saw the very
    same bars and every session is faithful."""
    sliced = frozen.loc[:ts]
    trimmed = _trim_to_period(sliced, settings.DAILY_STRUCTURE_PERIOD)
    if trimmed.index[0] > sliced.index[0]:
        return True   # the trim cut lead-in -> the live window is fully present
    full = _trim_to_period(frozen, settings.DAILY_STRUCTURE_PERIOD)
    return len(full) == len(frozen)


def fired_window_sessions(frozen: pd.DataFrame, as_of, lps_spans,
                          knowable_from=None) -> tuple[list, str | None]:
    """The fair pops-up-live window as frame sessions ending at ``as_of``.

    The walk covers where the setup was LIVE, not just when the mark was
    typed: ``knowable_from`` onward when declared (v1 override); otherwise
    the union of each marked-LPS span in ``lps_spans`` (``[start, end]``
    pairs) extended ``FIRED_EVENT_TAIL_SESSIONS`` past its end, plus the
    last ``FIRED_WINDOW_SESSIONS`` sessions before the as-of. Walked
    oldest-first so the reported fire is the FIRST night the pick would have
    appeared. Every window is CLAMPED to the frame's faithful-basis zone
    (``full_live_basis``) and capped at ``FIRED_WALK_MAX_SESSIONS`` keeping
    the OLDEST sessions. Returns ``(sessions, clamp_note|None)`` — every
    clamp is NAMED, never silent."""
    idx = frozen.index[frozen.index <= pd.Timestamp(as_of)]
    if knowable_from:
        sessions = list(idx[idx >= pd.Timestamp(knowable_from)])
    else:
        picked = set(idx[-FIRED_WINDOW_SESSIONS:])
        for start, end in lps_spans:
            start = pd.Timestamp(start)
            end = pd.Timestamp(end or start)
            in_span = idx[(idx >= start) & (idx <= end)]
            picked.update(in_span)
            after = idx[idx > end]
            picked.update(after[:FIRED_EVENT_TAIL_SESSIONS])
        sessions = sorted(picked)
    notes = []
    faithful = [ts for ts in sessions if full_live_basis(frozen, ts)]
    if len(faithful) != len(sessions):
        notes.append(
            f"walked {len(faithful)}/{len(sessions)} sessions — the frozen "
            f"frame's lead-in cannot reproduce the live "
            f"{settings.DAILY_STRUCTURE_PERIOD} basis before "
            + (faithful[0].strftime("%Y-%m-%d") if faithful else "any session"))
    if len(faithful) > FIRED_WALK_MAX_SESSIONS:
        notes.append(f"walk capped at the oldest {FIRED_WALK_MAX_SESSIONS} "
                     f"of {len(faithful)} sessions")
        faithful = faithful[:FIRED_WALK_MAX_SESSIONS]
    return faithful, ("; ".join(notes) or None)
