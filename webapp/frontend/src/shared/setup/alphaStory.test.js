// The grade panel for a row the alpha reader wrote (Tue 13/10/2026, his "the Grade section at the advanced chart
// block is completely broken"): the box, the story's words, the mini and the LPS, in the order the chart played them.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { buildPhaseRegions } from '../charts/chartPhaseOverlay.js';
import { alphaStory, alphaTechnicalCells } from './alphaStory.js';

// 60 daily candles from 2026-08-03 on, weekdays only, so the days below land on real bars.
const candles = (() => {
  const out = [];
  const day = new Date(Date.UTC(2026, 7, 3));
  while (out.length < 60) {
    if (day.getUTCDay() !== 0 && day.getUTCDay() !== 6) {
      const i = out.length;
      out.push({ time: day.toISOString().slice(0, 10), open: 50 + i * 0.1, high: 51 + i * 0.1, low: 49 + i * 0.1, close: 50 + i * 0.1 });
    }
    day.setUTCDate(day.getUTCDate() + 1);
  }
  return out;
})();

const scanRow = (overrides = {}) => ({
  candles,
  trigger: 57.3,
  alpha: {
    boxes: [
      { role: 'parent', r: 56, r_day: '2026-08-05', s: 50, s_day: '2026-08-07', opened: '2026-08-05', end: null, ranges_tall: 3.0 },
      { role: 'mini', r: 56, r_day: '2026-09-15', s: 54, s_day: '2026-09-16', opened: '2026-09-15', end: null, ranges_tall: 1.25 },
    ],
    lps: { against: 'mini', how: 'on', start: '2026-10-19', end: '2026-10-21', trigger: 57.3 },
    state: 'fired',
    grade: { score: 90, letter: 'S', empty_days: 2, base_days: 40, holds: true },
    events: [
      { kind: 'spring', day: '2026-08-26', price: 49.2, first: '2026-08-24', last: '2026-08-28', size: 0.8, committed: true, note: null },
      { kind: 'SOS', day: '2026-09-10', price: 57.5, first: '2026-09-02', last: '2026-09-10', size: 3.4, committed: true, note: null },
      { kind: 'Phase D', day: '2026-09-02', price: 51, first: null, last: null, size: null, committed: false, note: 'SOS' },
    ],
    ...overrides,
  },
});

test('the columns run in chart order: the box, the words by their day, the mini, the LPS', () => {
  const data = scanRow();
  const { columns, footnote } = alphaStory(data, buildPhaseRegions(data));
  assert.deepEqual(columns.map((c) => c.name), ['Box', 'Spring', 'Phase D', 'SOS', 'Mini', 'LPS']);
  assert.deepEqual(columns.map((c) => c.kind), ['chapter', 'mark', 'mark', 'mark', 'chapter', 'chapter']);
  assert.equal(footnote, null);
  // Each column lights its own band, never another's (the box is 'b'; the mini and each word have their own ids).
  assert.deepEqual(columns.map((c) => c.region),
    ['b', 'story:spring:2026-08-26', 'story:Phase D:2026-09-02', 'story:SOS:2026-09-10', 'mini', 'lps:active']);
});

test('the box carries its height in daily ranges and its days with a bar in it; the LPS its trigger', () => {
  const data = scanRow();
  const { columns } = alphaStory(data, buildPhaseRegions(data));
  const box = columns.find((c) => c.key === 'b');
  assert.equal(box.figure, '3.0');
  assert.equal(box.unit, 'ranges tall');
  assert.equal(box.fraction, 38 / 40, '38 of 40 base days had a bar in the box');
  assert.match(box.detail, /^R 56\.00 \/ S 50\.00 · opened 05\/08$/);
  const lps = columns.find((c) => c.key === 'lps');
  assert.equal(lps.figure, '57.30');
  assert.equal(lps.detail, '19/10–21/10 · 3 receding days · resting on the mini');
  const mini = columns.find((c) => c.key === 'mini');
  assert.equal(mini.fraction, null, 'the grade is read on the box, never the mini');
});

test('each word says what it did, short on the rail and whole in the tooltip', () => {
  const data = scanRow();
  const { columns } = alphaStory(data, buildPhaseRegions(data));
  const byName = Object.fromEntries(columns.map((c) => [c.name, c]));
  assert.equal(byName.Spring.detail, '26/08 · 0.8 daily ranges under support');
  assert.equal(byName.Spring.title, 'Spring, Wed 26/08/2026: 0.8 daily ranges under support.');
  assert.equal(byName.SOS.detail, '10/09 · ran 3.4 daily ranges');
  assert.equal(byName['Phase D'].detail, '02/09 · opened by the SOS · still forming');
});

test('a row that named no word says so; an archived row says the archive keeps no story', () => {
  const quiet = scanRow({ events: [] });
  assert.match(alphaStory(quiet, buildPhaseRegions(quiet)).footnote, /named no spring/);
  // The archive keeps the boxes, the LPS's box and the score: no events key at all, and no LPS days.
  const archived = { candles, trigger: 57.3, alpha: {
    boxes: scanRow().alpha.boxes, lps: { against: 'parent' }, grade: { score: 90, letter: 'S' } } };
  const told = alphaStory(archived, buildPhaseRegions(archived));
  assert.match(told.footnote, /^No story came with this row/);
  assert.deepEqual(told.columns.map((c) => c.name), ['Box', 'Mini', 'LPS']);
  const lps = told.columns.find((c) => c.key === 'lps');
  assert.equal(lps.figure, '57.30', "the row's own trigger");
  assert.equal(lps.region, null, 'no LPS days stored, nothing to light');
  assert.equal(told.columns[0].fraction, null, 'no empty-day count stored: a hairline, never a measured zero');
});

test('no block, no columns', () => {
  assert.deepEqual(alphaStory({ candles }), { columns: [], footnote: null });
  assert.deepEqual(alphaStory(null), { columns: [], footnote: null });
});

test("the technical read's cells come from the reader's own read, never the old engine's dashes", () => {
  const data = scanRow();
  const cells = Object.fromEntries(alphaTechnicalCells(data, buildPhaseRegions(data)).map((c) => [c.k, c.v]));
  assert.equal(cells['Box width'], '12.0%');
  assert.equal(cells['Box height'], '3.0 ranges');
  assert.equal(cells.Base, '58 days', 'from the day the box opened (index 2) through the last candle (index 59)');
  assert.equal(cells.LPS, '3 days');
  assert.equal(cells.Mini, '1.3 ranges');
  // The box's own facts, moved here from the phase board's Box column (Thu 29/10/2026, "the dry stats section").
  assert.equal(cells['In box to SOS'], '38 of 40 days');
  assert.equal(cells.Hold, 'held');
  // The box's cells light the whole box on the chart, as the board's Box column did; the LPS cell does not.
  const byKey = Object.fromEntries(alphaTechnicalCells(data, buildPhaseRegions(data)).map((c) => [c.k, c]));
  assert.equal(byKey.Box.region, 'b');
  assert.equal(byKey.Base.region, 'b');
  assert.equal(byKey.LPS.region, undefined);
  // With no SOS named the grade's count runs to the last day, and the label stops saying "to SOS".
  const quiet = scanRow({ events: [] });
  const quietCells = Object.fromEntries(alphaTechnicalCells(quiet, buildPhaseRegions(quiet)).map((c) => [c.k, c.v]));
  assert.equal(quietCells['In box'], '38 of 40 days');
  assert.equal(quietCells['In box to SOS'], undefined);
  const noMini = scanRow({ boxes: [scanRow().alpha.boxes[0]] });
  assert.equal(Object.fromEntries(alphaTechnicalCells(noMini, buildPhaseRegions(noMini)).map((c) => [c.k, c.v])).Mini, 'none');
});
