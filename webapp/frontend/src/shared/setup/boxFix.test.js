// "Fix the box" on the lens (Fri 17/10/2026): the pure half, pinned on his AAPL swings.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EMPTY_FIX, applyFixClick, fixComplete, fixDiffers, fixPayload, fixPrompt, readerPair } from './boxFix.js';

// His AAPL: the climax bar of Tue 22/09/2026 (high 345.34) and the reaction low of Thu 24/09 (334.30).
const climax = { time: '2026-09-22', open: 340.14, high: 345.34, low: 338.75, close: 339.75 };
const reaction = { time: '2026-09-24', open: 336.72, high: 338.91, low: 334.30, close: 335.92 };
const last = { time: '2026-10-16', open: 346.09, high: 347.82, low: 340.46, close: 343.46 };
const data = {
  candles: [climax, reaction, last],
  two_eyes: { boxes: [{ role: 'parent', r: 345.34, r_day: '2026-09-22', s: 334.3, s_day: '2026-09-24', opened: '2026-09-22', end: null }] },
};
const nearHigh = (bar) => ({ date: bar.time, bar, price: bar.high - 0.3 });
const nearLow = (bar) => ({ date: bar.time, bar, price: bar.low + 0.3 });

test('the reader pair is the parent box on the wire, or null', () => {
  assert.deepEqual(readerPair(data), { r: 345.34, rDay: '2026-09-22', s: 334.3, sDay: '2026-09-24', opened: '2026-09-22' });
  assert.equal(readerPair({ two_eyes: { boxes: [{ role: 'earlier', r: 1, s: 0 }] } }), null);
  assert.equal(readerPair({}), null);
});

test('BC then AR: a click near the high is the resistance, the next near a low the support, a third starts over', () => {
  const one = applyFixClick(EMPTY_FIX, nearHigh(climax));
  assert.deepEqual(one, { r: 345.34, rDay: '2026-09-22', s: null, sDay: null });
  assert.equal(fixComplete(one), false);
  const two = applyFixClick(one, nearLow(reaction));
  assert.deepEqual(two, { r: 345.34, rDay: '2026-09-22', s: 334.3, sDay: '2026-09-24' });
  assert.equal(fixComplete(two), true);
  const three = applyFixClick(two, nearHigh(last));
  assert.deepEqual(three, { r: 347.82, rDay: '2026-10-16', s: null, sDay: null });
  assert.equal(applyFixClick(one, { date: null, bar: reaction, price: 335 }), one, 'no date: nothing moves');
  assert.equal(applyFixClick(one, { date: reaction.time, bar: null, price: 335 }), one, 'no bar: nothing moves');
});

test('SC then AR: the first click may be the low, and the higher line is the resistance whatever the order', () => {
  // A fall into a climax low (SC) and the reaction high (AR) after it.
  const sc = { time: '2026-03-02', open: 8.4, high: 8.42, low: 6.77, close: 8.1 };
  const ar = { time: '2026-03-11', open: 10.1, high: 11.5, low: 9.78, close: 11.2 };
  const first = applyFixClick(EMPTY_FIX, nearLow(sc));
  assert.deepEqual(first, { r: null, rDay: null, s: 6.77, sDay: '2026-03-02' });
  assert.match(fixPrompt(first), /now click the reaction high/);
  const second = applyFixClick(first, nearHigh(ar));
  assert.deepEqual(second, { r: 11.5, rDay: '2026-03-11', s: 6.77, sDay: '2026-03-02' });
  assert.equal(fixComplete(second), true);
  // Two highs, or two lows: still the higher line over the lower one.
  const twoHighs = applyFixClick(applyFixClick(EMPTY_FIX, nearHigh(ar)), nearHigh(sc));
  assert.deepEqual(twoHighs, { r: 11.5, rDay: '2026-03-11', s: 8.42, sDay: '2026-03-02' });
  const twoLows = applyFixClick(applyFixClick(EMPTY_FIX, nearLow(ar)), nearLow(sc));
  assert.deepEqual(twoLows, { r: 9.78, rDay: '2026-03-11', s: 6.77, sDay: '2026-03-02' });
});

test('the strip says the next step, and one price twice is no box', () => {
  assert.match(fixPrompt(EMPTY_FIX), /climax high \(BC\) or the climax low \(SC\)/);
  assert.match(fixPrompt({ r: 345.34, rDay: '2026-09-22', s: null, sDay: null }), /now click the reaction low/);
  const same = applyFixClick(applyFixClick(EMPTY_FIX, nearHigh(climax)), nearHigh(climax));
  assert.equal(fixComplete(same), false);
  assert.match(fixPrompt(same), /one price/);
  assert.equal(fixPrompt({ r: 345.34, rDay: '2026-09-22', s: 334.3, sDay: '2026-09-24' }), 'R 345.34 (2026-09-22) · S 334.30 (2026-09-24)');
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
