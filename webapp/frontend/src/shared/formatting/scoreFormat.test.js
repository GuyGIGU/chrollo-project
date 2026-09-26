// The one score formatter (TA-grade build task 11): absence is a dash,
// never zero; a genuine zero renders as the number it is.
import test from 'node:test';
import assert from 'node:assert/strict';
import { formatScore } from './scoreFormat.js';

test('absence renders as a dash, never zero', () => {
  assert.equal(formatScore(null), '—');
  assert.equal(formatScore(undefined), '—');
  assert.equal(formatScore(Number.NaN), '—');
  assert.equal(formatScore('not-a-number'), '—');
});

test('real numbers render — including a genuine zero', () => {
  assert.equal(formatScore(0), '0');
  assert.equal(formatScore(104.6), '105');
  assert.equal(formatScore(61.24, 1), '61.2');
  assert.equal(formatScore('88'), '88');
});
