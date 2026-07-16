"""Shared point-in-time replay layer (Calibration at Scale, Task 6).

ONE home for the jobs every mark-replay tool repeats, so the sealed-corpus
GATE (``tools.marks_corpus``), the A/B renderer (``tools.band_rails_ab``) and
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
from engine_alpha.evaluation import _prepare_eval_frame
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


def prepared_frame(raw: pd.DataFrame, as_of) -> tuple[pd.DataFrame, float] | None:
    """The faithful live-twin frame at one eval date: slice to ``as_of``, run
    ``_prepare_eval_frame`` (baseline filters -> 2y trim -> ATR columns), take
    the live ATR snapshot. None when the prep refuses the slice."""
    prep = _prepare_eval_frame(raw.loc[:pd.Timestamp(as_of)])
    if prep is None:
        return None
    df = prep["df"]
    atr = float(df.iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET]["ATR_10"])
    return df, atr


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
