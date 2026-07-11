import test from 'node:test';
import assert from 'node:assert/strict';
import { parseWorklist, worklistLabel } from './calibrationWorklist.js';

test('parses mixed separators, folds case, drops junk and duplicates', () => {
  const items = parseWorklist(
    'klac 2025-09-11\nBODI,2026-04-15\nVLO\t2026-07-07\n' +
    'not a line\nKLAC 2025-09-11\nZZ 2026-13-45-ish\n');
  assert.deepEqual(items, [
    { ticker: 'KLAC', asOf: '2025-09-11' },
    { ticker: 'BODI', asOf: '2026-04-15' },
    { ticker: 'VLO', asOf: '2026-07-07' },
  ]);
});

test('semicolons separate entries too (single-line paste survives)', () => {
  assert.deepEqual(parseWorklist('BODI 2026-04-15; KLAC 2025-09-05'), [
    { ticker: 'BODI', asOf: '2026-04-15' },
    { ticker: 'KLAC', asOf: '2025-09-05' },
  ]);
});

test('empty and null input parse to an empty queue', () => {
  assert.deepEqual(parseWorklist(''), []);
  assert.deepEqual(parseWorklist(null), []);
});

test('worklistLabel clamps and names the current entry', () => {
  const items = parseWorklist('KLAC 2025-09-11\nBODI 2026-04-15');
  assert.equal(worklistLabel(items, 0), '1/2 · KLAC 2025-09-11');
  assert.equal(worklistLabel(items, 5), '2/2 · BODI 2026-04-15');
  assert.equal(worklistLabel([], 0), '');
});
