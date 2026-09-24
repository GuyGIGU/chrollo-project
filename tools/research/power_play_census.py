"""Power-Play species census — the clock-sweep evidence instrument (program Task 3).

The species preset's clock value (`docs/power_play_program_2026-08.md` Task 1) is
RULED from evidence, not transcribed from a book. This instrument produces that
evidence: for every pole-qualified episode in the cache it asks, per candidate
reading clock (default 20→15→10→8), whether the episode was structurally
watchable BEFORE its breakout, and what the one cascade actually did at that
clock's own first legal look.

PRICING (publish the arithmetic — the reason this tool screens first):
a naive grid is every ticker x every session x every clock through the full row
work; the species precondition (the explosive prior leg) is a rolling return —
pure vectorized arithmetic — so the census screens the whole panel in seconds,
emits bounded (ticker, episode) pairs, and pays the row work ONLY at each
episode's per-clock first legal look. A ROW is NOT just the ~30 ms cascade: it
pays its own (ticker, as-of) frame prep (~hundreds of ms, and the first look
moves with the clock so prep is rarely shared across clocks) plus a second
anchor enumeration for the seeding trace — the honest per-row figure is
~ROW_MS, and a full-cache 4-clock run (~56k rows) is HOURS, not minutes
(the original 30 ms plan under-priced exactly this; corrected 2026-08-17,
program doc Task 10). The run header prints the plan with the real counts
before any election runs.

WHAT A ROW IS. An EPISODE is (ticker, climax date, AR date), discovered by the
vectorized screen with the collector's own mechanics (trailing local-max peak,
AR = the argmin low within AR_MAX_BARS whose close confirmed >= AR_MIN_DROP_PCT).
Per (episode, clock) the census records ONE verdict at the clock's first legal
look — the session where the anchor first becomes seedable: the AR-age and
climax-age walls of `collect_root_anchors` solved AS-OF-CONSISTENTLY
(`power_play.first_legal_look` — against the reaction the walk could see
OUTSIDE its own edge reserve, i.e. through bar `p - skip`, never the
hindsight-final AR; skip = STRUCTURE_EDGE_SKIP_BARS). Honest absences are first-class rows: an episode
whose breakout prints BEFORE the clock's first legal look is
`not_watched_clock` (no election is run — the wall itself is the finding), and
one whose first legal look lies beyond the cache is `pending`. Everything else
runs the REAL cascade — `prepared_frame` (truncate-then-prep, the live twin)
then `read_structure_under` with the clock override whose KEY SET is derived
from `settings.POWER_PLAY_WINDOWS` itself (a third preset key would otherwise
move the lane's read and not this instrument's — program Task 1 §D).

Election match basis: the elected box OPENS at the episode's AR (<= 5 sessions
apart, back-extension tolerance), compared in DATES — the prepared frame is
2y-trimmed so positions never compare across frames.

OUTCOMES start at each clock's OWN knowable bar: forward returns are measured
from the row's as-of close on the RAW frame (the election never saw those bars —
the frozen-grading-frame pattern, EC-10), with partial horizons partitioned
(`*_complete` flags), never silently mixed.

SIDECAR ONLY: rows go to `--out` JSON (never `setup_archive`), stamped with the
clock, `engine_config_version`, cache state, screen params, and the power-play
marks fingerprint — analyzed partitioned.

BATTERY (tests/tooling/test_power_play_census.py): determinism, the lookahead tripwire
on the operand the pipeline guarantees (a prepared frame may not extend past its
as-of; a violation VOIDs the run and says so on EVERY output mode — EC-31),
sealed-output guard on every out-path (EC-14), hand-reasoned first-legal-look
arithmetic, honest-absence rows.

Read-only: reads the parquet cache (pass --cache to read another checkout's
cache in place), writes nothing but its own report. No network, no backend.

Interpreter: run with the ChrolloDashboard venv python — this machine's bare
`python` is a documented trap (two colliding installs); the copy-runnable
command with the exact interpreter path lives in
docs/power_play_program_2026-08.md ("The ruling loop").

    python -m tools.research.power_play_census --plan                    # print the pricing plan only
    python -m tools.research.power_play_census --out output/pp_census.json
    python -m tools.research.power_play_census --cache "..\\Chrollo Project\\market_data_cache_5y.parquet" --out ...
    python -m tools.research.power_play_census --tickers MAN FTNT --out ...   # bounded debug run
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:  # works under both `python -m tools.research.power_play_census` and `python tools/research/power_play_census.py`
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output
_ROOT = configure_path()

import pandas as pd                                          # noqa: E402

from config import settings                                  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash       # noqa: E402
from engine_alpha.structure.box.box_primitives import (          # noqa: E402
    collect_root_anchors,
)
from engine_alpha.structure.context.power_play import (              # noqa: E402
    first_legal_look,                                        # noqa: F401 — the battery's seam
    ticker_episodes,
)
from tools.calibration.calibration_harness import parse_variant          # noqa: E402
from tools.calibration.marks_json import (                               # noqa: E402
    load_marks_json,
    marks_json_fingerprint,
)
from tools.calibration.replay import prepared_frame_with_reason, read_structure_under  # noqa: E402

_MARKS_PATH = os.path.join(_ROOT, "docs", "power_play_marks_2026-08.json")

# The measured unit costs the pricing plan is built on. ELECTION_MS is the
# cascade alone (2026-08-14: ~30 ms; scan eval 164 s / 5,502 tickers) — the
# original plan priced rows at this figure and under-priced the real run
# into "minutes". ROW_MS is the honest per-row figure: per-(ticker, as-of)
# frame prep (~hundreds of ms, rarely shared across clocks) + the cascade +
# the second anchor enumeration for the seeding trace (2026-08-17
# correction; the first full-cache run measured hours).
ELECTION_MS = 30.0
ROW_MS = 400.0
_SESSIONS_PER_YEAR = 250

# The row verdicts are a CLOSED set — the sheets and any later analysis switch
# on these, never reconstruct them from null patterns.
VERDICTS = ("elected_episode", "elected_other", "no_election",
            "refused_universe", "not_watched_clock", "pending")

# Screen defaults: the ONE registered pole-qualifier constants (settings
# POWER_PLAY_POLE_*, manifest-listed — program Task 5); stamped into every row.
# getattr with the literature anchors as fallback: the tools bootstrap resolves
# the repo-root config, but a stale interpreter must not crash the instrument.
POLE_MIN_GAIN = float(getattr(settings, "POWER_PLAY_POLE_MIN_GAIN", 0.90))
POLE_WINDOW_BARS = int(getattr(settings, "POWER_PLAY_POLE_WINDOW_BARS", 40))
_MATCH_TOL_SESSIONS = 5     # box open vs episode AR (back-extension tolerance)
_FWD_HORIZONS = (10, 20)


# ------------------------------------------------------------------ panel ----

def load_panel(path=None, tickers=None):
    """The cached OHLC panel as {ticker: frame}. ``path`` defaults to the
    live cache; pass another checkout's parquet to read it in place."""
    path = path or settings.CACHE_FILENAME
    data = pd.read_parquet(path, engine=settings.PARQUET_ENGINE)
    level0 = sorted(set(data.columns.get_level_values(0)))
    if tickers:
        wanted = {t.strip().upper() for t in tickers}
        level0 = [t for t in level0 if t in wanted]
    frames = {}
    for t in level0:
        df = data[t].dropna()
        if len(df):
            frames[t] = df
    return frames, os.path.basename(str(path))


# ----------------------------------------------------------------- screen ----

def screen_episodes(frames, pole_gain=POLE_MIN_GAIN, pole_window=POLE_WINDOW_BARS):
    """The bounded (ticker, episode) pairs the elections will run on."""
    episodes = []
    for ticker in sorted(frames):
        episodes.extend(ticker_episodes(ticker, frames[ticker], pole_gain, pole_window))
    return episodes


# ---------------------------------------------------------------- elections ----

def _no_lookahead(df, as_of) -> bool:
    """The operand the pipeline GUARANTEES (truncate-then-prep): a prepared
    frame may not extend past its as-of. The tripwire compares exactly this."""
    return len(df) == 0 or df.index[-1] <= pd.Timestamp(as_of)


def _forward(raw_closes, p, horizon):
    """Forward return from position ``p`` over ``horizon`` bars on the RAW
    frame — measured strictly AFTER the election, never fed to it (EC-10)."""
    if p + horizon < len(raw_closes) and raw_closes[p] > 0:
        return round(float(raw_closes[p + horizon] / raw_closes[p] - 1.0), 4), True
    return None, False


def _election_row(frames, prep_cache, ep, clock, violations, extra_overrides=None):
    raw = frames[ep["ticker"]]
    # As-of-consistent: solved against the reaction the walk could SEE on each
    # day — outside its own edge reserve — never the hindsight-final AR
    # (2026-08-17 review, McKinney; reserve correction 2026-08-20, finding 3:
    # both biases land on exactly the short swept clocks).
    p = first_legal_look(ep, clock, raw)
    row = {"ticker": ep["ticker"], "climax": ep["climax_date"],
           "ar": ep["ar_date"], "breakout": ep["breakout_date"],
           "pole_gain": ep["gain"], "depth": ep["depth"], "clock": clock}
    if p >= len(raw):
        row.update({"verdict": "pending", "first_legal_look": None})
        return row
    as_of = raw.index[p]
    row["first_legal_look"] = str(as_of.date())
    row["watchable_pre_breakout"] = (ep["breakout"] is None or p < ep["breakout"])
    if not row["watchable_pre_breakout"]:
        row["verdict"] = "not_watched_clock"     # the wall IS the finding
        return row

    key = (ep["ticker"], str(as_of.date()))
    if key not in prep_cache:                    # prep once per (ticker, as-of)
        prep_cache[key] = prepared_frame_with_reason(raw, as_of)
    prep, reason = prep_cache[key]
    if prep is None:
        row.update({"verdict": "refused_universe",
                    "refused_gate": reason[0] if reason else "unknown"})
        return row
    df, atr = prep
    if not _no_lookahead(df, as_of):
        violations.append(f"{ep['ticker']}@{as_of.date()}: prepared frame ends "
                          f"{df.index[-1].date()} past its as-of")
    # The override's KEY SET is derived from the preset dict itself — never a
    # hand-typed twin of it (2026-08-17 review, Fowler; EC-33): a third key
    # joining POWER_PLAY_WINDOWS moves this instrument's read WITH the
    # lane's, by construction.
    overrides = {key: clock for key in settings.POWER_PLAY_WINDOWS}
    # The census measures THE SPECIES READ: clock + the species story form
    # (the resistance contraction, program Task 6). getattr-guarded so the
    # instrument still runs on a checkout predating the form flag.
    if hasattr(settings, "POWER_PLAY_STORY_FORM_ENABLED"):
        overrides["POWER_PLAY_STORY_FORM_ENABLED"] = True
    # Experiment overrides (--override NAME=VALUE): validated settings names
    # through the SAME scoped core (AP-10) — the occupancy/traversal
    # relaxation sweep the operator approved 2026-08-18 rides exactly here,
    # stamped into the sidecar so a relaxed run can never masquerade as the
    # production read.
    if extra_overrides:
        overrides.update(extra_overrides)
    structure = read_structure_under(df, atr, overrides)
    skip = int(settings.STRUCTURE_EDGE_SKIP_BARS)
    eval_df = df.iloc[:-skip] if len(df) > skip else df
    seeding: list = []
    row["pairs_enumerated"] = len(
        collect_root_anchors(eval_df, clock, seeding_trace=seeding))
    if seeding:
        # The anchor seam's own refusal words (program Task 9) — the census
        # and the live product answer "why didn't it seed" identically.
        row["seeding_refusals"] = sorted({rec["leg"] for rec in seeding})

    if structure is None or structure.box is None:
        row["verdict"] = "no_election"
    else:
        box = structure.box
        open_ts = df.index[int(box.start_bar)]
        sessions_apart = abs(int(raw.index.searchsorted(open_ts)) - ep["ar"])
        row["elected"] = {"open": str(open_ts.date()),
                          "R": round(float(box.R), 4), "S": round(float(box.S), 4),
                          "base_len": int(len(df) - int(box.start_bar))}
        row["verdict"] = ("elected_episode" if sessions_apart <= _MATCH_TOL_SESSIONS
                          else "elected_other")

    closes = raw["Close"].to_numpy(dtype=float)
    for h in _FWD_HORIZONS:
        value, complete = _forward(closes, p, h)
        row[f"fwd_{h}"] = value
        row[f"fwd_{h}_complete"] = complete
    return row


# -------------------------------------------------------------------- run ----

def pricing(n_tickers, n_episodes, clocks):
    naive_h = n_tickers * _SESSIONS_PER_YEAR * len(clocks) * ROW_MS / 3.6e6
    planned = n_episodes * len(clocks)
    return {"naive_grid_hours_per_cache_year": round(naive_h, 1),
            "elections_planned": planned,
            "planned_minutes": round(planned * ROW_MS / 6e4, 1),
            "election_ms": ELECTION_MS, "row_ms": ROW_MS}


def run_census(frames, clocks, pole_gain=POLE_MIN_GAIN,
               pole_window=POLE_WINDOW_BARS, marks_path=_MARKS_PATH,
               extra_overrides=None):
    # Experiment overrides scope the WHOLE species read — the SCREEN included:
    # the breakout wall is consumed by ticker_episodes at screen time, and the
    # first wall A/B (2026-08-18) ran as a silent no-op because the lever only
    # wrapped the elections while the stamp claimed otherwise. One scope, no
    # halves.
    if extra_overrides:
        from engine_alpha.structure.context.htf import window_override
        with window_override(dict(extra_overrides)):
            episodes = screen_episodes(frames, pole_gain, pole_window)
    else:
        episodes = screen_episodes(frames, pole_gain, pole_window)
    plan = pricing(len(frames), len(episodes), clocks)

    # PRE-FLIGHT (2026-08-17 review, Hunt): the stamp's marks input is fully
    # decidable at minute zero — a malformed mark must abort BEFORE the
    # hours-long sweep, never at its finish line. Loaded once, reused below.
    try:
        marks_fp = marks_json_fingerprint(load_marks_json(marks_path))
    except FileNotFoundError:
        marks_fp = "absent"

    violations: list[str] = []
    prep_cache: dict = {}
    rows = []
    last_ticker = None
    for ep in episodes:
        if ep["ticker"] != last_ticker:
            # Per-ticker cache scope: the first look moves with the clock, so
            # (ticker, as-of) keys essentially never recur ACROSS tickers and
            # whole-run retention was a GB-scale leak over an hours-long
            # full-cache sweep (2026-08-17 review, Performance).
            prep_cache.clear()
            last_ticker = ep["ticker"]
        for clock in clocks:
            rows.append(_election_row(frames, prep_cache, ep, clock, violations,
                                      extra_overrides))
    rows.sort(key=lambda r: (r["ticker"], r["climax"], r["clock"]))

    per_clock = {}
    for clock in clocks:
        sub = [r for r in rows if r["clock"] == clock]
        counts = {v: sum(1 for r in sub if r["verdict"] == v) for v in VERDICTS}
        counts["pairs_enumerated_total"] = sum(r.get("pairs_enumerated", 0) for r in sub)
        counts["cascades_run"] = sum(
            1 for r in sub if r["verdict"] in
            ("elected_episode", "elected_other", "no_election"))
        per_clock[str(clock)] = counts

    last = max((str(df.index[-1].date()) for df in frames.values()), default=None)
    return {
        "tool": "power_play_census",
        "params": {"clocks": list(clocks), "pole_min_gain": pole_gain,
                   "pole_window_bars": pole_window,
                   "match_tol_sessions": _MATCH_TOL_SESSIONS,
                   "story_form": bool(hasattr(
                       settings, "POWER_PLAY_STORY_FORM_ENABLED")),
                   "extra_overrides": dict(extra_overrides or {})},
        "engine_config_version": manifest_hash(),
        "cache_state": {"tickers": len(frames), "last_session": last},
        "marks_fingerprint": marks_fp,
        "pricing": plan,
        "episodes": len(episodes),
        "per_clock": per_clock,
        "tripwire": ("OK" if not violations else
                     "VOID: lookahead — " + "; ".join(violations)),
        "rows": rows,
    }


def report(result):
    """The stdout verdict — printed on EVERY run, --json included (EC-31)."""
    plan = result["pricing"]
    print(f"\n  POWER-PLAY CENSUS — {result['episodes']} episodes over "
          f"{result['cache_state']['tickers']} tickers "
          f"(cache through {result['cache_state']['last_session']})")
    print(f"  pricing: naive grid ≈ {plan['naive_grid_hours_per_cache_year']} h "
          f"per cache-year; this run {plan['elections_planned']} elections "
          f"≈ {plan['planned_minutes']} min")
    print(f"  manifest {result['engine_config_version'][:12]} · marks "
          f"{result['marks_fingerprint'][:12]}")
    extra = result["params"].get("extra_overrides") or {}
    if extra:
        print("  EXPERIMENT OVERRIDES (not the production read): "
              + ", ".join(f"{k}={v}" for k, v in sorted(extra.items())))
    print("\n  clock  watch-able  not-watched  pending  refused  "
          "elected-ep  elected-other  no-elect  pairs  cascades")
    print("  " + "-" * 96)
    for clock in result["params"]["clocks"]:
        c = result["per_clock"][str(clock)]
        watchable = (c["elected_episode"] + c["elected_other"]
                     + c["no_election"] + c["refused_universe"])
        print(f"  {clock:>5}  {watchable:>10}  {c['not_watched_clock']:>11}  "
              f"{c['pending']:>7}  {c['refused_universe']:>7}  "
              f"{c['elected_episode']:>10}  {c['elected_other']:>13}  "
              f"{c['no_election']:>8}  {c['pairs_enumerated_total']:>5}  "
              f"{c['cascades_run']:>8}")
    print(f"\n  TRIPWIRE: {result['tripwire']}")
    if result["tripwire"] != "OK":
        print("  !! this run is VOID — do not rule on it")


def save(result, out_path):
    with open(refuse_sealed_output(out_path), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    print(f"\n  wrote {out_path} ({len(result['rows'])} rows)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache", default=None,
                    help="parquet cache path (default: settings.CACHE_FILENAME)")
    ap.add_argument("--clocks", default="20,15,10,8",
                    help="comma-separated reading clocks to sweep")
    ap.add_argument("--pole-gain", type=float, default=POLE_MIN_GAIN)
    ap.add_argument("--pole-window", type=int, default=POLE_WINDOW_BARS)
    ap.add_argument("--tickers", nargs="*", default=None,
                    help="bound the run to these tickers (debug)")
    ap.add_argument("--out", default=None, help="sidecar JSON path")
    ap.add_argument("--plan", action="store_true",
                    help="screen + print the pricing plan; run no elections")
    ap.add_argument("--override", action="append", default=[],
                    metavar="NAME=VALUE",
                    help="settings override for this run (repeatable) — the "
                         "experiment lever (AP-10: rides the one scoped "
                         "override); names validated, values stamped into "
                         "the sidecar")
    args = ap.parse_args(argv)

    extra_overrides: dict = {}
    for spec in args.override:
        extra_overrides.update(parse_variant(spec))
    for name in extra_overrides:
        if not hasattr(settings, name):
            ap.error(f"--override names an unknown setting: {name!r}")

    clocks = [int(c) for c in args.clocks.split(",") if c.strip()]
    if args.out:
        # PRE-FLIGHT the sealed-output refusal (2026-08-17 review, Hunt): a
        # mistyped out-path is decidable NOW — not after the hours-long sweep
        # whose rows it would discard.
        refuse_sealed_output(args.out)
    frames, cache_name = load_panel(args.cache, args.tickers)
    print(f"  cache: {cache_name}; {len(frames)} tickers", file=sys.stderr)

    if args.plan:
        episodes = screen_episodes(frames, args.pole_gain, args.pole_window)
        plan = pricing(len(frames), len(episodes), clocks)
        print(f"\n  PLAN — {len(episodes)} episodes screened; "
              f"naive grid ≈ {plan['naive_grid_hours_per_cache_year']} h per "
              f"cache-year; planned {plan['elections_planned']} elections "
              f"≈ {plan['planned_minutes']} min")
        return 0

    result = run_census(frames, clocks, args.pole_gain, args.pole_window,
                        extra_overrides=extra_overrides)
    result["cache_state"]["path"] = cache_name
    # SAVE BEFORE REPORT: the sidecar is the run's product and the summary is
    # commentary — a console that cannot encode the report (the cp1252 pipe
    # trap, 2026-08-18: a full sweep died at the '≈' print with its rows in
    # memory) must never cost the sweep.
    if args.out:
        save(result, args.out)
    report(result)
    return 3 if result["tripwire"] != "OK" else 0


if __name__ == "__main__":
    sys.exit(main())
