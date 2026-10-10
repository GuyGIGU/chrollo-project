"""The morning check (go-live plan task 9): a scanned night checks itself.

Run the morning after a night, outside the scan slot. It sets the night the screen shows beside a replay of the same
night, read again by the reader that scanned it, and says whether they agree:

* **The same fires.** The scan's market-data file is copied (`parallel_night.copy_panel`) and only the copy is read,
  ticker by ticker, by the scan's own worker for the reader whose engine stamp the night carries. The market-cap
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
import json
import os
import sqlite3
import sys
from urllib.request import pathname2url

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from the repo root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output  # type: ignore
ROOT = configure_path()

from core.archive.db_path import archive_db_path  # noqa: E402
from core.calibration.replay import flag_capture  # noqa: E402
from core.pipeline.universe.descriptor import resolve_universe  # noqa: E402
from engine_alpha import reader  # noqa: E402
from engine_alpha.evaluation import EVAL_ERROR  # noqa: E402
from tools.calibration import parallel_night as night  # noqa: E402

LEDGER = "ledger.txt"
CLEAN = "clean"
#: How many clean new-reader nights in a row the go-live wants before it calls the flip settled.
NIGHTS_WANTED = 10


# --------------------------------------------------------------------------- #
# The replay: the scan's own worker, one ticker at a time (top level: pickled) #
# --------------------------------------------------------------------------- #
def _outcome(ticker: str, result) -> dict:
    return {"ticker": ticker, "fired": isinstance(result, dict), "crashed": result is EVAL_ERROR,
            "not_read": result.reason if isinstance(result, reader.NotRead) else None}


def read_new(ticker: str, df, spy_6m_return: float, breadth_pct) -> dict:
    """The new reader's scan worker (it names a chart it would not read)."""
    with flag_capture(TWO_EYES_READER_ENABLED=True):
        return _outcome(ticker, reader.scan_read(ticker, df, spy_6m_return, breadth_pct))


def read_old(ticker: str, df, spy_6m_return: float, breadth_pct) -> dict:
    """The old reader's read, as the scan's base read (its lanes move no fire)."""
    with flag_capture(TWO_EYES_READER_ENABLED=False):
        return _outcome(ticker, reader.evaluate_ticker(ticker, df, spy_6m_return, breadth_pct))


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
        if len(parts) < 4 or parts[1] != reader.READER_NEW or parts[3] != CLEAN:
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
    versions = {reader.READER_NEW: night._version(True), reader.READER_OLD: night._version(False)}
    which = next((name for name, stamp in versions.items() if stamp == scan["stamp"]), None)
    record = {**{k: scan[k] for k in ("night", "stamp", "shown", "not_read")}, "reader": which, "read": 0,
              "replay_fires": [],
              "floor": {"from": "the scan's recorded removals", "removed": scan["floor_removed"]}}
    diffs = []
    if which is None:
        diffs.append(f"the night's engine stamp {scan['stamp'][:8]} is neither reader of this tree (old "
                     f"{versions[reader.READER_OLD][:8]}, new {versions[reader.READER_NEW][:8]}): the replay "
                     "cannot vouch for it")
    else:
        copied = night.copy_panel(panel, meta, out_dir)
        frames, spy, breadth, panel_night, _tickers = night.load_night(copied["copy"], copied["meta"])
        if panel_night.isoformat() != scan["night"]:
            diffs.append(f"the market data on disk ends {panel_night.isoformat()}, the screen is of {scan['night']}: "
                         "not replayed")
        else:
            worker = read_new if which == reader.READER_NEW else read_old
            rows, _seconds = night.run_pass(worker, frames, spy, breadth,
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
    if night.in_scan_slot(night.now_et()):
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
