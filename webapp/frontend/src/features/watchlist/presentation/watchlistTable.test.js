import assert from 'node:assert/strict';
import test from 'node:test';
import { buildWatchlistRows, finvizLink, sortWatchlistRows } from './watchlistTable.js';

// A tiny scan: three tickers with setups, one off-scan name lives only in the
// watchlist. `screenerData.chart_data` is keyed by ticker.
const scan = {
  chart_data: {
    GEV: { tier: 'A', ta_grade: 88, setup: 'LPS' },
    CRNX: { tier: 'S', ta_grade: 92, setup: 'BREAKOUT' },
    AGCO: { tier: 'A', ta_grade: 74, setup: 'REBOUND' },
  },
};

test('the live columns divide the quote by the wire bases, and nothing is invented without one', () => {
  const records = [{ ticker: 'OLD', created_at: '2026-10-22T19:27:00', side: 'S', ready: 2,
    saved_market_cap: 500e6, saved_sector: 'Technology', saved_industry: 'Software' }];
  const gains = { OLD: { status: 'ok', basis: 10, prev_close: 12.5, dist_52w_high: -0.08, d30: 0.25 } };
  const [row] = buildWatchlistRows(['OLD'], scan, { records, prices: { OLD: 12 }, gains });
  assert.equal(row.in_scan, false);
  assert.equal(row.side, 'S');
  assert.ok(Math.abs(row.diff_since_add - 0.2) < 1e-12);   // 12 against the high before the add
  assert.ok(Math.abs(row.change - (12 / 12.5 - 1)) < 1e-12); // against the close before the quote's day
  assert.equal(row.off_52w_high, 0.08);                      // his sheet's "8%"
  assert.equal(row.best_30d, 0.25);
  assert.equal(row.industry, 'Software');
  assert.equal(row.added, '2026-10-22T19:27:00');
  const [unpriced] = buildWatchlistRows(['OLD'], scan, { records, gains });
  assert.equal(unpriced.change, null);
  assert.equal(unpriced.diff_since_add, null);
  const [unmeasured] = buildWatchlistRows(['OLD'], scan, { records, prices: { OLD: 12 } });
  assert.equal(unmeasured.diff_since_add, null);
  assert.equal(unmeasured.off_52w_high, null);
});

test('a row without a record reads as a long', () => {
  const [row] = buildWatchlistRows(['GEV'], scan);
  assert.equal(row.side, 'L');
});

test('default order: the newest add first', () => {
  const records = [
    { ticker: 'Z1', side: 'S', created_at: '2026-10-20T10:00:00' },
    { ticker: 'A0', side: 'L', created_at: '2026-10-23T10:00:00' },
    { ticker: 'M2', side: 'L', created_at: '2026-10-21T10:00:00' },
  ];
  const rows = buildWatchlistRows(records.map((r) => r.ticker), scan, { records });
  assert.deepEqual(sortWatchlistRows(rows).map((r) => r.ticker), ['A0', 'M2', 'Z1']);   // not A-Z either way
  assert.deepEqual(sortWatchlistRows(rows, 'side', 'asc').map((r) => r.ticker), ['A0', 'M2', 'Z1']);
  assert.deepEqual(sortWatchlistRows(rows, 'side', 'desc').map((r) => r.ticker), ['Z1', 'A0', 'M2']);
});

test('Added sort compares every saved ticker and keeps undated optimistic rows last', () => {
  const records = [{ ticker: 'OLD', created_at: '2026-10-22T09:00:00' }, { ticker: 'GEV', created_at: '2026-10-21T09:00:00' }];
  const rows = buildWatchlistRows(['GEV', 'OLD', 'NEW'], scan, { records });
  assert.deepEqual(sortWatchlistRows(rows, 'added', 'desc').map((row) => row.ticker), ['OLD', 'GEV', 'NEW']);
  assert.deepEqual(sortWatchlistRows(rows, 'added', 'asc').map((row) => row.ticker), ['GEV', 'OLD', 'NEW']);
});

test('buildWatchlistRows joins the scan and flags in-scan vs off-scan', () => {
  const rows = buildWatchlistRows(new Set(['CRNX', 'ZZZZ']), scan);
  const crnx = rows.find((r) => r.ticker === 'CRNX');
  const zzzz = rows.find((r) => r.ticker === 'ZZZZ');

  assert.equal(crnx.in_scan, true);
  assert.equal(crnx.data, scan.chart_data.CRNX);

  // Off-scan: explicit nulls + a null data handle, never undefined.
  assert.equal(zzzz.in_scan, false);
  assert.equal(zzzz.data, null);
});

test('buildWatchlistRows tolerates an empty set and a null scan (before first scan)', () => {
  assert.deepEqual(buildWatchlistRows(new Set(), scan), []);
  const rows = buildWatchlistRows(new Set(['CRNX']), null);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].in_scan, false); // nothing scanned yet -> off-scan
});

test('ticker sort compares every name alphabetically both ways', () => {
  const rows = buildWatchlistRows(new Set(['CRNX', 'ZZZZ', 'AAAA']), scan);
  assert.deepEqual(sortWatchlistRows(rows, 'ticker', 'asc').map((r) => r.ticker), ['AAAA', 'CRNX', 'ZZZZ']);
  assert.deepEqual(sortWatchlistRows(rows, 'ticker', 'desc').map((r) => r.ticker), ['ZZZZ', 'CRNX', 'AAAA']);
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

test('earnings: the next report from the scan or the save, flagged inside the shown week, gone once past', () => {
  const data = { chart_data: { GEV: { fund_sheet: { next_earnings: { day: '2026-10-29', confirmed: true } } } } };
  const records = [{ ticker: 'NEXT', saved_next_earnings: '2026-11-03', saved_earnings_confirmed: false },
    { ticker: 'PAST', saved_next_earnings: '2026-10-20' }];
  const options = { records, weekStart: '2026-10-26', today: '2026-10-26' };
  const [gev, next, past] = buildWatchlistRows(['GEV', 'NEXT', 'PAST'], data, options);
  assert.deepEqual([gev.earnings, gev.earnings_days, gev.earnings_confirmed, gev.earnings_this_week], ['2026-10-29', 3, true, true]);
  assert.deepEqual([next.earnings, next.earnings_days, next.earnings_confirmed, next.earnings_this_week], ['2026-11-03', 8, false, false]);
  assert.deepEqual([past.earnings, past.earnings_days], [null, null]); // a stale saved date is not a next report
  assert.equal(buildWatchlistRows(['GEV'], data, { ...options, weekStart: '2026-11-02' })[0].earnings_this_week, false);
  assert.deepEqual(sortWatchlistRows(buildWatchlistRows(['PAST', 'NEXT', 'GEV'], data, options), 'earnings', 'asc')
    .map((r) => r.ticker), ['GEV', 'NEXT', 'PAST']);
});

test('the Finviz link names the tickers in the order shown, class shares as Finviz spells them', () => {
  assert.equal(finvizLink(['NVDA', 'BRK.B', 'AAPL']), 'https://finviz.com/screener.ashx?v=211&t=NVDA,BRK-B,AAPL');
  assert.equal(finvizLink([]), null);
});

test('a number sort orders by the value and keeps unmeasured names last both ways', () => {
  const gains = { GEV: { since_add: 0.3, d30: 0.3 }, CRNX: { since_add: -0.05, d30: -0.05 }, AGCO: { since_add: 0.12, d30: 0.12 } };
  const rows = buildWatchlistRows(['GEV', 'CRNX', 'AGCO', 'OFF'], scan, { gains });
  for (const key of ['best_since_add', 'best_30d']) {
    assert.deepEqual(sortWatchlistRows(rows, key, 'desc').map((r) => r.ticker), ['GEV', 'AGCO', 'CRNX', 'OFF']);
    assert.deepEqual(sortWatchlistRows(rows, key, 'asc').map((r) => r.ticker), ['CRNX', 'AGCO', 'GEV', 'OFF']);
  }
  const priced = buildWatchlistRows(['GEV', 'OFF', 'CRNX'], scan, {
    prices: { GEV: 11, CRNX: 9, OFF: 10 }, gains: { GEV: { basis: 10 }, CRNX: { basis: 10 } } });
  assert.deepEqual(sortWatchlistRows(priced, 'diff_since_add', 'asc').map((r) => r.ticker), ['CRNX', 'GEV', 'OFF']);
});

test('sector: the scan’s fund, else the saved sector’s fund; industry from the scan or the save; both sort with blanks last', () => {
  const data = { chart_data: {
    NVDA: { sector_etf: 'XLK', fund_sheet: { snapshot: { industry: 'Semiconductors' } } },   // the fund alone
    XOM: { fund_sheet: { snapshot: { sector: 'Energy', industry: 'Oil & Gas Integrated' } } },
  } };
  const records = [{ ticker: 'HUM', saved_sector: 'Healthcare', saved_industry: 'Healthcare Plans' },
    { ticker: 'ODD', saved_sector: 'Shell Companies' }];
  const [nvda, xom, hum, odd, bare] = buildWatchlistRows(['NVDA', 'XOM', 'HUM', 'ODD', 'BARE'], data, { records });
  assert.deepEqual([nvda.sector_etf, nvda.sector, nvda.industry], ['XLK', null, 'Semiconductors']);
  assert.deepEqual([xom.sector_etf, xom.industry], ['XLE', 'Oil & Gas Integrated']);
  assert.deepEqual([hum.sector_etf, hum.sector, hum.industry], ['XLV', 'Healthcare', 'Healthcare Plans']);
  assert.deepEqual([odd.sector_etf, odd.sector], [null, 'Shell Companies']);   // no fund invented
  assert.deepEqual([bare.sector_etf, bare.industry], [null, null]);
  const rows = [nvda, xom, hum, odd, bare];
  assert.deepEqual(sortWatchlistRows(rows, 'sector', 'asc').map((r) => r.ticker), ['XOM', 'NVDA', 'HUM', 'BARE', 'ODD']);
  assert.deepEqual(sortWatchlistRows(rows, 'sector', 'desc').map((r) => r.ticker), ['HUM', 'NVDA', 'XOM', 'BARE', 'ODD']);
  assert.deepEqual(sortWatchlistRows(rows, 'industry', 'asc').map((r) => r.ticker), ['HUM', 'XOM', 'NVDA', 'BARE', 'ODD']);
});
