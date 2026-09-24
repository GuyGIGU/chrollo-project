import assert from 'node:assert/strict';
import test from 'node:test';
import { indexForDate, thumbGeometry } from './frameThumb.js';

const series = [
  { t: '2026-01-05', c: 10 },
  { t: '2026-01-06', c: 12 },
  { t: '2026-01-07', c: 11 },
  { t: '2026-01-08', c: 13 },
];
const preview = { series, lo: 9, hi: 14 };

test('indexForDate finds the first session at/after the date', () => {
  assert.equal(indexForDate(series, '2026-01-06'), 1);   // exact hit
  assert.equal(indexForDate(series, '2026-01-06half'), 2); // between 06 and 07
  assert.equal(indexForDate(series, '2020-01-01'), 0);   // before all -> first
  assert.equal(indexForDate(series, '2030-01-01'), 3);   // after all -> last
});

test('thumbGeometry returns null when there is nothing to draw', () => {
  assert.equal(thumbGeometry({ series: [], lo: 1, hi: 2 }, null), null);
  assert.equal(thumbGeometry(null, null), null);
  assert.equal(thumbGeometry({ series, lo: NaN, hi: 2 }, null), null); // non-finite envelope
});

test('thumbGeometry maps a close line across the full width, no box', () => {
  const g = thumbGeometry(preview, null, { width: 74, height: 34, pad: 3 });
  assert.equal(g.box, null);
  const pts = g.points.split(' ');
  assert.equal(pts.length, 4);
  // first point at the left pad, last at the right pad (full-width line)
  assert.equal(Number(pts[0].split(',')[0]), 3);
  assert.equal(Number(pts[3].split(',')[0]), 71);
});

test('thumbGeometry draws the operator box from its start to the right edge', () => {
  const box = { r: 12.5, s: 10.5, boxStart: '2026-01-07', boxEnd: '2026-01-08' };
  const g = thumbGeometry(preview, box, { width: 74, height: 34, pad: 3 });
  assert.ok(g.box, 'box geometry present');
  assert.equal(g.box.right, 71);
  assert.ok(g.box.x > 3 && g.box.x < 71, 'box starts inside, not at the left edge');
  assert.equal(Math.round(g.box.x + g.box.width), 71); // spans to the right pad
  assert.ok(g.box.ry < g.box.sy, 'R (top) is above S (bottom) in SVG y');
});

test('thumbGeometry expands the y-range so an out-of-frame rail still fits', () => {
  // R above the frame high (14) and S below the frame low (9) must stay in view
  const box = { r: 20, s: 4, boxStart: '2026-01-05', boxEnd: '2026-01-08' };
  const g = thumbGeometry(preview, box, { width: 74, height: 34, pad: 3 });
  assert.ok(g.box.ry >= 3, 'R rail within the top pad');
  assert.ok(g.box.sy <= 31, 'S rail within the bottom pad');
});

test('thumbGeometry ignores a malformed box (r<=s or missing span)', () => {
  const g = thumbGeometry(preview, { r: 10, s: 12, boxStart: 'a', boxEnd: 'b' }, {});
  assert.equal(g.box, null); // inverted rails -> no box, line still drawn
  assert.equal(thumbGeometry(preview, { r: 12, s: 10 }, {}).box, null); // no span
});
