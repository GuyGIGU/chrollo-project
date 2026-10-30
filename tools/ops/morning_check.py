"""The morning check (go-live plan task 9): a scanned night checks itself.

Run the morning after a night, outside the scan slot. It sets the night the screen shows beside a replay of the same
night, read again by the reader that scanned it, and says whether they agree:

* **The same fires.** The scan's market-data file is copied and only the copy is read, ticker by ticker, by the
  scan's own worker, once the night's engine stamp is this tree's. The market-cap
  floor is applied the way the scan applied it: from the scan's own recorded removals (its payload's
  ``market_cap_floor.refused_tickers``), so no market cap is looked up again and nothing goes to the network.
* **Every fire archived under that night's stamp.** The archive is opened read-only (sqlite ``mode=ro``); every fire
  on the screen must have its row for that night, stamped with the engine version the screen carries.
* **The charts not read.** The scan's list of charts the new reader would not read, by name and reason, beside the
  replay's own.

Side files only (EC-46): OUT/panel (the copy, overwritten each morning), OUT/nights/<night>.json and .txt, and
OUT/ledger.txt, which keeps one line a night: ``<night> <reader> <stamp> clean`` or ``... NOT CLEAN - <the
differences>``. Checking a night again replaces its line. US stocks only (the screen he trades).

    python -m tools.ops.morning_check                      # the scan's own files, into output/morning_check
    python -m tools.ops.morning_check OUT --panel PATH --meta PATH --payload PATH
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from urllib.request import pathname2url

import pandas as pd

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from the repo root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output  # type: ignore
ROOT = configure_path()

from config import settings  # noqa: E402
from core.archive.db_path import archive_db_path  # noqa: E402
from core.calibration.replay import flag_capture  # noqa: E402
from core.pipeline.context.market_context import get_market_context  # noqa: E402
from core.pipeline.market_data.market_calendar import MARKET_TZ  # noqa: E402
from core.pipeline.market_data.market_data_health import eligible_tickers_for  # noqa: E402
from core.pipeline.screening.screener import _prepare_ticker_frames  # noqa: E402
from core.pipeline.universe.descriptor import resolve_universe  # noqa: E402
from engine_alpha import reader  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.sentinels import EVAL_ERROR  # noqa: E402

LEDGER = "ledger.txt"
CLEAN = "clean"
#: The ledger's reader token. One reader since the old engine retired (31/10/2026); the token stays so the
#: lines written before it keep counting.
READER = "new"
#: How long the scan slot lasts from the scan's own hour: the nightly scan (12 to 17 minutes) and its catch-up.
SLOT_HOURS = 2
#: The eligibility ledgers the scan reads beside its meta file (`market_data_health._state_path`).
_LEDGERS = (("QUARANTINE_FILENAME", "ticker_quarantine.json"), ("TICKER_ADMISSION_FILENAME", "ticker_admission.json"))
#: How many clean new-reader nights in a row the go-live wants before it calls the flip settled.
NIGHTS_WANTED = 10


# --------------------------------------------------------------------------- #
# The slot and the copy                                                        #
# --------------------------------------------------------------------------- #
def now_et() -> dt.datetime:
    """The market's clock, naive."""
    return dt.datetime.now(MARKET_TZ).replace(tzinfo=None)


def in_scan_slot(now: dt.datetime) -> bool:
    """Is it the nightly scan's slot: from its hour to two hours after (America/New_York)."""
    hour = int(settings.SCAN_SCHEDULE_HOUR_ET)
    return hour <= now.hour < hour + SLOT_HOURS


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_panel(panel: str, meta: str, out_dir: str) -> dict:
    """Copy the panel, its meta and the eligibility ledgers beside the meta into OUT/panel; only the copies are
    read from here on."""
    folder = os.path.join(out_dir, "panel")
    os.makedirs(folder, exist_ok=True)
    copy = os.path.join(folder, os.path.basename(panel))
    shutil.copyfile(panel, copy)
    meta_copy = os.path.join(folder, os.path.basename(meta))
    if os.path.exists(meta):
        shutil.copyfile(meta, meta_copy)
    for setting, default in _LEDGERS:
        name = getattr(settings, setting, default)
        if os.path.exists(os.path.join(os.path.dirname(meta), name)):
            shutil.copyfile(os.path.join(os.path.dirname(meta), name), os.path.join(folder, name))
    return {"source": os.path.abspath(panel), "copy": copy, "meta": meta_copy,
            "bytes": os.path.getsize(copy), "sha256": _sha256(copy)}


def load_night(panel_copy: str, meta_copy: str, universe=None) -> tuple:
    """The night's frames, prepared as the scan prepares them, and the two market numbers the scan hands the
    reader. Returns ``(frames, spy_6m_return, breadth_pct, night, tickers)``.

    The market context is computed from the copy and its cache file is written beside the copy, never over the
    service's own (the scan's helper writes one wherever its setting points; here the setting points into OUT). A
    rerun into the same folder on the same night reuses that file, by the helper's own cache rule.
    """
    uni = resolve_universe(universe)
    data = pd.read_parquet(panel_copy, engine=settings.PARQUET_ENGINE)
    if getattr(data.index, "tz", None) is not None:
        data.index = data.index.tz_localize(None)
    index_symbols = list(uni.index_symbols)
    tickers = [s for s in dict.fromkeys(data.columns.get_level_values(0)) if s not in set(index_symbols)]
    eligible = eligible_tickers_for(tickers, meta_file=meta_copy, index_symbols=index_symbols)
    frames = _prepare_ticker_frames(eligible, data, uni)
    context_file = os.path.abspath(os.path.join(os.path.dirname(panel_copy), "market_context.json"))
    with flag_capture(MARKET_CONTEXT_FILENAME=context_file):
        context = get_market_context(data, frames, uni)
    breadth = context.get("breadth_pct")
    return (frames, float(context.get("spy_6m_return") or 0.0), None if breadth is None else float(breadth),
            data.index[-1].date(), len(tickers))


# --------------------------------------------------------------------------- #
# The replay: the scan's own worker, one ticker at a time (top level: pickled) #
# --------------------------------------------------------------------------- #
def _outcome(ticker: str, result) -> dict:
    return {"ticker": ticker, "fired": isinstance(result, dict), "crashed": result is EVAL_ERROR,
            "not_read": result.reason if isinstance(result, reader.NotRead) else None}


def read_new(ticker: str, df, spy_6m_return: float, breadth_pct) -> dict:
    """The scan's own worker (it names a chart the reader would not read)."""
    return _outcome(ticker, reader.scan_read(ticker, df, spy_6m_return, breadth_pct))


def run_pass(worker, frames: dict, spy_6m_return: float, breadth_pct, workers: int) -> tuple:
    """The reader over every frame; ``(rows, wall clock in seconds)``. ``workers`` 0 reads in this process."""
    started = time.perf_counter()
    if workers == 0:
        rows = [worker(ticker, df, spy_6m_return, breadth_pct) for ticker, df in frames.items()]
    else:
        rows, step = [], max(1, len(frames) // 10)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(worker, ticker, df, spy_6m_return, breadth_pct) for ticker, df in frames.items()]
            for done, future in enumerate(as_completed(futures), 1):
                rows.append(future.result())
                if done % step == 0 or done == len(futures):
                    print(f"  {worker.__name__}: {done} of {len(futures)}", flush=True)
    return sorted(rows, key=lambda r: r["ticker"]), time.perf_counter() - started


def _version() -> str:
    """This tree's engine stamp (EC-46's stamp)."""
    return manifest_hash()


# --------------------------------------------------------------------------- #
# What the scan recorded                                                       #
# --------------------------------------------------------------------------- #
def scan_of(payload_path: str) -> dict:
    """The night as the screen's own file records it."""
    with open(payload_path, encoding="utf-8") as f:
        payload = json.load(f)
    identity = payload.get("scan_identity") or {}
    context = payload.get("market_context") or {}
    counts = (context.get("_scan_metrics") or {}).get("counts") or {}
    return {"night": identity.get("scan_date"), "stamp": identity.get("engine_config_version") or "?",
            "universe_type": identity.get("universe_type") or "us_equities",
            "shown": sorted(payload.get("ordered_tickers") or []),
            "floor_removed": sorted((context.get("market_cap_floor") or {}).get("refused_tickers") or []),
            "not_read": sorted(context.get("not_read") or [], key=lambda n: n.get("ticker", "")),
            "crashed": int(counts.get("errored_tickers") or 0),
            "archived": context.get("archived", True) is not False}


def archived_stamps(db_path: str, night_day: str, universe_type: str) -> dict:
    """``{ticker: engine stamp}`` of the night's screener rows, read through a read-only connection."""
    uri = "file:" + pathname2url(os.path.abspath(db_path)) + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        rows = con.execute("SELECT ticker, engine_config_version FROM setup_archive WHERE scan_date = ? "
                           "AND universe_type = ? AND COALESCE(source, 'screener') = 'screener'",
                           (night_day, universe_type)).fetchall()
    finally:
        con.close()
    return {ticker: stamp for ticker, stamp in rows}


def _names(names) -> str:
    return ", ".join(sorted(names))


def archive_differences(scan: dict, db_path: str) -> list:
    if not scan["archived"]:
        return ["not archived: the screen is an undo night's re-read (archiving off); the archive keeps the night "
                "before it"]
    try:
        stamps = archived_stamps(db_path, scan["night"], scan["universe_type"])
    except sqlite3.Error as exc:
        return [f"the archive could not be read: {exc}"]
    shown = set(scan["shown"])
    diffs = []
    missing = shown - set(stamps)
    other = {t for t in shown & set(stamps) if stamps[t] != scan["stamp"]}
    extra = set(stamps) - shown
    if missing:
        diffs.append(f"not in the archive: {_names(missing)}")
    if other:
        diffs.append(f"archived under another engine stamp: {_names(other)}")
    if extra:
        diffs.append(f"archived that night, not on the screen: {_names(extra)}")
    return diffs


def replay_differences(scan: dict, rows: list) -> list:
    fires = {r["ticker"] for r in rows if r["fired"]} - set(scan["floor_removed"])
    shown = set(scan["shown"])
    scan_not_read = {n["ticker"] for n in scan["not_read"]}
    replay_not_read = {r["ticker"] for r in rows if r["not_read"]}
    crashed = sum(1 for r in rows if r["crashed"])
    diffs = []
    if fires - shown:
        diffs.append(f"in the replay, not on the screen: {_names(fires - shown)}")
    if shown - fires:
        diffs.append(f"on the screen, not in the replay: {_names(shown - fires)}")
    if scan_not_read - replay_not_read:
        diffs.append(f"not read by the scan, read by the replay: {_names(scan_not_read - replay_not_read)}")
    if replay_not_read - scan_not_read:
        diffs.append(f"not read by the replay, read by the scan: {_names(replay_not_read - scan_not_read)}")
    if crashed != scan["crashed"]:
        diffs.append(f"crashed reads: {scan['crashed']} in the scan, {crashed} in the replay")
    return diffs


# --------------------------------------------------------------------------- #
# The ledger                                                                   #
# --------------------------------------------------------------------------- #
def write_ledger(path: str, line: str) -> list:
    """Add the night's line, replacing an earlier line of the same night; the lines stay in night order."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
    day = line.split(" ", 1)[0]
    lines = sorted([l for l in lines if l.split(" ", 1)[0] != day] + [line], key=lambda l: l.split(" ", 1)[0])
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return lines


def clean_run(lines: list) -> int:
    """Clean new-reader nights in a row, counted back from the latest night."""
    run = 0
    for line in reversed(lines):
        parts = line.split(" ", 3)
        if len(parts) < 4 or parts[1] != READER or parts[3] != CLEAN:
            break
        run += 1
    return run


# --------------------------------------------------------------------------- #
# The morning                                                                  #
# --------------------------------------------------------------------------- #
def _board(record: dict, run: int) -> str:
    lines = [f"THE MORNING CHECK - the night of {record['night']}, the {record['reader'] or '?'} reader "
             f"(engine {record['stamp'][:8]})",
             f"  the screen: {len(record['shown'])} fires; the replay: {len(record['replay_fires'])} fires of "
             f"{record['read']} read, the floor took out {len(record['floor']['removed'])} "
             f"({record['floor']['from']}): {_names(record['floor']['removed']) or 'none'}",
             f"  charts the scan did not read: {len(record['not_read'])}"]
    lines += [f"    {n['ticker']}: {n.get('reason')}" for n in record["not_read"]]
    if record["differences"]:
        lines.append("  NOT CLEAN:")
        lines += [f"    {d}" for d in record["differences"]]
    else:
        lines.append("  clean: the screen is the replay, every fire is archived under that night's stamp")
    lines.append(f"  clean new-reader nights in a row: {run} of the {NIGHTS_WANTED} wanted")
    return "\n".join(lines)


def check(panel: str, meta: str, payload: str, out_dir: str, *, workers: int | None = None) -> tuple:
    """The whole morning; returns ``(record, ledger lines)``."""
    refuse_sealed_output(out_dir)
    scan = scan_of(payload)
    version = _version()
    which = READER if scan["stamp"] == version else None
    record = {**{k: scan[k] for k in ("night", "stamp", "shown", "not_read")}, "reader": which, "read": 0,
              "replay_fires": [],
              "floor": {"from": "the scan's recorded removals", "removed": scan["floor_removed"]}}
    diffs = []
    if which is None:
        diffs.append(f"the night's engine stamp {scan['stamp'][:8]} is not this tree's ({version[:8]}): the replay "
                     "cannot vouch for it")
    else:
        copied = copy_panel(panel, meta, out_dir)
        frames, spy, breadth, panel_night, _tickers = load_night(copied["copy"], copied["meta"])
        if panel_night.isoformat() != scan["night"]:
            diffs.append(f"the market data on disk ends {panel_night.isoformat()}, the screen is of {scan['night']}: "
                         "not replayed")
        else:
            rows, _seconds = run_pass(read_new, frames, spy, breadth,
                                      (os.cpu_count() or 4) if workers is None else int(workers))
            record.update(read=len(rows), replay_fires=sorted(r["ticker"] for r in rows if r["fired"]),
                          panel_sha256=copied["sha256"])
            diffs += replay_differences(scan, rows)
    diffs += archive_differences(scan, archive_db_path())
    record["differences"] = diffs
    verdict = CLEAN if not diffs else "NOT CLEAN - " + "; ".join(diffs)
    lines = write_ledger(os.path.join(out_dir, LEDGER),
                         f"{scan['night']} {which or '?'} {scan['stamp'][:8]} {verdict}")
    nights = os.path.join(out_dir, "nights")
    os.makedirs(nights, exist_ok=True)
    with open(os.path.join(nights, f"{scan['night']}.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, indent=1)
    with open(os.path.join(nights, f"{scan['night']}.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(_board(record, clean_run(lines)) + "\n")
    return record, lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", nargs="?", default=os.path.join(ROOT, "output", "morning_check"),
                    help="the folder for the copy, the night's side files and the ledger")
    ap.add_argument("--panel", help="the market-data file (default: the scan's own)")
    ap.add_argument("--meta", help="its meta file (default: the scan's own)")
    ap.add_argument("--payload", help="the screen's file of the night (default: the scan's own)")
    ap.add_argument("--workers", type=int, help="worker processes (default: one per core; 0 reads in this process)")
    args = ap.parse_args(argv)
    if in_scan_slot(now_et()):
        print("Refusing: it is the scan slot. Run the morning check after it. Nothing was read or written.")
        return 2
    uni = resolve_universe(None)
    panel, meta = uni.cache_paths()
    os.makedirs(args.out, exist_ok=True)
    record, lines = check(args.panel or panel, args.meta or meta, args.payload or uni.artifact_path(), args.out,
                          workers=args.workers)
    print(_board(record, clean_run(lines)))
    return 0 if not record["differences"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
