"""Shared point-in-time replay layer (Calibration at Scale, Task 6).

ONE home for the jobs every mark-replay consumer repeats — the sealed-corpus
GATE (``tools.regression.marks_corpus``), the agreement harness and the
workbench chips (both through ``domains.calibration.grading``), the chronology
battery (``tools.audits.event_map_chronology``), the election/shelf instruments
and tests, and the backend calibration read paths (``domains.calibration``
router + chips) — so two definitions of "what the engine saw" can never
turn a number into an argument about tooling. It is production code (moved
out of ``tools/`` on 2026-09-24) because the backend imports it:

* ``prepared_frame`` / ``prepared_frame_with_reason`` / ``snapped_election``
  — the live-twin point-in-time prep (reasoned: a refusal NAMES its first
  failing universe gate) and the day-snapped structure capture (elections
  are day-sensitive: BODI's flag-ON pair exists 2026-04-15 and dies 04-16).
* ``flag_capture`` — the ONE self-restoring engine-flag toggle for
  rule-variant batches; a leaked flag mid-batch silently poisons every
  subsequent measurement in the run.
* ``fired_window_sessions`` + the ``FIRED_*`` policy and frozen scalars —
  the ONE pops-up-live acceptance window the gate and the harness both grade;
  ``fired_window_walk`` — every fire in that window on one frozen frame, the
  walk the junk corpus and the fleet fixture grade (build step 1, 2026-09-13).
* ``load_sealed_fixture`` / ``fixture_frame`` — the sealed-corpus basis and
  its one lookup rule.

FROZEN calibration frames are deliberately NOT resolved here — their policy
is frozen-or-refuse (a mark must never silently replay on fallback data) and
``webapp.backend.frame_store.load_frame`` (digest-resolved) is their one door.

Gate vs instrument: this layer is shared UNDERNEATH the consumers; verdict
logic, baselines and ratchets stay with their owners (EC-9 spirit). Every
helper is read-only; live backend READ paths import this module.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager

import pandas as pd

from config import settings
from core.pipeline.market_data.downloads import _trim_to_period
from engine_alpha.evaluation import EVAL_ERROR, _evaluate_ticker, _prepare_eval_frame_with_reason
from engine_alpha.structure.box.gate_margins import (
    count_allowed,
    count_needed,
    outside_allowed,
)
from engine_alpha.structure.metrics.indicators import calculate_atr
from engine_alpha.structure.narrative.reader import read_structure

# count_needed / count_allowed / outside_allowed are re-exported here for the
# sibling instruments (near-miss lane Task 5): the ONE integer translation of
# the gate's fraction thresholds lives in engine_alpha.structure.box.gate_margins
# (EC-3); instruments import it from THIS seam so tooling never grows a twin.
_COUNT_MATH = (count_needed, count_allowed, outside_allowed)

# Sealed-corpus fixture paths (written by `tools.regression.marks_corpus --build-fixture`,
# read by every replay consumer). The corpus tool aliases these.
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BASELINE_DIR = os.path.join(_PROJECT_ROOT, "tests", "baselines")
SEALED_FIXTURE_PARQUET = os.path.join(BASELINE_DIR, "marks_corpus.parquet")
SEALED_BASELINE_JSON = os.path.join(BASELINE_DIR, "marks_corpus_baseline.json")


def load_sealed_fixture() -> tuple[dict[str, pd.DataFrame], dict]:
    """The committed sealed-corpus frames + ratchet baseline (hermetic)."""
    if not os.path.exists(SEALED_FIXTURE_PARQUET) or not os.path.exists(SEALED_BASELINE_JSON):
        raise FileNotFoundError(
            "No marks-corpus fixture - run `python -m tools.regression.marks_corpus "
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
    setup key — two marks on one ticker are two distinct drawn bases. Pass
    ``ticker`` ONLY for a legacy (non-digest) setup: it is the bare-ticker
    fallback for the old one-frame-per-ticker freeze. A graduated setup whose
    keyed frame is missing must surface as MISSING (None) — never silently
    borrow a same-ticker sibling's basis. The ONE lookup every fixture
    consumer shares (gate, chronology battery, election tests)."""
    df = frames.get(key)
    if df is not None or ticker is None:
        return df
    return frames.get(ticker)


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


# ------------------------------------------------------------------
# Marked-window instrument helpers (ONE definition — EC-3)
# ------------------------------------------------------------------
# Shared by the marked-window instruments (shelf harness, stat card) so two
# reports over the same mark can never measure different windows or a
# different ATR. The setting always exists; no silent default.
MARK_ATR_OFFSET = settings.STRUCTURE_ATR_SAMPLE_OFFSET


def session_pos(index: pd.DatetimeIndex, date_str, *, boundary: str = "start") -> int:
    """Resolve a mark date to a frame position. An exact session match wins;
    a non-session date resolves INWARD for its boundary role — a start
    boundary to the first session at-or-after, an END boundary to the last
    session at-or-before (resolving an end forward would silently add a
    post-mark bar to the measured window). Clamped to the frame."""
    ts = pd.Timestamp(str(date_str))
    p = int(index.get_indexer([ts])[0])
    if p != -1:
        return p
    p = int(index.searchsorted(ts))
    if boundary == "end":
        p -= 1
    return max(0, min(p, len(index) - 1))


def enrich_marked_frame(df: pd.DataFrame) -> pd.DataFrame:
    """The instrument enrichment (ATR/volume/spread columns) on a copy of a
    frozen frame — the columns the engine's measure functions expect."""
    df = df.copy()
    df["ATR_10"] = calculate_atr(df, 10)
    df["ATR_50"] = calculate_atr(df, 50)
    df["Vol_50"] = df["Volume"].rolling(50).mean()
    df["Spread"] = df["High"] - df["Low"]
    return df


def drawn_box_window(raw: pd.DataFrame, box_start, box_end):
    """The operator's drawn-box window on a frozen frame, plus the instrument
    ATR — the ONE derivation every drawn-geometry instrument shares (EC-13):
    enrich, slice to the box end (end boundaries resolve inward), take ATR_10
    at ``MARK_ATR_OFFSET``, slice to the box start. Raises ``ValueError`` when
    the ATR is unavailable — a mark instrument fails loudly, never guesses."""
    frozen = enrich_marked_frame(raw)
    end = session_pos(frozen.index, box_end, boundary="end")
    df = frozen.iloc[: end + 1]
    if len(df) < MARK_ATR_OFFSET + 1:
        raise ValueError(f"too few bars before box_end {box_end} ({len(df)})")
    atr_val = df["ATR_10"].iloc[-MARK_ATR_OFFSET]
    if pd.isna(atr_val) or float(atr_val) <= 0:
        raise ValueError(f"ATR unavailable at box_end {box_end}")
    bs = session_pos(df.index, box_start)
    return df.iloc[bs:], float(atr_val)


def judged_window(df: pd.DataFrame, cand_start: int) -> pd.DataFrame:
    """The exact window the pair election judged a strict candidate on:
    ``validate_equilibrium`` enumerates over ``df.iloc[:-STRUCTURE_EDGE_SKIP_BARS]``
    (the box as of ~5 bars ago, uncontaminated by the live edge), so a
    candidate's window is cand_start .. len(df) - skip — NOT the frame end.
    The junk self-check against the trace's own detail numbers certifies this
    slice; a drift there voids the run. Promoted here verbatim from
    ``tools.research.rail_margin_evidence`` (near-miss lane Task 5) — the third
    sibling instrument imports it from this seam."""
    skip = settings.STRUCTURE_EDGE_SKIP_BARS
    end = len(df) - skip if len(df) > skip else len(df)
    return df.iloc[cand_start:end]


@contextmanager
def flag_capture(**overrides):
    """Toggle engine flags for one capture, guaranteed restored — even on a
    crash mid-capture. Refuses unknown flag names loudly: a typo'd override
    that silently does nothing measures the wrong engine.

    ALL names are validated before ANY flag is set — a typo in the second
    name of a multi-flag override must not leave the first one flipped with
    the restoring finally never entered.

    The save/restore core DELEGATES to the engine's one scoped override
    (``htf.window_override``) — the instrument and the live lane enter a
    shared read through the SAME mechanism, so a behavioral change to it can
    never diverge the census's measured read from the lane's live read
    (2026-08-17 review, Fowler; EC-3 — this wrapper keeps only its
    validate-all-names-first loudness)."""
    for name in overrides:
        if not hasattr(settings, name):
            raise AttributeError(f"flag_capture: settings.{name} does not exist")
    from engine_alpha.structure.context.htf import window_override
    with window_override(dict(overrides)):
        yield


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
# truth. Moved here verbatim from tools/calibration/calibration_harness.py 2026-07-24
# (Guided List graduation, PLAN-guided-list-gap-breach Task 1); the harness
# re-exports for report stamping. Changing any of these values or the window
# semantics is a deliberate re-freeze event, never a tuning knob.
FIRED_WINDOW_SESSIONS = 10   # default backward window ending at the mark's as-of
FIRED_EVENT_TAIL_SESSIONS = 5    # sessions walked past each marked-LPS end
FIRED_WALK_MAX_SESSIONS = 40     # hard cap per mark; oldest kept, clamp named

# Frozen market scalars for replays (scoring-only inputs — they shape
# Score/Tier, never the fire/no-fire decision), pinned HERE so the gate and
# the harness replay the same deterministic basis with no SPY/breadth history
# alongside the frozen frame. Frozen with the baselines: moving either is a
# deliberate re-freeze event.
FROZEN_BREADTH = 0.5
FROZEN_SPY_6M = 0.0


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


def fired_window_walk(ticker: str, frozen: pd.DataFrame, spy_6m: float,
                      breadth, as_of=None, *, evaluate=None) -> dict:
    """Every fire in the fired-policy window of one frozen frame — the ONE
    window walk the junk corpus (``tools.regression.negative_corpus``) and the fleet
    fixture (``tools.regression.shadow_diff``) grade, so neither reads one day per
    frame while the marks ratchet reads the window (final method, build
    step 1, 2026-09-13). Unlike the ratchet's ``_replay_setup`` this does
    NOT stop at the first fire: a precision guard needs every fire day, and
    the fleet guard pins the first and the last.

    Walks ``fired_window_sessions(frozen, as_of, [])`` — the last
    ``FIRED_WINDOW_SESSIONS`` frame sessions ending at ``as_of`` (default:
    the frame's last session), clamped to the faithful-basis zone with the
    clamp NAMED — oldest first, slicing ``frozen.loc[:ts]`` and skipping
    slices under 200 rows. Returns ``{"window": [first, last] (ISO),
    "clamp_note": str|None, "fires": [{"day": ISO, "result": dict}],
    "errors": [{"day": ISO}], "evaluated": int}`` (``evaluated`` counts the
    days actually run, so a report can never claim a window it skipped);
    consumers project the raw result
    themselves (Score/Tier, the shadow guard's canonical fields).

    ``evaluate`` defaults to the pipeline's ``_evaluate_ticker`` (imported
    from ``engine_alpha.evaluation``, the same function, so this production
    module does not load the scan conductor); a consumer
    passes its own module-bound name so its tests can monkeypatch that
    binding exactly as they always have."""
    evaluate = evaluate or _evaluate_ticker
    as_of = frozen.index[-1] if as_of is None else as_of
    sessions, note = fired_window_sessions(frozen, as_of, [])
    out = {"window": [sessions[0].date().isoformat(), sessions[-1].date().isoformat()]
           if sessions else [],
           "clamp_note": note, "fires": [], "errors": [], "evaluated": 0}
    for ts in sessions:
        sliced = frozen.loc[:ts]
        if len(sliced) < 200:
            continue
        out["evaluated"] += 1
        result = evaluate(ticker, sliced, spy_6m, breadth)
        day = ts.date().isoformat()
        if result is EVAL_ERROR:
            out["errors"].append({"day": day})
        elif result is not None:
            out["fires"].append({"day": day, "result": result})
    return out
