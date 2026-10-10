import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EMPTY } from '../formatting/format.js';
import {
  accelLabel, fundamentalsCells, fundamentalsNote, hasFundamentalsRead, quarterLabel,
} from './fundamentalsRead.js';

test('quarterLabel: month and year off the ISO text, null when unreadable', () => {
  assert.equal(quarterLabel('2026-06-30'), 'Jun 2026 quarter');
  assert.equal(quarterLabel('2025-12-31'), 'Dec 2025 quarter');
  assert.equal(quarterLabel('2026-13-01'), null);
  assert.equal(quarterLabel(null), null);
});

test('accelLabel: a difference of growth rates, in signed percentage points', () => {
  assert.equal(accelLabel(0.153), '+15 pts');
  assert.equal(accelLabel(-0.4), '−40 pts');
  assert.equal(accelLabel(0), '+0 pts');
  assert.equal(accelLabel(null), EMPTY);
});

test('fundamentalsCells: label and value per read, in order, naming the quarter', () => {
  const cells = fundamentalsCells({
    market_cap: 1_250_000_000, fund_eps_growth_yoy: 0.452, fund_sales_growth_yoy: -0.031,
    fund_eps_growth_accel: 0.12, fund_earnings_surprise: 0.084, fund_quarter_end: '2026-06-30',
  });
  assert.deepEqual(cells.map((c) => c.k),
    ['Market cap', 'EPS growth', 'Sales growth', 'EPS acceleration', 'Earnings surprise']);
  assert.deepEqual(cells.map((c) => c.v), ['$1.3B', '+45%', '−3%', '+12 pts', '+8%']);
  assert.match(cells[1].title, /of the Jun 2026 quarter against/);
  assert.deepEqual(fundamentalsCells({}).map((c) => c.v), [EMPTY, EMPTY, EMPTY, EMPTY, EMPTY]);
});

test('fundamentalsNote: the quarter when known', () => {
  assert.equal(fundamentalsNote({ fund_quarter_end: '2026-03-31' }), 'Mar 2026 quarter');
  assert.equal(fundamentalsNote({}), 'the business, not the setup');
});

test('hasFundamentalsRead: false only when the payload carries none of it', () => {
  assert.equal(hasFundamentalsRead({}), false);
  assert.equal(hasFundamentalsRead({ fund_quarter_end: '2026-06-30' }), false);
  assert.equal(hasFundamentalsRead({ fund_eps_growth_yoy: 0 }), true);
  assert.equal(hasFundamentalsRead({ market_cap: 4e8 }), true);
});
