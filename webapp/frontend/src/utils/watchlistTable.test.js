import assert from 'node:assert/strict';
import test from 'node:test';
import { buildWatchlistRows, sortWatchlistRows } from './watchlistTable.js';

// A tiny scan: three tickers with setups, one off-scan name lives only in the
// watchlist. `screenerData.chart_data` is keyed by ticker.
const scan = {
  chart_data: {
    GEV: { tier: 'A', score: 88, setup: 'LPS' },
    CRNX: { tier: 'S', score: 92, setup: 'BREAKOUT' },
    AGCO: { tier: 'A', score: 74, setup: 'REBOUND' },
  },
};

test('buildWatchlistRows joins the scan and flags in-scan vs off-scan', () => {
  const rows = buildWatchlistRows(new Set(['CRNX', 'ZZZZ']), scan);
  const crnx = rows.find((r) => r.ticker === 'CRNX');
  const zzzz = rows.find((r) => r.ticker === 'ZZZZ');

  assert.equal(crnx.in_scan, true);
  assert.equal(crnx.tier, 'S');
  assert.equal(crnx.score, 92);
  assert.equal(crnx.setup, 'BREAKOUT');
  assert.equal(crnx.data, scan.chart_data.CRNX);

  // Off-scan: explicit nulls + a null data handle, never undefined.
  assert.equal(zzzz.in_scan, false);
  assert.equal(zzzz.tier, null);
  assert.equal(zzzz.score, null);
  assert.equal(zzzz.setup, null);
  assert.equal(zzzz.data, null);
});

test('buildWatchlistRows tolerates an empty set and a null scan (before first scan)', () => {
  assert.deepEqual(buildWatchlistRows(new Set(), scan), []);
  const rows = buildWatchlistRows(new Set(['CRNX']), null);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].in_scan, false); // nothing scanned yet -> off-scan
  assert.equal(rows[0].score, null);
});

test('buildWatchlistRows coerces a NaN/missing score to null (fx-guard-safe)', () => {
  const rows = buildWatchlistRows(new Set(['BAD']), { chart_data: { BAD: { tier: 'B', score: 'nope', setup: 'LPS' } } });
  assert.equal(rows[0].score, null);
  assert.equal(rows[0].in_scan, true); // it IS in the scan, just with a bad number
});

test('default sort: tier S>A>B>C, score-desc within a tier, off-scan last', () => {
  const rows = buildWatchlistRows(new Set(['GEV', 'CRNX', 'AGCO', 'ZZZZ']), scan);
  const order = sortWatchlistRows(rows).map((r) => r.ticker);
  // CRNX (S) first; GEV (A/88) before AGCO (A/74); off-scan ZZZZ last.
  assert.deepEqual(order, ['CRNX', 'GEV', 'AGCO', 'ZZZZ']);
});

test('off-scan rows sink last regardless of sort direction', () => {
  const rows = buildWatchlistRows(new Set(['CRNX', 'ZZZZ', 'AAAA']), scan);
  const asc = sortWatchlistRows(rows, 'ticker', 'asc').map((r) => r.ticker);
  const desc = sortWatchlistRows(rows, 'ticker', 'desc').map((r) => r.ticker);
  assert.deepEqual(asc, ['CRNX', 'AAAA', 'ZZZZ']);   // scanned first, then off-scan alpha
  assert.deepEqual(desc, ['CRNX', 'ZZZZ', 'AAAA']);  // scanned still first; off-scan reversed
});

test('score column sorts numerically and is symmetric under direction', () => {
  const rows = buildWatchlistRows(new Set(['GEV', 'CRNX', 'AGCO']), scan);
  assert.deepEqual(sortWatchlistRows(rows, 'score', 'desc').map((r) => r.ticker), ['CRNX', 'GEV', 'AGCO']);
  assert.deepEqual(sortWatchlistRows(rows, 'score', 'asc').map((r) => r.ticker), ['AGCO', 'GEV', 'CRNX']);
});

test('tier ordinal beats alphabetical (S must rank above A)', () => {
  const rows = buildWatchlistRows(new Set(['GEV', 'CRNX']), scan); // A then S alphabetically
  assert.deepEqual(sortWatchlistRows(rows, 'tier', 'asc').map((r) => r.ticker), ['CRNX', 'GEV']);
});

test('sort is stable/deterministic — sorting twice yields the same order', () => {
  const rows = buildWatchlistRows(new Set(['GEV', 'CRNX', 'AGCO', 'ZZZZ', 'AAAA']), scan);
  const once = sortWatchlistRows(rows).map((r) => r.ticker);
  const twice = sortWatchlistRows(sortWatchlistRows(rows)).map((r) => r.ticker);
  assert.deepEqual(once, twice);
});

test('does not mutate the input array', () => {
  const rows = buildWatchlistRows(new Set(['AGCO', 'CRNX']), scan);
  const before = rows.map((r) => r.ticker);
  sortWatchlistRows(rows);
  assert.deepEqual(rows.map((r) => r.ticker), before);
});

test('setup column sorts alphabetically both ways; a null setup coalesces, never throws', () => {
  const rows = buildWatchlistRows(new Set(['GEV', 'CRNX', 'AGCO']), scan);
  assert.deepEqual(sortWatchlistRows(rows, 'setup', 'asc').map((r) => r.setup), ['BREAKOUT', 'LPS', 'REBOUND']);
  assert.deepEqual(sortWatchlistRows(rows, 'setup', 'desc').map((r) => r.setup), ['REBOUND', 'LPS', 'BREAKOUT']);
  // an in-scan row whose setup is null coalesces to '' (sorts first asc) rather than throwing
  const withNull = buildWatchlistRows(new Set(['CRNX', 'NUL']), {
    chart_data: { ...scan.chart_data, NUL: { tier: 'B', score: 50, setup: null } },
  });
  assert.deepEqual(sortWatchlistRows(withNull, 'setup', 'asc').map((r) => r.ticker), ['NUL', 'CRNX']);
});

test('an in-scan row with a non-finite score orders deterministically (null = lowest)', () => {
  const rows = buildWatchlistRows(new Set(['CRNX', 'BAD']), {
    chart_data: { CRNX: { tier: 'S', score: 92, setup: 'X' }, BAD: { tier: 'S', score: 'nope', setup: 'Y' } },
  });
  // both in-scan; score desc sinks the null-score row last, asc floats it first — pinned so a
  // flip of the -Infinity coalescing would fail here rather than silently reshuffle.
  assert.deepEqual(sortWatchlistRows(rows, 'score', 'desc').map((r) => r.ticker), ['CRNX', 'BAD']);
  assert.deepEqual(sortWatchlistRows(rows, 'score', 'asc').map((r) => r.ticker), ['BAD', 'CRNX']);
});

test('an in-scan row with a null tier ranks below D but still above off-scan rows', () => {
  const rows = buildWatchlistRows(new Set(['CRNX', 'NOTIER', 'OFF']), {
    chart_data: { CRNX: { tier: 'S', score: 90, setup: 'X' }, NOTIER: { tier: null, score: 60, setup: 'Y' } },
  });
  // CRNX (S, rank 0) → NOTIER (in-scan, null tier → rank 99) → OFF (off-scan, gated last).
  assert.deepEqual(sortWatchlistRows(rows, 'tier', 'asc').map((r) => r.ticker), ['CRNX', 'NOTIER', 'OFF']);
});
