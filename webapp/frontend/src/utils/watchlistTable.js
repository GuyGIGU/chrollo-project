// Pure data helpers for the Watchlist InstrumentTable — no React, unit-tested in
// watchlistTable.test.js. Two transforms the whole panel leans on:
//   buildWatchlistRows — join the watchlist ticker Set with the current scan
//   sortWatchlistRows  — order the rows with a deterministic total order
// Off-scan tickers (starred names not in today's scan) are the COMMON case, so
// they get explicit null fields + in_scan:false rather than a bare undefined.

import { finiteOrNull, numAsc } from './format.js';
import { TIER_LETTERS } from '../components/wireVocabulary.js';

// Tier rank for sorting: S is best (0). DERIVED from the one ladder tuple
// (EC-33) - a hand-typed copy here would sink a newly first-class letter to 99.
export const TIER_RANK = Object.fromEntries(TIER_LETTERS.map((t, i) => [t, i]));
const tierRank = (tier) => (tier in TIER_RANK ? TIER_RANK[tier] : 99);

// One normalized row per watchlisted ticker. `data` is the raw chart_data entry
// (or null off-scan); the flat fields exist so the sort + simple cells never
// dereference undefined.
export function buildWatchlistRows(watchlist, screenerData) {
  const chartData = screenerData?.chart_data || {};
  return Array.from(watchlist || []).map((ticker) => {
    const data = chartData[ticker] || null;
    return {
      ticker,
      in_scan: data != null,
      tier: data?.tier ?? null,
      // The 0-100 grade (the tier's own source). The legacy raw score retired
      // from display 2026-08-22; the scales never coalesce, so a pre-grade row
      // is null here and renders as the dash.
      grade: finiteOrNull(data?.ta_grade),
      setup: data?.setup ?? null,
      data,
    };
  });
}

// A deterministic total order. Off-scan rows ALWAYS sink to the bottom whatever
// the direction (they have no tier/score to rank), so the live setups the trader
// opened the panel for stay on top; scanned rows order by the active column; the
// tier default breaks ties on score (desc) so the best setups float up, and
// every path ends on the ticker so nothing wobbles under the watchlist poll.
export function sortWatchlistRows(rows, sortBy = 'tier', sortDir = 'asc') {
  const dir = sortDir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (a.in_scan !== b.in_scan) return a.in_scan ? -1 : 1;
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
    case 'setup': return String(a.setup ?? '').localeCompare(String(b.setup ?? ''));
    case 'ticker': return a.ticker.localeCompare(b.ticker);
    default: return 0;
  }
}

// Descending numeric compare over the shared NaN-free numAsc (format.js).
const compareDesc = (a, b) => -numAsc(a, b);
