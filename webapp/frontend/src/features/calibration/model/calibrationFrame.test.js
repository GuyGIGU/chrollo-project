import test from 'node:test';
import assert from 'node:assert/strict';
import {
  autoEditStep,
  eveOfBuyDate,
  frameSwap,
  marksOnFrame,
  representativeBoxFor,
  savedBoxesForFrame,
} from './calibrationFrame.js';
import { emptyDraft, initialMarkingState } from './calibrationMarking.js';

const CHART = {
  ticker: 'KLAC', as_of_session: '2026-04-15', frame_digest: 'dg1',
  candles: [{ time: '2026-04-13' }, { time: '2026-04-14' }, { time: '2026-04-15' },
            { time: '2026-04-16' }],
};
const KEY = 'KLAC|2026-04-15|dg1';
const mark = (id, over = {}) => ({ id, ticker: 'KLAC', as_of_date: '2026-04-15',
                                   frame_digest: 'dg1', verdict: 'box', label: '', ...over });
const drawn = { ...emptyDraft(), resistance: 12, rAnchorDate: '2026-04-01' };

test('savedBoxesForFrame: saved boxes on this exact frame, minus the one being edited', () => {
  const marks = [
    mark(1),
    mark(2, { label: 'alt' }),
    mark(3, { verdict: 'no_structure' }),       // a negative draws nothing
    mark(4, { as_of_date: '2026-04-10' }),      // another session
    mark(5, { frame_digest: 'dg0' }),           // restated: the OLD digest never draws
  ];
  assert.deepEqual(savedBoxesForFrame(marks, CHART, null).map((m) => m.id), [1, 2]);
  assert.deepEqual(savedBoxesForFrame(marks, CHART, 2).map((m) => m.id), [1]);
  assert.deepEqual(savedBoxesForFrame(marks, null, null), []);
});

test('marksOnFrame: every verdict on this ticker + session + digest (what Re Mark deletes)', () => {
  const marks = [
    mark(1), mark(2, { verdict: 'engine_wrong' }),
    mark(3, { ticker: 'AAPL' }), mark(4, { frame_digest: 'dg0' }), mark(5, { as_of_date: '2026-04-10' }),
  ];
  assert.deepEqual(marksOnFrame(marks, CHART).map((m) => m.id), [1, 2]);
  assert.deepEqual(marksOnFrame(marks, null), []);
});

test('representativeBoxFor: highest revision wins, then the primary (empty) label', () => {
  const marks = [
    mark(1, { label: 'b', revision: 2 }),
    mark(2, { label: 'a', revision: 3 }),
    mark(3, { label: '', revision: 3 }),
    mark(4, { verdict: 'no_structure', revision: 9 }),  // negatives never represent
    mark(5, { ticker: 'AAPL', revision: 9 }),
  ];
  assert.equal(representativeBoxFor(marks, CHART).id, 3);
  assert.deepEqual(marks.map((m) => m.id), [1, 2, 3, 4, 5]); // input order untouched
  // A missing revision counts as 0; a missing label sorts as the empty one.
  assert.equal(representativeBoxFor([mark(6, { label: 'x' }), mark(7, { label: undefined })], CHART).id, 7);
  assert.equal(representativeBoxFor([mark(8, { revision: 1 }), mark(9)], CHART).id, 8);
});

test('representativeBoxFor: null without a chart or without a saved box on the frame', () => {
  assert.equal(representativeBoxFor([mark(1)], null), null);
  assert.equal(representativeBoxFor([mark(1, { verdict: 'engine_wrong' })], CHART), null);
  assert.equal(representativeBoxFor([], CHART), null);
});

test('eveOfBuyDate: the session before the buy, or null', () => {
  assert.equal(eveOfBuyDate('2026-04-16', CHART), '2026-04-15');
  assert.equal(eveOfBuyDate('2026-04-14', CHART), '2026-04-13');
  assert.equal(eveOfBuyDate('2026-04-13', CHART), null);   // the very first bar
  assert.equal(eveOfBuyDate('2026-05-01', CHART), null);   // not on this frame
  assert.equal(eveOfBuyDate(null, CHART), null);
  assert.equal(eveOfBuyDate('2026-04-16', null), null);
  assert.equal(eveOfBuyDate('2026-04-16', { ...CHART, candles: undefined }), null);
});

test('frameSwap: a fresh frame starts clean and is flagged for auto-edit', () => {
  assert.deepEqual(frameSwap(CHART, null, undefined), {
    load: { type: 'load', frameKey: KEY, draft: null, editingId: null, pristine: true },
    label: '', note: '', autoEditKey: KEY,
  });
});

test('frameSwap: a cached frame resumes its draft, edit binding and dirtiness', () => {
  const cached = { draft: drawn, editingId: 7, pristine: false };
  assert.deepEqual(frameSwap(CHART, null, cached), {
    load: { type: 'load', frameKey: KEY, draft: drawn, editingId: 7, pristine: false },
    label: '', note: '', autoEditKey: null,             // work in hand: never auto-edit over it
  });
  // A cached but still EMPTY draft is fresh again: auto-edit may fire.
  const empty = { draft: emptyDraft(), editingId: null, pristine: true };
  assert.equal(frameSwap(CHART, null, empty).autoEditKey, KEY);
  assert.equal(frameSwap(CHART, null, empty).load.draft, empty.draft);
});

test('frameSwap: a carry for this ticker wins over the cache and brings its label and note', () => {
  const carry = { ticker: 'KLAC', draft: drawn, label: 'primary', note: 'why' };
  const cached = { draft: emptyDraft(), editingId: 7, pristine: true };
  assert.deepEqual(frameSwap(CHART, carry, cached), {
    load: { type: 'load', frameKey: KEY, draft: drawn, editingId: null, pristine: false },
    label: 'primary', note: 'why', autoEditKey: null,
  });
  const bare = frameSwap(CHART, { ticker: 'KLAC', draft: drawn }, undefined);
  assert.equal(bare.label, '');
  assert.equal(bare.note, '');
});

test('frameSwap: a carry stranded on another ticker is discarded, never bled onto this frame', () => {
  const carry = { ticker: 'AAPL', draft: drawn, label: 'primary', note: 'why' };
  assert.deepEqual(frameSwap(CHART, carry, undefined), frameSwap(CHART, null, undefined));
});

test('autoEditStep: waits until the flagged frame, its load and its marks have landed', () => {
  const landed = initialMarkingState(null, KEY);
  const box = mark(1);
  assert.equal(autoEditStep(null, CHART, landed, box), 'wait');                 // nothing flagged
  assert.equal(autoEditStep(KEY, null, landed, box), 'wait');                   // no chart
  assert.equal(autoEditStep('AAPL|x|y', CHART, landed, box), 'wait');           // flag for another frame
  assert.equal(autoEditStep(KEY, CHART, initialMarkingState(null, 'OLD'), box), 'wait'); // load pending
  assert.equal(autoEditStep(KEY, CHART, landed, null), 'wait');                 // marks still loading
  assert.equal(autoEditStep(KEY, CHART, landed, box), 'enter');
});

test('autoEditStep: cancels over an edit or a drawn draft', () => {
  const box = mark(1);
  assert.equal(autoEditStep(KEY, CHART, initialMarkingState(null, KEY, 5), box), 'cancel');
  assert.equal(autoEditStep(KEY, CHART, initialMarkingState(drawn, KEY), box), 'cancel');
  assert.equal(autoEditStep(KEY, CHART, initialMarkingState(drawn, KEY), null), 'cancel');
});
