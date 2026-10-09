// The off-scan card's chart-state line (build task 15 of the two-eyes reader).
//
// The plan's Done-when: "a failed or pending read is a screen state, never one of your ten words, and a card never
// keeps showing the PREVIOUS ticker's state while a new one loads (a live defect the blind check found in the
// chart-state hook)". The hook kept the last answer in state and only replaced it when the next one arrived, so a
// card handed a new ticker went on saying the old ticker's word, with the old ticker's lines, until the fetch
// landed — and for good when it failed.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { chartStateLine, entryFor, pendingEntry, settledEntry } from './chartStateEntry.js';

// His ten words (the reader's table). The screen's own states must never be one of them.
const HIS_TEN_WORDS = [
  'fired', 'crossed', 'lines, no LPS yet', 'forming N of 15', 'root candidate, unconfirmed',
  'beyond R, undetermined', 'under S, undetermined', 'broke down', 'not scanned', 'no lines',
];

const LINES = {
  ticker: 'AAA', state: 'lines, no LPS yet', why: null, distance_ranges: null,
  R: 101.25, S: 98.5, open: '2026-03-02', age: 48, turns_at_r: 2, turns_at_s: 3,
};

test('a card handed a new ticker shows that ticker loading, never the last one\'s answer', () => {
  const answered = settledEntry('AAA', LINES);
  assert.deepEqual(entryFor(answered, 'BBB'), pendingEntry('BBB'));
  assert.equal(entryFor(answered, 'AAA'), answered);
  assert.deepEqual(entryFor(null, 'AAA'), pendingEntry('AAA'));
});

test('a read the server could not make, or a fetch that failed, is the failed screen state', () => {
  assert.equal(settledEntry('AAA', null).screen, 'failed');
  assert.equal(settledEntry('AAA', { ticker: 'AAA', state: null, failed: true, why: 'the read failed' }).screen,
    'failed');
  assert.equal(settledEntry('AAA', LINES).screen, 'ready');
});

test('the two screen states have their own words, and neither is one of his ten', () => {
  const pending = chartStateLine(pendingEntry('AAA'));
  const failed = chartStateLine(settledEntry('AAA', null));
  assert.equal(pending, 'reading the chart…');
  assert.equal(failed, 'the read failed');
  for (const line of [pending, failed]) assert.ok(!HIS_TEN_WORDS.includes(line), line);
  assert.equal(chartStateLine(null), null, 'no ticker, no line: the card keeps its own copy');
});

test('a word reads as it always has: the door\'s leg and its distance, or the lines and their facts', () => {
  assert.equal(
    chartStateLine(settledEntry('AAA', {
      ticker: 'AAA', state: 'not scanned', why: 'under the 50-day average', distance_ranges: 1.34,
    })),
    'not scanned: under the 50-day average (1.3 ranges)',
  );
  assert.equal(
    chartStateLine(settledEntry('AAA', LINES)),
    'lines, no LPS yet · R 101.25 / S 98.50 · open Mon 02/03/2026 · 48 days · turns 2 / 3',
  );
});

test('the new reader\'s word carries the days that ride beside it, never written into the word', () => {
  assert.equal(
    chartStateLine(settledEntry('AAA', {
      ticker: 'AAA', state: 'beyond R, undetermined', why: null, distance_ranges: null,
      R: 101.25, S: 98.5, open: '2026-03-02', days: 3,
    })),
    'beyond R, undetermined (3 days) · R 101.25 / S 98.50 · open Mon 02/03/2026',
  );
});
