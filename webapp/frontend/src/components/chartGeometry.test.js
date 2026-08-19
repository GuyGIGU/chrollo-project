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
  modalFocusLogicalRange,
  marketFocusLogicalRange,
  marketFetchDays,
  CHART_FRAMING,
  colorMiniCandles,
  colorTimeframeCandles,
  boxRailSpecs,
  tradeVisibleLogicalRange,
} from './chartGeometry.js';
import { CHART_COLORS } from './chartTheme.js';

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

test('buildLevelData: endIndex bounds the tail (inner-box rails stop early)', () => {
  const candles = makeCandles(6);
  const out = buildLevelData(candles, 1, 5, 3); // indices 1,2,3 inclusive
  assert.equal(out.length, 3);
  assert.deepEqual(out[0], { time: candles[1].time, value: 5 });
  assert.deepEqual(out.at(-1), { time: candles[3].time, value: 5 }); // stops at endIndex
  // explicit undefined endIndex behaves like the default (runs to the end)
  assert.equal(buildLevelData(candles, 1, 5, undefined).length, 5);
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
  // base 40 + the 18-bar approach leg both fit inside the 72-bar budget, so the
  // budget is what binds here (a base+leg that does NOT fit is the next test).
  const range = miniFocusLogicalRange({ candles, base_len: 40, forward_bars: 0 }, 72);
  assert.equal(range.to - range.from, 72);
});

test('miniFocusLogicalRange: a base WIDER than the budget stretches the window, never crops the box', () => {
  const candles = makeCandles(300);
  // RULING 2026-08-09 (crop vs stretch, McKinney's open question): the box is the
  // datum — a base whose left edge sits off-pane misreports where it began, so the
  // budget yields rather than cropping. base_len 200 with a 72-bar budget:
  // baseStart 100, minus the 18-bar approach leg -> from 82, i.e. 217 bars, well
  // past the nominal cap. Dense, but honest about an unusually long base.
  const range = miniFocusLogicalRange({ candles, base_len: 200, forward_bars: 0 }, 72);
  assert.equal(range.from, 82);
  assert.equal(range.to, 299);
  assert.ok(range.to - range.from > 72, 'the cap yields to the box, it does not crop it');
});

test('miniFocusLogicalRange: the proportion trim drops old context but always keeps the approach leg', () => {
  // A tall pre-base advance then a tight box: the un-trimmed window would give
  // the box a sliver of the price range, so the oldest bars are dropped — but the
  // trim stops minContextBars before the box opens, never eating the leg.
  const candles = makeCandles(200).map((c, i) => {
    // A steep run-up into a flat 30-bar box at the right edge.
    const inBox = i >= 170;
    const level = inBox ? 200 : 10 + i;
    return { ...c, open: level, close: level, high: level + (inBox ? 1 : 1.5), low: level - (inBox ? 1 : 1.5) };
  });
  const data = { candles, base_len: 30, forward_bars: 0, R: 201, S: 199 };
  const trimmed = miniFocusLogicalRange(data, 130, 90);
  // Two floors bound the trim and the LESS aggressive one wins: the 18-bar leg
  // rule would allow from=152, but the 55-bar window floor stops it at 144 —
  // so 26 context bars survive, comfortably more than the leg minimum.
  assert.equal(trimmed.from, 144);
  assert.equal(trimmed.to, 199);
  // Without a box height there is nothing to trim toward — the untrimmed window stands.
  const untrimmed = miniFocusLogicalRange({ ...data, R: null, S: null }, 130, 90);
  assert.ok(untrimmed.from < trimmed.from, 'no box height -> no proportion trim');
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

// --- window totality + the extremes table (the cases nobody spot-checks) ---
//
// These pin the invariants that must survive ANY density retune: the range is
// always integer and ordered inside the candle array, a tiny base is padded to
// the floor, a huge base is capped at the budget, and no input shape yields NaN.

test('miniFocusLogicalRange: a boxless payload falls back to the last budget bars, never NaN', () => {
  const candles = makeCandles(200);
  // No base_len at all — the market panes and hover previews reuse this math on
  // plain candle arrays. Before totality this returned {from: NaN}.
  for (const boxless of [{}, { base_len: null }, { base_len: 0 }, { base_len: 'x' }, { base_len: NaN }]) {
    const range = miniFocusLogicalRange({ candles, ...boxless }, 130, 90);
    assert.equal(range.to, 199);
    assert.equal(range.from, 69); // 199 - 130, the same to-from width the boxed path uses
    assert.ok(Number.isInteger(range.from) && Number.isInteger(range.to));
  }
});

test('miniFocusLogicalRange: a non-finite forward_bars degrades to zero, not NaN', () => {
  const candles = makeCandles(120);
  const range = miniFocusLogicalRange({ candles, base_len: 10, forward_bars: undefined }, 130, 90);
  assert.equal(range.to, 119); // forwardBars 0 -> baseEnd 119, rightPadding 5, clamped to last index
  assert.equal(range.to - range.from, 90); // floor still applies
});

test('miniFocusLogicalRange: an inverted min/max pair cannot exceed the budget', () => {
  const candles = makeCandles(300);
  // floor(120) > budget(60): the floor must be clamped DOWN to the budget, or the
  // window silently blows the max it was given.
  const range = miniFocusLogicalRange({ candles, base_len: 8, forward_bars: 0 }, 60, 120);
  assert.equal(range.to - range.from, 60);
});

test('miniFocusLogicalRange: history shorter than the floor yields the whole history', () => {
  const candles = makeCandles(30);
  const range = miniFocusLogicalRange({ candles, base_len: 5, forward_bars: 0 }, 130, 90);
  assert.equal(range.from, 0); // clamped left — never negative
  assert.equal(range.to, 29);
});

test('miniFocusLogicalRange: forward_bars exceeding history clamps, never negative', () => {
  const candles = makeCandles(20);
  const range = miniFocusLogicalRange({ candles, base_len: 4, forward_bars: 999 }, 130, 90);
  assert.equal(range.from, 0);
  assert.ok(range.to >= range.from && range.to <= 19);
});

test('miniFocusLogicalRange: single candle is a degenerate but valid range', () => {
  const range = miniFocusLogicalRange({ candles: makeCandles(1), base_len: 1, forward_bars: 0 }, 130, 90);
  assert.deepEqual(range, { from: 0, to: 0 });
});

test('modalFocusLogicalRange: base plus context bars, running to the last candle', () => {
  const candles = makeCandles(400);
  // base_len 30, fwd 2 -> baseEnd 397; context = max(30+90, 120) = 120 -> from 277
  const range = modalFocusLogicalRange({ candles, base_len: 30, forward_bars: 2 });
  assert.deepEqual(range, { from: 277, to: 399 });
});

test('modalFocusLogicalRange: the minimum window floors a tiny base; short history clamps at 0', () => {
  const candles = makeCandles(400);
  // base_len 5 -> context = max(95, 120) = 120 (the floor wins)
  assert.equal(modalFocusLogicalRange({ candles, base_len: 5, forward_bars: 0 }).from, 279);
  // history shorter than the context -> from 0, never negative
  assert.equal(modalFocusLogicalRange({ candles: makeCandles(40), base_len: 5, forward_bars: 0 }).from, 0);
  assert.equal(modalFocusLogicalRange({ candles: [], base_len: 5, forward_bars: 0 }), null);
});

test('modalFocusLogicalRange: a boxless payload still resolves a window', () => {
  const candles = makeCandles(300);
  const range = modalFocusLogicalRange({ candles }); // no base_len, no forward_bars
  assert.deepEqual(range, { from: 179, to: 299 }); // context = max(0+90, 120) = 120
});

test('marketFocusLogicalRange: last N bars, or null when history is shorter than the budget', () => {
  assert.deepEqual(marketFocusLogicalRange(makeCandles(300), 130), { from: 170, to: 299 });
  assert.equal(marketFocusLogicalRange(makeCandles(130), 130), null); // exactly the budget -> fitContent
  assert.equal(marketFocusLogicalRange(makeCandles(50), 130), null);
  assert.equal(marketFocusLogicalRange([], 130), null);
  assert.equal(marketFocusLogicalRange(makeCandles(300), 0), null);
});

test('marketFetchDays: the strip fetches deep enough to fund SMA200 across the WHOLE visible window', () => {
  // The bug this exists to prevent: a hand-picked 400-day fetch (~275 sessions)
  // under a 130-bar window left SMA200 starting ~54 bars into the pane.
  const { visibleBars, smaWarmupBars } = CHART_FRAMING.market;
  const days = marketFetchDays(visibleBars, smaWarmupBars);
  const sessions = days * (252 / 365);
  assert.ok(
    sessions >= visibleBars + smaWarmupBars - 1,
    `fetch of ${days}d ≈ ${sessions.toFixed(0)} sessions must cover ${visibleBars} visible + ${smaWarmupBars - 1} warm-up`,
  );
  assert.equal(marketFetchDays(0, 0), 0);
  assert.equal(marketFetchDays(null, undefined), 0);
});

test('CHART_FRAMING: every surface profile is complete and internally consistent', () => {
  // The profile table is the ONE place proportion is retuned — a missing or
  // inverted field there silently mis-frames a whole surface.
  for (const [name, profile] of Object.entries(CHART_FRAMING)) {
    assert.ok(profile.scaleMargins.top >= 0 && profile.scaleMargins.bottom >= 0, `${name} margins`);
    assert.ok(profile.scaleMargins.top + profile.scaleMargins.bottom < 1, `${name} margins leave price room`);
    assert.ok(profile.volumeScaleTop > 0 && profile.volumeScaleTop < 1, `${name} volume band`);
  }
  assert.ok(CHART_FRAMING.mini.minVisibleBars <= CHART_FRAMING.mini.maxVisibleBars);
});

test('colorMiniCandles: greys the r/s anchor pair — the limbs R and S are drawn from', () => {
  const candles = makeCandles(20);
  // base_len 6, fwd 0 -> baseEnd 19, baseStart 14. The root swing is the ANCHOR PAIR:
  // r_anchor=1 -> idx 15 (its high sets R), s_anchor=4 -> idx 18 (its low sets S).
  const data = {
    candles,
    base_len: 6,
    forward_bars: 0,
    r_anchor: 1,
    s_anchor: 4,
    // Phase A sits outside the box and must NOT drive the grey bars.
    _phase_a_start_date: '2024-01-05',
    _phase_a_end_date: '2024-01-08',
    _phase_b_start_date: '2024-01-15',
    lps_len: 0,
  };
  const out = colorMiniCandles(data);
  assert.equal(candles[15].color, undefined); // source untouched (deep clone)
  assert.equal(out[15].color, CHART_COLORS.baseLimb); // R anchor
  assert.equal(out[16].color, CHART_COLORS.baseLimb); // the limb between the anchors
  assert.equal(out[18].color, CHART_COLORS.baseLimb); // S anchor
  // The box OPEN must not be swept in — folding baseStart into the span was the
  // long-standing "root-swing grey drag" bug.
  assert.equal(out[14].color, undefined);
  assert.equal(out[19].color, undefined);
  // Phase A bars (idx 4..7, outside the consolidation) stay unpainted.
  assert.equal(out[4].color, undefined);
  assert.equal(out[7].color, undefined);
});

test('colorMiniCandles: anchor order does not matter; missing anchors paint no root swing', () => {
  const candles = makeCandles(20);
  const base = { candles, base_len: 6, forward_bars: 0, lps_len: 0 };
  // s_anchor before r_anchor -> still spans min..max, never inverted.
  const flipped = colorMiniCandles({ ...base, r_anchor: 4, s_anchor: 1 });
  assert.equal(flipped[15].color, CHART_COLORS.baseLimb);
  assert.equal(flipped[18].color, CHART_COLORS.baseLimb);
  assert.equal(flipped[14].color, undefined);
  // No anchor pair emitted -> no grey at all (degrade, never guess a span).
  const none = colorMiniCandles({ ...base });
  assert.ok(none.every((candle) => candle.color === undefined));
});

test('colorMiniCandles: lps_offset path paints gold', () => {
  const candles = makeCandles(20);
  const out = colorMiniCandles({
    candles,
    base_len: 6,
    forward_bars: 0,
    r_anchor: 0,
    s_anchor: 1,
    lps_len: 3,
    lps_offset: 0,
  });
  // lpsEnd = 19-0 = 19, lpsStart = 17 -> gold
  assert.equal(out[19].color, CHART_COLORS.goldMuted);
  assert.equal(out[17].color, CHART_COLORS.goldMuted);
});

test('colorMiniCandles: the single active LPS zone paints gold; out-of-range resolves nothing', () => {
  const candles = makeCandles(20); // 2024-01-01 .. 2024-01-20
  const out = colorMiniCandles({
    candles,
    base_len: 4,
    forward_bars: 0,
    r_anchor: 0,
    s_anchor: 1,
    lps_len: 0,
    // ONE drawn LPS per setup (operator ruling 2026-08-09): the shared colorer
    // sources only the active elected zone from buildPhaseRegions — the
    // prior-test staircase is measurement, never drawn. The zone needs a
    // price box (low/high) to resolve.
    _lps_zone_start_date: '2024-01-07',
    _lps_zone_end_date: '2024-01-08',
    _lps_zone_low: 10,
    _lps_zone_high: 20,
  });
  assert.equal(out[6].color, '#F6D86B'); // indices 6..7 paint the LPS gold
  assert.equal(out[7].color, '#F6D86B');
  assert.equal(out[5].color, undefined); // outside the zone stays unpainted
  assert.equal(out[8].color, undefined);

  // Out-of-range zone -> no region resolves; with lps_len 0 nothing paints.
  const none = colorMiniCandles({
    candles,
    base_len: 4,
    forward_bars: 0,
    lps_len: 0,
    _lps_zone_start_date: '2099-01-01',
    _lps_zone_end_date: '2099-02-01',
    _lps_zone_low: 1,
    _lps_zone_high: 2,
  });
  assert.ok(none.every((candle) => candle.color === undefined));
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
  assert.equal(out[1].color, CHART_COLORS.baseLimb); // 2024-01-02 limb grey (span start, inclusive)
  assert.equal(out[3].color, CHART_COLORS.baseLimb); // 2024-01-04 limb grey (span end, inclusive)
  assert.equal(out[6].color, CHART_COLORS.gold); // 2024-01-07 lps gold (span start)
  assert.equal(out[7].color, CHART_COLORS.gold); // 2024-01-08 lps gold (span end, inclusive upper bound)
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

// --- boxRailSpecs: the ONE rail read shared by the mini card and the modal ---

test('boxRailSpecs: R/S/mid anchored at the box start', () => {
  const candles = makeCandles(20);
  const specs = boxRailSpecs({ candles, base_len: 6, forward_bars: 0, R: 20, S: 10 });
  // baseEnd = 19, baseStart = 14 (setupIndexes math)
  assert.equal(specs.length, 3); // no inner box -> exactly R/S/mid
  assert.deepEqual(specs[0], { kind: 'rail', startIndex: 14, value: 20 });
  assert.deepEqual(specs[1], { kind: 'rail', startIndex: 14, value: 10 });
  assert.deepEqual(specs[2], { kind: 'mid', startIndex: 14, value: 15 }); // (R+S)/2
});

test('boxRailSpecs: string-typed R/S ship as the COERCED numbers', () => {
  // The exact input class finiteNumber exists to absorb: the guard and the
  // shipped values must be the same coerced pair, never guard-on-coerced /
  // ship-raw (two string rails beside a numeric mid).
  const specs = boxRailSpecs({ candles: makeCandles(20), base_len: 6, R: '20', S: '10' });
  assert.deepEqual(specs.map((s) => s.value), [20, 10, 15]);
  for (const spec of specs) assert.equal(typeof spec.value, 'number');
});

test('boxRailSpecs: a candles-only payload draws NO rails', () => {
  // The Watchlist page's clean chart: no R/S -> no parent trio, no NaN mid.
  assert.deepEqual(boxRailSpecs({ candles: makeCandles(20) }), []);
  assert.deepEqual(
    boxRailSpecs({ candles: makeCandles(20), R: 20 }), []); // half a box is no box
});

test('boxRailSpecs: forward bars shift the anchor left, clamped at 0', () => {
  const candles = makeCandles(20);
  const specs = boxRailSpecs({ candles, base_len: 6, forward_bars: 5, R: 20, S: 10 });
  // baseEnd = 19-5 = 14, baseStart = 9
  assert.equal(specs[0].startIndex, 9);
  // base longer than history -> clamped to 0, never negative
  const clamped = boxRailSpecs({ candles: makeCandles(4), base_len: 30, forward_bars: 0, R: 2, S: 1 });
  assert.equal(clamped[0].startIndex, 0);
});

test('boxRailSpecs: inner box only when all three inner fields are finite', () => {
  const base = { candles: makeCandles(20), base_len: 6, forward_bars: 0, R: 20, S: 10 };
  const withInner = boxRailSpecs({ ...base, inner_R: 18, inner_S: 12, inner_start_bar: 16 });
  assert.equal(withInner.length, 5);
  // No inner_end_bar -> inner rails run to the last candle (index 19).
  assert.deepEqual(withInner[3], { kind: 'inner', startIndex: 16, endIndex: 19, value: 18 });
  assert.deepEqual(withInner[4], { kind: 'inner', startIndex: 16, endIndex: 19, value: 12 });
  // a null (or missing) inner field suppresses BOTH inner rails
  assert.equal(boxRailSpecs({ ...base, inner_R: 18, inner_S: null, inner_start_bar: 16 }).length, 3);
  assert.equal(boxRailSpecs({ ...base, inner_R: 18, inner_S: 12 }).length, 3);
});

test('boxRailSpecs: inner start bar is truncated and clamped into the candle range', () => {
  const base = { candles: makeCandles(10), base_len: 4, forward_bars: 0, R: 20, S: 10 };
  assert.equal(boxRailSpecs({ ...base, inner_R: 18, inner_S: 12, inner_start_bar: 3.9 })[3].startIndex, 3);
  assert.equal(boxRailSpecs({ ...base, inner_R: 18, inner_S: 12, inner_start_bar: 99 })[3].startIndex, 9); // clamp right
  assert.equal(boxRailSpecs({ ...base, inner_R: 18, inner_S: 12, inner_start_bar: -4 })[3].startIndex, 0); // clamp left
});

test('boxRailSpecs: inner_end_bar bounds the inner rails before the reserved edge', () => {
  const base = { candles: makeCandles(20), base_len: 6, forward_bars: 0, R: 20, S: 10 };
  // The coil stops at inner_end_bar (the last anchored bar), NOT the chart edge.
  const bounded = boxRailSpecs({ ...base, inner_R: 18, inner_S: 12, inner_start_bar: 10, inner_end_bar: 14 });
  assert.equal(bounded[3].endIndex, 14);
  assert.equal(bounded[4].endIndex, 14);
  // clamp: end past the last candle -> last index; end before start -> start
  assert.equal(boxRailSpecs({ ...base, inner_R: 18, inner_S: 12, inner_start_bar: 10, inner_end_bar: 99 })[3].endIndex, 19);
  assert.equal(boxRailSpecs({ ...base, inner_R: 18, inner_S: 12, inner_start_bar: 10, inner_end_bar: 6 })[3].endIndex, 10);
  // no inner_end_bar -> backward-compatible draw-to-edge
  assert.equal(boxRailSpecs({ ...base, inner_R: 18, inner_S: 12, inner_start_bar: 10 })[3].endIndex, 19);
});
