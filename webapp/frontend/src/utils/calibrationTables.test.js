import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildCoverageRows, sortCoverageRows, buildMarkRows, sortMarkRows,
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
