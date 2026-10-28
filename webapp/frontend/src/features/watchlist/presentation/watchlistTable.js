// Pure data helpers for the Watchlist InstrumentTable — no React, unit-tested in
// watchlistTable.test.js. Two transforms the whole panel leans on:
//   buildWatchlistRows — join one week's saved tickers with the current scan
//   sortWatchlistRows  — order the rows with a deterministic total order
// Off-scan tickers (starred or typed-in names not in today's scan) are the
// COMMON case, so they get explicit null fields + in_scan:false rather than a
// bare undefined.

import { finiteOrNull, numAsc } from '../../../shared/formatting/format.js';

// The operator's sheet's "% Best Diff" columns, measured server-side
// (GET /watchlist/best-gains): `field` is the wire name, `days` the window after the add.
// The list shows the 30-day one (his weekly sheet); the others ride its hover.
export const BEST_GAIN_COLUMNS = [
  { key: 'best_since_add', field: 'since_add', days: null },
  ...[60, 30, 14, 7, 2].map((days) => ({ key: `best_${days}d`, field: `d${days}`, days })),
];
const BEST_GAIN_KEYS = BEST_GAIN_COLUMNS.map((column) => column.key);

// His sheet names a sector by its SPDR fund. The scan sends the fund for the
// names it read; a name off the scan only has its saved sector, labelled here.
const SECTOR_ETFS = {
  Technology: 'XLK', Healthcare: 'XLV', 'Financial Services': 'XLF', 'Consumer Cyclical': 'XLY',
  'Consumer Defensive': 'XLP', 'Communication Services': 'XLC', Industrials: 'XLI', Energy: 'XLE',
  Utilities: 'XLU', 'Real Estate': 'XLRE', 'Basic Materials': 'XLB',
};

const ratio = (price, base) => (price != null && base > 0 ? price / base - 1 : null);

// Calendar days, on the ISO dates themselves (no clock, no time zone).
const dayNumber = (iso) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
  return match ? Date.UTC(+match[1], +match[2] - 1, +match[3]) / 86400000 : null;
};
// Today on the market's calendar.
const newYorkToday = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(new Date());

// The next report: tonight's scan's, else the one the save quoted while it is
// still ahead. `this_week` = it falls in the shown week (Monday to Friday).
function nextEarnings(data, record, weekStart, today) {
  const scanned = data?.fund_sheet?.next_earnings;
  const day = scanned?.day || record?.saved_next_earnings || null;
  const confirmed = scanned?.day ? scanned.confirmed ?? null : record?.saved_earnings_confirmed ?? null;
  const days = dayNumber(day) == null || dayNumber(today) == null ? null : dayNumber(day) - dayNumber(today);
  if (days == null || days < 0) {
    return { earnings: null, earnings_days: null, earnings_confirmed: null, earnings_this_week: false };
  }
  const monday = dayNumber(weekStart);
  return { earnings: day, earnings_days: days, earnings_confirmed: confirmed,
    earnings_this_week: monday != null && dayNumber(day) >= monday && dayNumber(day) <= monday + 4 };
}

// One normalized row per saved ticker. `data` is the raw chart_data entry
// (or null off-scan); the flat fields exist so the sort + simple cells never
// dereference undefined. Live columns divide the latest quote by the wire's
// bases: Change % by the close before the quote's day, % Diff since add by
// the high of the day before the add (his buy-stop basis, as the best gains).
export function buildWatchlistRows(tickers, screenerData, {
  records = [], prices = {}, gains = {}, weekStart = null, today = newYorkToday(),
} = {}) {
  const chartData = screenerData?.chart_data || {};
  const byTicker = new Map(records.map((record) => [record.ticker, record]));
  return Array.from(tickers || []).map((ticker) => {
    const data = chartData[ticker] || null;
    const record = byTicker.get(ticker) || null;
    const price = finiteOrNull(prices[ticker]);
    const facts = data?.fund_sheet?.snapshot;
    const gain = gains[ticker] || null;
    const dist52 = finiteOrNull(gain?.dist_52w_high);
    const sector = facts?.sector || record?.saved_sector || null;
    return {
      ticker,
      in_scan: data != null,
      side: record?.side || 'L',
      record,
      // The save's audit stamp (UTC), for display only: the week comes from the scan.
      added: record?.created_at || null,
      price,
      change: ratio(price, finiteOrNull(gain?.prev_close)),
      diff_since_add: ratio(price, finiteOrNull(gain?.basis)),
      ...Object.fromEntries(BEST_GAIN_COLUMNS.map(({ key, field }) => [key, finiteOrNull(gain?.[field])])),
      gain_status: gain?.status ?? null,
      // The wire's distance is signed (-0.08 = 8% under the high); his sheet reads it as 8%.
      off_52w_high: dist52 == null ? null : -dist52,
      market_cap: finiteOrNull(data?.market_cap ?? record?.saved_market_cap),
      ...nextEarnings(data, record, weekStart, today),
      sector,
      sector_etf: data?.sector_etf || SECTOR_ETFS[sector] || null,
      industry: facts?.industry || record?.saved_industry || null,
      data,
    };
  });
}

// A Finviz chart page of these tickers, in this order, to open or share.
export const finvizLink = (tickers) => (tickers.length
  ? `https://finviz.com/screener.ashx?v=211&t=${tickers.map((t) => t.replace('.', '-')).join(',')}`
  : null);

const NUMERIC_KEYS = ['change', 'diff_since_add', ...BEST_GAIN_KEYS, 'off_52w_high', 'market_cap'];
// Text columns; the sector sorts by its fund, as shown.
const TEXT_FIELD = { added: 'added', earnings: 'earnings', sector: 'sector_etf', industry: 'industry' };

// A deterministic total order. The default is the newest add first. A number
// or text sort keeps the names without a value last both ways; a final ticker
// tie-break keeps the list steady under the watchlist poll.
export function sortWatchlistRows(rows, sortBy = 'added', sortDir = 'desc') {
  const dir = sortDir === 'asc' ? 1 : -1;
  const field = TEXT_FIELD[sortBy] || sortBy;
  return [...rows].sort((a, b) => {
    if (NUMERIC_KEYS.includes(sortBy) || sortBy in TEXT_FIELD) {
      const [va, vb] = [a[field], b[field]];
      if ((va == null) !== (vb == null)) return va == null ? 1 : -1;
    }
    const primary = keyCompare(a, b, sortBy, field) * dir;
    if (primary !== 0) return primary;
    return a.ticker.localeCompare(b.ticker);
  });
}

function keyCompare(a, b, key, field) {
  if (NUMERIC_KEYS.includes(key)) return numAsc(a[key], b[key]);
  if (key === 'ticker' || key === 'side' || key in TEXT_FIELD) return String(a[field] ?? '').localeCompare(String(b[field] ?? ''));
  return 0;
}
