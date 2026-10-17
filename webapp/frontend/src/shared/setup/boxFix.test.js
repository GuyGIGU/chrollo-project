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

test('the reader pair is the parent box on the wire, or null', () => {
  assert.deepEqual(readerPair(data), { r: 345.34, rDay: '2026-09-22', s: 334.3, sDay: '2026-09-24', opened: '2026-09-22' });
  assert.equal(readerPair({ two_eyes: { boxes: [{ role: 'earlier', r: 1, s: 0 }] } }), null);
  assert.equal(readerPair({}), null);
});

test('the first click is the resistance on the bar HIGH, the second the support on the bar LOW, a third starts over', () => {
  const one = applyFixClick(EMPTY_FIX, { date: climax.time, bar: climax });
  assert.deepEqual(one, { r: 345.34, rDay: '2026-09-22', s: null, sDay: null });
  assert.equal(fixComplete(one), false);
  const two = applyFixClick(one, { date: reaction.time, bar: reaction });
  assert.deepEqual(two, { r: 345.34, rDay: '2026-09-22', s: 334.3, sDay: '2026-09-24' });
  assert.equal(fixComplete(two), true);
  const three = applyFixClick(two, { date: last.time, bar: last });
  assert.deepEqual(three, { r: 347.82, rDay: '2026-10-16', s: null, sDay: null });
  assert.equal(applyFixClick(one, { date: null, bar: reaction }), one, 'no date: nothing moves');
  assert.equal(applyFixClick(one, { date: reaction.time, bar: null }), one, 'no bar: nothing moves');
});

test('a support over the resistance is no box, and the strip says what to do', () => {
  const upside = applyFixClick({ r: 334.3, rDay: '2026-09-24', s: null, sDay: null }, { date: climax.time, bar: climax });
  assert.equal(fixComplete(upside), false);
  assert.match(fixPrompt(upside), /must sit under/);
  assert.match(fixPrompt(EMPTY_FIX), /HIGH is the resistance/);
  assert.match(fixPrompt({ r: 345.34, rDay: '2026-09-22', s: null, sDay: null }), /LOW is the support/);
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
