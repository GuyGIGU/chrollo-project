import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CALIBRATION_VIEW_BARS,
  cacheKey,
  cacheKeysFor,
  classifyChartResponse,
  initialVisibleRange,
  normalizeTicker,
} from './calibrationChartUtils.js';

test('normalizeTicker folds whitespace and case', () => {
  assert.equal(normalizeTicker('  klac '), 'KLAC');
  assert.equal(normalizeTicker(null), '');
});

test('cacheKey uses the normalized ticker', () => {
  assert.equal(cacheKey(' bodi ', '2026-04-15'), 'BODI|2026-04-15');
});

test('cacheKeysFor keeps a throttle-time preserved copy out of the sitting cache', () => {
  const preserved = (reason) => ({ ticker: 'SKYT', as_of_session: '2026-04-13', source: 'preserved', preserved_reason: reason });
  assert.deepEqual(cacheKeysFor('SKYT|2026-04-13', preserved('rate_limited')), []);
  assert.deepEqual(cacheKeysFor('SKYT|2026-04-13', preserved('vendor_error')), []);
  // The vendor has no data at all (a delisted ticker): the copy IS the chart.
  assert.deepEqual(cacheKeysFor('SKYT|2026-04-13', preserved('no_data')), ['SKYT|2026-04-13']);
});

test('cacheKeysFor aliases the resolved session (Sunday and its Friday are one payload)', () => {
  const body = { ticker: 'KLAC', as_of_session: '2025-09-05' };
  assert.deepEqual(cacheKeysFor('KLAC|2025-09-07', body),
    ['KLAC|2025-09-07', 'KLAC|2025-09-05']);
  // Requested a real session: one key, no duplicate alias.
  assert.deepEqual(cacheKeysFor('KLAC|2025-09-05', body), ['KLAC|2025-09-05']);
  assert.deepEqual(cacheKeysFor('KLAC|2025-09-05', null), ['KLAC|2025-09-05']);
});

test('classifyChartResponse: real payload', () => {
  const out = classifyChartResponse(true, 200, { candles: [] });
  assert.equal(out.kind, 'chart');
});

test('classifyChartResponse: 200 without candles is the stale service, never a chart', () => {
  const out = classifyChartResponse(true, 200, '<!doctype html>');
  assert.equal(out.kind, 'failure');
  assert.equal(out.failure.class, 'service_stale');
});

test('classifyChartResponse: named failure detail passes through', () => {
  const detail = { class: 'no_data', message: 'vendor returned nothing' };
  const out = classifyChartResponse(false, 404, { detail });
  assert.deepEqual(out.failure, detail);
});

test('classifyChartResponse: unclassified failure keeps the status visible', () => {
  const out = classifyChartResponse(false, 500, null);
  assert.equal(out.failure.class, 'unknown');
  assert.match(out.failure.message, /500/);
});

// ---- the opening frame -------------------------------------------------------

// `n` consecutive daily bars from 2025-01-01, one per calendar day — index i is
// dated day(i), so the expected logical indexes read straight off the dates.
const day = (i) => new Date(Date.UTC(2025, 0, 1 + i)).toISOString().slice(0, 10);
const bars = (n) => Array.from({ length: n }, (_, i) => ({ time: day(i), open: 1, high: 1, low: 1, close: 1 }));

test('initialVisibleRange: a fresh lookup opens on the last 180 bars to the as-of, plus 12 forward', () => {
  assert.equal(CALIBRATION_VIEW_BARS, 180);
  // as-of = bar 249: bars 70..249 are the 180 observed, 12 forward bars past the line.
  assert.deepEqual(initialVisibleRange(bars(300), day(249)), { from: 70, to: 261 });
  // No saved setup and an empty hint read the same.
  assert.deepEqual(initialVisibleRange(bars(300), day(249), {}), { from: 70, to: 261 });
});

test('initialVisibleRange: a saved box older than the 180 bars widens the left edge to show it all', () => {
  // Box starts at bar 40: the view opens 25 bars (about a month) before it.
  assert.deepEqual(initialVisibleRange(bars(300), day(249), { boxStart: day(40) }),
    { from: 15, to: 261 });
  // A box inside the 180 bars never NARROWS the view.
  assert.deepEqual(initialVisibleRange(bars(300), day(249), { boxStart: day(200) }),
    { from: 70, to: 261 });
});

test('initialVisibleRange: a saved buy past the forward edge widens the right edge to it', () => {
  assert.deepEqual(initialVisibleRange(bars(300), day(249), { triggerDate: day(280) }),
    { from: 70, to: 283 });
  // A buy already on screen leaves the forward edge alone.
  assert.deepEqual(initialVisibleRange(bars(300), day(249), { triggerDate: day(255) }),
    { from: 70, to: 261 });
});

test('initialVisibleRange: the left edge clamps at the first bar', () => {
  assert.deepEqual(initialVisibleRange(bars(300), day(100)), { from: 0, to: 112 });
  assert.deepEqual(initialVisibleRange(bars(300), day(249), { boxStart: day(10) }),
    { from: 0, to: 261 });
  // A box drawn before the window's first bar opens at the first bar too.
  assert.deepEqual(initialVisibleRange(bars(300).slice(50), day(249), { boxStart: day(10) }),
    { from: 0, to: 211 });
});

test('initialVisibleRange: the as-of bar is found BY DATE, never by bar count', () => {
  // A non-finite row before the as-of is skipped by the backend, so the as-of
  // bar sits one index earlier than its position in the frame.
  const skipped = bars(300).filter((_, i) => i !== 100);
  assert.deepEqual(initialVisibleRange(skipped, day(249)), { from: 69, to: 260 });
  // The as-of row itself skipped: the frame ends on the bar before it.
  const asOfGone = bars(300).filter((_, i) => i !== 249);
  assert.deepEqual(initialVisibleRange(asOfGone, day(249)), { from: 69, to: 260 });
});

test('initialVisibleRange: no bars or no known as-of -> null (the caller fits the content)', () => {
  assert.equal(initialVisibleRange([], day(10)), null);
  assert.equal(initialVisibleRange(null, day(10)), null);
  assert.equal(initialVisibleRange(bars(30), null), null);
  assert.equal(initialVisibleRange(bars(30), undefined, { boxStart: day(3) }), null);
  // An as-of before every bar names no bar to frame.
  assert.equal(initialVisibleRange(bars(30).slice(5), day(2)), null);
});
