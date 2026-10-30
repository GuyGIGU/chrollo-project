// Pure data helpers for the calibration InstrumentTables — no React, no
// fetch, unit-tested in calibrationTables.test.js. Same shape as the watchlist's
// watchlistTable.js: a build* transform that normalizes raw rows and a sort*
// transform with a deterministic, NaN-free total order (a NaN comparator leaves
// Array.sort unspecified — the flicker we refuse).
//
// THREE grains, named so they can never collapse into each other (Task 4):
//   mark     — one saved row: (ticker, as_of, label)
//   setup    — one (ticker, as_of): the frozen snapshot the operator marked and
//              the unit the right rail edits + tests; two setups on one symbol
//              are two as-of sessions and MUST stay two rows
//   coverage — one ticker, aggregated over ALL its marks
// Reusing "coverage" for a rail row is exactly the ambiguity that would let
// "two setups on one symbol" silently become one entry — hence the split.

// NaN-free comparators (numAsc/strAsc) live in format.js — one shared home the
// watchlist and this module both import, so the missing-value ordering can
// never drift between the two ledgers (EC-3).
import { EMPTY, finiteOrNull, numAsc, strAsc } from '../../../shared/formatting/format.js';

// ============================================================================
// COVERAGE — "what have I calibrated": one row per ticker, aggregated over ALL
// marks (the whole population, not one ticker's slice). boxes vs negatives is
// the calibration analog of the watchlist's tier/score — it says at a glance
// how much real ground truth a ticker carries.
// ============================================================================
export function buildCoverageRows(marks) {
  const byTicker = new Map();
  for (const m of marks || []) {
    const row = byTicker.get(m.ticker)
      ?? { ticker: m.ticker, count: 0, boxes: 0, negatives: 0, latestAsOf: m.as_of_date, latest: m };
    row.count += 1;
    if (m.verdict === 'box') row.boxes += 1;
    else row.negatives += 1;
    // ISO 'YYYY-MM-DD' string compare === chronological; keep the newest session
    // AND the mark itself (its frame + geometry feed the thumbnail/dot below).
    if (m.as_of_date > row.latestAsOf) { row.latestAsOf = m.as_of_date; row.latest = m; }
    byTicker.set(m.ticker, row);
  }
  // Project each ticker's newest mark into the flat, render-safe fields the
  // coverage table's meter/dot/thumbnail read. `latest` (a raw mark) is dropped
  // so a cell never dereferences a MarkOut. "Complete" = the operator fully
  // specified it: at least one event AND a knowable-from session.
  return [...byTicker.values()].map(({ latest, ...row }) => ({
    ...row,
    latestComplete: (Array.isArray(latest.events) ? latest.events.length : 0) > 0
      && Boolean(latest.knowable_from_date),
    latestDigest: latest.frame_digest ?? null,
    latestIsBox: latest.verdict === 'box',
    latestResistance: finiteOrNull(latest.resistance),
    latestSupport: finiteOrNull(latest.support),
    latestBoxStart: latest.box_start_date ?? null,
    latestBoxEnd: latest.box_end_date ?? null,
  }));
}

// Default: newest activity first (latestAsOf desc) — the ticker just worked
// floats up when resuming a sitting. Every path ends on the ticker so nothing
// wobbles under the summary refresh that follows each save.
export function sortCoverageRows(rows, sortBy = 'latestAsOf', sortDir = 'desc') {
  const dir = sortDir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const primary = coverageCompare(a, b, sortBy) * dir;
    if (primary !== 0) return primary;
    return a.ticker.localeCompare(b.ticker);
  });
}

function coverageCompare(a, b, key) {
  switch (key) {
    case 'count': return numAsc(a.count, b.count);
    case 'boxes': return numAsc(a.boxes, b.boxes);
    case 'latestAsOf': return strAsc(a.latestAsOf, b.latestAsOf);
    case 'ticker': return strAsc(a.ticker, b.ticker);
    default: return 0;
  }
}

// ============================================================================
// MARKS — the loaded ticker's ledger. Flat, sort-safe fields so a cell or the
// comparator never dereferences a raw MarkOut; `raw` carries the full row for
// the edit/delete handlers. Negatives have no geometry, so R/S/span read null.
// ============================================================================
export function buildMarkRows(marks) {
  return (marks || []).map((m) => ({
    id: m.id,
    asOf: m.as_of_date,
    label: m.label || '',
    verdict: m.verdict,
    isBox: m.verdict === 'box',
    resistance: finiteOrNull(m.resistance),
    support: finiteOrNull(m.support),
    boxStart: m.box_start_date ?? null,
    boxEnd: m.box_end_date ?? null,
    events: Array.isArray(m.events) ? m.events.length : 0,
    revision: finiteOrNull(m.revision) ?? 0,
    // Frame identity, flat — the thumbnail keys its feed on it and the
    // fired chip keys its cache on (id, revision). Only on row.raw before.
    frameDigest: m.frame_digest ?? null,
    raw: m,
  }));
}

// Default: newest session first (asOf desc). Ties break on id asc so the order
// is total and stable across the refresh that follows every write.
export function sortMarkRows(rows, sortBy = 'asOf', sortDir = 'desc') {
  const dir = sortDir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const primary = markCompare(a, b, sortBy) * dir;
    if (primary !== 0) return primary;
    return a.id - b.id;
  });
}

function markCompare(a, b, key) {
  switch (key) {
    case 'id': return numAsc(a.id, b.id);
    case 'asOf': return strAsc(a.asOf, b.asOf);
    case 'label': return strAsc(a.label, b.label);
    case 'verdict': return strAsc(a.verdict, b.verdict);
    case 'resistance': return numAsc(a.resistance, b.resistance);
    case 'support': return numAsc(a.support, b.support);
    case 'events': return numAsc(a.events, b.events);
    case 'revision': return numAsc(a.revision, b.revision);
    default: return 0;
  }
}

// ============================================================================
// SETUP — one row per (ticker, as_of): the frozen snapshot the operator marked,
// and the unit the right rail edits and tests against the engine. The common
// case is exactly one box mark per session; when a session carries several marks
// (an extra label, a negative) the BOX is the representative the row's
// geometry / thumbnail / grade read, and every raw mark rides along under
// `allMarks` for the per-setup cascade delete. Row fields answer the operator's
// priority order (Box/R/S → LPS → Trigger) at a glance.
// ============================================================================
export function buildSetupRows(marks) {
  const bySetup = new Map();
  for (const m of marks || []) {
    const key = `${m.ticker}|${m.as_of_date}`;
    const group = bySetup.get(key)
      ?? { key, ticker: m.ticker, asOf: m.as_of_date, marks: [] };
    group.marks.push(m);
    bySetup.set(key, group);
  }
  return [...bySetup.values()].map(({ key, ticker, asOf, marks: group }) => {
    const rep = representativeMark(group);
    const events = Array.isArray(rep.events) ? rep.events : [];
    return {
      key,
      ticker,
      asOf,
      count: group.length,
      label: rep.label || '',
      verdict: rep.verdict,
      isBox: rep.verdict === 'box',
      resistance: finiteOrNull(rep.resistance),
      support: finiteOrNull(rep.support),
      boxStart: rep.box_start_date ?? null,
      boxEnd: rep.box_end_date ?? null,
      events: events.length,
      // The LPS + Trigger the engine test grades against — surfaced flat so the
      // rail never re-reads a raw mark's events inside JSX.
      hasLps: events.some((e) => e.event_type === 'lps'),
      triggerDate: rep.trigger_date ?? null,
      triggerPrice: finiteOrNull(rep.trigger_price),
      hasTrigger: rep.trigger_date != null,
      revision: finiteOrNull(rep.revision) ?? 0,
      frameDigest: rep.frame_digest ?? null,
      // The operator's per-setup annotation (why the engine might miss / what
      // would make it hit) — surfaced flat so the rail shows a ✎ hint on hover.
      note: rep.note || null,
      raw: rep,        // the representative box — load / edit / grade key
      allMarks: group, // every raw mark at this session — cascade delete
    };
  });
}

// The setup's ground truth is its box: prefer a box over a negative, then the
// latest revision, then the empty (primary) label — a deterministic pick so the
// row is stable regardless of the marks' arrival order.
function representativeMark(group) {
  return [...group].sort((a, b) => {
    const box = (a.verdict === 'box' ? 0 : 1) - (b.verdict === 'box' ? 0 : 1);
    if (box !== 0) return box;
    const rev = numAsc(finiteOrNull(b.revision) ?? 0, finiteOrNull(a.revision) ?? 0);
    if (rev !== 0) return rev;
    return strAsc(a.label || '', b.label || '');
  })[0];
}

// Default: grouped by ticker (A→Z), newest setup first within a ticker — the
// rail reads like a watchlist. Every path ends on (ticker, newest-session) so
// the order is total and never wobbles under the post-save summary refresh.
export function sortSetupRows(rows, sortBy = 'ticker', sortDir = 'asc') {
  const dir = sortDir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const primary = setupCompare(a, b, sortBy) * dir;
    if (primary !== 0) return primary;
    if (a.ticker !== b.ticker) return a.ticker.localeCompare(b.ticker);
    return strAsc(b.asOf, a.asOf); // newest session first within a ticker
  });
}

function setupCompare(a, b, key) {
  switch (key) {
    case 'ticker': return strAsc(a.ticker, b.ticker);
    case 'asOf': return strAsc(a.asOf, b.asOf);
    case 'verdict': return strAsc(a.verdict, b.verdict);
    case 'resistance': return numAsc(a.resistance, b.resistance);
    case 'support': return numAsc(a.support, b.support);
    case 'events': return numAsc(a.events, b.events);
    case 'revision': return numAsc(a.revision, b.revision);
    case 'count': return numAsc(a.count, b.count);
    default: return 0;
  }
}

// ============================================================================
// RAIL SEARCH + PAGES — operator ask 2026-10-02: "add a way to search the
// tickers and split the list into pages of 20 setups. since we already got 40
// and I'm planning to add more". The rail runs filter -> sort -> page; each
// step is pure and never mutates its input.
// ============================================================================
export const SETUPS_PER_PAGE = 20;

// Case-insensitive substring on the ticker OR the label, so a query finds a
// symbol and a named setup alike. Two setups on one ticker both match — the
// filter keeps rows, never collapses them. An empty query is a no-op.
export function filterSetupRows(rows, query) {
  const q = String(query ?? '').trim().toLowerCase();
  if (!q) return rows;
  return rows.filter((row) => String(row.ticker ?? '').toLowerCase().includes(q)
    || String(row.label ?? '').toLowerCase().includes(q));
}

// At least one page, so "1/1" is the floor even for an empty list.
export const pageCount = (total, size = SETUPS_PER_PAGE) =>
  Math.max(1, Math.ceil(total / size));

// The rows on a 1-based page; a page past either end clamps into range (a
// delete that empties the last page shows the new last page, never a blank).
export function pageSlice(rows, page, size = SETUPS_PER_PAGE) {
  const current = Math.min(Math.max(1, page), pageCount(rows.length, size));
  return rows.slice((current - 1) * size, current * size);
}

// The 1-based page that holds the row with `key`, or null when it is not in
// the (filtered, sorted) list — how the rail follows the loaded setup.
export function pageOfKey(rows, key, size = SETUPS_PER_PAGE) {
  const index = rows.findIndex((row) => row.key === key);
  return index < 0 ? null : Math.floor(index / size) + 1;
}

// The row `step` places from the loaded setup in the (filtered, sorted) list: how ↑/↓ walk the rail.
// Wraps at either end, like the watchlist rail; with no loaded setup in the list, ↓ starts at the top and ↑ at the bottom.
export function adjacentSetupRow(rows, activeKey, step) {
  if (!rows?.length) return null;
  const index = rows.findIndex((row) => row.key === activeKey);
  if (index < 0) return step > 0 ? rows[0] : rows[rows.length - 1];
  return rows[(index + step + rows.length) % rows.length];
}

// The rail's Setup date WITH its year — "13 Apr 26" — so setups a year apart
// on one symbol never read alike. Non-date strings pass through; empty is the
// em-dash, like every other formatter in the app.
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export function setupDateLabel(iso) {
  if (!iso) return EMPTY;
  const match = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return iso;
  return `${Number(match[3])} ${MONTHS[Number(match[2]) - 1]} ${match[1].slice(2)}`;
}
