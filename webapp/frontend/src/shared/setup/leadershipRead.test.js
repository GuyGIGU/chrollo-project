import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EMPTY } from '../formatting/format.js';
import {
  hasLeadershipRead, leadershipCells, ma200TrendLabel, rsLabel, stageCells, trendTemplateLabel,
} from './leadershipRead.js';

test('rsLabel: rounds the percentile onto the 1-99 scale', () => {
  assert.equal(rsLabel(84.21), '84');
  assert.equal(rsLabel(99.99), '99');
  assert.equal(rsLabel(0.01), '1');
  assert.equal(rsLabel(null), EMPTY);
  assert.equal(rsLabel(NaN), EMPTY);
});

test('trendTemplateLabel: criteria passed out of seven', () => {
  assert.equal(trendTemplateLabel(7), '7/7');
  assert.equal(trendTemplateLabel(0), '0/7');
  assert.equal(trendTemplateLabel(undefined), EMPTY);
});

test('leadershipCells: label, card text and value per read, in order', () => {
  const cells = leadershipCells({ rs_rating: 84.21, stage2_trend_pass_count: 6, dollar_volume_50d: 32_620_000 });
  assert.deepEqual(cells.map((c) => c.k), ['RS rating', 'Trend template', 'Dollar volume']);
  assert.deepEqual(cells.map((c) => c.card), ['RS 84', '6/7', '$32.6M']);
  assert.match(cells[0].title, /^RS rating 84:/);
});

test('ma200TrendLabel: the percent the wire carries, signed', () => {
  assert.equal(ma200TrendLabel(3.14), '+3.1%');
  assert.equal(ma200TrendLabel(-1.24), '−1.2%');
  assert.equal(ma200TrendLabel(null), EMPTY);
});

test('stageCells: distance off the 52-week low (a fraction) and the 200-day change', () => {
  const cells = stageCells({ stage2_52w_low_pct: 0.8412, stage2_ma200_slope_1m_pct: 0.42 });
  assert.deepEqual(cells.map((c) => c.k), ['Off 52-week low', '200-day trend']);
  assert.deepEqual(cells.map((c) => c.v), ['+84%', '+0.4%']);
  assert.match(cells[0].title, /^Off 52-week low \+84%:/);
  assert.deepEqual(stageCells({}).map((c) => c.v), [EMPTY, EMPTY]);
});

test('hasLeadershipRead: false only when the payload predates the read', () => {
  assert.equal(hasLeadershipRead({}), false);
  assert.equal(hasLeadershipRead({ rs_rating: null, stage2_trend_pass_count: null }), false);
  assert.equal(hasLeadershipRead({ stage2_trend_pass_count: 0 }), true);
  assert.equal(hasLeadershipRead({ dollar_volume_50d: 1_000 }), true);
});
