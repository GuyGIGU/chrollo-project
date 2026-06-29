import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  finiteNumber,
  buildLevelData,
  buildFullLevelData,
  buildPositiveLevel,
  candleDate,
  indexOnOrAfter,
  setupIndexes,
  miniFocusLogicalRange,
  colorMiniCandles,
  colorTimeframeCandles,
  tradeVisibleLogicalRange,
} from './chartGeometry.js';

// Build N daily candles starting 2024-01-01, no color set.
const makeCandles = (n) =>
  Array.from({ length: n }, (_, i) => {
    const day = String((i % 28) + 1).padStart(2, '0');
    const month = String(Math.floor(i / 28) + 1).padStart(2, '0');
    return { time: `2024-${month}-${day}`, open: 10 + i, high: 11 + i, low: 9 + i, close: 10 + i };
  });

test('finiteNumber: null/empty/NaN -> null, finite -> number', () => {
  assert.equal(finiteNumber(null), null);
  assert.equal(finiteNumber(undefined), null);
  assert.equal(finiteNumber(''), null);
  assert.equal(finiteNumber('abc'), null);
  assert.equal(finiteNumber(0), 0); // 0 is finite, must NOT become null
  assert.equal(finiteNumber('12.5'), 12.5);
  assert.equal(finiteNumber(42), 42);
});

test('buildLevelData: repeats value from startIndex to end', () => {
  const candles = makeCandles(5);
  const out = buildLevelData(candles, 2, 99);
  assert.equal(out.length, 3);
  assert.deepEqual(out[0], { time: candles[2].time, value: 99 });
  assert.equal(out.at(-1).time, candles[4].time);
});

test('buildFullLevelData: one point per candle', () => {
  const candles = makeCandles(4);
  const out = buildFullLevelData(candles, 7);
  assert.equal(out.length, 4);
  assert.ok(out.every((p) => p.value === 7));
});

test('buildPositiveLevel: empty for non-finite or <= 0', () => {
  const candles = makeCandles(3);
  assert.deepEqual(buildPositiveLevel(candles, 0), []);
  assert.deepEqual(buildPositiveLevel(candles, -5), []);
  assert.deepEqual(buildPositiveLevel(candles, null), []);
  assert.equal(buildPositiveLevel(candles, 12.3).length, 3);
  assert.equal(buildPositiveLevel(candles, 12.3)[0].value, 12.3);
});

test('candleDate: string slice and object form', () => {
  assert.equal(candleDate({ time: '2024-03-15T00:00:00' }), '2024-03-15');
  assert.equal(candleDate({ time: { year: 2024, month: 3, day: 5 } }), '2024-03-05');
  assert.equal(candleDate({}), '');
});

test('indexOnOrAfter: first candle on/after the target date', () => {
  const candles = makeCandles(10); // 2024-01-01 .. 2024-01-10
  assert.equal(indexOnOrAfter(candles, '2024-01-01'), 0);
  assert.equal(indexOnOrAfter(candles, '2024-01-05'), 4);
  assert.equal(indexOnOrAfter(candles, '2024-01-04T12:00:00'), 3); // sliced to date
  assert.equal(indexOnOrAfter(candles, null), null);
});

test('setupIndexes: baseEnd subtracts forward bars; baseStart clamps at 0', () => {
  const candles = makeCandles(30);
  // base_len 10, 3 forward bars: baseEnd = 30-1-3 = 26, baseStart = 26-10+1 = 17
  const idx = setupIndexes({ candles, base_len: 10, forward_bars: 3 });
  assert.equal(idx.baseEnd, 26);
  assert.equal(idx.baseStart, 17);
  assert.equal(idx.forwardBars, 3);
  // base longer than history clamps baseStart at 0
  const idx2 = setupIndexes({ candles, base_len: 100, forward_bars: 0 });
  assert.equal(idx2.baseStart, 0);
  assert.equal(idx2.baseEnd, 29);
});

test('miniFocusLogicalRange: padded window around the base, capped at maxVisibleBars', () => {
  const candles = makeCandles(60);
  const range = miniFocusLogicalRange({ candles, base_len: 12, forward_bars: 2 }, 72);
  // baseEnd = 60-1-2 = 57, baseStart = 57-12+1 = 46
  // rightPadding = clamp(2+5,5,9)=7 -> rightEdge = min(59, 57+7)=59 (... 64 capped to 59)
  assert.equal(range.to, 59);
  // leftPadding = clamp(round(12*0.28)=3, 6,10)=6 -> leftEdge = max(0, 46-6)=40
  // from = max(40, 59-72) = 40
  assert.equal(range.from, 40);
  assert.equal(miniFocusLogicalRange({ candles: [], base_len: 1, forward_bars: 0 }, 72), null);
});

test('miniFocusLogicalRange: maxVisibleBars caps a wide window', () => {
  const candles = makeCandles(300);
  const range = miniFocusLogicalRange({ candles, base_len: 200, forward_bars: 0 }, 72);
  // rightEdge near 299; from must be rightEdge - 72 because the base is huge
  assert.equal(range.to - range.from, 72);
});

test('colorMiniCandles: clones input, paints limb grey and lps gold', () => {
  const candles = makeCandles(20);
  const data = {
    candles,
    base_len: 6,
    forward_bars: 0,
    r_anchor: 1,
    s_anchor: 4,
    lps_tests: [],
    lps_len: 0,
  };
  const out = colorMiniCandles(data);
  // source untouched (deep clone)
  assert.equal(candles[15].color, undefined);
  // baseEnd = 19, baseStart = 14; limbStart=15, limbEnd=18 -> grey
  assert.equal(out[15].color, '#596070');
  assert.equal(out[18].color, '#596070');
  assert.equal(out[13].color, undefined);
});

test('colorMiniCandles: lps_offset path paints gold', () => {
  const candles = makeCandles(20);
  const out = colorMiniCandles({
    candles,
    base_len: 6,
    forward_bars: 0,
    r_anchor: 0,
    s_anchor: 1,
    lps_tests: [],
    lps_len: 3,
    lps_offset: 0,
  });
  // lpsEnd = 19-0 = 19, lpsStart = 17 -> gold
  assert.equal(out[19].color, '#d4b85a');
  assert.equal(out[17].color, '#d4b85a');
});

test('colorTimeframeCandles: paints by date span, shallow-clones', () => {
  const candles = makeCandles(10);
  const out = colorTimeframeCandles(candles, {
    limbStart: '2024-01-02',
    limbEnd: '2024-01-04',
    lpsStart: '2024-01-07',
    lpsEnd: '2024-01-08',
  });
  assert.equal(candles[1].color, undefined); // source untouched
  assert.equal(out[1].color, '#5d6474'); // 2024-01-02 limb grey
  assert.equal(out[3].color, '#5d6474'); // 2024-01-04 limb grey
  assert.equal(out[6].color, '#e3b341'); // 2024-01-07 lps gold
  assert.equal(out[0].color, undefined); // outside both spans
});

test('colorTimeframeCandles: missing dates paint nothing', () => {
  const candles = makeCandles(5);
  const out = colorTimeframeCandles(candles, {});
  assert.ok(out.every((c) => c.color === undefined));
});

test('tradeVisibleLogicalRange: +/-45 around opening date, clamped', () => {
  const candles = makeCandles(120);
  // Fixture months wrap every 28 days, so 2024-02-01 is index 28.
  const entryIndex = candles.findIndex((c) => c.time >= '2024-02-01');
  const range = tradeVisibleLogicalRange(candles, '2024-02-01');
  assert.ok(range);
  assert.equal(range.from, Math.max(0, entryIndex - 45));
  assert.equal(range.to, Math.min(119, entryIndex + 45));
  assert.equal(tradeVisibleLogicalRange(candles, null), null);
  assert.equal(tradeVisibleLogicalRange(candles, '2099-01-01'), null); // no match
});
