"""Near-miss review report — the lane's product (near-miss lane Task 11).

One near-miss = one fixed-shape row in decision order: the failing leg with
its NATIVE margin first (the engine's own quanta — ranks exist only WITHIN a
leg; no cross-leg scalar is ruled, so none is printed), then the episode
sentence, then the explicitly-counterfactual would-be line (a near-miss is a
refusal under review, NEVER a pick), then operator coordinates (calendar
dates + prices — census drill idiom, never bar indices), then recurrence.

Header states the junk-heavy expectation BEFORE row one: the rail campaign
proved floors sit where junk begins — most rows SHOULD look like junk; the
forward-return cohort is the payoff, not nightly gold. Default batch is
bounded and forced-ranked (NEW episodes first), fired tickers hidden per the
Task-6 axis-5 ruling; ``--all`` reveals both. Empty is an affirmative report
(collector state + populations), never silence.

Integrity: read-only against every ground-truth store (no path promotes a
near-miss into a mark — EC-9 stays one-way); ``--json`` passes the
sealed-output guard (EC-14); modes refuse to combine; an unknown filter
value aborts naming the offender; a filtered run stamps the EXACT set
scored.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.research.near_miss_report                # ranked review batch
    python -m tools.research.near_miss_report --all          # every row, fired incl.
    python -m tools.research.near_miss_report --leg occupancy
    python -m tools.research.near_miss_report --ticker EGBN
    python -m tools.research.near_miss_report --outcomes    # the payoff cohort only
    python -m tools.research.near_miss_report --json OUT     # rows as JSON (alone)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:  # works under both `python -m tools.research.near_miss_report` and `python tools/research/near_miss_report.py`
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

_PROJECT_ROOT = configure_path(backend=True)

BATCH = 8   # bounded default review batch (plan: 5-10, forced-ranked)

# ONE committed source per vocabulary (review 2026-07-26 finding 9): the
# writer's stamping tuple IS the ruled T-COARSE-8 set the model CHECK
# enforces, and the occupancy membership comes from the ruled taxonomy —
# a re-ruling re-scores this surface instead of desyncing it.
from core.archive.near_miss_writer import _FAILING_LEGS as _LEGS
from engine_alpha.structure.box.gate_margins import OCCUPANCY_FAMILY

# The failing coarse leg's native margin lives in these cohort columns; the
# occupancy concept displays its BINDING member (min of the family margins).
_OCC_MEMBERS = tuple(f"nm_{leg}" for leg in OCCUPANCY_FAMILY)
_LEG_COLUMN = {leg: f"nm_{leg}" for leg in _LEGS if leg != "occupancy"}


def _native_margin(row) -> tuple[str, float]:
    """(display, sort_value) of the failing leg's native margin."""
    if row.failing_leg == "occupancy":
        members = {c[3:]: getattr(row, c) for c in _OCC_MEMBERS}
        leg, m = min(members.items(), key=lambda kv: kv[1])
        return f"occupancy[{leg} {m:+d}]", float(m)
    value = getattr(row, _LEG_COLUMN[row.failing_leg])
    disp = f"{value:+d}" if isinstance(value, int) else f"{value:+.4f}"
    return f"{row.failing_leg} {disp}", float(value)


def _load_rows():
    import database
    from archive_models import NearMissArchive

    session = database.SessionLocal()
    try:
        return session.query(NearMissArchive).all()
    finally:
        session.close()


def _print_row(row, latest_seen: str) -> None:
    margin_disp, _ = _native_margin(row)
    is_new = row.first_seen == row.last_seen == latest_seen
    badge = "NEW " if is_new else f"seen {row.nights_seen}x"
    fired = "  [FIRED-TICKER]" if row.fired_any_night else ""
    outcome = ""
    if row.bars_to_date:
        trig = ("touched " + row.trigger_date if row.triggered
                else "untouched" if row.triggered == 0 else "immature")
        outcome = (f"\n      outcome: mfe {row.mfe_to_date:+.3f} "
                   f"ret {row.ret_to_date:+.3f} over {row.bars_to_date} bars; "
                   f"would-be trigger {trig}")
    print(f"  {row.ticker:6} {margin_disp:28} {badge:9}"
          f" pool={row.pool}{fired}\n"
          f"      sentence: {row.episode_profile or '(none)'}\n"
          f"      never elected, never fired\n"
          f"      R {row.r_level} / S {row.s_level}; window "
          f"{row.window_start_date}..{row.window_end_date}; first refusal "
          f"{row.first_seen} (close {row.scan_close}); anchors "
          f"{row.r_anchor_date} / {row.s_anchor_date}{outcome}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true",
                    help="every row (fired tickers + beyond the batch cap)")
    ap.add_argument("--leg", help="filter: one failing-leg label")
    ap.add_argument("--ticker", help="filter: one ticker")
    ap.add_argument("--outcomes", action="store_true",
                    help="only outcome-bearing episodes (the payoff cohort) "
                         "— a bounded batch, never an --all archaeology dig")
    ap.add_argument("--json", help="dump rows as JSON (runs alone; EC-14)")
    args = ap.parse_args()

    if args.json and (args.all or args.leg or args.ticker or args.outcomes):
        ap.error("--json runs alone; combine with no other flag")
    if args.leg and args.leg not in _LEGS:
        ap.error(f"unknown failing-leg {args.leg!r} — the ruled vocabulary "
                 f"is {'/'.join(_LEGS)}")

    from config import settings
    rows = _load_rows()

    if args.json:
        path = refuse_sealed_output(args.json)
        payload = [{c.name: getattr(r, c.name)
                    for c in r.__table__.columns} for r in rows]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1, default=str)
        print(f"wrote {path} ({len(payload)} rows)")
        return 0

    print("=" * 78)
    print("  NEAR-MISS REVIEW — refusals under review, NEVER missed winners")
    print("  Expectation, stated first: floors sit where junk begins (rail")
    print("  campaign, sealed) — most rows SHOULD read as junk. The payoff is")
    print("  the forward-return cohort, not nightly gold.")
    print("=" * 78)

    if not rows:
        flag = "ON" if settings.NEAR_MISS_LANE_ENABLED else "OFF"
        print(f"\n0 near-misses recorded. Collector flag: {flag}; archive "
              f"gate ARCHIVE_LIVE_SCANS: {settings.ARCHIVE_LIVE_SCANS}. "
              "The lane is wired; no archived scan has produced a qualifying "
              "refusal. (This tool cannot see whether a scan ran — if you "
              "expected rows, check the nightly scan record first.)")
        return 0

    # The NEW reference night comes from the UNFILTERED cohort, so the badge
    # means the same night in every view (review 2026-07-26 finding 12).
    latest = max(r.last_seen for r in rows)

    scope = []
    if args.leg:
        rows = [r for r in rows if r.failing_leg == args.leg]
        scope.append(f"leg={args.leg}")
    if args.ticker:
        rows = [r for r in rows if r.ticker == args.ticker.upper()]
        scope.append(f"ticker={args.ticker.upper()}")
    if args.outcomes:
        rows = [r for r in rows if r.bars_to_date]
        scope.append("outcomes-only")

    if not rows:
        # Affirmative filtered-empty state — the drill's zero is a REPORT,
        # never a traceback (review 2026-07-26 finding 3).
        print(f"\n0 episode(s) match [{', '.join(scope)}] — the exact set "
              "scored is empty. The lane and cohort are fine; nothing under "
              "this filter has been refused near enough to rule.")
        return 0

    seams = sorted({r.engine_config_version[:8] for r in rows})
    rulesets = sorted({r.lane_ruleset for r in rows})
    span = (min(r.first_seen for r in rows), max(r.last_seen for r in rows))
    print(f"\ncohort: {len(rows)} episode(s)"
          + (f" [filtered: {', '.join(scope)} — the EXACT set scored]"
             if scope else "")
          + f"; span {span[0]}..{span[1]}; ruleset(s) {', '.join(rulesets)}; "
          f"engine seam(s) {', '.join(seams)}")

    hidden_fired = 0
    if not args.all:
        visible = [r for r in rows if not r.fired_any_night]
        hidden_fired = len(rows) - len(visible)
        rows = visible

    # Forced rank: NEW episodes first; within a leg by native margin (nearest
    # first); legs grouped alphabetically — never a cross-leg scalar.
    rows.sort(key=lambda r: (
        0 if (r.first_seen == r.last_seen == latest) else 1,
        r.failing_leg, -_native_margin(r)[1], r.ticker))

    shown = rows if args.all else rows[:BATCH]
    print(f"showing {len(shown)} of {len(rows)}"
          + (f" (+{hidden_fired} fired-ticker episode(s) hidden)"
             if hidden_fired else "")
          + ("" if len(shown) == len(rows) and not hidden_fired
             else " — --all for the rest") + "\n")
    for row in shown:
        _print_row(row, latest)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
