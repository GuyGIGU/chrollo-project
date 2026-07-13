// Pure data helpers for the two calibration InstrumentTables — no React, no
// fetch, unit-tested in calibrationTables.test.js. Same shape as the watchlist's
// watchlistTable.js: a build* transform that normalizes raw rows and a sort*
// transform with a deterministic, NaN-free total order (a NaN comparator leaves
// Array.sort unspecified — the flicker we refuse). Two surfaces lean on this:
//   coverage — every ticker the operator has marked, aggregated from all marks
//   marks    — the loaded ticker's own ledger of saved marks

// NaN-free comparators (numAsc/strAsc) live in format.js — one shared home the
// watchlist and this module both import, so the missing-value ordering can
// never drift between the two ledgers (EC-3).
import { finiteOrNull, numAsc, strAsc } from './format.js';

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
    // agreement chip keys its cache on (id, revision). Only on row.raw before.
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
