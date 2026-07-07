// Pure data helpers for the Watchlist InstrumentTable — no React, unit-tested in
// watchlistTable.test.js. Two transforms the whole panel leans on:
//   buildWatchlistRows — join the watchlist ticker Set with the current scan
//   sortWatchlistRows  — order the rows with a deterministic total order
// Off-scan tickers (starred names not in today's scan) are the COMMON case, so
// they get explicit null fields + in_scan:false rather than a bare undefined.

import { finiteOrNull } from './format.js';

// Tier rank for sorting: S is best (0). Unknown / off-scan tiers sink past D.
export const TIER_RANK = { S: 0, A: 1, B: 2, C: 3, D: 4 };
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
      score: finiteOrNull(data?.score),
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
      const byScore = compareDesc(a.score, b.score);
      if (byScore !== 0) return byScore;
    }
    return a.ticker.localeCompare(b.ticker);
  });
}

function keyCompare(a, b, key) {
  switch (key) {
    case 'tier': return tierRank(a.tier) - tierRank(b.tier);
    case 'score': return compareAsc(a.score, b.score);
    case 'setup': return String(a.setup ?? '').localeCompare(String(b.setup ?? ''));
    case 'ticker': return a.ticker.localeCompare(b.ticker);
    default: return 0;
  }
}

// Numeric compares that never return NaN — a NaN comparator leaves Array.sort
// order unspecified, which is exactly the flicker we are avoiding. Null coalesces
// to -Infinity so a missing value is ordered, not poisoned.
function compareAsc(a, b) {
  const na = a == null ? -Infinity : a;
  const nb = b == null ? -Infinity : b;
  return na < nb ? -1 : na > nb ? 1 : 0;
}
function compareDesc(a, b) {
  return -compareAsc(a, b);
}
