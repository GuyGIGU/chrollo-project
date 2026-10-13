// The phase overlay's pure read (build task 15 of the two-eyes reader): the two-eyes reader's dated block, located.
//
// The wire carries the box's days and the LPS's days; this module only finds their bars and builds the bands the
// chart lights. The old engine's own fields (bar offsets, the LPS zone's price box) are not carried on a two-eyes
// row, so its bands come from the block or not at all.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { buildPhaseRegions, rootSwingRange, storyRegionId } from './chartPhaseOverlay.js';

// 40 daily candles, 2024-01-01 onward (28 days a month, as chartGeometry.test.js builds them): index 14 is
// 2024-01-15, 28 is 2024-02-01; each bar's high is 11 + i and its low 9 + i.
const makeCandles = (n) =>
  Array.from({ length: n }, (_, i) => {
    const day = String((i % 28) + 1).padStart(2, '0');
    const month = String(Math.floor(i / 28) + 1).padStart(2, '0');
    return { time: `2024-${month}-${day}`, open: 10 + i, high: 11 + i, low: 9 + i, close: 10 + i };
  });

const twoEyesPayload = (block = {}) => ({
  candles: makeCandles(40),
  R: 20,
  S: 10,
  two_eyes: {
    boxes: [
      { role: 'parent', r: 20, r_day: '2024-01-16', s: 10, s_day: '2024-01-18', opened: '2024-01-15', end: null },
    ],
    lps: { against: 'parent', how: null, start: '2024-02-02', end: '2024-02-03', trigger: 18.5 },
    ...block,
  },
});

test('rootSwingRange: a two-eyes box greys the span between its two anchor days', () => {
  assert.deepEqual(rootSwingRange(twoEyesPayload(), makeCandles(40)), { startIndex: 15, endIndex: 17 });
  // The anchor days in either order, never inverted.
  const flipped = twoEyesPayload({
    boxes: [{ role: 'parent', r: 20, r_day: '2024-01-18', s: 10, s_day: '2024-01-16', opened: '2024-01-15', end: null }],
  });
  assert.deepEqual(rootSwingRange(flipped, makeCandles(40)), { startIndex: 15, endIndex: 17 });
  // No parent on the block: no grey, and never the old engine's bar offsets.
  assert.equal(rootSwingRange({ ...twoEyesPayload({ boxes: [] }), base_len: 6, r_anchor: 1, s_anchor: 2 },
    makeCandles(40)), null);
});

test('buildPhaseRegions: a two-eyes row lights its box from the day it opened and its LPS over its own days', () => {
  const regions = buildPhaseRegions(twoEyesPayload());
  const byKey = Object.fromEntries(regions.map((region) => [region.key, region]));
  assert.deepEqual(Object.keys(byKey).sort(), ['b', 'lps']);
  assert.equal(byKey.b.startIndex, 14);
  assert.equal(byKey.b.endIndex, 39);
  assert.equal(byKey.b.range, 'setupBox');
  assert.equal(byKey.lps.startIndex, 29);
  assert.equal(byKey.lps.endIndex, 30);
  // The LPS band spans its own bars, located: the lowest low and the highest high of its days.
  assert.equal(byKey.lps.low, 9 + 29);
  assert.equal(byKey.lps.high, 11 + 30);
});

test('buildPhaseRegions: a two-eyes row lights its mini and each word of its story on its own key (Tue 13/10/2026)', () => {
  const regions = buildPhaseRegions(twoEyesPayload({
    boxes: [
      { role: 'parent', r: 20, r_day: '2024-01-16', s: 10, s_day: '2024-01-18', opened: '2024-01-15', end: null },
      { role: 'mini', r: 18, r_day: '2024-01-24', s: 15, s_day: '2024-01-25', opened: '2024-01-24', end: null },
    ],
    events: [
      { kind: 'spring', day: '2024-01-20', price: 9.5, first: '2024-01-19', last: '2024-01-22', size: 0.8, committed: true },
      { kind: 'spring test', day: '2024-01-26', price: 10.2, first: null, last: null, size: null, committed: true },
      { kind: 'Phase D', day: '2024-01-27', price: 12, first: null, last: null, size: null, committed: true, note: 'SOS' },
    ],
  }));
  const byId = Object.fromEntries(regions.map((region) => [region.id, region]));
  assert.deepEqual(regions.map((region) => region.key), ['b', 'mini', 'story', 'story', 'story', 'lps']);
  // The mini over its own lines from the day it opened; never the box's key, so lighting the box lights it alone.
  assert.deepEqual([byId.mini.startIndex, byId.mini.endIndex, byId.mini.low, byId.mini.high], [23, 39, 15, 18]);
  // A word over its own swing, a word with no swing on its one day, Phase D from its day to the setup's last bar.
  const spring = byId['story:spring:2024-01-20'];
  assert.deepEqual([spring.startIndex, spring.endIndex, spring.token], [18, 21, '--accent-pink']);
  const test_ = byId['story:spring test:2024-01-26'];
  assert.deepEqual([test_.startIndex, test_.endIndex], [25, 25]);
  const phaseD = byId['story:Phase D:2024-01-27'];
  assert.deepEqual([phaseD.startIndex, phaseD.endIndex, phaseD.token], [26, 39, '--accent-blue']);
  assert.equal(storyRegionId({ kind: 'SOS', day: '2024-01-27' }), 'story:SOS:2024-01-27');
});

test('buildPhaseRegions: a two-eyes row with no LPS window lights its box alone', () => {
  const regions = buildPhaseRegions(twoEyesPayload({ lps: { against: 'parent' } }));
  assert.deepEqual(regions.map((region) => region.key), ['b']);
});

test('buildPhaseRegions: an old row is read exactly as before', () => {
  const regions = buildPhaseRegions({
    candles: makeCandles(40),
    R: 20,
    S: 10,
    base_len: 10,
    _phase_b_start_date: '2024-02-01',
    _lps_zone_start_date: '2024-02-05',
    _lps_zone_end_date: '2024-02-06',
    _lps_zone_low: 12,
    _lps_zone_high: 14,
  });
  assert.deepEqual(regions.map((region) => [region.key, region.startIndex, region.endIndex]),
    [['b', 28, 39], ['lps', 32, 33]]);
});
