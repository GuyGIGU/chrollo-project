"""The species fixture pair + dark ratchet baseline (program Task 10).

Freezes MAN (the operator's specimen, truncated to the LAST session BEFORE his
2026-08-13 breakout) and FTNT (the fired control, at its 2026-08-13 fire) from
the cache into a committed parquet, content-digest-bound (EC-12), and captures
two reads as the RATCHET baseline:

  * the SPECIES read (``species_watch`` under production values — the species
    flags are what the watch itself embodies), and
  * the DEFAULT read (``read_structure`` at production values, flags off).

The baseline is a CHANGE DETECTOR, not a must-fire spec: any deviation fails
the acceptance battery. Species must-fire marks arrive only by per-mark
operator graduation (EC-9); the sealed 28/33 corpus is untouched by this tool.

DELIBERATE BASELINE WRITER (the marks_corpus --build-fixture precedent): this
tool intentionally writes under tests/baselines/ — re-running it is a ratchet
recapture, legal ONLY in a declared flip/seam commit with committed evidence
(EC-29). It is not routed through refuse_sealed_output for exactly that
reason; do not point any other tool at these paths.

    python -m tools.power_play_fixture --build [--cache PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os

try:
    from tools._bootstrap import configure_path
except ImportError:                                  # invoked as a script
    from _bootstrap import configure_path            # type: ignore
_ROOT = configure_path()

import pandas as pd                                          # noqa: E402

from config import settings                                  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash       # noqa: E402

FIXTURE_PARQUET = os.path.join(_ROOT, "tests", "baselines",
                               "power_play_fixture.parquet")
BASELINE_JSON = os.path.join(_ROOT, "tests", "baselines",
                             "power_play_baseline.json")

# The frozen pair: ticker -> as-of. MAN stops the day BEFORE his breakout
# (the whole point: the species read must see it pre-breakout); FTNT at the
# session it fired tier-S live.
FIXTURE_AS_OF = {"MAN": "2026-08-12", "FTNT": "2026-08-13"}


def frame_digest(df: pd.DataFrame) -> str:
    """Content digest over the frame's OHLCV values (EC-12): deterministic,
    engine-independent, recomputed at check time by the battery.

    ``lineterminator`` is pinned to LF because ``to_csv`` otherwise defaults to
    ``os.linesep`` — the digest then hashed the OPERATING SYSTEM alongside the
    data, so the same frame sealed as two different values on Windows and
    Linux and this battery could never pass off-Windows (every CI run from
    2026-08-12). ``frame_store.ohlcv_digest``, which binds the operator's
    marks, always joined on an explicit "\n" and was never affected.
    """
    canon = df[["Open", "High", "Low", "Close", "Volume"]].to_csv(
        float_format="%.8f", lineterminator="\n")
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def capture(df: pd.DataFrame) -> dict:
    """The two reads the ratchet freezes, on ONE fixture frame."""
    from engine_alpha.evaluation import _prepare_eval_frame_with_reason
    from engine_alpha.structure.narrative.reader import read_structure
    from engine_alpha.evaluation import species_watch

    watch, stats = species_watch(df)
    species = {"state": None if watch is None else watch["state"],
               "clock": None if watch is None else watch["clock"],
               "fields": None if watch is None else watch["fields"],
               "stats": {k: v for k, v in sorted(stats.items())
                         if k != "pp_eval_ms"}}

    prep, reason = _prepare_eval_frame_with_reason(df)
    if prep is None:
        default = {"elects": False, "refused": reason[0] if reason else "?"}
    else:
        pdf = prep["df"]
        atr = float(pdf.iloc[-int(settings.STRUCTURE_ATR_SAMPLE_OFFSET)]["ATR_10"])
        s = read_structure(pdf, atr)
        default = {"elects": bool(s is not None and s.box is not None)}
        if default["elects"]:
            default["box_open"] = str(pdf.index[int(s.box.start_bar)].date())
    return {"species": species, "default_read": default}


def build(cache_path=None) -> None:
    cache = pd.read_parquet(cache_path or settings.CACHE_FILENAME,
                            engine=settings.PARQUET_ENGINE)
    frames = {}
    baseline = {"manifest": manifest_hash(), "tickers": {}}
    for ticker, as_of in FIXTURE_AS_OF.items():
        raw = cache[ticker].dropna()
        frame = raw.loc[:pd.Timestamp(as_of)]
        frames[ticker] = frame
        entry = {"as_of": as_of, "bars": int(len(frame)),
                 "frame_digest": frame_digest(frame)}
        entry.update(capture(frame))
        baseline["tickers"][ticker] = entry
        print(f"  {ticker} @ {as_of}: {entry['bars']} bars, "
              f"species={entry['species']['state']}, "
              f"default elects={entry['default_read']['elects']}")

    combined = pd.concat(frames, axis=1)         # (ticker, field) MultiIndex
    os.makedirs(os.path.dirname(FIXTURE_PARQUET), exist_ok=True)
    combined.to_parquet(FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    with open(BASELINE_JSON, "w", encoding="utf-8") as fh:
        json.dump(baseline, fh, indent=1, sort_keys=True)
    print(f"  wrote {FIXTURE_PARQUET}\n  wrote {BASELINE_JSON}")


def load_fixture():
    """The committed pair, as {ticker: frame} + the baseline dict."""
    data = pd.read_parquet(FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    with open(BASELINE_JSON, encoding="utf-8") as fh:
        baseline = json.load(fh)
    frames = {t: data[t].dropna()
              for t in set(data.columns.get_level_values(0))}
    return frames, baseline


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--cache", default=None)
    args = ap.parse_args(argv)
    if args.build:
        build(args.cache)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
