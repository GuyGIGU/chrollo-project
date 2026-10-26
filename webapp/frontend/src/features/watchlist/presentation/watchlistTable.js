// Pure data helpers for the Watchlist InstrumentTable — no React, unit-tested in
// watchlistTable.test.js. Two transforms the whole panel leans on:
//   buildWatchlistRows — join one week's saved tickers with the current scan
//   sortWatchlistRows  — order the rows with a deterministic total order
// Off-scan tickers (starred or typed-in names not in today's scan) are the
// COMMON case, so they get explicit null fields + in_scan:false rather than a
// bare undefined.

import { finiteOrNull, numAsc } from '../../../shared/formatting/format.js';
import { TIER_LETTERS } from '../../../shared/presentation/wireVocabulary.js';
import { nearTriggerFrac, triggerDistanceFrac, triggerFired } from '../../../shared/setup/triggerProximity.js';

// Tier rank for sorting: S is best (0). DERIVED from the one ladder tuple
// (EC-33) - a hand-typed copy here would sink a newly first-class letter to 99.
export const TIER_RANK = Object.fromEntries(TIER_LETTERS.map((t, i) => [t, i]));
const tierRank = (tier) => (tier in TIER_RANK ? TIER_RANK[tier] : 99);

// The operator's sheet's "% Best Diff" columns, measured server-side
// (GET /watchlist/best-gains): `field` is the wire name, `days` the window after the add.
// This week's list shows the 30-day one (his weekly sheet); a past week shows all six.
export const BEST_GAIN_COLUMNS = [
  { key: 'best_since_add', field: 'since_add', days: null },
  ...[60, 30, 14, 7, 2].map((days) => ({ key: `best_${days}d`, field: `d${days}`, days })),
];
const BEST_GAIN_KEYS = BEST_GAIN_COLUMNS.map((column) => column.key);

// The ready mark's ladder: 0 watching, 1 ✓ (a valid LPS, take it on the
// trigger), 2 ✓✓ (top candidate this week). A click steps to the next.
export const READY_MARKS = ['', '✓', '✓✓'];
export const nextReady = (ready) => ((ready ?? 0) + 1) % READY_MARKS.length;

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

// His "leaders and top competitors": the sector's and the group's rank and the
// stock's place in its group, resolved by the scan (market_context.leadership).
function leadershipFacts(ticker, leadership, sectorName, industryName) {
  const stock = leadership?.stocks?.[ticker] || null;
  const industry = stock?.group || industryName || null;
  const group = industry ? leadership?.groups?.[industry] || null : null;
  const sector = group?.sector || sectorName || null;
  const sectorFacts = sector ? leadership?.sectors?.[sector] || null : null;
  return {
    sector, sector_rank: sectorFacts?.rank ?? null, sector_of: sectorFacts?.of ?? null,
    sector_leading: Boolean(sectorFacts?.leading),
    industry, group_rank: group?.rank ?? null, group_of: group?.of ?? null, group_leading: Boolean(group?.leading),
    rs: finiteOrNull(stock?.rs), place: stock?.place ?? null, place_of: stock?.of ?? null,
  };
}

// One normalized row per saved ticker. `data` is the raw chart_data entry
// (or null off-scan); the flat fields exist so the sort + simple cells never
// dereference undefined. Live columns divide the latest quote by the wire's
// bases: Change % by the close before the quote's day, % Diff since add by
// the high of the day before the add (his buy-stop basis, as the best gains).
// The trigger is tonight's scan's, else the one the save quoted (his plan).
export function buildWatchlistRows(tickers, screenerData, {
  records = [], prices = {}, gains = {}, leadership = null, weekStart = null, today = newYorkToday(),
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
    const scanTrigger = finiteOrNull(data?.trigger);
    const plan = { trigger: scanTrigger ?? finiteOrNull(record?.saved_trigger) };
    return {
      ticker,
      in_scan: data != null,
      side: record?.side || 'L',
      ready: record?.ready ?? 0,
      tier: data?.tier ?? null,
      // The 0-100 grade the tier letter is cut from: shown on the tier's hover.
      grade: finiteOrNull(data?.ta_grade),
      record,
      // The save's audit stamp (UTC), for display only: the week comes from the scan.
      added: record?.created_at || null,
      price,
      trigger: plan.trigger,
      trigger_saved: scanTrigger == null && plan.trigger != null,
      to_trigger: triggerDistanceFrac(plan, price),
      triggered: triggerFired(plan, price),
      near_trigger: nearTriggerFrac(plan, price) != null,
      change: ratio(price, finiteOrNull(gain?.prev_close)),
      diff_since_add: ratio(price, finiteOrNull(gain?.basis)),
      ...Object.fromEntries(BEST_GAIN_COLUMNS.map(({ key, field }) => [key, finiteOrNull(gain?.[field])])),
      gain_status: gain?.status ?? null,
      // The wire's distance is signed (-0.08 = 8% under the high); his sheet reads it as 8%.
      off_52w_high: dist52 == null ? null : -dist52,
      market_cap: finiteOrNull(data?.market_cap ?? record?.saved_market_cap),
      ...nextEarnings(data, record, weekStart, today),
      ...leadershipFacts(ticker, leadership, facts?.sector || record?.saved_sector,
        facts?.industry || record?.saved_industry),
      data,
    };
  });
}

// A Finviz chart page of these tickers, in this order, to open or share.
export const finvizLink = (tickers) => (tickers.length
  ? `https://finviz.com/screener.ashx?v=211&t=${tickers.map((t) => t.replace('.', '-')).join(',')}`
  : null);

const NUMERIC_KEYS = ['to_trigger', 'change', 'diff_since_add', ...BEST_GAIN_KEYS, 'off_52w_high', 'market_cap', 'rs'];
// Columns that sort on another field: the date, and the leadership ranks.
const SORT_FIELD = { earnings: 'earnings', sector: 'sector_rank', industry: 'group_rank' };
const sortValue = (row, key) => row[SORT_FIELD[key] || key];

// A deterministic total order. The default is his priority order: ✓✓ first,
// then ✓, then the rest; longs before shorts within a mark; newest add first.
// Scan-only sorts keep off-scan names last; a number sort keeps unmeasured
// names last both ways; a final ticker tie-break keeps the list steady under
// the watchlist poll.
export function sortWatchlistRows(rows, sortBy = 'ready', sortDir = 'desc') {
  const dir = sortDir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (['tier', 'grade'].includes(sortBy) && a.in_scan !== b.in_scan) return a.in_scan ? -1 : 1;
    if ([...NUMERIC_KEYS, 'added', ...Object.keys(SORT_FIELD)].includes(sortBy)) {
      const [va, vb] = [sortValue(a, sortBy), sortValue(b, sortBy)];
      if ((va == null) !== (vb == null)) return va == null ? 1 : -1;
    }
    const primary = keyCompare(a, b, sortBy) * dir;
    if (primary !== 0) return primary;
    if (sortBy === 'tier') {
      const byGrade = -numAsc(a.grade, b.grade);
      if (byGrade !== 0) return byGrade;
    }
    if (sortBy === 'ready') {
      const bySide = a.side.localeCompare(b.side);
      if (bySide !== 0) return bySide;
      const byAdded = String(b.added ?? '').localeCompare(String(a.added ?? ''));
      if (byAdded !== 0) return byAdded;
    }
    return a.ticker.localeCompare(b.ticker);
  });
}

function keyCompare(a, b, key) {
  switch (key) {
    case 'ready': return a.ready - b.ready;
    case 'tier': return tierRank(a.tier) - tierRank(b.tier);
    case 'grade': return numAsc(a.grade, b.grade);
    case 'ticker': return a.ticker.localeCompare(b.ticker);
    case 'side':
    case 'added':
    case 'earnings': return String(a[key] ?? '').localeCompare(String(b[key] ?? ''));
    case 'sector':
    case 'industry': return numAsc(sortValue(a, key), sortValue(b, key));
    default: return NUMERIC_KEYS.includes(key) ? numAsc(a[key], b[key]) : 0;
  }
}
