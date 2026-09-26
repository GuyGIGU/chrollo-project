import test from 'node:test';
import assert from 'node:assert/strict';
import {
  engineLine,
  engineTitle,
  failureNotice,
  paneBody,
  paneTitle,
} from './calibrationPaneText.js';

const failure = (cls, message = 'vendor said no') => ({ class: cls, message });

test('paneTitle: loading wins, then the failure class, then the blank prompt', () => {
  assert.equal(paneTitle(true, failure('network')), 'Loading…');
  assert.equal(paneTitle(false, failure('bad_ticker')), 'Lookup failed — bad_ticker');
  assert.equal(paneTitle(false, null), 'Pull up a chart');
});

test('paneBody: a known failure class carries its actionable hint', () => {
  assert.equal(paneBody(false, failure('network', 'backend unreachable')),
    'backend unreachable. Start the dashboard service, then retry.');
  assert.equal(paneBody(false, failure('service_stale', 'old service')),
    'old service. Run update_dashboard.bat to load the new backend, then retry.');
  assert.equal(paneBody(false, failure('future_date', 'in the future')),
    'in the future. Pick a past session.');
});

test('paneBody: every failure class the backend names has a hint', () => {
  for (const cls of ['bad_ticker', 'bad_date', 'future_date', 'rate_limited', 'no_data',
                     'no_bars_at_date', 'network', 'service_stale', 'freeze_failed', 'unknown']) {
    assert.notEqual(paneBody(false, failure(cls, 'm')), 'm', cls);
  }
});

test('paneBody: an unnamed class shows the bare message; loading and blank have their own copy', () => {
  assert.equal(paneBody(false, failure('weird_class', 'something odd')), 'something odd');
  assert.equal(paneBody(true, null), 'Fetching candles through the provider (bounded).');
  assert.equal(paneBody(false, null),
    'Enter a ticker and an as-of date. The chart renders on Chrollo’s own data — '
    + 'marks drawn here are born on the exact frame the engine replays.');
});

test('failureNotice: a rate-limit reads as busy, never as failed', () => {
  assert.equal(failureNotice(failure('rate_limited', 'vendor throttled')),
    'Vendor busy. vendor throttled. The data vendor is briefly throttling — any loaded '
    + 'chart stays up; wait a few seconds and retry.');
  assert.equal(failureNotice(failure('bad_ticker', 'ticker rejected')),
    'Lookup failed — bad_ticker. ticker rejected. Tickers are 1-10 chars: A-Z, 0-9, dot or dash.');
});

test('engineLine: status first, then the plain verdict', () => {
  assert.equal(engineLine(null, 'loading'), 'engine: reading…');
  assert.equal(engineLine({ elected: true }, 'engine read failed — backend unreachable'),
    'engine: engine read failed — backend unreachable');
  assert.equal(engineLine(null, null), 'engine: —');
  assert.equal(engineLine({ elected: false, reason: 'no structure' }, null),
    'engine: does NOT confirm your box here');
});

test('engineLine: an elected box names its rails, span and snap', () => {
  const read = { elected: true, R: 104.5, S: 95.25, box_start_date: '2025-02-03',
                 eval_session: '2025-06-20', snapped: 2 };
  assert.equal(engineLine(read, null),
    'engine finds a box — R 104.50 / S 95.25 · from 2025-02-03 @ 2025-06-20 (snapped −2)');
  assert.equal(engineLine({ ...read, snapped: 0 }, null),
    'engine finds a box — R 104.50 / S 95.25 · from 2025-02-03 @ 2025-06-20');
});

test('engineLine: a missing rail renders the null guard, never NaN', () => {
  const read = { elected: true, R: null, S: undefined, box_start_date: 'a', eval_session: 'b' };
  assert.equal(engineLine(read, null), 'engine finds a box — R — / S — · from a @ b');
});

test('engineTitle: the raw detector reason only when the engine refused', () => {
  assert.equal(engineTitle({ elected: false, reason: 'no structure elects' }),
    'engine detail: no structure elects');
  assert.equal(engineTitle({ elected: false }), undefined);
  assert.equal(engineTitle({ elected: true, reason: 'x' }), undefined);
  assert.equal(engineTitle(null), undefined);
});
