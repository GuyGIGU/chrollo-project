// His events on a fixed box (Sat 18/10/2026): the pure half, pinned on his AAPL swings.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  EMPTY_EVENTS, EVENT_KINDS, TOOLS, TOOL_NAMES, TOOL_HOW, allEvents, applyToolClick, armTool, eventWords, eventsPayload,
  labelEvent, marksFromFix, miniEvent, removeEvent, removeMiniPart, toolPrompt,
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
const click = (day) => ({ date: day, bar: bar(day), price: (bar(day).high + bar(day).low) / 2 });
const place = (state, tool, ...days) => days.reduce((now, day) => applyToolClick(now, click(day), candles), armTool(state, tool));

test('the vocabulary is his seven, and every tool has a name and a how', () => {
  assert.deepEqual(EVENT_KINDS, ['spring', 'upthrust', 'sos', 'lps', 'former_lps', 'span', 'mini']);
  assert.deepEqual(TOOLS, ['rail-r', 'rail-s', 'mini-r', 'mini-s', 'mini-span', 'spring', 'upthrust', 'sos', 'lps', 'former_lps', 'span']);
  for (const tool of TOOLS) assert.ok(TOOL_NAMES[tool] && TOOL_HOW[tool], tool);
});

test('a button arms its tool, the same button disarms, an unknown word arms nothing', () => {
  const armed = armTool(EMPTY_EVENTS, 'spring');
  assert.equal(armed.tool, 'spring');
  assert.equal(armTool(armed, 'spring').tool, null);
  assert.equal(armTool(armed, 'lps').tool, 'lps');
  assert.equal(armTool(EMPTY_EVENTS, 'creek').tool, null);
  assert.equal(applyToolClick(EMPTY_EVENTS, click('2026-10-01'), candles), EMPTY_EVENTS, 'no tool: nothing moves');
});

test('a spring is one click on its tip, an upthrust one click on its top, and the tool disarms', () => {
  const spring = place(EMPTY_EVENTS, 'spring', '2026-10-01');
  assert.deepEqual(spring.events, [{ kind: 'spring', first_day: '2026-10-01', last_day: '2026-10-01', price: 325.81, band_high: null, band_low: null, label: null }]);
  assert.equal(spring.tool, null);
  const up = place(spring, 'upthrust', '2026-10-13');
  assert.equal(up.events[1].price, 348.15);
  assert.equal(up.events[1].kind, 'upthrust');
});

test('the SOS is the launch low then the top, in either order; an LPS is its first and last day at the lowest low', () => {
  let state = armTool(EMPTY_EVENTS, 'sos');
  state = applyToolClick(state, click('2026-10-13'), candles);
  assert.equal(state.anchor.date, '2026-10-13');
  assert.equal(toolPrompt(state), 'launch 13/10: now click the SOS top');
  state = applyToolClick(state, click('2026-10-12'), candles);
  assert.deepEqual(state.events, [{ kind: 'sos', first_day: '2026-10-12', last_day: '2026-10-13', price: 348.15, band_high: null, band_low: null, label: null }]);
  state = place(state, 'lps', '2026-10-16', '2026-10-14');
  assert.deepEqual(state.events[1], { kind: 'lps', first_day: '2026-10-14', last_day: '2026-10-16', price: 340.46, band_high: null, band_low: null, label: null });
  state = place(state, 'former_lps', '2026-10-12', '2026-10-12');
  assert.equal(state.events[2].first_day, state.events[2].last_day, 'a one-day stretch is allowed');
});

test('the mini works like the box: Mini resistance on a high, Mini support on a low, its own span, else the earlier line to the edge', () => {
  let state = place(EMPTY_EVENTS, 'mini-r', '2026-10-14');
  assert.deepEqual(state.mini, { r: 348.0, rDay: '2026-10-14', s: null, sDay: null, spanStart: null, spanEnd: null });
  assert.equal(miniEvent(state.mini, '2026-10-16'), null, 'one line is no mini');
  state = place(state, 'mini-s', '2026-10-15');
  assert.deepEqual(miniEvent(state.mini, '2026-10-16'), { kind: 'mini', first_day: '2026-10-14', last_day: '2026-10-16', price: null, band_high: 348.0, band_low: 341.8, label: null });
  state = place(state, 'mini-span', '2026-10-15', '2026-10-13');
  assert.deepEqual(state.mini, { r: 348.0, rDay: '2026-10-14', s: 341.8, sDay: '2026-10-15', spanStart: '2026-10-13', spanEnd: '2026-10-15' });
  assert.equal(miniEvent(state.mini, '2026-10-16').first_day, '2026-10-13');
  assert.equal(miniEvent(state.mini, '2026-10-16').last_day, '2026-10-15');
  assert.equal(allEvents(state, '2026-10-16').length, 1, 'the mini rides with the events');
  assert.deepEqual(removeMiniPart(state, 'span').mini, { ...state.mini, spanStart: null, spanEnd: null });
  assert.equal(removeMiniPart(state, 'r').mini.r, null);
  // Crossed lines: the Support click on a bar whose low sits over the Resistance click's high.
  const crossed = place(place(EMPTY_EVENTS, 'mini-r', '2026-10-01'), 'mini-s', '2026-10-14');
  assert.deepEqual([crossed.mini.r, crossed.mini.rDay, crossed.mini.s, crossed.mini.sDay], [343.1, '2026-10-14', 333.0, '2026-10-01']);
});

test('a span keeps his label, an event can be removed, and the payload is the list as a whole', () => {
  let state = place(EMPTY_EVENTS, 'span', '2026-10-12', '2026-10-15');
  state = labelEvent(state, 0, ' the dull middle ');
  assert.equal(eventWords(state.events[0]), 'span 12/10–15/10 337.60 "the dull middle"');
  assert.deepEqual(eventsPayload(state.events), [{ kind: 'span', first_day: '2026-10-12', last_day: '2026-10-15', price: 337.6, band_high: null, band_low: null, label: 'the dull middle' }]);
  assert.deepEqual(removeEvent(state, 0).events, []);
  assert.equal(eventWords({ kind: 'spring', first_day: '2026-10-01', last_day: '2026-10-01', price: 325.81 }), 'spring 01/10 325.81');
  assert.equal(eventWords({ kind: 'mini', first_day: '2026-10-14', last_day: '2026-10-16', band_high: 348, band_low: 340.46 }), 'mini 14/10–16/10 348.00/340.46');
});

test('the page tells him the next click', () => {
  assert.equal(toolPrompt(EMPTY_EVENTS), null);
  assert.equal(toolPrompt(armTool(EMPTY_EVENTS, 'spring')), 'click its tip: the bar whose low poked under support');
  assert.equal(toolPrompt(armTool(EMPTY_EVENTS, 'former_lps')), 'click the first day of the former LPS');
  assert.equal(toolPrompt(armTool(EMPTY_EVENTS, 'mini-span')), "click the mini's first day");
  assert.equal(toolPrompt(armTool(EMPTY_EVENTS, 'mini-r')), "click the mini's top bar: the line lands on its high");
  const half = applyToolClick(armTool(EMPTY_EVENTS, 'lps'), click('2026-10-14'), candles);
  assert.equal(toolPrompt(half), '14/10: now click the last day of the LPS');
});

test('the marks are seated from the fix saved before: its events as they were, the mini as lines and span', () => {
  const saved = { events: [
    { id: 1, kind: 'span', first_day: '2026-08-03', last_day: '2026-10-07', price: 70.55, band_high: null, band_low: null, label: null },
    { id: 5, kind: 'mini', first_day: '2026-08-31', last_day: '2026-10-07', price: null, band_high: 82.65, band_low: 78.18, label: null },
    { id: 2, kind: 'spring', first_day: '2026-09-10', last_day: '2026-09-10', price: 70.55, band_high: null, band_low: null, label: 'his' },
  ] };
  const seated = marksFromFix(saved);
  assert.equal(seated.tool, null);
  assert.deepEqual(seated.events.map((e) => [e.kind, e.first_day, e.last_day, e.price, e.label]),
    [['span', '2026-08-03', '2026-10-07', 70.55, null], ['spring', '2026-09-10', '2026-09-10', 70.55, 'his']]);
  assert.deepEqual(seated.mini, { r: 82.65, rDay: '2026-08-31', s: 78.18, sDay: '2026-08-31', spanStart: '2026-08-31', spanEnd: '2026-10-07' });
  assert.deepEqual(miniEvent(seated.mini, '2026-10-16'), { kind: 'mini', first_day: '2026-08-31', last_day: '2026-10-07', price: null, band_high: 82.65, band_low: 78.18, label: null }, 'the seated mini re-saves as it was');
  assert.deepEqual(marksFromFix(null), EMPTY_EVENTS);
});
