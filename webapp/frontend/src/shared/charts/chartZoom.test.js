import test from 'node:test';
import assert from 'node:assert/strict';
import { MIN_SPAN_BARS, ZOOM_IN, ZOOM_OUT, zoomedRange } from './chartZoom.js';

test('zoomedRange keeps the right edge and scales the span', () => {
  assert.deepEqual(zoomedRange({ from: 100, to: 200 }, ZOOM_IN), { from: 120, to: 200 });
  assert.deepEqual(zoomedRange({ from: 100, to: 200 }, ZOOM_OUT), { from: 75, to: 200 });
});

test('zoomedRange never goes under the minimum span, and null in is null out', () => {
  assert.deepEqual(zoomedRange({ from: 190, to: 200 }, ZOOM_IN), { from: 200 - MIN_SPAN_BARS, to: 200 });
  assert.equal(zoomedRange(null, ZOOM_IN), null);
  assert.equal(zoomedRange({ from: NaN, to: 10 }, ZOOM_IN), null);
});
