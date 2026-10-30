"""The active-reader audit must detect broken reads, drift and wrong data epochs."""
from dataclasses import replace
import datetime as dt
import json

import pandas as pd
import pytest

from tools.audits import live_reader_audit as audit


def test_float_roundoff_is_not_a_changed_read_but_price_and_date_changes_are():
    old = {'r': 100.0, 'day': '2026-10-22', 'ranges_tall': 1.308183036648268}
    assert audit.same_read(old, {**old, 'ranges_tall': 1.3081830366566656})
    assert not audit.same_read(old, {**old, 'r': 100.01})
    assert not audit.same_read(old, {**old, 'day': '2026-10-21'})


def test_sealed_alb_replays_through_both_public_paths():
    from core.calibration.replay import load_sealed_fixture

    frames, _ = load_sealed_fixture()
    frame = frames['ALB:2026-04-13'].loc[:'2026-04-07']
    result = audit.reader.scan_read('ALB', frame)
    chart = {'two_eyes': result[audit.SCREEN_KEY], 'score': result['Score'],
             'ta_grade': result['_ta_grade'], 'tier': result['Tier']}
    assert audit.inspect_frame('ALB', frame, chart, repeat=True) == []
    changed = {**chart, 'score': chart['score'] - 1}
    assert 'score differs from the saved scan' in audit.inspect_frame('ALB', frame, changed)


def test_future_anchor_and_a_lost_fire_are_failures(monkeypatch):
    from engine_alpha.two_eyes.record import Box, Grade, Line, Lps, Read

    day = dt.date(2026, 3, 6)
    read = Read('AAA', day, boxes=(Box(Line(100, day + dt.timedelta(days=1)), Line(90, day), day),),
                lps=Lps(day, day, 'parent', 99), state='fired', close=98,
                grade=Grade(100, 'S', 0, 1, True, clarity={'method': 'test'}))
    frame = pd.DataFrame(index=pd.DatetimeIndex([day]))
    def answer(*args, stamp, **kwargs):
        stamp['reader'] = 'new'
        return read
    monkeypatch.setattr(audit.reader, 'read_record', answer)
    result = audit.to_result(read)
    chart = {'two_eyes': result[audit.SCREEN_KEY], 'score': 100, 'ta_grade': 100, 'tier': 'S'}
    assert 'box contains a future date' in audit.inspect_frame('AAA', frame, chart)
    read = replace(read, lps=None, state='lines, no LPS yet')
    assert any('no longer fires' in issue for issue in audit.inspect_frame('AAA', frame, chart))


def test_audit_refuses_a_different_engine_epoch(tmp_path):
    (tmp_path / 'output').mkdir()
    (tmp_path / 'output/screener_data.json').write_text(json.dumps({
        'scan_identity': {'engine_config_version': 'old-version'},
    }))
    with pytest.raises(ValueError, match='hashes differ'):
        audit.audit(tmp_path)


def test_audit_cuts_the_cache_at_the_saved_session(tmp_path, monkeypatch):
    (tmp_path / 'output').mkdir()
    (tmp_path / 'output/screener_data.json').write_text(json.dumps({
        'scan_identity': {'engine_config_version': audit.manifest_hash(), 'scan_date': '2026-10-22'},
        'chart_data': {'AAA': {}}, 'ordered_tickers': ['AAA'],
    }))
    frame = pd.DataFrame(1.0, index=pd.to_datetime(['2026-10-21', '2026-10-22', '2026-10-23']),
                         columns=pd.MultiIndex.from_product([['AAA'], ['Open', 'High', 'Low', 'Close', 'Volume']]))
    frame.loc['2026-10-21', ('AAA', 'Volume')] = float('nan')
    frame.to_parquet(tmp_path / 'market_data_cache_5y.parquet')
    def inspect(ticker, cut, expected, **kwargs):
        assert str(cut.index[-1].date()) == '2026-10-22'
        assert len(cut) == 1, 'the audit must use the same complete rows as the scan'
        return []
    monkeypatch.setattr(audit, 'inspect_frame', inspect)
    report = audit.audit(tmp_path)
    assert report['checked'] == report['passed'] == 1
