"""
Seed recall report — how many of the cherry-picked seed winners does the engine
actually re-detect, and which does it miss?

The seed archive (``core/archive/seed.py`` ``SEED_SETUPS``) is a recall
benchmark: each ``(ticker, trigger_date)`` is a known historical winner, and
``core.archive.seed`` runs the REAL screener pipeline retrospectively on it,
scanning a ``-WINDOW_BACK / +WINDOW_FWD`` day window. If the engine fires the
setup is archived (``source='seed'``); if it never fires the seed is silently
dropped (only a log line). This report recovers the recall RATE — and, more
usefully, *which* known winners the engine fails to re-find — by comparing the
``SEED_SETUPS`` list against the archived seed rows.

It answers the original question behind the seed archive: "is the engine good
enough to find the winners I already know?" (The live ``/archive/missed-winners``
track answers the forward-looking question; this is the backward-looking recall.)

The default archive-backed report is read-only and never downloads market data.
Fresh modes re-download historical seed data; ``--fresh-capture`` writes only the
baseline JSON, never the archive DB.

Usage:
    python -m core.archive.seed_recall
    python -m core.archive.seed_recall --fresh-check
    python -m core.archive.seed_recall --fresh-capture
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Mapping, Optional
from core.archive.db_path import archive_db_path

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
_DB_PATH = archive_db_path()
_BASELINE_PATH = os.path.join(_PROJECT_ROOT, "tests", "baselines", "seed_recall_baseline.json")

# Hermetic offline guard: a committed OHLCV fixture (frozen seed-winner frames +
# SPY) replayed through the real engine with no network, and its own baseline.
_HERMETIC_FIXTURE = os.path.join(_PROJECT_ROOT, "tests", "baselines", "seed_recall_fixture.parquet")
_HERMETIC_BASELINE = os.path.join(_PROJECT_ROOT, "tests", "baselines", "seed_recall_hermetic_baseline.json")
_HERMETIC_SPY_KEY = "SPY"  # reserved fixture column-group for the RS reference (never a seed)

SeedKey = tuple[str, str]

# Known seed setups where yfinance's adjusted fund history has drifted enough
# that the historical chart no longer represents the operator-labeled setup.
# Keep them visible in reports, but exclude them from recall math.
SEED_RECALL_IGNORES: dict[SeedKey, str] = {
    ("USO", "2026-02-26"): "yfinance adjusted-history drift on fund data",
    ("BRZU", "2026-03-31"): "yfinance adjusted-history drift on leveraged-fund data",
}


# ------------------------------------------------------------------
# Pure logic (unit-tested; no DB / no network)
# ------------------------------------------------------------------
def _dedup(seed_setups: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop duplicate (ticker, date) pairs, preserving order — mirrors the
    in-batch dedup core.archive.seed does."""
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for ticker, day in seed_setups:
        if (ticker, day) in seen:
            continue
        seen.add((ticker, day))
        out.append((ticker, day))
    return out


def filter_ignored_seeds(
    seed_setups: list[tuple[str, str]],
    ignored_seeds: Optional[Mapping[SeedKey, str]] = None,
) -> tuple[list[tuple[str, str]], list[dict]]:
    """Split seed setups into active seeds and explicitly ignored bad-data seeds."""
    ignored_lookup = SEED_RECALL_IGNORES if ignored_seeds is None else ignored_seeds
    active: list[tuple[str, str]] = []
    ignored: list[dict] = []
    for ticker, trigger in _dedup(seed_setups):
        reason = ignored_lookup.get((ticker, trigger))
        if reason:
            ignored.append({
                "ticker": ticker,
                "trigger_date": trigger,
                "reason": reason,
            })
        else:
            active.append((ticker, trigger))
    return active, ignored


def match_seeds(
    seed_setups: list[tuple[str, str]],
    seed_rows: list[dict],
    window_back: int = 10,
    window_fwd: int = 3,
) -> tuple[list[dict], list[dict]]:
    """Split seeds into (hits, misses) by whether the engine re-detected them.

    A seed ``(ticker, trigger_date)`` is a HIT if an archived seed row exists for
    the same ticker whose ``scan_date`` falls within
    ``[trigger_date - window_back, trigger_date + window_fwd]`` calendar days —
    the same window ``core.archive.seed`` scans when deciding whether the
    screener fired. Otherwise it is a MISS (the engine never fired in-window).
    """
    rows_by_ticker: dict[str, list[dict]] = defaultdict(list)
    for row in seed_rows:
        rows_by_ticker[row["ticker"]].append(row)

    hits: list[dict] = []
    misses: list[dict] = []
    for ticker, trigger in _dedup(seed_setups):
        try:
            trigger_d = date.fromisoformat(trigger)
        except ValueError:
            misses.append({"ticker": ticker, "trigger_date": trigger})
            continue
        lo = trigger_d - timedelta(days=window_back)
        hi = trigger_d + timedelta(days=window_fwd)

        match = None
        for row in rows_by_ticker.get(ticker, []):
            try:
                scan_d = date.fromisoformat(row["scan_date"])
            except (ValueError, TypeError):
                continue
            if lo <= scan_d <= hi:
                match = row
                break

        if match is not None:
            hits.append({
                "ticker": ticker,
                "trigger_date": trigger,
                "scan_date": match["scan_date"],
                "tier": match.get("tier"),
                "score": match.get("score"),
            })
        else:
            misses.append({"ticker": ticker, "trigger_date": trigger})

    return hits, misses


def summarize_recall(hits: list[dict], misses: list[dict], ignored: Optional[list[dict]] = None) -> dict:
    """Aggregate hits/misses into the recall scorecard."""
    ignored = ignored or []
    total = len(hits) + len(misses)
    raw_total = total + len(ignored)
    tier_dist: dict[str, int] = defaultdict(int)
    scores: list[float] = []
    for hit in hits:
        tier_dist[hit.get("tier") or "?"] += 1
        if hit.get("score") is not None:
            scores.append(float(hit["score"]))
    scores.sort()
    return {
        "total": total,
        "raw_total": raw_total,
        "fired": len(hits),
        "missed": len(misses),
        "ignored": len(ignored),
        "recall": (len(hits) / total) if total else 0.0,
        "tier_dist": dict(tier_dist),
        "score_min": scores[0] if scores else None,
        "score_median": scores[len(scores) // 2] if scores else None,
        "score_max": scores[-1] if scores else None,
    }


def summarize_fresh_results(
    seed_setups: list[tuple[str, str]],
    results: Mapping[SeedKey, Optional[dict]],
    ignored_seeds: Optional[Mapping[SeedKey, str]] = None,
) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """Build a recall scorecard from fresh engine results.

    ``core.archive.seed.fired_seeds_fresh`` returns ``result|None`` by seed key.
    This normalizes those results to the same ``(summary, hits, misses, ignored)``
    shape used by the archive-backed report.
    """
    active, ignored = filter_ignored_seeds(seed_setups, ignored_seeds)
    hits: list[dict] = []
    misses: list[dict] = []
    for ticker, trigger in active:
        result = results.get((ticker, trigger))
        if result is None:
            misses.append({"ticker": ticker, "trigger_date": trigger})
            continue
        hits.append({
            "ticker": ticker,
            "trigger_date": trigger,
            "scan_date": result.get("scan_date"),
            "tier": result.get("tier"),
            "score": result.get("score"),
        })
    return summarize_recall(hits, misses, ignored), hits, misses, ignored


def diff_against_baseline(
    current: dict,
    current_misses: list[dict],
    baseline: dict,
    tol: float = 1e-9,
) -> tuple[bool, list[str]]:
    """Compare a fresh recall run against a captured baseline.

    Returns ``(ok, lines)``. The guard FAILS (ok=False) when either:
      - recall regresses below the baseline rate (beyond ``tol``), or
      - a known winner that used to be re-found is now missed (a NEW entry in
        the miss-set) — the stricter, more useful signal than the rate alone.

    Recovered names (previously missed, now found) are reported but never fail
    the guard — finding more winners is always allowed.
    """
    lines: list[str] = []
    ok = True

    base_recall = float(baseline.get("recall", 0.0))
    cur_recall = float(current.get("recall", 0.0))
    if cur_recall + tol < base_recall:
        ok = False
        lines.append(f"RECALL REGRESSED: {cur_recall * 100:.1f}% < baseline {base_recall * 100:.1f}%")
    else:
        lines.append(f"recall {cur_recall * 100:.1f}% (baseline {base_recall * 100:.1f}%)")

    base_miss = {(m["ticker"], m["trigger_date"]) for m in baseline.get("misses", [])}
    cur_miss = {(m["ticker"], m["trigger_date"]) for m in current_misses}

    new_misses = sorted(cur_miss - base_miss)
    if new_misses:
        ok = False
        lines.append(f"NEW MISSES ({len(new_misses)}) - winners no longer re-found:")
        lines.extend(f"  {t:<6} {d}" for t, d in new_misses)

    recovered = sorted(base_miss - cur_miss)
    if recovered:
        lines.append(f"Recovered ({len(recovered)}) - previously-missed winners now found:")
        lines.extend(f"  {t:<6} {d}" for t, d in recovered)

    return ok, lines


# ------------------------------------------------------------------
# DB load (read-only) + report
# ------------------------------------------------------------------
def load_seed_rows(db_path: str = _DB_PATH) -> list[dict]:
    """Read archived seed rows (source='seed') from the archive DB, read-only."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Archive DB not found at {db_path}")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.execute(
            "SELECT ticker, scan_date, tier, score FROM setup_archive WHERE source = 'seed'"
        )
        return [
            {"ticker": t, "scan_date": d, "tier": tier, "score": score}
            for (t, d, tier, score) in cur.fetchall()
        ]
    finally:
        con.close()


def _recall_now(db_path: str = _DB_PATH) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """Compute the current recall scorecard from the archive.

    Returns ``(summary, hits, misses, ignored)``. Raises if the seed archive is empty —
    a recall measurement is meaningless without seed rows to match against.
    """
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    from core.archive.seed import SEED_SETUPS, WINDOW_BACK, WINDOW_FWD

    seed_rows = load_seed_rows(db_path)
    if not seed_rows:
        raise RuntimeError(
            "No source='seed' rows in the archive yet — run "
            "`python -m core.archive.seed` first to populate the seed archive."
        )
    active_seeds, ignored = filter_ignored_seeds(SEED_SETUPS)
    hits, misses = match_seeds(active_seeds, seed_rows, WINDOW_BACK, WINDOW_FWD)
    return summarize_recall(hits, misses, ignored), hits, misses, ignored


def _baseline_payload(s: dict, misses: list[dict], ignored: list[dict], basis: str) -> dict:
    return {
        "basis": basis,
        # Provenance only - diff_against_baseline reads just recall/misses.
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "recall": s["recall"],
        "fired": s["fired"],
        "missed": s["missed"],
        "total": s["total"],
        "raw_total": s["raw_total"],
        "ignored": s["ignored"],
        "ignored_seeds": sorted(
            ignored,
            key=lambda m: (m["trigger_date"], m["ticker"]),
        ),
        "misses": sorted(
            ({"ticker": m["ticker"], "trigger_date": m["trigger_date"]} for m in misses),
            key=lambda m: (m["trigger_date"], m["ticker"]),
        ),
    }


def _write_baseline(baseline: dict, baseline_path: str) -> None:
    os.makedirs(os.path.dirname(baseline_path), exist_ok=True)
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)


def capture_baseline(db_path: str = _DB_PATH, baseline_path: str = _BASELINE_PATH) -> dict:
    """Snapshot the current recall + miss-set to a baseline JSON for the guard."""
    s, _hits, misses, ignored = _recall_now(db_path)
    baseline = _baseline_payload(s, misses, ignored, basis="archive")
    _write_baseline(baseline, baseline_path)
    print(f"Captured recall baseline -> {baseline_path}")
    print(
        f"  recall {s['recall'] * 100:.1f}%  "
        f"({s['fired']}/{s['total']} active fired, {s['missed']} missed, {s['ignored']} ignored)"
    )
    return baseline


def check_baseline(db_path: str = _DB_PATH, baseline_path: str = _BASELINE_PATH) -> bool:
    """Compare current recall to the captured baseline. Returns True if it holds.

    The baseline records its measurement basis. ``basis=fresh`` means the guard
    re-runs the current engine instead of comparing against possibly stale local
    archive rows.
    """
    if not os.path.exists(baseline_path):
        print(f"No baseline at {baseline_path} - run with --capture or --fresh-capture first.")
        return False
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    if baseline.get("basis") == "fresh":
        print("Baseline basis is fresh; running the fresh engine guard.")
        return fresh_check_baseline(baseline_path=baseline_path)

    s, _hits, misses, _ignored = _recall_now(db_path)
    ok, lines = diff_against_baseline(s, misses, baseline)

    print("=" * 64)
    print("  SEED RECALL GUARD - archive rows vs. captured baseline")
    print("=" * 64)
    for line in lines:
        print(line)
    print()
    print("PASS - recall held and no winners were lost." if ok
          else "FAIL - recall guard failed; see drift above.")
    if not ok:
        print("Tip: run with --fresh-check before re-seeding; an archive-only fail can mean stale seed rows.")
    return ok


def fresh_check_baseline(baseline_path: str = _BASELINE_PATH) -> bool:
    """Compare the current engine on fresh data to the captured baseline."""
    if not os.path.exists(baseline_path):
        print(f"No baseline at {baseline_path} - run with --capture or --fresh-capture first.")
        return False
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    from core.archive.seed import SEED_SETUPS, fired_seeds_fresh

    results = fired_seeds_fresh(SEED_SETUPS)
    s, _hits, misses, _ignored = summarize_fresh_results(SEED_SETUPS, results)
    ok, lines = diff_against_baseline(s, misses, baseline)

    print("=" * 64)
    print("  SEED RECALL GUARD - fresh engine vs. captured baseline")
    print("=" * 64)
    for line in lines:
        print(line)
    print()
    print("PASS - fresh recall held and no winners were lost." if ok
          else "FAIL - fresh recall guard failed; see drift above.")
    return ok


def capture_fresh_baseline(baseline_path: str = _BASELINE_PATH) -> dict:
    """Snapshot fresh current-engine recall + miss-set to the baseline JSON."""
    from core.archive.seed import SEED_SETUPS, fired_seeds_fresh

    results = fired_seeds_fresh(SEED_SETUPS)
    s, _hits, misses, ignored = summarize_fresh_results(SEED_SETUPS, results)
    baseline = _baseline_payload(s, misses, ignored, basis="fresh")
    _write_baseline(baseline, baseline_path)
    print(f"Captured fresh recall baseline -> {baseline_path}")
    print(
        f"  recall {s['recall'] * 100:.1f}%  "
        f"({s['fired']}/{s['total']} active fired, {s['missed']} missed, {s['ignored']} ignored)"
    )
    return baseline


# ------------------------------------------------------------------
# Hermetic offline guard — frozen OHLCV fixture, no network, hard-gates CI
# ------------------------------------------------------------------
#
# ``--fresh-check`` above is the TRUTH but needs the network + live vendor data,
# so on CI it can only be advisory (a rate-limited runner reds on the FETCH, not
# on a real recall regression). This guard closes that gap: it freezes every
# active seed winner's full download frame + SPY into a committed parquet
# (``--build-fixture``, one-time, network) and then replays those frozen frames
# through the SAME ``_scan_back_seeds`` fold the live recall uses — offline and
# deterministic. Once frozen, the ONLY thing that can move a seed from fired to
# missed is an engine code change, so a detector edit that silently drops a known
# winner reds the build with no network (the sibling of ``tools.regression.shadow_diff``,
# but over the curated winners via the seed twin ``_evaluate_at_date``). The
# frozen closes are a point-in-time adjusted snapshot; that is irrelevant to
# regression detection — the guard measures engine drift on FIXED inputs.
def build_hermetic_fixture(fixture_path: str = _HERMETIC_FIXTURE,
                           reseal: bool = False) -> list[str]:
    """Freeze every active seed winner's download frame + SPY into a committed
    parquet so the recall guard can replay them offline (network; one-time).

    Rebuilding an EXISTING fixture is a baseline recapture — allowed only at an
    explicit flip/seam commit (EC-29), so it refuses unless ``reseal`` (the
    ``--reseal-fixture`` flag) is passed. Every build stamps a ``.meta.json``
    sidecar with the covered ticker set + freeze date, so the artifact records
    which population it froze and when.
    """
    import pandas as pd

    from config import settings
    from core.archive.seed import SEED_SETUPS, _download_seed_data

    if os.path.exists(fixture_path) and not reseal:
        raise RuntimeError(
            f"Hermetic fixture already exists at {fixture_path} — rebuilding it "
            "silently moves the recall guard's ground truth (EC-29: baselines "
            "recapture only at a flip/seam commit). Pass --reseal-fixture with "
            "--build-fixture if this IS a deliberate seam recapture."
        )

    active, _ignored = filter_ignored_seeds(SEED_SETUPS)
    data, spy_close = _download_seed_data(active)

    frames: dict[str, "pd.DataFrame"] = dict(data)
    if spy_close is not None:
        # Only the Close is consumed by the RS reference — freeze just that.
        frames[_HERMETIC_SPY_KEY] = spy_close.to_frame("Close")
    if not frames:
        raise RuntimeError("No seed frames downloaded — cannot build a hermetic fixture.")

    combined = pd.concat(frames, axis=1)  # MultiIndex columns: (ticker, field)
    os.makedirs(os.path.dirname(fixture_path), exist_ok=True)
    combined.to_parquet(fixture_path, engine=settings.PARQUET_ENGINE)

    frozen = sorted(frames)
    covered = [t for t in frozen if t != _HERMETIC_SPY_KEY]
    missing = sorted({t for t, _ in active} - set(covered))

    # Population stamp (EC-46 spirit): the sidecar records WHICH seed
    # population the fixture froze and WHEN, alongside the parquet.
    meta_path = fixture_path + ".meta.json"
    meta = {
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed_tickers": covered,
        "missing_tickers": missing,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"Built hermetic seed fixture: {len(covered)} seed tickers + SPY -> {fixture_path}")
    print(f"  population stamp -> {meta_path}")
    if missing:
        print(f"  WARNING: {len(missing)} seed tickers had no data and will read as MISSES: {', '.join(missing)}")
    return frozen


def _load_hermetic_fixture(
    fixture_path: str = _HERMETIC_FIXTURE,
) -> tuple[dict, Optional[object]]:
    """Load the frozen fixture back into ``({ticker: frame}, spy_close|None)``."""
    import pandas as pd

    from config import settings

    if not os.path.exists(fixture_path):
        raise FileNotFoundError(
            f"No hermetic seed fixture at {fixture_path} — run "
            "`python -m core.archive.seed_recall --build-fixture` first (network, one-time)."
        )
    combined = pd.read_parquet(fixture_path, engine=settings.PARQUET_ENGINE)
    level0 = list(dict.fromkeys(combined.columns.get_level_values(0)))
    frames = {t: combined[t].dropna() for t in level0}
    spy_frame = frames.pop(_HERMETIC_SPY_KEY, None)
    spy_close = None
    if spy_frame is not None and "Close" in spy_frame.columns:
        spy_close = spy_frame["Close"]
    return frames, spy_close


def hermetic_replay(fixture_path: str = _HERMETIC_FIXTURE) -> dict:
    """Replay the frozen seed fixture through the real engine, offline.

    Returns ``{(ticker, trigger_date): result|None}`` — the same shape as
    ``core.archive.seed.fired_seeds_fresh``, but reading the committed parquet
    instead of the network.
    """
    from core.archive.seed import SEED_SETUPS, _scan_back_seeds

    active, _ignored = filter_ignored_seeds(SEED_SETUPS)
    frames, spy_close = _load_hermetic_fixture(fixture_path)
    return _scan_back_seeds(active, frames, spy_close)


def capture_hermetic_baseline(
    fixture_path: str = _HERMETIC_FIXTURE,
    baseline_path: str = _HERMETIC_BASELINE,
) -> dict:
    """Snapshot the offline-replay recall + miss-set as the hermetic baseline."""
    from core.archive.seed import SEED_SETUPS

    results = hermetic_replay(fixture_path)
    s, _hits, misses, ignored = summarize_fresh_results(SEED_SETUPS, results)
    baseline = _baseline_payload(s, misses, ignored, basis="hermetic")
    _write_baseline(baseline, baseline_path)
    print(f"Captured hermetic recall baseline -> {baseline_path}")
    print(
        f"  recall {s['recall'] * 100:.1f}%  "
        f"({s['fired']}/{s['total']} active fired, {s['missed']} missed, {s['ignored']} ignored)"
    )
    return baseline


def hermetic_check_baseline(
    fixture_path: str = _HERMETIC_FIXTURE,
    baseline_path: str = _HERMETIC_BASELINE,
) -> bool:
    """Replay the frozen fixture offline and fail if a winner is newly missed.

    Deterministic + network-free — the hard CI gate the advisory ``--fresh-check``
    cannot be. Returns True if recall held and no known winner was dropped.
    """
    from core.archive.seed import SEED_SETUPS

    if not os.path.exists(baseline_path):
        print(f"No hermetic baseline at {baseline_path} - run with --hermetic-capture first.")
        return False
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    results = hermetic_replay(fixture_path)
    s, _hits, misses, _ignored = summarize_fresh_results(SEED_SETUPS, results)
    ok, lines = diff_against_baseline(s, misses, baseline)

    print("=" * 64)
    print("  SEED RECALL GUARD - HERMETIC offline replay vs. captured baseline")
    print("=" * 64)
    for line in lines:
        print(line)
    print()
    print("PASS - hermetic recall held and no winners were lost." if ok
          else "FAIL - hermetic recall guard failed; a known winner was dropped.")
    return ok


def run(db_path: str = _DB_PATH) -> None:
    print("=" * 64)
    print("  SEED RECALL — can the engine re-find the winners I picked?")
    print("=" * 64)
    print(f"DB: {db_path}")

    try:
        s, hits, misses, ignored = _recall_now(db_path)
    except RuntimeError as e:
        print()
        print(str(e))
        return

    from core.archive.seed import WINDOW_BACK, WINDOW_FWD

    print()
    print(f"Seeds (unique):   {s['raw_total']}")
    print(f"Measured seeds:   {s['total']}")
    print(f"Ignored:          {s['ignored']}")
    print(f"Re-detected:      {s['fired']}")
    print(f"Missed:           {s['missed']}")
    print(f"RECALL:           {s['recall'] * 100:.1f}%")
    print(f"  (window matched: trigger -{WINDOW_BACK} / +{WINDOW_FWD} calendar days)")

    print()
    print("Hit tier distribution:")
    if s["tier_dist"]:
        for tier in sorted(s["tier_dist"]):
            print(f"  {tier}: {s['tier_dist'][tier]}")
    else:
        print("  (none)")
    if s["score_median"] is not None:
        print(f"Hit score:        min {s['score_min']:.1f} / med {s['score_median']:.1f} / max {s['score_max']:.1f}")

    print()
    print(f"MISSES ({len(misses)}) — known winners the engine did NOT re-find in-window:")
    if misses:
        for m in sorted(misses, key=lambda x: x["trigger_date"]):
            print(f"  {m['ticker']:<6} {m['trigger_date']}")
    else:
        print("  (none — perfect recall on the seed set)")

    if ignored:
        print()
        print(f"IGNORED ({len(ignored)}) — excluded from recall math because source data is unreliable:")
        for m in sorted(ignored, key=lambda x: x["trigger_date"]):
            print(f"  {m['ticker']:<6} {m['trigger_date']}  {m['reason']}")

    print()
    print("Note: a MISS means no seed row was archived in-window. With a seeded")
    print("archive that means the engine did not fire; if the archive was never")
    print("seeded, run `python -m core.archive.seed` before trusting these numbers.")


def run_fresh() -> None:
    """Re-evaluate the CURRENT engine against the seed winners on FRESH data,
    bypassing the archive entirely.

    The DB-based report reads whatever rows the archive holds — which can be
    STALE (written by an older engine) and report yesterday's recall. ``--fresh``
    re-runs the live engine on freshly downloaded data so engine changes that
    silently drop winners surface immediately (the blind spot that hid a
    14-winner regression in 2026-06). Needs network + a few minutes — use
    ``--fresh-check`` after touching the detector. Plain ``--check`` also runs
    the fresh guard when the captured baseline is ``basis=fresh``.
    """
    from collections import Counter

    from core.archive.seed import SEED_SETUPS, fired_seeds_fresh

    print("=" * 64)
    print("  SEED RECALL — FRESH re-eval of the CURRENT engine (not the archive)")
    print("=" * 64)
    results = fired_seeds_fresh(SEED_SETUPS)
    s, hits, misses, ignored = summarize_fresh_results(SEED_SETUPS, results)
    total = s["total"]

    print()
    print(f"Measured seeds:   {total}")
    print(f"Re-detected:      {s['fired']}")
    print(f"Missed:           {s['missed']}")
    print(f"RECALL (fresh):   {s['recall'] * 100:.1f}%" if total else "RECALL: n/a")
    tiers = Counter(hit["tier"] for hit in hits)
    print(f"Hit tiers:        {dict(sorted(tiers.items()))}")

    print()
    print(f"MISSES ({len(misses)}) — winners the live engine did NOT re-fire in-window:")
    for miss in sorted(misses, key=lambda x: x["trigger_date"]):
        print(f"  {miss['ticker']:<6} {miss['trigger_date']}")
    if ignored:
        print()
        print(f"IGNORED ({len(ignored)}): "
              f"{[m['ticker'] for m in ignored]}  (unreliable source data)")
    print()
    print("Tip: a FRESH miss the DB-based report counts as a HIT means the archive")
    print("is stale — re-seed (`python -m core.archive.seed --force`) to refresh it.")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Report the screener's recall on the seed winners.")
    ap.add_argument("--db", default=_DB_PATH, help="Path to the archive SQLite DB")
    ap.add_argument("--baseline", default=_BASELINE_PATH, help="Path to the recall baseline JSON")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--capture", action="store_true",
                       help="Snapshot current archive-row recall + miss-set as the baseline")
    group.add_argument("--check", action="store_true",
                       help="Fail (exit 1) if recall regressed or a known winner is newly missed. "
                            "Uses the captured baseline basis.")
    group.add_argument("--fresh", action="store_true",
                       help="Re-evaluate the CURRENT engine on fresh data, bypassing the "
                            "(possibly stale) archive (network; slower)")
    group.add_argument("--fresh-check", action="store_true",
                       help="Run the baseline guard against fresh engine results instead of "
                            "archive rows (network; slower; read-only)")
    group.add_argument("--fresh-capture", action="store_true",
                       help="Snapshot fresh current-engine recall + miss-set as the baseline "
                            "(network; slower; writes only the baseline JSON)")
    group.add_argument("--build-fixture", action="store_true",
                       help="Freeze each active seed winner's OHLCV + SPY into the committed "
                            "hermetic fixture parquet (network; one-time; refuses to overwrite "
                            "an existing fixture without --reseal-fixture)")
    group.add_argument("--hermetic-capture", action="store_true",
                       help="Snapshot the OFFLINE fixture-replay recall + miss-set as the "
                            "hermetic baseline (no network; needs the fixture)")
    group.add_argument("--hermetic-check", action="store_true",
                       help="Replay the committed fixture OFFLINE and fail (exit 1) if a known "
                            "winner is newly missed — the hard, network-free CI gate")
    ap.add_argument("--reseal-fixture", action="store_true",
                    help="Allow --build-fixture to OVERWRITE the existing committed fixture — "
                         "a baseline recapture, legal only at a flip/seam commit (EC-29)")
    args = ap.parse_args()

    if args.reseal_fixture and not args.build_fixture:
        ap.error("--reseal-fixture only modifies --build-fixture")

    try:
        if args.capture:
            capture_baseline(db_path=args.db, baseline_path=args.baseline)
        elif args.check:
            ok = check_baseline(db_path=args.db, baseline_path=args.baseline)
            sys.exit(0 if ok else 1)
        elif args.fresh:
            run_fresh()
        elif args.fresh_check:
            ok = fresh_check_baseline(baseline_path=args.baseline)
            sys.exit(0 if ok else 1)
        elif args.fresh_capture:
            capture_fresh_baseline(baseline_path=args.baseline)
        elif args.build_fixture:
            build_hermetic_fixture(reseal=args.reseal_fixture)
        elif args.hermetic_capture:
            capture_hermetic_baseline()
        elif args.hermetic_check:
            ok = hermetic_check_baseline()
            sys.exit(0 if ok else 1)
        else:
            run(db_path=args.db)
    except RuntimeError as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
