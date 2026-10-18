// "Fix the box" (Fri 17/10/2026, the tools Sat 18/10/2026): the pure half, pinned on his AAPL swings.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EMPTY_FIX, applyRailClick, draftFromFix, fixComplete, fixDiffers, fixPayload, readerPair } from './boxFix.js';

// His AAPL: the climax bar of Tue 22/09/2026 (high 345.34) and the reaction low of Thu 24/09 (334.30).
const climax = { time: '2026-09-22', open: 340.14, high: 345.34, low: 338.75, close: 339.75 };
const reaction = { time: '2026-09-24', open: 336.72, high: 338.91, low: 334.30, close: 335.92 };
const last = { time: '2026-10-16', open: 346.09, high: 347.82, low: 340.46, close: 343.46 };
const data = {
  candles: [climax, reaction, last],
  two_eyes: { boxes: [{ role: 'parent', r: 345.34, r_day: '2026-09-22', s: 334.3, s_day: '2026-09-24', opened: '2026-09-22', end: null }] },
};
const on = (bar) => ({ date: bar.time, bar });

test('the reader pair is the parent box on the wire, or null', () => {
  assert.deepEqual(readerPair(data), { r: 345.34, rDay: '2026-09-22', s: 334.3, sDay: '2026-09-24', opened: '2026-09-22' });
  assert.equal(readerPair({ two_eyes: { boxes: [{ role: 'earlier', r: 1, s: 0 }] } }), null);
  assert.equal(readerPair({}), null);
});

test('Resistance lands on the bar high, Support on the bar low, each with its day', () => {
  const one = applyRailClick(EMPTY_FIX, 'r', on(climax));
  assert.deepEqual(one, { r: 345.34, rDay: '2026-09-22', s: null, sDay: null });
  assert.equal(fixComplete(one), false);
  const two = applyRailClick(one, 's', on(reaction));
  assert.deepEqual(two, { r: 345.34, rDay: '2026-09-22', s: 334.3, sDay: '2026-09-24' });
  assert.equal(fixComplete(two), true);
  const moved = applyRailClick(two, 'r', on(last));
  assert.deepEqual(moved, { r: 347.82, rDay: '2026-10-16', s: 334.3, sDay: '2026-09-24' }, 'a second Resistance click moves the line');
  assert.equal(applyRailClick(one, 's', { date: null, bar: reaction }), one, 'no date: nothing moves');
  assert.equal(applyRailClick(one, 's', { date: reaction.time, bar: null }), one, 'no bar: nothing moves');
});

test('SC then AR: Support may come first, and crossed lines swap so the higher one is the resistance', () => {
  const sc = { time: '2026-03-02', open: 8.4, high: 8.42, low: 6.77, close: 8.1 };
  const ar = { time: '2026-03-11', open: 10.1, high: 11.5, low: 9.78, close: 11.2 };
  const first = applyRailClick(EMPTY_FIX, 's', on(sc));
  assert.deepEqual(first, { r: null, rDay: null, s: 6.77, sDay: '2026-03-02' });
  const second = applyRailClick(first, 'r', on(ar));
  assert.deepEqual(second, { r: 11.5, rDay: '2026-03-11', s: 6.77, sDay: '2026-03-02' });
  // Called the wrong way round: the Resistance click on the low bar, the Support click on the high bar.
  const crossed = applyRailClick(applyRailClick(EMPTY_FIX, 'r', on(sc)), 's', on(ar));
  assert.deepEqual(crossed, { r: 9.78, rDay: '2026-03-11', s: 8.42, sDay: '2026-03-02' });
  assert.equal(fixComplete(crossed), true);
});

test('a fix differs from the reader by a cent or more, and always when the reader shows no box', () => {
  const same = { r: 345.34, rDay: '2026-09-22', s: 334.3, sDay: '2026-09-24' };
  assert.equal(fixDiffers(same, readerPair(data)), false);
  assert.equal(fixDiffers({ ...same, s: 333.05 }, readerPair(data)), true);
  assert.equal(fixDiffers(same, null), true);
  assert.equal(fixDiffers({ ...same, s: null }, readerPair(data)), false, 'an unfinished draft differs from nothing');
});

test('the payload carries his lines, the reader pair beside them, the chart last day and the stamp', () => {
  const draft = { r: 345.34, rDay: '2026-09-22', s: 333.05, sDay: '2026-09-21' };
  assert.deepEqual(fixPayload('AAPL', data, draft, { engine_config_version: 'two-eyes-0.9.2-test' }), {
    ticker: 'AAPL', scan_day: '2026-10-16', resistance: 345.34, r_day: '2026-09-22', support: 333.05, s_day: '2026-09-21',
    reader_resistance: 345.34, reader_r_day: '2026-09-22', reader_support: 334.3, reader_s_day: '2026-09-24',
    reader_opened_day: '2026-09-22', ruleset: 'two-eyes-0.9.2-test', note: null,
  });
  const bare = fixPayload('AAPL', { candles: [last] }, draft);
  assert.equal(bare.reader_resistance, null);
  assert.equal(bare.ruleset, '');
});

test('the draft is seated from the fix saved before, so a save never puts the reader pair back over his lines', () => {
  const saved = { resistance: 79.11, r_day: '2026-08-03', support: 75.31, s_day: '2026-08-04', events: [] };
  assert.deepEqual(draftFromFix(saved), { r: 79.11, rDay: '2026-08-03', s: 75.31, sDay: '2026-08-04' });
  assert.equal(draftFromFix(null), EMPTY_FIX);
  assert.equal(draftFromFix({ resistance: null, support: 1 }), EMPTY_FIX);
});
