// His events on a fixed box (Sat 18/10/2026): the pure half, pinned on his AAPL swings.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  EMPTY_EVENTS, EVENT_KINDS, EVENT_TAG, applyEventClick, armEvent, eventPrompt, eventWords, eventsPayload,
  labelEvent, removeEvent,
} from './boxFixEvents.js';

// His AAPL: the spring's tip Thu 01/10 (low 325.81), THE SOS launching Mon 12/10 and topping Tue 13/10
// (high 348.15), the LPS Wed 14/10 to Fri 16/10 (lowest low 340.46).
const candles = [
  { time: '2026-10-01', open: 331.2, high: 333.0, low: 325.81, close: 332.4 },
  { time: '2026-10-12', open: 338.0, high: 341.9, low: 337.6, close: 341.2 },
  { time: '2026-10-13', open: 342.0, high: 348.15, low: 341.0, close: 347.5 },
  { time: '2026-10-14', open: 347.0, high: 348.0, low: 343.1, close: 345.0 },
  { time: '2026-10-15', open: 344.9, high: 346.2, low: 341.8, close: 343.9 },
  { time: '2026-10-16', open: 346.09, high: 347.82, low: 340.46, close: 343.46 },
];
const bar = (day) => candles.find((c) => c.time === day);
const click = (day, price) => ({ date: day, bar: bar(day), price: price ?? (bar(day).high + bar(day).low) / 2 });

test('the vocabulary is his seven, each with a letter', () => {
  assert.deepEqual(EVENT_KINDS, ['spring', 'upthrust', 'sos', 'lps', 'former_lps', 'span', 'mini']);
  assert.deepEqual(Object.keys(EVENT_TAG).sort(), [...EVENT_KINDS].sort());
  assert.equal(new Set(Object.values(EVENT_TAG)).size, 7, 'no two events share a letter');
});

test('a letter arms its event, the same letter disarms, an unknown word arms nothing', () => {
  const armed = armEvent(EMPTY_EVENTS, 'spring');
  assert.equal(armed.tool, 'spring');
  assert.equal(armEvent(armed, 'spring').tool, null);
  assert.equal(armEvent(armed, 'lps').tool, 'lps');
  assert.equal(armEvent(EMPTY_EVENTS, 'creek').tool, null);
  assert.equal(applyEventClick(EMPTY_EVENTS, click('2026-10-01'), candles), EMPTY_EVENTS, 'no tool: nothing moves');
});

test('a spring is one click on its tip, an upthrust one click on its top, and the tool disarms', () => {
  const spring = applyEventClick(armEvent(EMPTY_EVENTS, 'spring'), click('2026-10-01'), candles);
  assert.deepEqual(spring.events, [{ kind: 'spring', first_day: '2026-10-01', last_day: '2026-10-01', price: 325.81, band_high: null, band_low: null, label: null }]);
  assert.equal(spring.tool, null);
  const up = applyEventClick(armEvent(spring, 'upthrust'), click('2026-10-13'), candles);
  assert.equal(up.events[1].price, 348.15);
  assert.equal(up.events[1].kind, 'upthrust');
});

test('the SOS is the launch low then the top, in either order; an LPS is its first and last day at the lowest low', () => {
  let state = armEvent(EMPTY_EVENTS, 'sos');
  state = applyEventClick(state, click('2026-10-13'), candles);
  assert.equal(state.anchor.date, '2026-10-13');
  assert.equal(eventPrompt(state), 'launch 13/10: now click the SOS top');
  state = applyEventClick(state, click('2026-10-12'), candles);
  assert.deepEqual(state.events, [{ kind: 'sos', first_day: '2026-10-12', last_day: '2026-10-13', price: 348.15, band_high: null, band_low: null, label: null }]);
  state = applyEventClick(applyEventClick(armEvent(state, 'lps'), click('2026-10-16'), candles), click('2026-10-14'), candles);
  assert.deepEqual(state.events[1], { kind: 'lps', first_day: '2026-10-14', last_day: '2026-10-16', price: 340.46, band_high: null, band_low: null, label: null });
  state = applyEventClick(applyEventClick(armEvent(state, 'former_lps'), click('2026-10-12'), candles), click('2026-10-12'), candles);
  assert.equal(state.events[2].first_day, state.events[2].last_day, 'a one-day stretch is allowed');
});

test('the mini takes two corners, each snapping to the nearer end of its bar, the higher one its resistance', () => {
  let state = armEvent(EMPTY_EVENTS, 'mini');
  state = applyEventClick(state, click('2026-10-14', 347.9), candles);   // near the high 348.0
  assert.equal(state.anchor.snapped, 348.0);
  state = applyEventClick(state, click('2026-10-16', 340.6), candles);   // near the low 340.46
  assert.deepEqual(state.events, [{ kind: 'mini', first_day: '2026-10-14', last_day: '2026-10-16', price: null, band_high: 348.0, band_low: 340.46, label: null }]);
  const flat = applyEventClick(applyEventClick(armEvent(EMPTY_EVENTS, 'mini'), click('2026-10-14', 347.9), candles), click('2026-10-14', 347.95), candles);
  assert.deepEqual(flat.events, [], 'two corners on one price are no mini: the first is dropped');
});

test('a span keeps his label, an event can be removed, and the payload is the list as a whole', () => {
  let state = applyEventClick(applyEventClick(armEvent(EMPTY_EVENTS, 'span'), click('2026-10-12'), candles), click('2026-10-15'), candles);
  state = labelEvent(state, 0, ' the dull middle ');
  assert.equal(eventWords(state.events[0]), 'span 12/10–15/10 337.60 "the dull middle"');
  assert.deepEqual(eventsPayload(state.events), [{ kind: 'span', first_day: '2026-10-12', last_day: '2026-10-15', price: 337.6, band_high: null, band_low: null, label: 'the dull middle' }]);
  assert.deepEqual(removeEvent(state, 0).events, []);
  assert.equal(eventWords({ kind: 'spring', first_day: '2026-10-01', last_day: '2026-10-01', price: 325.81 }), 'spring 01/10 325.81');
  assert.equal(eventWords({ kind: 'mini', first_day: '2026-10-14', last_day: '2026-10-16', band_high: 348, band_low: 340.46 }), 'mini 14/10–16/10 348.00/340.46');
});

test('the strip tells him the next click', () => {
  assert.equal(eventPrompt(EMPTY_EVENTS), null);
  assert.equal(eventPrompt(armEvent(EMPTY_EVENTS, 'spring')), "click the spring's tip: the bar whose low poked under support");
  assert.equal(eventPrompt(armEvent(EMPTY_EVENTS, 'former_lps')), 'click the first day of the former LPS');
  assert.equal(eventPrompt(armEvent(EMPTY_EVENTS, 'mini')), 'click one corner of the mini');
  const half = applyEventClick(armEvent(EMPTY_EVENTS, 'lps'), click('2026-10-14'), candles);
  assert.equal(eventPrompt(half), '14/10: now click the last day of the LPS');
});
