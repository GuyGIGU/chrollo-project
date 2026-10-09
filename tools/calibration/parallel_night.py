"""One real scan night, read by BOTH readers (task 15 of the two-eyes-reader build).

The approval pack's last piece, in the plan's words: *"a real scan night replayed by BOTH readers on a COPIED panel,
outside the scan slot, into side files only, with fires, the tally of state words and the wall clock"*. It is the
go-live's dress rehearsal: the same night, read by the old reader as the scan reads it and by the new one as it
would.

* **A copied panel.** The scan's market-data file, its meta and the two eligibility ledgers beside the meta are
  copied into OUT/panel first, and only the copies are read: the service never finds its file held by this tool,
  and the night read is the night copied (its sha256 rides the side file).
* **Outside the scan slot.** It refuses to start from the slot's hour (America/New_York) until two hours after it,
  while the nightly scan and its catch-up run.
* **Side files only** (EC-46): OUT/night.json and OUT/night.txt, stamped with the engine's version under each reader
  and the panel's fingerprint. Nothing here writes the archive or the payload.
* **Both readers through the ONE door** (`engine_alpha.reader.evaluate_ticker`), each in its own pass over the same
  frames (the scan's own frame preparation and eligibility), each with its own wall clock: the old reader as the
  scan's base read, the new one with its switch on.

Not the scan's lanes. Beside the old reader the scan runs its near-miss lane, which records refusals and moves no
fire. Under the new reader the scan still refuses to start (`reader.scan_worker`): wiring the scan is the go-live
plan's, written after his approval.

    python -m tools.calibration.parallel_night OUT
    python -m tools.calibration.parallel_night OUT --panel PATH --meta PATH     # a panel other than the scan's own
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from the repo root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output  # type: ignore
configure_path()

from config import settings  # noqa: E402
from core.calibration.replay import flag_capture  # noqa: E402
from core.pipeline.context.market_context import get_market_context  # noqa: E402
from core.pipeline.market_data.market_calendar import MARKET_TZ  # noqa: E402
from core.pipeline.market_data.market_data_health import eligible_tickers_for  # noqa: E402
from core.pipeline.screening.screener import _prepare_ticker_frames  # noqa: E402
from core.pipeline.universe.descriptor import resolve_universe  # noqa: E402
from engine_alpha import reader  # noqa: E402
from engine_alpha.evaluation import EVAL_ERROR, WATCH_WIRE_STATES  # noqa: E402

#: How long the scan slot lasts from the scan's own hour: the nightly scan (12 to 17 minutes) and its catch-up.
SLOT_HOURS = 2
#: His ten words, the new reader's vocabulary (the table the screen reads).
STATE_WORDS = WATCH_WIRE_STATES
#: The eligibility ledgers the scan reads beside its meta file (`market_data_health._state_path`).
_LEDGERS = (("QUARANTINE_FILENAME", "ticker_quarantine.json"), ("TICKER_ADMISSION_FILENAME", "ticker_admission.json"))


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
    """The night's frames, prepared as the scan prepares them, and the two market numbers the old reader scores
    with. Returns ``(frames, spy_6m_return, breadth_pct, night, tickers)``.

    The market context is computed fresh from the copy and its cache file is written beside the copy, never over
    the service's own (the scan's helper writes one wherever its setting points; here the setting points into OUT).
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
# The two readers, one ticker at a time (top level: the pool pickles them)     #
# --------------------------------------------------------------------------- #
def _number(value):
    return None if value is None else round(float(value), 4)


def _row(ticker: str, result, seconds: float, stamp: dict) -> dict:
    # `reader`: the reader the door says answered (its out-of-band stamp), so a pass can never be the other reader
    # under this one's name.
    row = {"ticker": ticker, "reader": stamp.get("reader"), "fired": isinstance(result, dict),
           "failed": result is EVAL_ERROR, "seconds": round(seconds, 4)}
    if row["fired"]:
        row.update(tier=result.get("Tier"), score=_number(result.get("Score")),
                   trigger=_number(result.get("_trigger_price")), R=_number(result.get("_R")), S=_number(result.get("_S")))
    return row


def read_old(ticker: str, df, spy_6m_return: float, breadth_pct) -> dict:
    """The old reader, as the scan's base read."""
    started = time.perf_counter()
    stamp: dict = {}
    with flag_capture(TWO_EYES_READER_ENABLED=False):
        result = reader.evaluate_ticker(ticker, df, spy_6m_return, breadth_pct, stamp=stamp)
    return _row(ticker, result, time.perf_counter() - started, stamp)


def read_new(ticker: str, df, spy_6m_return: float, breadth_pct) -> dict:
    """The new reader, its switch on, and its word for the chart (none for a read that failed)."""
    started = time.perf_counter()
    watch, stamp = {}, {}
    with flag_capture(TWO_EYES_READER_ENABLED=True):
        result = reader.evaluate_ticker(ticker, df, spy_6m_return, breadth_pct, watch=watch, stamp=stamp)
    row = _row(ticker, result, time.perf_counter() - started, stamp)
    if row["failed"]:
        row["why"] = watch.get("refusal")      # the reader's own sentence: the go-live has to see each one
    else:
        row["state"] = watch.get("state")
    return row


def run_pass(worker, frames: dict, spy_6m_return: float, breadth_pct, workers: int) -> tuple:
    """One reader over every frame; ``(rows, wall clock in seconds)``. ``workers`` 0 reads in this process."""
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


# --------------------------------------------------------------------------- #
# The night, summed up                                                         #
# --------------------------------------------------------------------------- #
def _reader_summary(rows: list, seconds: float, words: bool) -> dict:
    fires = [{key: r.get(key) for key in ("ticker", "tier", "score", "trigger")} for r in rows if r["fired"]]
    out = {
        "read": len(rows),
        "answered_by": sorted({str(r.get("reader")) for r in rows}),
        "fires": sorted(fires, key=lambda f: (-(f["score"] or 0.0), f["ticker"])),
        "silent": sum(1 for r in rows if not r["fired"] and not r["failed"]),
        "failed": sum(1 for r in rows if r["failed"]),
        # Each failed read and the sentence the reader refused it with (the old reader's skip guard keeps none).
        "failures": [[r["ticker"], r.get("why")] for r in rows if r["failed"]],
        "tiers": dict(sorted(Counter(f["tier"] for f in fires if f["tier"]).items())),
        "wall_clock_s": round(seconds, 1),
        "median_read_s": round(statistics.median(r["seconds"] for r in rows), 4) if rows else None,
        "slowest": [[r["ticker"], r["seconds"]] for r in sorted(rows, key=lambda r: (-r["seconds"], r["ticker"]))[:5]],
    }
    out["failure_reasons"] = failure_reasons(out["failures"])
    if words:
        tally = Counter(r.get("state") for r in rows if not r["failed"])
        out["states"] = dict(sorted(tally.items(), key=lambda kv: (-kv[1], str(kv[0]))))
    return out


def summarize(old_rows: list, old_seconds: float, new_rows: list, new_seconds: float) -> dict:
    """Both readers' fires, the new reader's words, each reader's wall clock, and the fires compared by name."""
    old_fired = {r["ticker"] for r in old_rows if r["fired"]}
    new_fired = {r["ticker"] for r in new_rows if r["fired"]}
    return {
        "readers": {"old": _reader_summary(old_rows, old_seconds, words=False),
                    "new": _reader_summary(new_rows, new_seconds, words=True)},
        "both": sorted(old_fired & new_fired),
        "old_only": sorted(old_fired - new_fired),
        "new_only": sorted(new_fired - old_fired),
    }


def _day(iso) -> str:
    return dt.date.fromisoformat(iso).strftime("%a %d/%m/%Y") if iso else "?"


def _names(names: list) -> str:
    return ", ".join(names) if names else "none"


def failure_reasons(failures: list) -> dict:
    """The failed reads counted by the rule that refused them (a reader's sentence is ``rule: detail``)."""
    counts = Counter(str(why or "no reason given").split(": ", 1)[0] for _ticker, why in failures)
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def format_board(summary: dict) -> str:
    """The night in plain words."""
    panel = summary.get("panel") or {}
    old, new = summary["readers"]["old"], summary["readers"]["new"]
    lines = [f"ONE NIGHT, BOTH READERS — {_day(summary.get('night'))}"
             + (f" (a copy of {panel['source']}, {panel.get('read')} of {panel.get('tickers')} tickers read, "
                f"sha256 {panel['sha256'][:12]})" if panel else "")]
    for name, side in (("the old reader", old), ("the new reader", new)):
        lines.append(f"  {name}: {len(side['fires'])} fires of {side['read']} read, {side['failed']} failed reads, "
                     f"wall clock {side['wall_clock_s']:.0f} s (median read {side['median_read_s']} s)")
        tiers = " · ".join(f"{tier} {n}" for tier, n in side["tiers"].items()) or "none"
        lines.append(f"    its fires by tier: {tiers}")
        if side["failures"]:
            reasons = " · ".join(f"{rule} {n}" for rule, n in side["failure_reasons"].items())
            lines.append(f"    its failed reads, by the rule that refused them: {reasons}")
    lines.append(f"  both readers fire on {len(summary['both'])}: {_names(summary['both'])}")
    lines.append(f"  the old reader alone on {len(summary['old_only'])}: {_names(summary['old_only'])}")
    lines.append(f"  the new reader alone on {len(summary['new_only'])}: {_names(summary['new_only'])}")
    lines.append("  the new reader's words: " + " · ".join(f"{word} {n}" for word, n in new["states"].items()))
    for name, side in (("old", old), ("new", new)):
        lines.append(f"  the five slowest reads, {name}: "
                     + ", ".join(f"{ticker} {seconds:.2f} s" for ticker, seconds in side["slowest"]))
    return "\n".join(lines)


def _version(two_eyes: bool) -> str:
    """The engine's version stamp with the new reader's switch as each reader runs it (EC-46's stamp)."""
    from engine_alpha.freeze.manifest import manifest_hash

    with flag_capture(TWO_EYES_READER_ENABLED=two_eyes):
        return manifest_hash()


def replay(panel: str, out_dir: str, *, meta: str | None = None, workers: int | None = None,
           universe=None) -> dict:
    """The whole night: refuse a sealed folder and the slot, copy the panel, read it twice, write the side files."""
    refuse_sealed_output(out_dir)
    if in_scan_slot(now_et()):
        raise RuntimeError("it is the scan slot: run the night outside it")
    uni = resolve_universe(universe)
    if meta is None:
        meta = os.path.join(os.path.dirname(panel), os.path.basename(uni.cache_paths()[1]))
    copied = copy_panel(panel, meta, out_dir)
    frames, spy, breadth, night, tickers = load_night(copied["copy"], copied["meta"], uni)
    workers = (os.cpu_count() or 4) if workers is None else int(workers)
    old_rows, old_seconds = run_pass(read_old, frames, spy, breadth, workers)
    new_rows, new_seconds = run_pass(read_new, frames, spy, breadth, workers)
    summary = summarize(old_rows, old_seconds, new_rows, new_seconds)
    summary.update(night=night.isoformat(), panel={**copied, "tickers": tickers, "read": len(frames)})
    summary["readers"]["old"]["engine_config_version"] = _version(False)
    summary["readers"]["new"]["engine_config_version"] = _version(True)
    with open(os.path.join(out_dir, "night.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=1)
    with open(os.path.join(out_dir, "night.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(format_board(summary) + "\n")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", help="the folder the copy and the side files go to")
    ap.add_argument("--panel", help="the market-data file to copy (default: the scan's own)")
    ap.add_argument("--meta", help="its meta file (default: the meta file beside the panel)")
    ap.add_argument("--workers", type=int, help="worker processes (default: one per core; 0 reads in this process)")
    args = ap.parse_args(argv)
    if in_scan_slot(now_et()):
        print(f"Refusing: it is the scan slot ({int(settings.SCAN_SCHEDULE_HOUR_ET)}:00 to "
              f"{int(settings.SCAN_SCHEDULE_HOUR_ET) + SLOT_HOURS}:00 New York). Nothing was read or written.")
        return 2
    panel = args.panel or resolve_universe(None).cache_paths()[0]
    summary = replay(panel, args.out, meta=args.meta, workers=args.workers)
    print(format_board(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
