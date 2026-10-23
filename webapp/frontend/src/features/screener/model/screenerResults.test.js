import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildTagMap, setupTypes, presentTags, filterTickers } from './screenerResults.js';

const scan = {
  ordered_tickers: ['BETA', 'MISSING', 'ALPHA', 'GAMMA'],
  chart_data: {
    BETA: { tier: 'A', setup: 'LPS', price: 90, trigger: 100, base_len: 40, rs_rating: null, fired_tags: [{ id: 'new_fact' }] },
    ALPHA: { tier: 'S', setup: 'VCP', price: 98, trigger: 100, base_len: 80, rs_rating: 95, fired_tags: [{ id: 'new_fact' }] },
    GAMMA: { tier: 'A', setup: 'LPS', price: null, trigger: null, base_len: 40, rs_rating: 80 },
  },
};
const select = (changes = {}) => filterTickers({
  screenerData: scan, tierFilter: 'ALL', setupFilter: 'ALL', searchTerm: '',
  tagFilter: new Set(), sortBy: 'score', watchlist: new Set(['BETA']), liked: new Set(['ALPHA']),
  tagIdsByTicker: buildTagMap(scan), ...changes,
});

test('default selection preserves engine order and omits fires without a chart', () => {
  assert.deepEqual(select(), ['BETA', 'ALPHA', 'GAMMA']);
  assert.deepEqual(scan.ordered_tickers, ['BETA', 'MISSING', 'ALPHA', 'GAMMA']);
  assert.deepEqual(select({ screenerData: null }), []);
});

test('tier, shortlist, search and engine-provided tags compose', () => {
  assert.deepEqual(select({ tierFilter: 'LIKED' }), ['ALPHA']);
  assert.deepEqual(select({ tierFilter: 'A', setupFilter: 'LPS', searchTerm: 'be', tagFilter: new Set(['new_fact']) }), ['BETA']);
  assert.deepEqual(select({ tagFilter: new Set(['absent']) }), []);
  assert.deepEqual(setupTypes(scan), ['LPS', 'VCP']);
  assert.deepEqual([...presentTags(buildTagMap(scan))], ['new_fact']);
});

test('display sorts handle missing values and keep engine order for ties', () => {
  for (const sortBy of ['base', 'trigger', 'rs']) {
    const expected = sortBy === 'rs' ? ['ALPHA', 'GAMMA', 'BETA'] : ['ALPHA', 'BETA', 'GAMMA'];
    assert.deepEqual(select({ sortBy }), expected, sortBy);
  }
  assert.deepEqual(select(), ['BETA', 'ALPHA', 'GAMMA']);
});
