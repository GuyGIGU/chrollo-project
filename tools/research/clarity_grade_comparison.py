"""Replay the current operator examples and live scan through experimental clarity.

Read-only against the source checkout; write a comparison JSON to --output.
The source supplies the live DB, digest-bound frames, cache and saved scan.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

import pandas as pd

from tools._bootstrap import configure_path, refuse_sealed_output

configure_path(backend=True)

from config import settings
from domains.calibration import frame_store
from engine_alpha import reader
from engine_alpha.result import graded_read


def compare(source: Path) -> dict:
    con = sqlite3.connect((source / 'webapp/backend/trading_journal.db').as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    con.execute('BEGIN')
    marks = [dict(r) for r in con.execute('SELECT * FROM calibration_marks ORDER BY ticker, as_of_date')]
    events = [dict(r) for r in con.execute('SELECT * FROM calibration_mark_events')]
    hearts = [dict(r) for r in con.execute("SELECT * FROM setup_reviews WHERE verdict='liked'")]
    con.close()
    frame_store.FRAMES_DIR = str(source / 'calibration_frames')
    panel = pd.read_parquet(source / 'market_data_cache_5y.parquet')
    rows = []

    def assess(group, key, ticker, day, frame):
        raw = reader.read(ticker, frame.loc[:pd.Timestamp(day)])
        scored = graded_read(raw)
        g, old = scored.grade, raw.grade
        rows.append({'group': group, 'key': key, 'ticker': ticker, 'day': day,
                     'fired': raw.fired, 'failed': raw.failed, 'state': raw.state,
                     'integrity_score': None if old is None else old.score,
                     'integrity_letter': None if old is None else old.letter,
                     'score': None if g is None else g.score, 'letter': None if g is None else g.letter,
                     'clarity': None if g is None else g.clarity})

    for m in marks:
        eligible = [e for e in events if e['mark_id'] == m['id'] and e['event_type'] == 'lps'
                    and e['end_date'] <= m['as_of_date']
                    and (not m['trigger_date'] or e['end_date'] < m['trigger_date'])]
        day = max((e['end_date'] for e in eligible), default=m['as_of_date'])
        frame = frame_store.load_frame(m['ticker'], m['as_of_date'], digest=m['frame_digest'])
        if frame is None:
            raise ValueError(f"missing frozen frame for {m['ticker']} / {m['id']}")
        assess('calibration', m['id'], m['ticker'], day, frame)
    for heart in hearts:
        ticker = heart['ticker']
        frame = panel[ticker][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        assess('heart', heart['id'], ticker, heart['scan_date'], frame)
    payload = json.loads((source / 'output/screener_data.json').read_text(encoding='utf-8'))
    day = payload['scan_identity']['scan_date']
    for ticker in payload['ordered_tickers']:
        frame = panel[ticker][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        assess('live', ticker, ticker, day, frame)
    summary = {}
    for group in ['calibration', 'heart', 'live']:
        own = [r for r in rows if r['group'] == group]
        summary[group] = {'n': len(own), 'before': dict(Counter(r['integrity_letter'] for r in own)),
                          'after': dict(Counter(r['letter'] for r in own)),
                          'changed': sum(r['score'] != r['integrity_score'] for r in own),
                          'failed': sum(r['failed'] for r in own)}
        facts = [r['clarity']['facts'] for r in own if r['clarity']]
        print(group, summary[group], flush=True)
        if facts:
            print(pd.DataFrame(facts)[['main_swing_share', 'rail_alignment_error']].describe().round(3).to_string(), flush=True)
    return {'ruleset': settings.ALPHA_RULESET, 'summary': summary, 'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    refuse_sealed_output(str(args.output))
    report = compare(args.source.resolve())
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    main()
