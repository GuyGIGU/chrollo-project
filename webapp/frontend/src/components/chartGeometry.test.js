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

test('finiteNumber: null/empty/NaN/Infinity -> null, finite -> number', () => {
  assert.equal(finiteNumber(null), null);
  assert.equal(finiteNumber(undefined), null);
  assert.equal(finiteNumber(''), null);
  assert.equal(finiteNumber('abc'), null);
  assert.equal(finiteNumber(NaN), null); // the value the Number.isFinite guard exists for
  assert.equal(finiteNumber(Infinity), null); // must be null or it draws a phantom rail at the edge
  assert.equal(finiteNumber(-Infinity), null);
  assert.equal(finiteNumber(0), 0); // 0 is finite, must NOT become null
  assert.equal(finiteNumber('12.5'), 12.5);
  assert.equal(finiteNumber(42), 42);
});

test('buildLevelData: repeats value from startIndex to end', () => {
  const candles = makeCandles(5);
  const out = buildLevelData(candles, 2, 99);
  assert.equal(out.length, 3);
  assert.deepEqual(out[0], { time: candles[2].time, value: 99 });
  assert.deepEqual(out.at(-1), { time: candles[4].time, value: 99 }); // tail value too
  assert.deepEqual(buildLevelData([], 0, 5), []); // empty candles -> empty
});

test('buildFullLevelData: one point per candle, correct time mapping', () => {
  const candles = makeCandles(4);
  const out = buildFullLevelData(candles, 7);
  assert.equal(out.length, 4);
  assert.ok(out.every((p) => p.value === 7));
  assert.equal(out[0].time, candles[0].time);
  assert.equal(out.at(-1).time, candles[3].time); // time carried, not just value
  assert.deepEqual(buildFullLevelData([], 7), []);
});

test('buildPositiveLevel: empty for non-finite or <= 0', () => {
  const candles = makeCandles(3);
  assert.deepEqual(buildPositiveLevel(candles, 0), []);
  assert.deepEqual(buildPositiveLevel(candles, -5), []);
  assert.deepEqual(buildPositiveLevel(candles, null), []);
  assert.deepEqual(buildPositiveLevel(candles, Infinity), []);
  assert.equal(buildPositiveLevel(candles, 12.3).length, 3);
  assert.equal(buildPositiveLevel(candles, 12.3)[0].value, 12.3);
  assert.deepEqual(buildPositiveLevel([], 12.3), []); // empty candles -> empty
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

test('indexOnOrAfter: resolves over object-form (business-day) candles', () => {
  // lightweight-charts business-day time is {year,month,day}; the unpadded month
  // must still compare lexicographically right via candleDate's padding.
  const candles = [
    { time: { year: 2024, month: 1, day: 3 } },
    { time: { year: 2024, month: 1, day: 9 } },
    { time: { year: 2024, month: 10, day: 1 } },
  ];
  assert.equal(indexOnOrAfter(candles, '2024-01-09'), 1);
  assert.equal(indexOnOrAfter(candles, '2024-05-01'), 2); // skips into Oct, not before Jan
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

test('miniFocusLogicalRange: window adds real pre-base context (leftPadding >= 40)', () => {
  const candles = makeCandles(60);
  const range = miniFocusLogicalRange({ candles, base_len: 12, forward_bars: 2 }, 72);
  // baseEnd = 60-1-2 = 57, baseStart = 57-12+1 = 46
  // rightPadding = clamp(2+5,5,9)=7 -> rightEdge = min(59, 57+7)=59
  assert.equal(range.to, 59);
  // leftPadding = max(40, 12) = 40 -> desiredFrom = max(0, 46-40)=6
  // maxFrom = max(0, 59-72)=0 -> from = max(6,0)=6; min floor inert (minFrom=59) -> 6
  assert.equal(range.from, 6);
  assert.equal(miniFocusLogicalRange({ candles: [], base_len: 1, forward_bars: 0 }, 72), null);
});

test('miniFocusLogicalRange: maxVisibleBars caps a wide window', () => {
  const candles = makeCandles(300);
  const range = miniFocusLogicalRange({ candles, base_len: 200, forward_bars: 0 }, 72);
  // rightEdge near 299; from must be rightEdge - 72 because the base is huge
  assert.equal(range.to - range.from, 72);
});

test('miniFocusLogicalRange: minVisibleBars pads a tiny base out to the floor', () => {
  const candles = makeCandles(200);
  // base_len 10, fwd 0: baseEnd=199, baseStart=190, rightEdge=199.
  // desiredFrom = 190 - max(40,10)=150; without a floor the window would be only
  // ~49 bars. minVisibleBars=90 -> minFrom = 199-90 = 109 -> from clamped to 109.
  const range = miniFocusLogicalRange({ candles, base_len: 10, forward_bars: 0 }, 130, 90);
  assert.equal(range.to, 199);
  assert.equal(range.to - range.from, 90);
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

test('colorMiniCandles: date-keyed lps_tests span paints gold; out-of-range skipped', () => {
  const candles = makeCandles(20); // 2024-01-01 .. (28-day wrap)
  const out = colorMiniCandles({
    candles,
    base_len: 4,
    forward_bars: 0,
    r_anchor: 0,
    s_anchor: 1,
    lps_len: 0,
    lps_tests: [
      { start_date: '2024-01-06', end_date: '2024-01-08' }, // indices 5..7
      { start_date: '2099-01-01', end_date: '2099-02-01' }, // out of range -> skipped, no crash
    ],
  });
  assert.equal(out[5].color, '#d4b85a');
  assert.equal(out[6].color, '#d4b85a');
  assert.equal(out[7].color, '#d4b85a');
  assert.equal(out[4].color, undefined); // before the span
  assert.equal(out[8].color, undefined); // after the span
});

test('colorMiniCandles: base_len <= 0 returns an uncolored clone', () => {
  const candles = makeCandles(6);
  const out = colorMiniCandles({ candles, base_len: 0, forward_bars: 0 });
  assert.equal(out.length, 6);
  assert.ok(out.every((c) => c.color === undefined));
  assert.notEqual(out, candles); // still a clone, source untouched
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
  assert.equal(out[1].color, '#5d6474'); // 2024-01-02 limb grey (span start, inclusive)
  assert.equal(out[3].color, '#5d6474'); // 2024-01-04 limb grey (span end, inclusive)
  assert.equal(out[6].color, '#e3b341'); // 2024-01-07 lps gold (span start)
  assert.equal(out[7].color, '#e3b341'); // 2024-01-08 lps gold (span end, inclusive upper bound)
  assert.equal(out[0].color, undefined); // before the limb span
  assert.equal(out[4].color, undefined); // gap between the two spans stays unpainted
  assert.equal(out[5].color, undefined); // gap between the two spans stays unpainted
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
