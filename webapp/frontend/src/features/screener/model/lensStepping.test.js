// Where the big chart sits in its list and where Prev/Next land, including
// after he un-stars the chart on the Watchlist tier and it drops out of the list.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { canStepLens, lensPosition, stepTicker } from './lensStepping.js';

const LIST = ['A', 'B', 'C', 'D'];

test('lensPosition is 1-based; a dropped-out chart keeps the total, so the counter keeps its slot', () => {
  assert.deepEqual(lensPosition(LIST, 'A'), { n: 1, total: 4 });
  assert.deepEqual(lensPosition(LIST, 'C'), { n: 3, total: 4 });
  assert.deepEqual(lensPosition(LIST, 'X'), { n: null, total: 4 });
  assert.equal(lensPosition([], 'A'), null);
});

test('canStepLens: Prev/Next show whenever another setup is in the list', () => {
  assert.equal(canStepLens(LIST, 'A'), true);
  assert.equal(canStepLens(['A'], 'A'), false, 'one match, and it is the chart on screen');
  assert.equal(canStepLens(['B'], 'A'), true, 'he un-starred A; B is still a step away');
  assert.equal(canStepLens([], 'A'), false, 'nothing left');
});

test('in the list, Next and Prev step and wrap at both ends', () => {
  assert.equal(stepTicker(LIST, 'B', 1, 1), 'C');
  assert.equal(stepTicker(LIST, 'B', 1, -1), 'A');
  assert.equal(stepTicker(LIST, 'D', 3, 1), 'A');
  assert.equal(stepTicker(LIST, 'A', 0, -1), 'D');
});

test('in the list, its own place wins over a stale last index', () => {
  assert.equal(stepTicker(LIST, 'B', 3, 1), 'C');
  assert.equal(stepTicker(LIST, 'B', 3, -1), 'A');
});

test('dropped out: Next lands on the setup that slid into his old slot', () => {
  // He was on C (index 2) of A B C D E and un-starred it: the list is now A B D E.
  const after = ['A', 'B', 'D', 'E'];
  assert.equal(stepTicker(after, 'C', 2, 1), 'D');
});

test('dropped out: Prev lands on the setup before his old slot', () => {
  const after = ['A', 'B', 'D', 'E'];
  assert.equal(stepTicker(after, 'C', 2, -1), 'B');
  // His old slot was the first: Prev wraps to the end.
  assert.equal(stepTicker(['B', 'C'], 'A', 0, -1), 'C');
});

test('dropped out of the last slot: Next wraps to the first, Prev is the new last', () => {
  // He was on D (index 3) of A B C D: the list is now A B C.
  const after = ['A', 'B', 'C'];
  assert.equal(stepTicker(after, 'D', 3, 1), 'A');
  assert.equal(stepTicker(after, 'D', 3, -1), 'C');
});

test('an empty list goes nowhere', () => {
  assert.equal(stepTicker([], 'A', 0, 1), null);
  assert.equal(stepTicker([], 'A', 0, -1), null);
});

test('no last index is read as the first slot', () => {
  assert.equal(stepTicker(LIST, 'X', null, 1), 'A');
  assert.equal(stepTicker(LIST, 'X', undefined, 1), 'A');
  assert.equal(stepTicker(LIST, 'X', null, -1), 'D');
});
