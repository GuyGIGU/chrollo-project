import test from 'node:test';
import assert from 'node:assert/strict';
import { hasVolumeRead, volumeCells, volumeRatioLabel } from './volumeRead.js';

test('volumeRatioLabel: a ratio of the 50-day average, a dash when unmeasured', () => {
  assert.equal(volumeRatioLabel(0.62), '0.62× avg');
  assert.equal(volumeRatioLabel(1.5), '1.50× avg');
  assert.equal(volumeRatioLabel(null), '—');
  assert.equal(volumeRatioLabel(Number.NaN), '—');
});

test('volumeCells: the LPS pullback, then the spring, each from its own wire key', () => {
  const cells = volumeCells({ lps_volume_ratio: 0.62, spring_volume_ratio: 2.43 });
  assert.deepEqual(cells.map((c) => [c.k, c.v]), [
    ['LPS pullback', '0.62× avg'],
    ['Phase C spring', '2.43× avg'],
  ]);
  assert.deepEqual(volumeCells({ lps_volume_ratio: 0.8 }).map((c) => c.v), ['0.80× avg', '—']);
});

test('hasVolumeRead: a payload written before the read carries neither ratio', () => {
  assert.equal(hasVolumeRead({}), false);
  assert.equal(hasVolumeRead({ lps_volume_ratio: null, spring_volume_ratio: null }), false);
  assert.equal(hasVolumeRead({ spring_volume_ratio: 1.2 }), true);
});
