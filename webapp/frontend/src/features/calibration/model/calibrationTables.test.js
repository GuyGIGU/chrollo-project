import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildCoverageRows, sortCoverageRows, buildMarkRows, sortMarkRows,
  buildSetupRows, sortSetupRows,
  SETUPS_PER_PAGE, filterSetupRows, pageCount, pageSlice, pageOfKey, setupDateLabel,
  adjacentSetupRow,
} from './calibrationTables.js';

// A small marks population across three tickers: AGCO has a box + a negative,
// YPF one box, KLAC one negative. Dates are the frozen as-of sessions.
const marks = [
  { id: 1, ticker: 'AGCO', as_of_date: '2026-07-07', verdict: 'box', label: '',
    resistance: 119.24, support: 111.83, box_start_date: '2026-06-01',
    box_end_date: '2026-07-07', events: [{ event_type: 'phase_c' }], revision: 2 },
  { id: 2, ticker: 'AGCO', as_of_date: '2026-07-10', verdict: 'no_structure', label: 'chop',
    resistance: null, support: null, events: [], revision: 0 },
  { id: 3, ticker: 'YPF', as_of_date: '2026-05-06', verdict: 'box', label: '',
    resistance: 44.48, support: 41.35, box_start_date: '2026-04-08',
    box_end_date: '2026-05-06', events: [], revision: 1 },
  { id: 4, ticker: 'KLAC', as_of_date: '2026-09-11', verdict: 'engine_wrong', label: '',
    resistance: null, support: null, events: [], revision: 0 },
];

// ---- coverage ---------------------------------------------------------------

test('buildCoverageRows aggregates per ticker: count, box/negative split, latest as-of', () => {
  const rows = buildCoverageRows(marks);
  const agco = rows.find((r) => r.ticker === 'AGCO');
  assert.equal(agco.count, 2);
  assert.equal(agco.boxes, 1);
  assert.equal(agco.negatives, 1);
  assert.equal(agco.latestAsOf, '2026-07-10'); // the later of the two sessions
  const klac = rows.find((r) => r.ticker === 'KLAC');
  assert.equal(klac.boxes, 0);
  assert.equal(klac.negatives, 1);
});

test('buildCoverageRows tolerates null / empty (before first fetch)', () => {
  assert.deepEqual(buildCoverageRows(null), []);
  assert.deepEqual(buildCoverageRows([]), []);
});

test('default coverage sort: newest activity first, ticker breaks ties', () => {
  const rows = buildCoverageRows(marks);
  // KLAC 09-11 > AGCO 07-10 > YPF 05-06.
  assert.deepEqual(sortCoverageRows(rows).map((r) => r.ticker), ['KLAC', 'AGCO', 'YPF']);
});

test('coverage sorts by count and by ticker, symmetric under direction', () => {
  const rows = buildCoverageRows(marks);
  assert.deepEqual(sortCoverageRows(rows, 'count', 'desc').map((r) => r.ticker), ['AGCO', 'KLAC', 'YPF']);
  assert.deepEqual(sortCoverageRows(rows, 'ticker', 'asc').map((r) => r.ticker), ['AGCO', 'KLAC', 'YPF']);
  assert.deepEqual(sortCoverageRows(rows, 'ticker', 'desc').map((r) => r.ticker), ['YPF', 'KLAC', 'AGCO']);
});

test('coverage tie on count falls back to ticker deterministically', () => {
  const rows = buildCoverageRows(marks); // KLAC & YPF both count 1
  const asc = sortCoverageRows(rows, 'count', 'asc').map((r) => r.ticker);
  // count 1 rows (KLAC, YPF) sort before AGCO (count 2); the pair orders K<Y.
  assert.deepEqual(asc, ['KLAC', 'YPF', 'AGCO']);
});

test('coverage sort does not mutate its input and is idempotent', () => {
  const rows = buildCoverageRows(marks);
  const before = rows.map((r) => r.ticker);
  const once = sortCoverageRows(rows).map((r) => r.ticker);
  const twice = sortCoverageRows(sortCoverageRows(rows)).map((r) => r.ticker);
  assert.deepEqual(rows.map((r) => r.ticker), before); // untouched
  assert.deepEqual(once, twice);                        // stable
});

// ---- marks ledger -----------------------------------------------------------

test('buildMarkRows flattens geometry; negatives carry null R/S', () => {
  const rows = buildMarkRows(marks);
  const box = rows.find((r) => r.id === 1);
  assert.equal(box.isBox, true);
  assert.equal(box.resistance, 119.24);
  assert.equal(box.support, 111.83);
  assert.equal(box.events, 1);
  assert.equal(box.revision, 2);
  const neg = rows.find((r) => r.id === 2);
  assert.equal(neg.isBox, false);
  assert.equal(neg.resistance, null);
  assert.equal(neg.support, null);
  assert.equal(neg.events, 0);
  assert.equal(neg.raw, marks[1]); // the full row rides along for edit/delete
});

test('buildMarkRows coerces a non-finite R and a missing revision safely', () => {
  const rows = buildMarkRows([
    { id: 9, ticker: 'X', as_of_date: '2026-01-02', verdict: 'box', resistance: 'nope', support: 5 },
  ]);
  assert.equal(rows[0].resistance, null); // fx-guard-safe
  assert.equal(rows[0].revision, 0);      // missing -> 0, never NaN
  assert.equal(rows[0].label, '');        // null label -> ''
});

test('default mark sort: newest session first, id breaks ties', () => {
  const rows = buildMarkRows(marks);
  assert.deepEqual(sortMarkRows(rows).map((r) => r.id), [4, 2, 1, 3]); // 09-11, 07-10, 07-07, 05-06
});

test('marks sort by R numerically with nulls sunk, symmetric under direction', () => {
  const rows = buildMarkRows(marks);
  // desc: real R rows (119.24, 44.48) above the null-R negatives; asc mirrors.
  assert.deepEqual(sortMarkRows(rows, 'resistance', 'desc').map((r) => r.id), [1, 3, 2, 4]);
  assert.deepEqual(sortMarkRows(rows, 'resistance', 'asc').map((r) => r.id), [2, 4, 3, 1]);
});

test('marks sort by events (the Ev column) orders by count, not id', () => {
  // Regression: the Ev column is sortable but markCompare had no 'events' case,
  // so it silently fell through to the id tiebreak while the header claimed
  // sorted-by-events. Now it orders by the flat event count.
  const rows = buildMarkRows([
    { id: 1, ticker: 'X', as_of_date: '2026-01-01', verdict: 'box', events: [{}, {}, {}] },
    { id: 2, ticker: 'X', as_of_date: '2026-01-02', verdict: 'box', events: [] },
    { id: 3, ticker: 'X', as_of_date: '2026-01-03', verdict: 'box', events: [{}] },
  ]);
  assert.deepEqual(sortMarkRows(rows, 'events', 'desc').map((r) => r.id), [1, 3, 2]); // 3,1,0
  assert.deepEqual(sortMarkRows(rows, 'events', 'asc').map((r) => r.id), [2, 3, 1]);  // 0,1,3
});

test('marks sort by verdict groups alphabetically and stays total', () => {
  const rows = buildMarkRows(marks);
  // box, box, engine_wrong, no_structure -> ids [1,3] then 4 then 2 (id tiebreak)
  assert.deepEqual(sortMarkRows(rows, 'verdict', 'asc').map((r) => r.id), [1, 3, 4, 2]);
});

test('marks sort is idempotent and non-mutating', () => {
  const rows = buildMarkRows(marks);
  const before = rows.map((r) => r.id);
  const once = sortMarkRows(rows).map((r) => r.id);
  const twice = sortMarkRows(sortMarkRows(rows)).map((r) => r.id);
  assert.deepEqual(rows.map((r) => r.id), before);
  assert.deepEqual(once, twice);
});

// ---- v2 ledger fields: frame identity + coverage completeness ---------------

test('buildMarkRows lifts frame_digest flat (thumbnail/fired-chip key), null-safe', () => {
  const rows = buildMarkRows([
    { id: 7, ticker: 'X', as_of_date: '2026-01-02', verdict: 'box', frame_digest: 'abc123' },
    { id: 8, ticker: 'X', as_of_date: '2026-01-03', verdict: 'no_structure' }, // no digest
  ]);
  assert.equal(rows[0].frameDigest, 'abc123');
  assert.equal(rows[1].frameDigest, null); // missing -> null, never undefined
});

test('buildCoverageRows projects the NEWEST mark\'s frame + geometry, drops the raw', () => {
  const rows = buildCoverageRows([
    // older box, then a newer, fully-specified box on a different frame
    { id: 1, ticker: 'AGCO', as_of_date: '2026-07-07', verdict: 'box', resistance: 119, support: 111,
      box_start_date: '2026-06-01', box_end_date: '2026-07-07', frame_digest: 'old', events: [] },
    { id: 2, ticker: 'AGCO', as_of_date: '2026-07-10', verdict: 'box', resistance: 120, support: 112,
      box_start_date: '2026-06-05', box_end_date: '2026-07-10', frame_digest: 'new',
      events: [{ event_type: 'phase_c' }], knowable_from_date: '2026-07-08' },
  ]);
  const agco = rows.find((r) => r.ticker === 'AGCO');
  assert.equal(agco.latestDigest, 'new');       // newest session's frame, not the first-seen
  assert.equal(agco.latestIsBox, true);
  assert.equal(agco.latestResistance, 120);
  assert.equal(agco.latestSupport, 112);
  assert.equal(agco.latestBoxStart, '2026-06-05');
  assert.equal(agco.latestBoxEnd, '2026-07-10');
  assert.equal(agco.latestComplete, true);       // events + knowable-from
  assert.equal('latest' in agco, false);         // the raw mark never rides along
});

test('buildCoverageRows latestComplete is false without events OR without knowable-from', () => {
  const [noEvents] = buildCoverageRows([
    { id: 1, ticker: 'A', as_of_date: '2026-01-01', verdict: 'box', events: [], knowable_from_date: '2026-01-01' },
  ]);
  assert.equal(noEvents.latestComplete, false);  // has knowable-from but no event
  const [noKnowable] = buildCoverageRows([
    { id: 2, ticker: 'B', as_of_date: '2026-01-01', verdict: 'box', events: [{ event_type: 'lps' }] },
  ]);
  assert.equal(noKnowable.latestComplete, false); // has an event but no knowable-from
});

test('buildCoverageRows tolerates a negative latest with null geometry', () => {
  const [row] = buildCoverageRows([
    { id: 1, ticker: 'K', as_of_date: '2026-09-11', verdict: 'no_structure', events: [] },
  ]);
  assert.equal(row.latestIsBox, false);
  assert.equal(row.latestResistance, null);
  assert.equal(row.latestSupport, null);
  assert.equal(row.latestDigest, null);
  assert.equal(row.latestComplete, false);
});

// ---- setup grain: one row per (ticker, as_of) -------------------------------

test('buildSetupRows: two setups on ONE symbol are TWO rows (the core requirement)', () => {
  // AGCO marked at two as-of sessions must never collapse to one entry — the
  // operator adds "the same stock at a different date like a copy" precisely so
  // the engine tests each snapshot separately.
  const rows = buildSetupRows(marks);
  const agco = rows.filter((r) => r.ticker === 'AGCO');
  assert.equal(agco.length, 2);
  assert.deepEqual(agco.map((r) => r.asOf).sort(), ['2026-07-07', '2026-07-10']);
  // Four distinct (ticker, as_of) pairs across the population.
  assert.equal(rows.length, 4);
  assert.deepEqual([...new Set(rows.map((r) => r.key))].length, 4);
});

test('buildSetupRows: the box is the representative when a session carries several marks', () => {
  // One session, a box AND a negative on it: count=2, but the row's geometry is
  // the box's (the ground truth the thumbnail + engine test read).
  const rows = buildSetupRows([
    { id: 1, ticker: 'NVDA', as_of_date: '2026-03-02', verdict: 'no_structure',
      label: 'chop', resistance: null, support: null, events: [] },
    { id: 2, ticker: 'NVDA', as_of_date: '2026-03-02', verdict: 'box', label: '',
      resistance: 90.5, support: 82.1, box_start_date: '2026-02-01',
      box_end_date: '2026-03-02', revision: 3,
      events: [{ event_type: 'lps' }] },
  ]);
  assert.equal(rows.length, 1);
  const [row] = rows;
  assert.equal(row.count, 2);
  assert.equal(row.isBox, true);
  assert.equal(row.resistance, 90.5);
  assert.equal(row.support, 82.1);
  assert.equal(row.revision, 3);
  assert.equal(row.hasLps, true);
  assert.equal(row.allMarks.length, 2);        // both ride along for cascade delete
  assert.equal(row.raw.id, 2);                 // the box is the load/edit/grade key
});

test('buildSetupRows: surfaces the Trigger + LPS flat, null-safe', () => {
  const [row] = buildSetupRows([
    { id: 1, ticker: 'X', as_of_date: '2026-01-02', verdict: 'box',
      resistance: 12.4, support: 10.1, box_start_date: '2025-12-12',
      box_end_date: '2026-01-02', frame_digest: 'deadbeef', revision: 1,
      trigger_date: '2026-01-06', trigger_price: 12.55,
      events: [{ event_type: 'lps' }, { event_type: 'phase_c' }] },
  ]);
  assert.equal(row.hasLps, true);
  assert.equal(row.hasTrigger, true);
  assert.equal(row.triggerDate, '2026-01-06');
  assert.equal(row.triggerPrice, 12.55);
  assert.equal(row.frameDigest, 'deadbeef');
  assert.equal(row.events, 2);
  // A box with no trigger reads null, not undefined; a bad price sinks to null.
  const [bare] = buildSetupRows([
    { id: 2, ticker: 'Y', as_of_date: '2026-01-02', verdict: 'box',
      resistance: 5, support: 4, trigger_price: 'nope', events: [] },
  ]);
  assert.equal(bare.hasTrigger, false);
  assert.equal(bare.triggerDate, null);
  assert.equal(bare.triggerPrice, null);   // non-finite -> null, never NaN
  assert.equal(bare.hasLps, false);
});

test('buildSetupRows: surfaces the operator note, empty -> null (so the rail ✎ hides)', () => {
  const [withNote] = buildSetupRows([
    { id: 1, ticker: 'X', as_of_date: '2026-01-02', verdict: 'box',
      resistance: 5, support: 4, note: 'tight shelf the engine skips', events: [] },
  ]);
  assert.equal(withNote.note, 'tight shelf the engine skips');
  const [empty] = buildSetupRows([
    { id: 2, ticker: 'Y', as_of_date: '2026-01-02', verdict: 'box',
      resistance: 5, support: 4, note: '', events: [] },
  ]);
  assert.equal(empty.note, null);
});

test('buildSetupRows tolerates null / empty', () => {
  assert.deepEqual(buildSetupRows(null), []);
  assert.deepEqual(buildSetupRows([]), []);
});

test('buildSetupRows representative pick is deterministic regardless of input order', () => {
  const forward = [
    { id: 1, ticker: 'Z', as_of_date: '2026-01-02', verdict: 'box', label: '', revision: 1, resistance: 9, support: 8, events: [] },
    { id: 2, ticker: 'Z', as_of_date: '2026-01-02', verdict: 'box', label: 'second', revision: 5, resistance: 9.2, support: 8.1, events: [] },
  ];
  const reversed = [...forward].reverse();
  // Higher revision wins the representative slot either way.
  assert.equal(buildSetupRows(forward)[0].raw.id, 2);
  assert.equal(buildSetupRows(reversed)[0].raw.id, 2);
});

test('default setup sort: grouped by ticker A->Z, newest session first within a ticker', () => {
  const rows = sortSetupRows(buildSetupRows(marks));
  // AGCO(2), KLAC, YPF grouped; within AGCO the 07-10 setup floats above 07-07.
  assert.deepEqual(rows.map((r) => `${r.ticker}@${r.asOf}`), [
    'AGCO@2026-07-10', 'AGCO@2026-07-07', 'KLAC@2026-09-11', 'YPF@2026-05-06',
  ]);
});

test('setup sort by asOf desc, symmetric and non-mutating / idempotent', () => {
  const rows = buildSetupRows(marks);
  const before = rows.map((r) => r.key);
  const desc = sortSetupRows(rows, 'asOf', 'desc').map((r) => `${r.ticker}@${r.asOf}`);
  assert.deepEqual(desc, [
    'KLAC@2026-09-11', 'AGCO@2026-07-10', 'AGCO@2026-07-07', 'YPF@2026-05-06',
  ]);
  const once = sortSetupRows(rows).map((r) => r.key);
  const twice = sortSetupRows(sortSetupRows(rows)).map((r) => r.key);
  assert.deepEqual(rows.map((r) => r.key), before); // input untouched
  assert.deepEqual(once, twice);                     // stable
});

// ---- rail search + pages ----------------------------------------------------

// n setup rows: ticker T00..T(n-1), one session each, so row i is key `T<i>|...`.
const manyRows = (n) => Array.from({ length: n }, (_, i) => ({
  key: `T${String(i).padStart(2, '0')}|2026-01-02`,
  ticker: `T${String(i).padStart(2, '0')}`, asOf: '2026-01-02', label: '',
}));

test('filterSetupRows: an empty or blank query returns the input unchanged', () => {
  const rows = buildSetupRows(marks);
  assert.equal(filterSetupRows(rows, ''), rows);
  assert.equal(filterSetupRows(rows, '   '), rows);
  assert.equal(filterSetupRows(rows, null), rows);
});

test('filterSetupRows: case-insensitive ticker substring, trimmed', () => {
  const rows = buildSetupRows(marks);
  assert.deepEqual(filterSetupRows(rows, ' kl ').map((r) => r.ticker), ['KLAC']);
  assert.deepEqual(filterSetupRows(rows, 'yP').map((r) => r.ticker), ['YPF']);
  assert.deepEqual(filterSetupRows(rows, 'zzz'), []);
});

test('filterSetupRows: a label match finds the setup even when the ticker does not', () => {
  const rows = buildSetupRows(marks); // AGCO@07-10 carries the label 'chop'
  const hit = filterSetupRows(rows, 'CHOP');
  assert.deepEqual(hit.map((r) => `${r.ticker}@${r.asOf}`), ['AGCO@2026-07-10']);
});

test('filterSetupRows: two setups on one ticker are BOTH kept', () => {
  const rows = buildSetupRows(marks);
  const agco = filterSetupRows(rows, 'agco');
  assert.equal(agco.length, 2);
  assert.deepEqual(agco.map((r) => r.asOf).sort(), ['2026-07-07', '2026-07-10']);
});

test('filterSetupRows never mutates its input', () => {
  const rows = buildSetupRows(marks);
  const before = rows.map((r) => r.key);
  filterSetupRows(rows, 'agco');
  assert.deepEqual(rows.map((r) => r.key), before);
  assert.equal(rows.length, 4);
});

test('pages of 20: 41 setups split 20 / 20 / 1', () => {
  assert.equal(SETUPS_PER_PAGE, 20);
  const rows = manyRows(41);
  assert.equal(pageCount(rows.length), 3);
  assert.equal(pageSlice(rows, 1).length, 20);
  assert.equal(pageSlice(rows, 2).length, 20);
  assert.deepEqual(pageSlice(rows, 3).map((r) => r.ticker), ['T40']);
  assert.equal(pageSlice(rows, 2)[0].ticker, 'T20'); // page 2 starts at the 21st setup
  // Exactly 40 is two full pages; an empty list is still one page.
  assert.equal(pageCount(40), 2);
  assert.equal(pageCount(0), 1);
  assert.deepEqual(pageSlice([], 1), []);
});

test('pageSlice clamps a page past either end into range, and never mutates', () => {
  const rows = manyRows(41);
  assert.deepEqual(pageSlice(rows, 9).map((r) => r.ticker), ['T40']); // past the end -> last page
  assert.equal(pageSlice(rows, 0)[0].ticker, 'T00');                 // before the start -> first
  assert.equal(pageSlice(rows, -3)[0].ticker, 'T00');
  assert.equal(rows.length, 41);
});

test('pageOfKey: the 1-based page holding a key, null when it is not listed', () => {
  const rows = manyRows(41);
  assert.equal(pageOfKey(rows, 'T00|2026-01-02'), 1);
  assert.equal(pageOfKey(rows, 'T19|2026-01-02'), 1);
  assert.equal(pageOfKey(rows, 'T20|2026-01-02'), 2);
  assert.equal(pageOfKey(rows, 'T40|2026-01-02'), 3);
  assert.equal(pageOfKey(rows, 'NOPE|2026-01-02'), null);
  assert.equal(pageOfKey([], 'T00|2026-01-02'), null);
});

test('adjacentSetupRow walks the shown list and wraps', () => {
  const rows = manyRows(5);
  const at = (key, step) => adjacentSetupRow(rows, key, step)?.ticker;
  assert.equal(at('T01|2026-01-02', 1), 'T02');
  assert.equal(at('T01|2026-01-02', -1), 'T00');
  assert.equal(at('T04|2026-01-02', 1), 'T00'); // wraps past the bottom...
  assert.equal(at('T00|2026-01-02', -1), 'T04'); // ...and past the top
  // Nothing loaded (or the loaded setup filtered out): down starts at the top, up at the bottom.
  assert.equal(at(null, 1), 'T00');
  assert.equal(at('NOPE|x', -1), 'T04');
  assert.equal(adjacentSetupRow([], 'T00|2026-01-02', 1), null);
  assert.equal(rows.length, 5);
});

test('setupDateLabel: day, month and two-digit year; empty is the em-dash', () => {
  assert.equal(setupDateLabel('2026-04-13'), '13 Apr 26');
  assert.equal(setupDateLabel('2025-12-01'), '1 Dec 25');
  assert.equal(setupDateLabel(null), '—');
  assert.equal(setupDateLabel('not a date'), 'not a date');
});
