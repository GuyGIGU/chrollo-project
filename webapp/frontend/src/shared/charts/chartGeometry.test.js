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

// --- framing: the CARD is Finviz's daily, the last 94 trading days ---
//
// Thu 29/10/2026, his pick "Finviz Daily, exactly": every card shows the last 94
// trading days (Finviz's 466x219 daily image, measured the same day), whatever
// the rest, so every card is at one zoom. That is a fixed span, which he ruled
// "way way too much" on a short rest on 2026-09-02 (the card then framed the
// CONSOLIDATION: the rest owning ~baseWidthCap of the pane, floored, capped, the
// ceiling yielding); his 29/10 pick supersedes it for the card, and the popover
// keeps that model (tested below). The one widening left is the never-crop rule
// (2026-08-09): a base older than the window still shows its open and approach
// leg. The retired vertical trim is what these tests must keep out: it bought
// box height by deleting old bars, which is the horizontal axis the operator
// judges tightness on.

test('miniFocusLogicalRange: window adds real pre-base context', () => {
  const candles = makeCandles(60);
  // baseEnd = 60-1-2 = 57, baseStart = 46, rightPadding = clamp(2+5,5,9)=7 -> rightEdge 59.
  // The 94-day window wants more than the 60 candles carried, so it shows them all.
  const range = miniFocusLogicalRange({ candles, base_len: 12, forward_bars: 2 });
  assert.deepEqual(range, { from: 0, to: 59 });
  assert.equal(miniFocusLogicalRange({ candles: [], base_len: 1, forward_bars: 0 }), null);
});

test('miniFocusLogicalRange: a base WIDER than the window stretches it, never crops the box', () => {
  const candles = makeCandles(300);
  // RULING 2026-08-09 (crop vs stretch, McKinney's open question): the box is the
  // datum — a base whose left edge sits off-pane misreports where it began, so
  // the window yields rather than cropping. base_len 200 opens at 100: the 94-day
  // window would start at 206, so it opens to the box's open and its 18-day
  // approach leg, 82, and no further (until 29/10/2026 it zoomed out to the whole
  // history).
  const range = miniFocusLogicalRange({ candles, base_len: 200, forward_bars: 0 });
  assert.deepEqual(range, { from: 82, to: 299 });
  assert.ok(range.from <= 100 - CHART_FRAMING.mini.minContextBars, 'approach leg survives');
});

// --- window totality + the extremes table (the cases nobody spot-checks) ---
//
// These pin the invariants that must survive ANY density retune: the range is
// always integer and ordered inside the candle array, and no input shape yields NaN.

test('miniFocusLogicalRange: a boxless payload falls back to the widest legible window, never NaN', () => {
  const candles = makeCandles(200);
  // No base_len at all — the market panes and hover previews reuse this math on
  // plain candle arrays. Before totality this returned {from: NaN}. It takes the
  // SAME reference span as a boxed payload, so an unboxed chart is at one zoom.
  for (const boxless of [{}, { base_len: null }, { base_len: 0 }, { base_len: 'x' }, { base_len: NaN }]) {
    const range = miniFocusLogicalRange({ candles, ...boxless });
    assert.equal(range.to, 199);
    assert.equal(range.from, 106); // no rest to frame -> the card's 94 days, as a boxed one
    assert.ok(Number.isInteger(range.from) && Number.isInteger(range.to));
  }
});

test('miniFocusLogicalRange: a non-finite forward_bars degrades to zero, not NaN', () => {
  const candles = makeCandles(120);
  const range = miniFocusLogicalRange({ candles, base_len: 10, forward_bars: undefined });
  assert.equal(range.to, 119); // forwardBars 0 -> baseEnd 119, rightPadding 5, clamped to last index
  assert.equal(range.from, 26); // the card's 94 days
});

test('miniFocusLogicalRange: history shorter than the window yields the whole history', () => {
  const candles = makeCandles(30);
  const range = miniFocusLogicalRange({ candles, base_len: 5, forward_bars: 0 });
  assert.equal(range.from, 0); // clamped left — never negative
  assert.equal(range.to, 29);
});

test('miniFocusLogicalRange: forward_bars exceeding history clamps, never negative', () => {
  const candles = makeCandles(20);
  const range = miniFocusLogicalRange({ candles, base_len: 4, forward_bars: 999 });
  assert.deepEqual(range, { from: 0, to: 9 });
});

test('miniFocusLogicalRange: single candle is a degenerate but valid range', () => {
  const range = miniFocusLogicalRange({ candles: makeCandles(1), base_len: 1, forward_bars: 0 });
  assert.deepEqual(range, { from: 0, to: 0 });
});

test('miniFocusLogicalRange: every card is Finviz\'s 94 days, whatever the rest', () => {
  // His "Finviz Daily, exactly" (Thu 29/10/2026): one zoom on every card. A 10-, 20-, 40- and 60-day rest all
  // get the last 94 days (until then 80, 80, 113 and 130). Literal expectations — reading the answer off the
  // profile would pin nothing.
  const candles = makeCandles(300);
  for (const baseLen of [10, 20, 40, 60]) {
    assert.deepEqual(miniFocusLogicalRange({ candles, base_len: baseLen, forward_bars: 0 }), { from: 206, to: 299 }, `base ${baseLen}`);
  }
});

test('miniFocusLogicalRange: the 94 days hold until the box\'s approach leg would fall off the left edge', () => {
  // The never-crop clause is the card's only widening, and it is load-bearing now (the ceiling never yields):
  // a 76-day base opens at 224 and its 18-day leg starts at 206, the window's own left edge; one day older and
  // the window opens one day wider.
  const candles = makeCandles(300);
  assert.deepEqual(miniFocusLogicalRange({ candles, base_len: 76, forward_bars: 0 }), { from: 206, to: 299 });
  assert.deepEqual(miniFocusLogicalRange({ candles, base_len: 77, forward_bars: 0 }), { from: 205, to: 299 });
});

test('miniFocusLogicalRange: a LONGER base renders a strictly larger share of the pane', () => {
  // The operator's complaint, as an assertion. Under the retired trim a longer
  // base could render NARROWER than a shorter one (2,275 of 25,904 card pairs).
  const candles = makeCandles(300);
  const measure = (baseLen) => {
    const range = miniFocusLogicalRange({ candles, base_len: baseLen, forward_bars: 0 });
    const baseStart = 300 - baseLen;
    return {
      width: range.to - range.from + 1,
      share: (range.to - Math.max(range.from, baseStart) + 1) / (range.to - range.from + 1),
    };
  };
  const shorter = measure(30);
  const longer = measure(95);
  assert.ok(longer.share > shorter.share, 'a longer rest must be drawn wider');
  assert.ok(longer.width > shorter.width, 'and it must have earned a wider window');
});

test('miniFocusLogicalRange: a monster base opens the card to its open and approach leg, no further', () => {
  // Operator 2026-09-02, "for monster bases simply zoom out the base", now by the never-crop clause alone:
  // base_len 280 over 300 candles opens at 20, so the card starts at 2 (until 29/10/2026 the whole history).
  const candles = makeCandles(300);
  const range = miniFocusLogicalRange({ candles, base_len: 280, forward_bars: 0 });
  assert.deepEqual(range, { from: 2, to: 299 });
  assert.ok(range.to - range.from + 1 > CHART_FRAMING.mini.legibilityCeilingBars);
});

test('the box\'s open is NEVER cropped, at any base length, on any profile', () => {
  // Since Thu 29/10/2026 the card never yields (Finviz's fixed 94 days), so on the
  // CARD this sweep guards the clamp itself: delete it and every card base past
  // 76 days goes red here. The history below is the popover's.
  // RULING 2026-08-09, as a property sweep rather than a fixture. It is proved
  // this way on purpose: since the ceiling learned to yield (2026-09-02) the
  // never-crop CLAMP in miniFocusLogicalRange is redundant — a base long enough
  // to threaten its own leg now earns a window ~2.5x its own width (1 / the
  // card's 0.40 cap, re-swept 2026-10-04) — so a
  // fixture aimed at the clamp would pass with the clamp deleted, i.e. would not
  // be a guard at all. This sweep instead pins the INVARIANT the ruling is
  // about, and goes red the moment any future constant re-opens the hole
  // (turn the yield off with ceilingYieldShare > 1 and delete the clamp, and
  // every base past ~197 bars starts cropping here).
  for (const profile of [CHART_FRAMING.mini, CHART_FRAMING.popover]) {
    for (const length of [60, 120, 231, 300]) {
      const candles = makeCandles(length);
      for (let baseLen = 1; baseLen <= length + 40; baseLen += 1) {
        for (const forward of [0, 3, 20]) {
          const range = miniFocusLogicalRange({ candles, base_len: baseLen, forward_bars: forward }, profile);
          const baseEnd = Math.max(0, length - 1 - forward);
          const baseStart = Math.max(0, baseEnd - baseLen + 1);
          assert.ok(
            range.from <= baseStart,
            `${profile.minWindowBars}/${length}/${baseLen}/${forward}: from ${range.from} crops a box opening at ${baseStart}`,
          );
          assert.ok(range.to >= baseEnd || range.to === length - 1, 'the box end stays on pane');
          assert.ok(Number.isInteger(range.from) && range.from >= 0);
        }
      }
    }
  }
});

test('modalFocusLogicalRange: opens on its fixed span, running to the last candle', () => {
  const candles = makeCandles(400);
  const range = modalFocusLogicalRange({ candles, base_len: 30, forward_bars: 2 });
  assert.deepEqual(range, { from: 250, to: 399 }); // 400 - 150 (Thu 16/10/2026: one year read stretched)
  assert.equal(range.to - range.from + 1, CHART_FRAMING.modal.minWindowBars);
});

test('modalFocusLogicalRange: a tiny base takes the same span; short history clamps at 0', () => {
  const candles = makeCandles(400);
  assert.equal(modalFocusLogicalRange({ candles, base_len: 5, forward_bars: 0 }).from, 250);
  // history shorter than the year -> from 0, never negative
  assert.equal(modalFocusLogicalRange({ candles: makeCandles(40), base_len: 5, forward_bars: 0 }).from, 0);
  assert.equal(modalFocusLogicalRange({ candles: [], base_len: 5, forward_bars: 0 }), null);
});

test('modalFocusLogicalRange: a boxless payload still resolves a window', () => {
  const candles = makeCandles(300);
  const range = modalFocusLogicalRange({ candles }); // no base_len, no forward_bars
  assert.deepEqual(range, { from: 0, to: 299 }); // no rest to frame -> the widest legible window
});

test('modalFocusLogicalRange: a tall leg over a tiny box does NOT trim back to a sliver', () => {
  // The shipped modal was pinned at 81 trading days on 140 of 230 real setups —
  // the retired trim proved its 40% vertical target unreachable and then trimmed
  // maximally anyway. The shipped suite never caught it because makeCandles has no
  // R/S, so boxHeight was 0 and the trim short-circuited. This fixture is that
  // shape WITH finite R/S: a steep run-up into a box ~1% of the visible range.
  const candles = makeCandles(300).map((c, i) => {
    const inBox = i >= 269;
    const level = inBox ? 400 : 10 + i;
    return { ...c, open: level, close: level, high: level + (inBox ? 1 : 2), low: level - (inBox ? 1 : 2) };
  });
  const range = modalFocusLogicalRange({ candles, base_len: 31, forward_bars: 0, R: 401, S: 399 });
  assert.deepEqual(range, { from: 150, to: 299 });
  assert.equal(range.to - range.from + 1, CHART_FRAMING.modal.minWindowBars);
});

test('miniFocusLogicalRange: the hover glance frames at its OWN span, not the card\'s', () => {
  // The popover is a real surface with real constants and, until the 2026-09-02
  // review, no outcome pin at all: copying the card's own pair into it
  // passed the whole suite while rendering every glance far outside its own band — under the module's own band, beside the 2.3 the operator called
  // indecipherable (2026-08-12). Literal expectations on purpose; a
  // `width === profile.minWindowBars` assertion reads its answer off the very
  // constant it is meant to pin and survives the mutation.
  const candles = makeCandles(300);
  const glance = (baseLen) => miniFocusLogicalRange({ candles, base_len: baseLen, forward_bars: 0 }, CHART_FRAMING.popover);

  // A short rest falls back on the floor (55).
  assert.deepEqual(glance(10), { from: 245, to: 299 });
  // Under the ceiling the card's 0.40 cap sets it: ceil(40/0.40) = 100 days.
  assert.deepEqual(glance(35), { from: 200, to: 299 });
  // Over the cap, under the yield: it holds at the ceiling (105).
  assert.deepEqual(glance(60), { from: 195, to: 299 });
  // A rest that does not FIT the pane yields to the window the cap wants,
  // ceil(106/0.40) = 265 days — and the glance yields at 1, not at the card's
  // 0.75, which is what keeps that a tail.
  assert.deepEqual(glance(101), { from: 35, to: 299 });
  // Just under the knee the never-crop clamp is what widens it, not the yield:
  // 114 bars is neither the ceiling nor a yielded window.
  assert.deepEqual(glance(100), { from: 186, to: 299 });
});

test('CHART_FRAMING: the glance agrees with the card, and the modal never frames closer than either', () => {
  // ONE rule about how much pane a base may own on the card and on its preview,
  // the hover glance (different spans, same share). The modal may frame wider
  // but never closer: the card is the close-up, the modal is the stock
  // (operator 2026-10-02 — card and glance 0.45, modal 0.35; card and glance
  // 0.40 since 2026-10-04).
  assert.equal(CHART_FRAMING.mini.baseWidthCap, CHART_FRAMING.popover.baseWidthCap);
  assert.ok(
    CHART_FRAMING.modal.baseWidthCap <= CHART_FRAMING.mini.baseWidthCap,
    'the modal must not let a base own more of the big chart than of the card',
  );
});

test('CHART_FRAMING: the card\'s price fit is Finviz\'s daily chart', () => {
  // Thu 29/10/2026, his "Finviz Daily, exactly", measured on Finviz's 466x219 daily image: the bars from ~12%
  // under the top (the ticker line sits there) to ~20% over the date axis, volume in the band under them. It
  // replaces the 2026-10-02 close-up (an 88% price band, volume a strip in the bottom 8%). Literals: a retune
  // away from Finviz's fit is a decision to make on purpose.
  const { scaleMargins, volumeScaleTop } = CHART_FRAMING.mini;
  assert.deepEqual(scaleMargins, { top: 0.13, bottom: 0.2 });
  assert.equal(volumeScaleTop, 0.83);
  assert.ok(volumeScaleTop >= 1 - scaleMargins.bottom, 'the volume band starts under the bars, not over them');
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

// The whole reference model, as a membership list. It is a hand-maintained
// mirror of the profile shape, so the test counts how many profiles it matched:
// rename a field on both sides and the block would silently stop guarding ALL
// of them, which the count catches.
const BOX_KEYS = ['minWindowBars', 'legibilityCeilingBars', 'ceilingYieldShare', 'baseWidthCap', 'minContextBars'];

test('CHART_FRAMING: every surface profile is complete and internally consistent', () => {
  // The profile table is the ONE place proportion is retuned — a missing or
  // inverted field there silently mis-frames a whole surface.
  let boxFramed = 0;
  for (const [name, profile] of Object.entries(CHART_FRAMING)) {
    assert.ok(profile.scaleMargins.top >= 0 && profile.scaleMargins.bottom >= 0, `${name} margins`);
    assert.ok(profile.scaleMargins.top + profile.scaleMargins.bottom < 1, `${name} margins leave price room`);
    assert.ok(profile.volumeScaleTop > 0 && profile.volumeScaleTop < 1, `${name} volume band`);
    // Box-framed surfaces carry the whole reference model or none of it: a
    // half-declared profile silently mis-frames a surface with no error.
    // Membership, never `minWindowBars != null` — keying the gate on one field
    // makes THAT field's omission the one omission the block cannot see, and a
    // missing minWindowBars sends Math.max(undefined, …) -> NaN straight into
    // setVisibleLogicalRange (2026-09-02 review).
    if (BOX_KEYS.some((key) => key in profile)) {
      boxFramed += 1;
      for (const key of BOX_KEYS) assert.ok(key in profile, `${name} half-declares the reference model: missing ${key}`);
      assert.ok(Number.isFinite(profile.minWindowBars) && profile.minWindowBars > 0, `${name} window floor`);
      assert.ok(
        Number.isFinite(profile.legibilityCeilingBars) && profile.legibilityCeilingBars >= profile.minWindowBars,
        `${name} ceiling must not sit below the window floor`,
      );
      assert.ok(profile.baseWidthCap > 0 && profile.baseWidthCap < 1, `${name} base-width cap`);
      assert.ok(Number.isFinite(profile.minContextBars) && profile.minContextBars >= 0, `${name} approach leg`);
      // The yield share must sit ABOVE the cap: at or below it the ceiling would
      // yield for every base that crosses the cap at all, which is the "raise the
      // ceiling" variant measured to cost 45 cards their legibility. Infinity is a
      // profile that never yields (the card since Thu 29/10/2026: only the
      // never-crop clause widens it); any other share past 1 is a typo.
      assert.ok(
        profile.ceilingYieldShare > profile.baseWidthCap
          && (profile.ceilingYieldShare <= 1 || profile.ceilingYieldShare === Infinity),
        `${name} ceiling-yield share must sit above the base-width cap`,
      );
    }
  }
  assert.ok(boxFramed >= 3, `BOX_KEYS matched only ${boxFramed} profiles — the completeness block has gone dark`);
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

// --- the alpha reader's dated block (build task 15) ---
//
// The wire carries DAYS and resolved prices; the browser only locates each day's bar and draws. A day survives
// any window, so the scan's card, the modal and the archive's chart (whose candles are fetched again, over another
// window) all find the same bars. makeCandles: index 14 = 2024-01-15, 27 = 2024-01-28, 28 = 2024-02-01.
const alphaPayload = (n = 40, block = {}) => ({
  candles: makeCandles(n),
  R: 20,
  S: 10,
  alpha: {
    boxes: [
      { role: 'parent', r: 20, r_day: '2024-01-16', s: 10, s_day: '2024-01-18', opened: '2024-01-15', end: null },
      { role: 'mini', r: 18, r_day: '2024-01-25', s: 15, s_day: '2024-01-26', opened: '2024-01-25', end: null },
    ],
    lps: { against: 'mini', how: 'on', start: '2024-02-02', end: '2024-02-03', trigger: 18.5 },
    state: 'fired',
    state_days: null,
    grade: { score: 92.3, letter: 'S' },
    ...block,
  },
});

test('boxRailSpecs: a alpha box draws each line from ITS OWN anchor day, the mini thinner', () => {
  const specs = boxRailSpecs(alphaPayload());
  assert.deepEqual(specs, [
    { kind: 'rail', startIndex: 15, endIndex: 39, value: 20 },  // R from its anchor day, 2024-01-16
    { kind: 'rail', startIndex: 17, endIndex: 39, value: 10 },  // S from ITS anchor day, 2024-01-18
    { kind: 'mid', startIndex: 14, endIndex: 39, value: 15 },   // the midline from the box's first day
    { kind: 'inner', startIndex: 24, endIndex: 39, value: 18 }, // the mini, from its own days
    { kind: 'inner', startIndex: 25, endIndex: 39, value: 15 },
  ]);
});

test('boxRailSpecs: the dated block wins over the legacy bar counts, and an ended box stops on its last day', () => {
  // A payload never carries both; if it did, the bar counts would draw the old engine's box.
  const payload = alphaPayload(40, {
    boxes: [{ role: 'parent', r: 20, r_day: '2024-01-16', s: 10, s_day: '2024-01-18', opened: '2024-01-15', end: '2024-01-20' }],
  });
  const specs = boxRailSpecs({ ...payload, base_len: 3, r_anchor: 0, s_anchor: 1 });
  assert.deepEqual(specs.map((s) => [s.startIndex, s.endIndex]), [[15, 19], [17, 19], [14, 19]]);
});

test('boxRailSpecs: a line anchored before the shipped window starts at its left edge; an unknown role draws nothing', () => {
  const specs = boxRailSpecs(alphaPayload(40, {
    boxes: [
      { role: 'parent', r: 20, r_day: '2023-11-02', s: 10, s_day: '2024-01-18', opened: '2023-11-01', end: null },
      { role: 'earlier', r: 30, r_day: '2024-01-02', s: 25, s_day: '2024-01-03', opened: '2024-01-02', end: '2024-01-10' },
    ],
  }));
  assert.deepEqual(specs.map((s) => [s.kind, s.startIndex, s.value]),
    [['rail', 0, 20], ['rail', 17, 10], ['mid', 0, 15]]);
  // A block with no box draws no rail, and never falls back to the old engine's counts.
  assert.deepEqual(boxRailSpecs({ ...alphaPayload(40, { boxes: [] }), base_len: 6 }), []);
});

test('miniFocusLogicalRange / modalFocusLogicalRange: a alpha box is framed from the day it opened', () => {
  // 300 candles; the box opened on index 150 (2024-06-11) and runs to the last candle (299): the frame a 150-bar
  // legacy base gets — and not the boxless fallback, which a payload with no bar counts would otherwise take. The
  // box is older than the card's 94 days on purpose: a shorter one gets those 94 days either way (29/10/2026).
  const payload = alphaPayload(300, {
    boxes: [{ role: 'parent', r: 20, r_day: '2024-06-12', s: 10, s_day: '2024-06-14', opened: '2024-06-11', end: null }],
  });
  const legacy = { candles: makeCandles(300), base_len: 150, forward_bars: 0 };
  assert.notDeepEqual(miniFocusLogicalRange({ candles: makeCandles(300) }), miniFocusLogicalRange(legacy));
  assert.deepEqual(miniFocusLogicalRange(payload), miniFocusLogicalRange(legacy));
  assert.deepEqual(modalFocusLogicalRange(payload), modalFocusLogicalRange(legacy));
});

test('colorMiniCandles: a alpha setup greys its two anchor days and paints its LPS gold', () => {
  const payload = alphaPayload();
  const out = colorMiniCandles(payload);
  assert.equal(payload.candles[15].color, undefined); // the source is untouched
  for (const index of [15, 16, 17]) assert.equal(out[index].color, CHART_COLORS.baseLimb);
  for (const index of [29, 30]) assert.equal(out[index].color, '#F6D86B');
  for (const index of [14, 18, 28, 31]) assert.equal(out[index].color, undefined);
});
