"""
Operator-marks acceptance gate (Event Map) - proves operator-marked MUST-fire
setups fire while their marked entry windows are live, and ratchets progress.

This is the must-FIRE sibling of ``tools.regression.negative_corpus`` (must-NOT-fire) and
the acceptance harness for the Event Map plan (docs/archive/PLAN-event-tape.md,
Task 1): the
corpus files under ``docs/marks/`` are the operator's ground-truth dissections
(EC-7: immutable test specs - a failing case is fixed in the ENGINE, never by
editing a mark, widening a window, or reinterpreting trigger rules), and each
setup is replayed point-in-time through the SAME per-ticker evaluation the
nightly screener runs, entirely offline from a committed fixture.

The matcher: a setup is a HIT when the pipeline fires on ANY session of its
fair window. The population is ONE kind of setup — digest-GRADUATED marks
(the Guided List, 2026-07-24: every setup carries ``frame_digest``, ``as_of``
and a ``trigger``, sealed through the EC-9 export) — graded on the ONE
fired-policy window owned by the replay seam
(``core.calibration.replay.fired_window_sessions``: marked-LPS spans + tail, union the
trailing as-of window, faithful-basis clamped, every clamp NAMED) — the SAME
pops-up-live criterion the agreement harness scores, so the gate and the
operator's scoreboard can never tell two different stories. The pre-Guided-
List legacy window machinery was deleted with its population (council review
2026-07-24); ``docs/marks/part2_2026-07.json`` stays on disk as EC-7 history
but does not gate. These semantics FREEZE with the baseline: changing them is
an EC-7 event, not a tuning knob.

**The population TRACKS the operator's drawings (his ruling, 2026-09-08).** It used
to be a sealed snapshot behind a human-gated export, and the measured result was a
standard demanding three marks he had DELETED (two as permanent expected-misses)
while five he had drawn were tested by nothing. ``--check`` now FAILS, not advises,
when the corpus no longer matches his live marks DB — on a machine that has one; an
absent DB is not drift, since CI grades the committed fixture.

The baseline is still a RATCHET, and a verdict belongs to ONE drawing
(``setup_digest``: rails, LPS spans, trigger, knowable-from, frame):
  * an UNCHANGED drawing keeps its verdict - a pinned hit that stops firing
    FAILS, and an expected miss that starts firing also FAILS, loudly (strict-
    xfail: a silent behavior change is never good news until a human looks);
  * a REDRAWN or newly DRAWN mark voids its old verdict, because that verdict was
    about a chart that no longer exists. Re-measured; if the engine cannot read
    it, it enters ``NEW_MARK_STAGE`` - pinned against silent conversion, reported
    separately as awaiting his review, and never blocking the rebuild. Drawing a
    chart must not turn his gate red before he has looked at it;
  * a DELETED mark leaves, and its ``STAGE_TAGS`` excuse leaves with it.

What did NOT change: nobody may make a red gate green by moving the target (EC-7).
He may redraw; an agent may not edit a mark to pass a test — and since a redrawn
mark's verdict is voided rather than carried, editing one cannot launder a
regression into a pass.

The FULL replay walks every window session (~150 evals, minutes) - too slow for
the default suite, so it is the dedicated CI / per-stage acceptance step
(``python -m tools.regression.marks_corpus --check``), like the hermetic seed-recall gate.
``tests/regression/test_marks_corpus.py`` keeps the plumbing honest on every pytest run.

Usage:
    python -m tools.regression.marks_corpus --build-fixture   # per-stage re-freeze, from the frozen frame store
    python -m tools.regression.marks_corpus --check           # fail (exit 1) on any ratchet break
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone

import pandas as pd

try:  # works under both `python -m tools.regression.marks_corpus` and `python tools/regression/marks_corpus.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path

# backend=True: the graduated build loads frozen frames (frame_store) and the
# loader validates tickers through the shared strict grammar (marks_validity)
# — both pure, root-safe backend modules, lazily imported where used.
_PROJECT_ROOT = configure_path(backend=True)

from config import settings
from engine_alpha.evaluation import EVAL_ERROR
from engine_alpha.freeze.manifest import manifest_hash
from core.pipeline.screening.screener import _evaluate_ticker

# The shared replay layer owns fixture paths + loading (Task 6 fold).
# No dual-form fallback needed: configure_path() above already put the repo
# root on sys.path, so `core.calibration.replay` resolves under both documented
# invocations.
from core.calibration.replay import (
    BASELINE_DIR as _BASELINE_DIR,
    FIRED_EVENT_TAIL_SESSIONS,
    FIRED_WALK_MAX_SESSIONS,
    FIRED_WINDOW_SESSIONS,
    FROZEN_BREADTH as _FROZEN_BREADTH,
    FROZEN_SPY_6M as _FROZEN_SPY_6M,
    SEALED_BASELINE_JSON as _BASELINE_JSON,
    SEALED_FIXTURE_PARQUET as _FIXTURE_PARQUET,
    fired_window_sessions,
    fixture_frame,
    load_sealed_fixture,
)

# The operator-marks corpus files (EC-7: append-only ground truth under docs/marks/).
# Population re-pointed 2026-07-24 (operator GO, PLAN-guided-list-gap-breach Task 1):
# the Guided List (33 setups graduated from the calibration DB via
# tools.calibration.guided_list_export, fingerprint-pinned) is THE gate population.
# part2_2026-07.json stays on disk as EC-7 history but no longer gates —
# one scoreboard, one ground truth.
CORPUS_FILES: tuple[str, ...] = (
    os.path.join(_PROJECT_ROOT, "docs", "marks", "guided_list_2026-07.json"),
)

# Second-window grace for the CHRONOLOGY battery's entry windows: an lps2 span
# has no second trigger, so its window runs this many sessions past the span
# end ("by the trigger"). The GATE itself never uses these windows — graduated
# setups are graded on the replay seam's fired-policy window. Frozen (EC-7).
NULL_TRIGGER_GRACE_SESSIONS = 2

# Build-order stage expected to convert each known miss (docs/archive/PLAN-event-tape.md
# ratchet). Verified at freeze time: the replayed miss-set must equal this key
# set exactly, so the baseline can never freeze an unexplained miss.
STAGE_TAGS: dict[str, str] = {
    # Guided List population (operator GO 2026-07-24; PLAN-guided-list-gap-breach).
    # Keys are FULL setup keys (ticker:label) — ORMP/NGL carry two instances
    # with different outcomes, so a bare-ticker tag would misapply.
    # Re-tagged 2026-07-24 after Tasks 3+4 falsified their original stages
    # (engagement-respect and commit-the-cause both tested + REJECTED — see
    # strategy_alpha.md): NKTR + EGBN belong to the rail-PLACEMENT family
    # (wick-anchored candidate rails inflate width / sit at the body level), a
    # named FUTURE stage outside this program's remaining tasks.
    # Task 6 (2026-07-24) closed the lps-envelope stage with a NO-MOVES
    # calibration answer: the marked-shelf terminal-turn envelope median is
    # 0.0 (his shelves genuinely rest), ORMP-2/PKE marked shelves PASS the
    # detector at the DRAWN rails, and NOK's launch-gate case is n=1. Every
    # chart-readable miss belongs to ONE family — rail-placement (the engine
    # anchors candidate rails at wick extremes / the body level where the operator
    # anchors body levels / the ceiling) — the named next program. SKYT is a
    # universe-gate exclusion (below SMA50 on 9/10 walked sessions), not a
    # chart-reading gap; converting it is an operator strategy decision.
    # THE RAIL PROGRAM EXECUTED 2026-07-25 (docs/rail_program_close_2026-07.md):
    # every margin lever AND the cluster-rail statistic answered NO under a
    # pre-registered protocol — these tags now mark CORRECT misses under
    # current doctrine (tested-DEAD; see strategy_alpha.md), not pending work.
    # Converting any of them requires an operator ruling or a new insight,
    # never a re-run of the tested levers.
    # STORY POOL LIVE 2026-07-26 (the "new insight" path taken): the ruled
    # narrative form converted NKTR:2026-04-10 + YPF:2026-05-18 (operator
    # eyeball passed; docs/event_map_program_2026-07.md) — tags removed at
    # the deliberate 26 -> 28 reseal. EGBN stays rail-placement: its ADMISSION
    # is certain but its wick-anchored candidate rails die upstream.
    # 2026-09-08: ORMP:2026-05-08 and PKE:2026-02-24 were DELETED from this dict
    # with the marks themselves. The operator had deleted both drawings from his
    # calibration DB, but the sealed corpus still carried them — so the engine
    # was being permanently EXCUSED for missing two charts that were no longer
    # ground truth. That is the concrete thing his "always test against the
    # updated marks" ruling fixed. A tag whose mark has left is now simply
    # unused; it does not need pruning to keep the build honest, but leaving one
    # here would re-assert a claim about a chart nobody stands behind.
    "EGBN:2026-01-15": "rail-placement",
    "NOK:2026-02-17": "rail-placement",
    "SKYT:2026-04-13": "universe-gate",
}

# The stage a mark carries when the operator has just drawn it and the engine
# cannot read it yet. It is NOT an accepted miss: it is pinned so it cannot start
# firing unannounced, and reported separately so it never inflates the
# "expected misses" count into looking like a settled question.
NEW_MARK_STAGE = "unreviewed-new-mark"

# Corpus schema: every key a graduated setup may carry (the EC-9 export's
# exact output shape). An unrecognized key FAILS the load (a typo'd mark
# silently skipped would shrink the acceptance set). The retired legacy
# grammar (bc/ar/springs/last_support/trigger_alt/…) was deleted with its
# population; part2_2026-07.json is EC-7 history, not a loadable input.
_REQUIRED_KEYS = ("ticker", "source", "lps", "trigger", "rails_drawn")
_ALLOWED_KEYS = frozenset({
    "ticker", "setup", "source", "notes",
    "lps", "lps2", "trigger", "rails_drawn",
    # Guided List graduation provenance: the frozen as-drawn basis. A setup
    # carrying frame_digest freezes from calibration_frames/ by digest (the
    # exact bars the operator marked), never from a live re-fetch.
    "as_of", "frame_digest", "knowable_from",
})
_DATE_SPAN_KEYS = ("lps", "lps2")
_DATE_SCALAR_KEYS = ("trigger", "as_of", "knowable_from")


def _parse_date(value: str, ctx: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"marks corpus: {ctx} is not an ISO date: {value!r}")


def _ticker_re():
    """The ONE strict ticker grammar (marks_validity.TICKER_RE, pure module) —
    lazy so the hermetic loader tests don't pay a backend import until a
    ticker is actually validated."""
    from marks_validity import TICKER_RE
    return TICKER_RE


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
            ticker = raw["ticker"]
            if not (isinstance(ticker, str) and _ticker_re().match(ticker)):
                raise ValueError(f"marks corpus: {ctx} ticker fails the strict "
                                 f"grammar: {ticker!r} (it becomes an identity "
                                 "key and a frame filename — rejected, never sanitized)")
            for key in _DATE_SPAN_KEYS:
                if raw.get(key) is not None:
                    span = raw[key]
                    if not (isinstance(span, list) and len(span) == 2):
                        raise ValueError(f"marks corpus: {ctx}.{key} must be a [start, end] pair")
                    lo, hi = (_parse_date(v, f"{ctx}.{key}") for v in span)
                    if lo > hi:
                        raise ValueError(f"marks corpus: {ctx}.{key} start after end")
            for key in _DATE_SCALAR_KEYS:
                if raw.get(key) is not None:
                    _parse_date(raw[key], f"{ctx}.{key}")
            if raw.get("frame_digest") and not raw.get("as_of"):
                raise ValueError(f"marks corpus: {ctx} carries frame_digest but no "
                                 "as_of - the drawn basis is unaddressable")
            rails = raw["rails_drawn"]
            if not (isinstance(rails, dict) and {"R", "S"} <= set(rails)):
                raise ValueError(f"marks corpus: {ctx}.rails_drawn needs R and S")
            r, s = rails.get("R"), rails.get("S")
            if not (isinstance(r, (int, float)) and isinstance(s, (int, float))
                    and r == r and s == s and float(r) > float(s) > 0):
                raise ValueError(f"marks corpus: {ctx}.rails_drawn must be ordered "
                                 f"positive numbers with R above S (got R={r!r} S={s!r})")
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


def corpus_provenance(paths: tuple[str, ...] = CORPUS_FILES) -> dict:
    """The graduation provenance embedded in the corpus file(s) (population,
    pinned marks fingerprint, authorization) - passed through into the frozen
    baseline so 'which ground truth' is answerable from either artifact.

    REFUSES when more than one file carries a provenance block: a last-write-
    wins merge would stamp one file's fingerprint over the whole gate,
    misattributing half the setups. Extending to a per-file provenance list is
    a deliberate schema change made WHEN a second graduation lands."""
    carriers: list[tuple[str, dict]] = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        if doc.get("_provenance"):
            carriers.append((os.path.basename(path), doc["_provenance"]))
    if len(carriers) > 1:
        raise ValueError(
            "marks corpus: multiple corpus files carry _provenance blocks "
            f"({[name for name, _ in carriers]}) - extend corpus_provenance to "
            "a per-file record before freezing over a multi-graduation corpus")
    return carriers[0][1] if carriers else {}


def eval_windows(setup: dict) -> list[tuple[date, date, int]]:
    """The marked entry window(s) as (start, end, grace_sessions) triples —
    consumed by the CHRONOLOGY battery only (the gate grades on the replay
    seam's fired-policy window). LPS start -> trigger (inclusive); an lps2
    span contributes its own window with grace past its end (it carries no
    second trigger). A second window fully inside the first collapses away.
    Frozen semantics (EC-7)."""
    lps_start = _parse_date(setup["lps"][0], "lps[0]")
    windows = [(lps_start, _parse_date(setup["trigger"], "trigger"), 0)]
    if setup.get("lps2"):
        second = (_parse_date(setup["lps2"][0], "lps2[0]"),
                  _parse_date(setup["lps2"][1], "lps2[1]"),
                  NULL_TRIGGER_GRACE_SESSIONS)
        first = windows[0]
        if not (second[0] >= first[0] and second[1] <= first[1]):
            windows.append(second)
    return windows


# ------------------------------------------------------------------
# Check (hermetic; reads only the committed fixture + baseline)
# ------------------------------------------------------------------
def _load_fixture() -> tuple[dict[str, pd.DataFrame], dict]:
    # Preserved name: the implementation moved DOWN into the shared replay
    # layer (Task 6) so the gate and the instruments load the same fixture.
    return load_sealed_fixture()


def _lps_spans(setup: dict) -> list[tuple[str, str]]:
    """A graduated setup's marked-LPS spans (lps + optional lps2)."""
    spans = [tuple(setup["lps"])]
    if setup.get("lps2"):
        spans.append(tuple(setup["lps2"]))
    return spans


def _replay_setup(setup: dict, df: pd.DataFrame, spy_6m: float) -> dict:
    """Replay one graduated setup on the ONE fired-policy window from the
    replay seam — the SAME pops-up-live criterion the agreement harness
    scores, so gate and scoreboard can never diverge. Returns
    ``{status, first_fire|reason, window, clamp_note}``: the walked window's
    span and any faithful-basis/cap clamp ride along so the seam's "every
    clamp is NAMED, never silent" contract survives into the baseline and
    the check report."""
    if not setup.get("frame_digest"):
        return {"status": "error",
                "reason": "legacy (non-digest) setups no longer gate - "
                          "graduate via tools.calibration.guided_list_export (EC-9)"}
    sessions, note = fired_window_sessions(
        df, setup["as_of"], _lps_spans(setup), setup.get("knowable_from"))
    if not sessions:
        return {"status": "error", "reason": "fired-policy window has no frame sessions"}
    out = {"window": [sessions[0].date().isoformat(), sessions[-1].date().isoformat()],
           "clamp_note": note}
    for ts in sessions:
        sliced = df.loc[:ts]
        if len(sliced) < 200:
            continue
        result = _evaluate_ticker(setup["ticker"], sliced, spy_6m, _FROZEN_BREADTH)
        if result is EVAL_ERROR:
            return {"status": "error",
                    "reason": f"EVAL_ERROR at {ts.date()} - a crash is neither a hit nor a miss"}
        if result is not None:
            return {**out, "status": "hit", "first_fire": ts.date().isoformat(),
                    "tier": result.get("Tier"), "score": result.get("Score")}
    return {**out, "status": "miss"}


def population_is_current(corpus_fingerprint: str | None) -> tuple[bool, str]:
    """Does the corpus still describe the operator's CURRENT drawings?

    **This is a FAILURE, not an advisory, since his 2026-09-08 ruling** — "the
    engine always Tests against the updated marks as a rule". It used to print an
    advisory nobody could act on without a re-pin ceremony, so it sat drifted for
    six weeks while the standard demanded three marks he had deleted (two of them
    as permanent expected-misses) and ignored five he had drawn.

    Returns ``(ok, message)``. The live DB is read ``mode=ro`` only. **An absent
    DB is OK, not a failure** — CI and any hermetic checkout have no marks DB, and
    the committed fixture is what they grade against; only a machine that HAS the
    operator's drawings can judge whether the corpus still matches them.
    """
    try:
        import sqlite3
        from urllib.request import pathname2url

        import database  # backend module: the ONE archive-path home
        if not os.path.exists(database._DB_PATH):
            return True, "no calibration-marks DB here — corpus currency not checked"
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        # EC-13: the ONE validated loader + fingerprint recipe (the export's own),
        # never a re-typed twin.
        from tools.calibration.calibration_harness import load_box_marks

        uri = "file:" + pathname2url(database._DB_PATH) + "?mode=ro"
        ro_engine = create_engine(
            "sqlite://", creator=lambda: sqlite3.connect(uri, uri=True))
        session = sessionmaker(bind=ro_engine)()
        try:
            rows, fingerprint = load_box_marks(session)
        finally:
            session.close()
            ro_engine.dispose()
    except Exception as exc:  # noqa: BLE001 — a broken read must not masquerade as drift
        return True, f"could not read the marks DB ({exc.__class__.__name__}) — currency not checked"

    if not rows:
        # A database with no drawings in it is not the operator's. The pytest
        # session points CHROLLO_DB_PATH at a throwaway file whose migrations
        # create an EMPTY calibration_marks table, and reading that as "he
        # deleted everything" wedged the gate red for the whole suite. Only a DB
        # that actually holds marks can judge whether the corpus still matches
        # them.
        return True, "the marks DB here holds no drawings — corpus currency not checked"
    if fingerprint == corpus_fingerprint:
        return True, f"corpus matches the live marks DB ({len(rows)} box marks)"
    return False, (
        f"THE CORPUS IS STALE: the live calibration-marks DB holds {len(rows)} box marks "
        f"whose fingerprint is {fingerprint[:16]}…, the corpus was built from "
        f"{(corpus_fingerprint or '(none)')[:16]}…\n"
        "  The operator drew, edited or deleted a mark since this standard was built, so the\n"
        "  gate is grading against drawings he no longer stands behind. Refresh it:\n"
        "      python -m tools.calibration.guided_list_export\n"
        "      python -m tools.regression.marks_corpus --build-fixture\n"
        "  Pinned verdicts survive the refresh by mark identity — a mark that fires must\n"
        "  still keep firing. Only the POPULATION follows him (his ruling, 2026-09-08)."
    )


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
            "  `python -m tools.regression.marks_corpus --build-fixture`."
        )

    # The fixture parquet is the ONLY in-repo carrier of the frozen drawn
    # bases (the frame store is operator-local) — verify each frame's CONTENT
    # against the digest the sealed corpus pins, so a regenerated, drifted,
    # or edited parquet can never silently change the replay basis while the
    # seal still reports PASS. frame_store is pure (pandas/stdlib), lazy here.
    from frame_store import ohlcv_digest

    by_key = {s["key"]: s for s in baseline["setups"]}
    for setup in setups:
        key = setup_key(setup)
        pinned = by_key.get(key)
        if pinned is None:
            ok = False
            lines.append(f"  {key}: in the corpus but not in the baseline - re-freeze deliberately")
            continue
        df = fixture_frame(frames, key,
                           None if setup.get("frame_digest") else setup["ticker"])
        if df is None or df.empty:
            ok = False
            lines.append(f"  {key}: frame MISSING from fixture parquet - rebuild the fixture")
            continue
        if setup.get("frame_digest") and ohlcv_digest(df) != setup["frame_digest"]:
            ok = False
            lines.append(f"  {key}: FIXTURE BASIS DRIFTED - the parquet frame no longer "
                         "matches the sealed frame_digest; the gate would grade bars the "
                         "operator never drew. Rebuild the fixture from the frame store.")
            continue
        got = _replay_setup(setup, df, float(pinned["spy_6m_return"]))
        if got["status"] == "error":
            ok = False
            lines.append(f"  {key}: {got['reason']}")
            continue
        if got.get("window") != pinned.get("windows", [None])[0] or \
                (got.get("clamp_note") or None) != pinned.get("window_clamp"):
            ok = False
            lines.append(f"  {key}: FIRED-POLICY WINDOW DRIFTED - frozen "
                         f"{pinned.get('windows')} clamp={pinned.get('window_clamp')!r}, "
                         f"derived {got.get('window')} clamp={got.get('clamp_note')!r}. "
                         "The acceptance criterion moved; re-freeze deliberately (EC-7).")
        if pinned["status"] == "hit" and got["status"] == "miss":
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
    pop = baseline.get("population")
    if pop:
        fp = baseline.get("marks_fingerprint") or ""
        print(f"population: {pop}   marks_fingerprint: {fp[:16]}{'…' if fp else ''}")
    # Epoch advisory (Hunt, ONE-Event-Map Task 12): the baseline has always
    # STAMPED the engine it was frozen against; recorded-but-unasserted
    # provenance has no authority, so say when the current engine differs.
    # An ADVISORY line, never a failure — the ratchet's verdict stays about
    # fires, and a config-epoch boundary is where the operator most needs to
    # know WHICH engine the PASS just graded.
    frozen_engine = baseline.get("engine_config_version")
    if frozen_engine and frozen_engine != manifest_hash():
        print(f"ADVISORY: engine config epoch differs from the seal — baseline "
              f"frozen at {frozen_engine[:16]}…, current {manifest_hash()[:16]}…; "
              "the verdict below grades TODAY'S engine against the sealed fires "
              "(re-freeze deliberately at the next flip/seam commit, EC-29).")
    # Is the standard still HIS standard? A failure since his 2026-09-08 ruling.
    current, currency_note = population_is_current(baseline.get("marks_fingerprint"))
    if not current:
        ok = False
        lines.append("  " + currency_note)

    if ok:
        hits = sum(1 for s in baseline["setups"] if s["status"] == "hit")
        unreviewed = [s["key"] for s in baseline["setups"]
                      if s["status"] == "miss" and s.get("stage") == NEW_MARK_STAGE]
        reviewed_misses = len(baseline["setups"]) - hits - len(unreviewed)
        print(f"ratchet held: {hits}/{len(baseline['setups'])} pinned hits still fire; "
              f"all {reviewed_misses} reviewed misses still miss.")
        if unreviewed:
            # Never folded into the miss count: these are charts he drew that the
            # engine cannot read yet and he has not looked at. They are pinned so
            # they cannot start firing unannounced, but calling them "expected"
            # would launder an open question into a settled one.
            print(f"AWAITING YOUR REVIEW: {len(unreviewed)} newly-drawn mark(s) the engine "
                  f"does not fire — {', '.join(sorted(unreviewed))}")
        print(f"({currency_note})")
        print("PASS")
    else:
        for line in lines:
            print(line)
        print()
        print("FAIL - the marks ratchet broke (see above).")
    return ok


# ------------------------------------------------------------------
# Fixture build (per-stage re-freeze; reads the operator-local frame store)
# ------------------------------------------------------------------
def _frozen_frame(ticker: str, as_of: str, digest: str):
    """The as-drawn frozen basis for a graduated mark (calibration_frames/ by
    digest). Lazy import: frame_store is pure and the build-time-only door."""
    from frame_store import load_frame
    return load_frame(ticker, as_of, digest=digest)


def setup_digest(setup: dict) -> str:
    """A digest of what the operator actually DREW for this setup — the rails,
    the LPS window(s), the trigger, the knowable-from override, the frame.

    This is the identity a pinned verdict belongs to. A verdict says "the engine
    fires THIS drawing"; if he moves the rails or re-dates the LPS, that sentence
    is about a chart that no longer exists and must not be carried forward as
    either a pass or a regression. Measured 2026-09-08: **ten of the thirty marks
    that survived the July seal had been edited** — LPS windows, triggers and
    rails — and the fingerprint could say only that *something* moved.

    Deliberately NOT the frame digest alone: the same bars can carry a completely
    redrawn box.
    """
    payload = {k: setup.get(k) for k in
               ("as_of", "rails_drawn", "lps", "lps2", "trigger",
                "knowable_from", "frame_digest")}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _previously_pinned() -> dict[str, str]:
    """``{setup key: setup_digest}`` from the LAST freeze — what drawing each
    pinned verdict was actually about.

    A key that is absent is a mark he has just DRAWN. A key whose digest differs
    is one he has REDRAWN. Both get a fresh verdict; only an unchanged drawing
    keeps its pin, which is what makes "a pinned hit must keep firing" mean
    something. Missing / unreadable baseline -> empty, so a first build treats
    every mark as new-to-the-standard.
    """
    try:
        with open(_BASELINE_JSON, encoding="utf-8") as f:
            return {s["key"]: s.get("setup_digest", "") for s in json.load(f).get("setups", [])}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def build_fixture() -> dict:
    """Freeze frames + the ratchet baseline.

    Every setup freezes the EXACT frozen frame the operator drew on, loaded
    from calibration_frames/ by digest — never a live re-fetch, so vendor
    restatements can never move the sealed basis. The scoring-only market
    scalars are the replay seam's frozen constants (harness parity).

    Refuses to freeze when the replayed miss-set differs from STAGE_TAGS -
    every frozen miss must carry the build-order stage expected to convert it,
    and a pinned hit that does not actually fire is a broken freeze, not a
    baseline. **One exception, added on the operator's 2026-09-08 ruling:** a
    mark he has drawn SINCE the last freeze is not yet subject to that rule. It
    enters tagged ``NEW_MARK_STAGE`` and is reported separately, because
    refusing the rebuild until someone hand-writes a stage for every new drawing
    is the ceremony that ruling removed.

    Marks he has DELETED simply do not appear in ``load_corpus()`` any more, so
    they leave here with no ceremony at all — which is the whole point.
    """
    setups = load_corpus()
    # What the PREVIOUS freeze knew, so "new" means new to the standard rather
    # than new to this run. Absent on a first build: then nothing is new.
    previously_pinned = _previously_pinned()
    fresh: list[tuple[str, str]] = []
    frames: dict[str, pd.DataFrame] = {}
    baseline_setups: list[dict] = []
    problems: list[str] = []
    for setup in setups:
        key, ticker = setup_key(setup), setup["ticker"]
        if not setup.get("frame_digest"):
            problems.append(f"{key}: no frame_digest - legacy setups no longer "
                            "gate; graduate via tools.calibration.guided_list_export (EC-9)")
            continue
        df = _frozen_frame(ticker, setup["as_of"], setup["frame_digest"])
        if df is None or df.empty:
            problems.append(f"{key}: no frozen frame matches digest "
                            f"{setup['frame_digest'][:12]} - the drawn basis is unbound")
            continue
        if len(df) < 200:
            problems.append(f"{key}: frozen frame has only {len(df)} bars")
            continue
        frames[key] = df  # keyed by setup: two marks on one ticker = two bases
        got = _replay_setup(setup, df, _FROZEN_SPY_6M)
        if got["status"] == "error":
            problems.append(f"{key}: {got['reason']}")
            continue
        stage = STAGE_TAGS.get(key)
        digest = setup_digest(setup)
        prior = previously_pinned.get(key)
        # Three states, and the third is the honest one:
        #   drawn    - no prior entry: he drew this since the last freeze.
        #   redrawn  - prior digest recorded AND different: he moved this drawing.
        #   unknown  - prior entry exists but recorded NO digest. Baselines frozen
        #              before 2026-09-08 did not carry one, so on the first build
        #              after that ruling we genuinely CANNOT tell an untouched mark
        #              from an edited one. Say so rather than claiming either.
        # 'drawn' and 'redrawn' void the old verdict; 'unknown' is treated the same
        # way for THIS build only, because assuming continuity is the direction that
        # silently carries a verdict about a chart that may no longer exist.
        if prior is None:
            provenance = "drawn"
        elif not prior:
            provenance = "unknown"
        elif prior != digest:
            provenance = "redrawn"
        else:
            provenance = "unchanged"
        is_fresh = provenance != "unchanged"
        if is_fresh:
            fresh.append((key, provenance))
        if got["status"] == "miss" and stage is None:
            if is_fresh:
                # A chart he has just drawn or redrawn that the engine cannot read.
                # It enters MEASURED, not required: refusing the whole rebuild here
                # would mean every drawing breaks his gate until someone hand-writes
                # a stage tag — the ceremony his 2026-09-08 ruling removed. Still
                # PINNED as a miss, so it cannot start firing unannounced.
                stage = NEW_MARK_STAGE
            else:
                problems.append(f"{key}: replays as a MISS but has no STAGE_TAGS entry - "
                                "every frozen miss must name its converting stage")
                continue
        if got["status"] == "hit" and stage is not None:
            if is_fresh:
                # He redrew it and now it fires. Good news, and the stale tag is
                # about the old drawing — drop it, but never silently.
                print(f"  {key}: the redrawn mark now FIRES — dropping its stale "
                      f"'{stage}' tag", flush=True)
                stage = None
            else:
                problems.append(f"{key}: replays as a HIT but STAGE_TAGS expects a miss - "
                                "remove the stale tag deliberately")
                continue
        entry = {"key": key, "ticker": ticker, "status": got["status"],
                 # The drawing this verdict is about — see setup_digest().
                 "setup_digest": digest,
                 "windows": [got["window"]],
                 "spy_6m_return": _FROZEN_SPY_6M, "bars": len(df)}
        if got.get("clamp_note"):
            # The seam's contract: every clamp is NAMED, never silent — the
            # narrowing survives into the frozen artifact and --check output.
            entry["window_clamp"] = got["clamp_note"]
        if got["status"] == "hit":
            entry.update({"first_fire": got["first_fire"], "tier": got.get("tier")})
        else:
            entry["stage"] = stage
        baseline_setups.append(entry)
        print(f"  {key}: {got['status'].upper()}"
              + (f" (first fire {got['first_fire']}, tier {got.get('tier')})"
                 if got["status"] == "hit" else f" (stage: {stage})")
              + (f" [clamped: {got['clamp_note']}]" if got.get("clamp_note") else ""),
              flush=True)

    if problems:
        raise RuntimeError("Refusing to freeze the marks corpus - unresolved setups:\n  "
                           + "\n  ".join(problems))

    os.makedirs(_BASELINE_DIR, exist_ok=True)
    # MultiIndex columns: (setup key, field). sort=True pins today's
    # union-and-sort index behavior against the pandas-4 default flip.
    combined = pd.concat(frames, axis=1, sort=True)
    combined.to_parquet(_FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    prov = corpus_provenance()
    baseline = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "breadth_pct": _FROZEN_BREADTH,
        "corpus_sha256": corpus_sha256(),
        # Graduation provenance (pass-through from the corpus file) + the engine
        # this baseline was frozen under: which ground truth, approved when, and
        # what read it — answerable from this artifact alone.
        "population": prov.get("population", "legacy"),
        "marks_fingerprint": prov.get("marks_fingerprint"),
        "authorization": prov.get("authorization"),
        "engine_config_version": manifest_hash(),
        # The acceptance bar graduated setups are graded on (the harness's
        # pops-up-live policy, owned by the replay seam) — frozen with the
        # baseline; changing it is an EC-7 event.
        "fired_policy": {"window_sessions": FIRED_WINDOW_SESSIONS,
                         "event_tail_sessions": FIRED_EVENT_TAIL_SESSIONS,
                         "max_walk_sessions": FIRED_WALK_MAX_SESSIONS},
        "setups": baseline_setups,
    }
    # newline="\n": tests/baselines/*.json is .gitattributes-pinned to LF —
    # writing platform CRLF would make every local re-freeze byte-differ from
    # the checkout (the corpus export learned this the hard way).
    with open(_BASELINE_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(baseline, f, indent=2)

    hits = sum(1 for s in baseline_setups if s["status"] == "hit")
    new_misses = [s["key"] for s in baseline_setups
                  if s["status"] == "miss" and s.get("stage") == NEW_MARK_STAGE]
    print(f"Built marks corpus: {hits} pinned hits / "
          f"{len(baseline_setups) - hits} misses -> {_FIXTURE_PARQUET}")
    if fresh:
        # Named, because this is the whole point of the 2026-09-08 ruling: the
        # standard followed him, and he must be able to see exactly where.
        drawn = sorted(k for k, why in fresh if why == "drawn")
        redrawn = sorted(k for k, why in fresh if why == "redrawn")
        unknown = [k for k, why in fresh if why == "unknown"]
        if drawn:
            print(f"  newly DRAWN since the last freeze ({len(drawn)}): {', '.join(drawn)}")
        if redrawn:
            print(f"  REDRAWN since the last freeze ({len(redrawn)}) - their old verdicts were "
                  f"void and did not carry: {', '.join(redrawn)}")
        if unknown:
            print(f"  provenance UNKNOWN ({len(unknown)}): the previous baseline predates the "
                  "per-drawing digest, so whether these were edited cannot be proven from it. "
                  "Treated as fresh for this build only; from now on the distinction is exact.")
    if new_misses:
        print(f"  AWAITING YOUR REVIEW ({len(new_misses)}) - drawn/redrawn and the engine does "
              f"NOT fire them: {', '.join(sorted(new_misses))}")
    return baseline


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Operator-marks acceptance guard (Event Map).")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--build-fixture", action="store_true",
                       help="Freeze corpus frames + the ratchet baseline from the frozen frame store")
    group.add_argument("--check", action="store_true",
                       help="Fail (exit 1) on any ratchet break (regressed hit, converted miss, corpus edit)")
    args = ap.parse_args()

    try:
        if args.build_fixture:
            build_fixture()
        elif args.check:
            sys.exit(0 if check_corpus() else 1)
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
