// Pure data helpers for the Watchlist InstrumentTable — no React, unit-tested in
// watchlistTable.test.js. Two transforms the whole panel leans on:
//   buildWatchlistRows — join the watchlist ticker Set with the current scan
//   sortWatchlistRows  — order the rows with a deterministic total order
// Off-scan tickers (starred names not in today's scan) are the COMMON case, so
// they get explicit null fields + in_scan:false rather than a bare undefined.

import { finiteOrNull, numAsc } from '../../../shared/formatting/format.js';
import { TIER_LETTERS } from '../../../shared/presentation/wireVocabulary.js';

// Tier rank for sorting: S is best (0). DERIVED from the one ladder tuple
// (EC-33) - a hand-typed copy here would sink a newly first-class letter to 99.
export const TIER_RANK = Object.fromEntries(TIER_LETTERS.map((t, i) => [t, i]));
const tierRank = (tier) => (tier in TIER_RANK ? TIER_RANK[tier] : 99);

// The operator's sheet's "% Best Diff" columns, measured server-side
// (GET /watchlist/best-gains): `field` is the wire name, `days` the window after the add.
export const BEST_GAIN_COLUMNS = [
  { key: 'best_since_add', field: 'since_add', days: null },
  ...[60, 30, 14, 7, 2].map((days) => ({ key: `best_${days}d`, field: `d${days}`, days })),
];
const BEST_GAIN_KEYS = BEST_GAIN_COLUMNS.map((column) => column.key);

// One normalized row per watchlisted ticker. `data` is the raw chart_data entry
// (or null off-scan); the flat fields exist so the sort + simple cells never
// dereference undefined.
export function buildWatchlistRows(watchlist, screenerData, { records = [], prices = {}, gains = {} } = {}) {
  const chartData = screenerData?.chart_data || {};
  const byTicker = new Map(records.map((record) => [record.ticker, record]));
  return Array.from(watchlist || []).map((ticker) => {
    const data = chartData[ticker] || null;
    const record = byTicker.get(ticker) || null;
    const savedPrice = finiteOrNull(record?.saved_price);
    const price = finiteOrNull(prices[ticker]);
    const facts = data?.fund_sheet?.snapshot;
    const gain = gains[ticker] || null;
    return {
      ticker,
      in_scan: data != null,
      tier: data?.tier ?? null,
      // The 0-100 grade (the tier's own source). The legacy raw score retired
      // from display 2026-08-22; the scales never coalesce, so a pre-grade row
      // is null here and renders as the dash.
      grade: finiteOrNull(data?.ta_grade),
      setup: data?.setup ?? null,
      record,
      added: record?.save_date || record?.created_at?.slice(0, 10) || null,
      saved_setup: record?.saved_setup ?? null,
      saved_price: savedPrice,
      price,
      // Price comparison only: never substitute a current scan price for the saved basis.
      vs_saved: savedPrice > 0 && price != null ? (price - savedPrice) / savedPrice : null,
      ...Object.fromEntries(BEST_GAIN_COLUMNS.map(({ key, field }) => [key, finiteOrNull(gain?.[field])])),
      gain_status: gain?.status ?? null,
      rs_rating: finiteOrNull(data?.rs_rating),
      market_cap: finiteOrNull(data?.market_cap ?? record?.saved_market_cap),
      sector: facts?.sector || record?.saved_sector || null,
      industry: facts?.industry || record?.saved_industry || null,
      data,
    };
  });
}

// A deterministic total order. Scan-specific sorts keep off-scan names last;
// date, quote and company-data sorts compare the whole saved list. The
// tier default breaks ties on score (desc) so the best setups float up, and
// final ticker tie-break keeps the list steady under the watchlist poll.
export function sortWatchlistRows(rows, sortBy = 'tier', sortDir = 'asc') {
  const dir = sortDir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    // Scan-specific sorts retain their established off-scan-last behavior.
    // Added date and quote/fundamental sorts compare the whole saved list.
    if (['tier', 'grade', 'setup', 'ticker'].includes(sortBy) && a.in_scan !== b.in_scan) return a.in_scan ? -1 : 1;
    if (['added', 'price', 'saved_price', 'vs_saved', ...BEST_GAIN_KEYS, 'rs_rating', 'market_cap'].includes(sortBy)) {
      if ((a[sortBy] == null) !== (b[sortBy] == null)) return a[sortBy] == null ? 1 : -1;
    }
    const primary = keyCompare(a, b, sortBy) * dir;
    if (primary !== 0) return primary;
    if (sortBy === 'tier') {
      const byGrade = compareDesc(a.grade, b.grade);
      if (byGrade !== 0) return byGrade;
    }
    return a.ticker.localeCompare(b.ticker);
  });
}

function keyCompare(a, b, key) {
  switch (key) {
    case 'tier': return tierRank(a.tier) - tierRank(b.tier);
    case 'grade': return numAsc(a.grade, b.grade);
    case 'setup': return String(a.saved_setup || a.setup || '').localeCompare(String(b.saved_setup || b.setup || ''));
    case 'ticker': return a.ticker.localeCompare(b.ticker);
    case 'added':
    case 'sector':
    case 'industry': return String(a[key] ?? '').localeCompare(String(b[key] ?? ''));
    case 'price':
    case 'saved_price':
    case 'vs_saved':
    case 'rs_rating':
    case 'market_cap': return numAsc(a[key], b[key]);
    default: return BEST_GAIN_KEYS.includes(key) ? numAsc(a[key], b[key]) : 0;
  }
}

// Descending numeric compare over the shared NaN-free numAsc (format.js).
const compareDesc = (a, b) => -numAsc(a, b);
