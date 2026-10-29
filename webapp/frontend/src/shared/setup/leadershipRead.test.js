import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EMPTY } from '../formatting/format.js';
import {
  advanceLabel, cycleStageLabel, hasLeadershipRead, leadershipCells, ma200TrendLabel, rsLabel, stageCells,
  trendTemplateLabel,
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

test('cycleStageLabel: the stage the wire carries, in the book\'s word', () => {
  assert.equal(cycleStageLabel(1), '1 · neglect');
  assert.equal(cycleStageLabel(2), '2 · advance');
  assert.equal(cycleStageLabel(3), '3 · top');
  assert.equal(cycleStageLabel(4), '4 · decline');
  assert.equal(cycleStageLabel(null), EMPTY);
  assert.equal(cycleStageLabel(5), EMPTY);
});

test('advanceLabel: the week the advance began and its age, or a dash when either is missing', () => {
  assert.equal(advanceLabel('2026-05-29', 20), 'Fri 29/05/2026 · 20 wk');
  assert.equal(advanceLabel(null, 20), EMPTY);
  assert.equal(advanceLabel('2026-05-29', null), EMPTY);
});

test('stageCells: the stage, its advance, the distance off the 52-week low (a fraction) and the 200-day change', () => {
  const cells = stageCells({
    cycle_stage: 2, advance_start: '2026-05-29', advance_weeks: 20,
    stage2_52w_low_pct: 0.8412, stage2_ma200_slope_1m_pct: 0.42,
  });
  assert.deepEqual(cells.map((c) => c.k), ['Stage', 'Advance', 'Off 52-week low', '200-day trend']);
  assert.deepEqual(cells.map((c) => c.v), ['2 · advance', 'Fri 29/05/2026 · 20 wk', '+84%', '+0.4%']);
  assert.match(cells[0].title, /^Stage 2 · advance: a week closed above a rising 40-week average/);
  assert.match(cells[1].title, /began the week ending Fri 29\/05\/2026/);
  assert.match(cells[2].title, /^Off 52-week low \+84%:/);
  assert.deepEqual(stageCells({}).map((c) => c.v), [EMPTY, EMPTY, EMPTY, EMPTY]);
  assert.match(stageCells({}).at(0).title, /not read/);
});

test('hasLeadershipRead: false only when the payload predates the read', () => {
  assert.equal(hasLeadershipRead({}), false);
  assert.equal(hasLeadershipRead({ rs_rating: null, stage2_trend_pass_count: null }), false);
  assert.equal(hasLeadershipRead({ stage2_trend_pass_count: 0 }), true);
  assert.equal(hasLeadershipRead({ dollar_volume_50d: 1_000 }), true);
});
