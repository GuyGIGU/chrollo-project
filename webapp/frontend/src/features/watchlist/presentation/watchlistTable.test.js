import assert from 'node:assert/strict';
import test from 'node:test';
import { buildWatchlistRows, sortWatchlistRows } from './watchlistTable.js';

// A tiny scan: three tickers with setups, one off-scan name lives only in the
// watchlist. `screenerData.chart_data` is keyed by ticker.
const scan = {
  chart_data: {
    GEV: { tier: 'A', ta_grade: 88, setup: 'LPS' },
    CRNX: { tier: 'S', ta_grade: 92, setup: 'BREAKOUT' },
    AGCO: { tier: 'A', ta_grade: 74, setup: 'REBOUND' },
  },
};

test('dated rows keep the saved basis and off-scan metadata without inventing quotes', () => {
  const records = [{ ticker: 'OLD', save_date: '2026-10-22', saved_setup: 'VCP', saved_price: 10,
    saved_market_cap: 500e6, saved_sector: 'Technology', saved_industry: 'Software' }];
  const [row] = buildWatchlistRows(new Set(['OLD']), scan, { records, prices: { OLD: 12 } });
  assert.equal(row.in_scan, false);
  assert.equal(row.saved_price, 10);
  assert.equal(row.vs_saved, 0.2);
  assert.equal(row.industry, 'Software');
  assert.equal(row.added, '2026-10-22');
  const [unpriced] = buildWatchlistRows(new Set(['OLD']), scan, { records });
  assert.equal(unpriced.price, null);
  assert.equal(unpriced.vs_saved, null);
  const [unbound] = buildWatchlistRows(new Set(['GEV']), scan, { prices: { GEV: 99 } });
  assert.equal(unbound.saved_price, null);
  assert.equal(unbound.vs_saved, null);
});

test('Added sort compares every saved ticker and keeps undated optimistic rows last', () => {
  const records = [{ ticker: 'OLD', save_date: '2026-10-22' }, { ticker: 'GEV', save_date: '2026-10-21' }];
  const rows = buildWatchlistRows(new Set(['GEV', 'OLD', 'NEW']), scan, { records });
  assert.deepEqual(sortWatchlistRows(rows, 'added', 'desc').map((row) => row.ticker), ['OLD', 'GEV', 'NEW']);
  assert.deepEqual(sortWatchlistRows(rows, 'added', 'asc').map((row) => row.ticker), ['GEV', 'OLD', 'NEW']);
});

test('setup sorting follows the saved setup displayed in the ledger', () => {
  const records = [{ ticker: 'CRNX', saved_setup: 'Z' }, { ticker: 'GEV', saved_setup: 'A' }];
  const rows = buildWatchlistRows(new Set(['CRNX', 'GEV']), scan, { records });
  assert.deepEqual(sortWatchlistRows(rows, 'setup', 'asc').map((row) => row.ticker), ['GEV', 'CRNX']);
});

test('buildWatchlistRows joins the scan and flags in-scan vs off-scan', () => {
  const rows = buildWatchlistRows(new Set(['CRNX', 'ZZZZ']), scan);
  const crnx = rows.find((r) => r.ticker === 'CRNX');
  const zzzz = rows.find((r) => r.ticker === 'ZZZZ');

  assert.equal(crnx.in_scan, true);
  assert.equal(crnx.tier, 'S');
  assert.equal(crnx.grade, 92);
  assert.equal(crnx.setup, 'BREAKOUT');
  assert.equal(crnx.data, scan.chart_data.CRNX);

  // Off-scan: explicit nulls + a null data handle, never undefined.
  assert.equal(zzzz.in_scan, false);
  assert.equal(zzzz.tier, null);
  assert.equal(zzzz.grade, null);
  assert.equal(zzzz.setup, null);
  assert.equal(zzzz.data, null);
});

test('buildWatchlistRows tolerates an empty set and a null scan (before first scan)', () => {
  assert.deepEqual(buildWatchlistRows(new Set(), scan), []);
  const rows = buildWatchlistRows(new Set(['CRNX']), null);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].in_scan, false); // nothing scanned yet -> off-scan
  assert.equal(rows[0].grade, null);
});

test('buildWatchlistRows coerces a NaN/missing grade to null (fx-guard-safe)', () => {
  const rows = buildWatchlistRows(new Set(['BAD']), { chart_data: { BAD: { tier: 'B', ta_grade: 'nope', setup: 'LPS' } } });
  assert.equal(rows[0].grade, null);
  assert.equal(rows[0].in_scan, true); // it IS in the scan, just with a bad number
});

test('default sort: tier S>A>B>C, grade-desc within a tier, off-scan last', () => {
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

test('grade column sorts numerically and is symmetric under direction', () => {
  const rows = buildWatchlistRows(new Set(['GEV', 'CRNX', 'AGCO']), scan);
  assert.deepEqual(sortWatchlistRows(rows, 'grade', 'desc').map((r) => r.ticker), ['CRNX', 'GEV', 'AGCO']);
  assert.deepEqual(sortWatchlistRows(rows, 'grade', 'asc').map((r) => r.ticker), ['AGCO', 'GEV', 'CRNX']);
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
    chart_data: { ...scan.chart_data, NUL: { tier: 'B', ta_grade: 50, setup: null } },
  });
  assert.deepEqual(sortWatchlistRows(withNull, 'setup', 'asc').map((r) => r.ticker), ['NUL', 'CRNX']);
});

test('an in-scan row with a non-finite grade orders deterministically (null = lowest)', () => {
  const rows = buildWatchlistRows(new Set(['CRNX', 'BAD']), {
    chart_data: { CRNX: { tier: 'S', ta_grade: 92, setup: 'X' }, BAD: { tier: 'S', ta_grade: 'nope', setup: 'Y' } },
  });
  // both in-scan; score desc sinks the null-grade row last, asc floats it first — pinned so a
  // flip of the -Infinity coalescing would fail here rather than silently reshuffle.
  assert.deepEqual(sortWatchlistRows(rows, 'grade', 'desc').map((r) => r.ticker), ['CRNX', 'BAD']);
  assert.deepEqual(sortWatchlistRows(rows, 'grade', 'asc').map((r) => r.ticker), ['BAD', 'CRNX']);
});

test('an in-scan row with a null tier ranks below D but still above off-scan rows', () => {
  const rows = buildWatchlistRows(new Set(['CRNX', 'NOTIER', 'OFF']), {
    chart_data: { CRNX: { tier: 'S', ta_grade: 90, setup: 'X' }, NOTIER: { tier: null, ta_grade: 60, setup: 'Y' } },
  });
  // CRNX (S, rank 0) → NOTIER (in-scan, null tier → rank 99) → OFF (off-scan, gated last).
  assert.deepEqual(sortWatchlistRows(rows, 'tier', 'asc').map((r) => r.ticker), ['CRNX', 'NOTIER', 'OFF']);
});

test('rows carry the six best-gain columns from the wire, and a name without an answer stays null', () => {
  const gains = {
    GEV: { status: 'ok', since_add: 0.3, d60: 0.3, d30: 0.25, d14: 0.1, d7: 0.05, d2: -0.01 },
    OFF: { status: 'no_pin', since_add: null, d60: null, d30: null, d14: null, d7: null, d2: null },
  };
  const [gev, off, crnx] = buildWatchlistRows(['GEV', 'OFF', 'CRNX'], scan, { gains });
  assert.deepEqual([gev.best_since_add, gev.best_60d, gev.best_30d, gev.best_14d, gev.best_7d, gev.best_2d],
    [0.3, 0.3, 0.25, 0.1, 0.05, -0.01]);
  assert.equal(gev.gain_status, 'ok');
  assert.equal(off.best_since_add, null);
  assert.equal(off.gain_status, 'no_pin');
  assert.equal(crnx.best_7d, null);          // not in the answer yet: a dash, never a zero
  assert.equal(crnx.gain_status, null);
});

test('a best-gain sort orders by the gain and keeps unmeasured names last both ways', () => {
  const gains = { GEV: { since_add: 0.3 }, CRNX: { since_add: -0.05 }, AGCO: { since_add: 0.12 } };
  const rows = buildWatchlistRows(['GEV', 'CRNX', 'AGCO', 'OFF'], scan, { gains });
  assert.deepEqual(sortWatchlistRows(rows, 'best_since_add', 'desc').map((r) => r.ticker), ['GEV', 'AGCO', 'CRNX', 'OFF']);
  assert.deepEqual(sortWatchlistRows(rows, 'best_since_add', 'asc').map((r) => r.ticker), ['CRNX', 'AGCO', 'GEV', 'OFF']);
});
