"""Replay a saved stock scan through the active new reader, offline and read-only.

This checks the saved fires, their chronology, grades and exact dated wire
blocks. It is not a negative-corpus or ranking-quality study. A different
engine hash is incomparable and refuses the check; it is never auto-repinned.

    python -m tools.audits.live_reader_audit --source PATH --check --repeat
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from tools._bootstrap import configure_path, refuse_sealed_output

ROOT = Path(configure_path())

from config import settings  # noqa: E402
from engine_alpha import reader  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.two_eyes_adapter import to_result  # noqa: E402
from engine_alpha.two_eyes_archive import SCREEN_KEY  # noqa: E402


def same_read(left, right):
    """Keep dated facts exact; ignore float round-off far below quoted cents."""
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(same_read(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(same_read(a, b) for a, b in zip(left, right))
    if type(left) in (int, float) and type(right) in (int, float):
        return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-10)
    return type(left) is type(right) and left == right


def inspect_frame(ticker, frame, expected, *, repeat=False):
    """A cut frame and its saved chart, checked through the public reader door."""
    issues = []
    stamp = {}
    read = reader.read_record(ticker, frame, stamp=stamp)
    if stamp.get('reader') != reader.READER_NEW:
        issues.append('the new reader did not answer')
    if read is None or read.failed or not read.fired:
        reason = None if read is None else read.refusal or read.state
        return issues + [f'saved fire no longer fires: {reason}']
    day = frame.index[-1].date()
    if read.as_of != day:
        issues.append('read date does not match the final supplied session')
    for box in read.boxes:
        if (not all(math.isfinite(v) for v in (box.support.price, box.resistance.price))
                or box.support.price >= box.resistance.price):
            issues.append('box rails are not ordered')
        dates = [box.opened_day, box.support.anchor_day, box.resistance.anchor_day, box.end_day]
        if any(d is not None and d > day for d in dates):
            issues.append('box contains a future date')
    if read.lps is None or not read.lps.start_day <= read.lps.end_day <= day:
        issues.append('LPS chronology is invalid')
    for event in read.events:
        dates = [event.day, event.first_day, event.last_day, event.known_day]
        if any(d is not None and d > day for d in dates):
            issues.append('event contains a future date')
    result = to_result(read)
    if not same_read(result[SCREEN_KEY], expected['two_eyes']):
        issues.append('dated reading differs from the saved scan')
    for actual, saved, label in [(result['Score'], expected['score'], 'score'),
                                 (result['_ta_grade'], expected['ta_grade'], 'technical grade'),
                                 (result['Tier'], expected['tier'], 'tier')]:
        if actual != saved:
            issues.append(f'{label} differs from the saved scan')
    if read.grade is None:
        issues.append('fire has no measured grade')
    elif read.grade.clarity is None or read.grade.clarity.get('method') is None:
        issues.append('clarity could not be composed')
    if repeat:
        again = reader.scan_read(ticker, frame)
        if not isinstance(again, dict) or not same_read(again[SCREEN_KEY], result[SCREEN_KEY]):
            issues.append('repeated scan read differs from the public record')
    return issues


def audit(source: Path, *, repeat=False):
    payload_path = source / 'output/screener_data.json'
    payload = json.loads(payload_path.read_text(encoding='utf-8'))
    identity = payload['scan_identity']
    current_hash = manifest_hash()
    if identity['engine_config_version'] != current_hash:
        raise ValueError('saved scan and current engine hashes differ; compare versions as an experiment')
    charts, tickers = payload['chart_data'], payload['ordered_tickers']
    if not tickers or len(tickers) != len(set(tickers)) or set(tickers) != set(charts):
        raise ValueError('saved scan membership is empty, duplicated or inconsistent')
    panel = pd.read_parquet(source / 'market_data_cache_5y.parquet')
    issues = []
    for number, ticker in enumerate(tickers, 1):
        try:
            # Match the scan's ticker-frame preparation, including volume.
            frame = panel[ticker][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            frame = frame.loc[:pd.Timestamp(identity['scan_date'])]
            if frame.empty or str(frame.index[-1].date()) != identity['scan_date']:
                found = ['cache does not cover the saved scan session']
            else:
                found = inspect_frame(ticker, frame, charts[ticker], repeat=repeat)
        except Exception as exc:
            found = [f'{type(exc).__name__}: {exc}']
        if found:
            issues.append({'ticker': ticker, 'issues': found})
            print(f"  {ticker}: {'; '.join(found)}", flush=True)
        if number % 25 == 0:
            print(f'Checked {number}/{len(tickers)} charts', flush=True)
    return {'reader': settings.TWO_EYES_RULESET, 'engine_config_version': current_hash,
            'scan_identity': identity, 'checked': len(tickers), 'repeat': repeat,
            'passed': len(tickers) - len(issues), 'issues': issues,
            'scope': 'Saved US stock fires only; no negative-corpus or predictive claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--repeat', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        refuse_sealed_output(str(args.output))
    try:
        report = audit(args.source.resolve(), repeat=args.repeat)
    except (ValueError, OSError, KeyError) as exc:
        print(f'REFUSED: {exc}')
        return 2
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(f"Live reader: {report['passed']}/{report['checked']} saved fires passed")
    for row in report['issues']:
        print(f"  {row['ticker']}: {'; '.join(row['issues'])}")
    return int(bool(report['issues']) and args.check)


if __name__ == '__main__':
    raise SystemExit(main())
