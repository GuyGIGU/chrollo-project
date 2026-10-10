import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  CALIBRATION_SORT_OPTIONS,
  archiveListPath,
  calibrationResult,
  defaultSortFor,
  isCalibration,
} from './calibrationList.js';

test('archiveListPath: his calibration setups come from their own route', () => {
  assert.equal(archiveListPath('calibration'), '/archive/calibration-setups');
  assert.equal(archiveListPath('curated'), '/archive/episodes');
  assert.equal(archiveListPath('all'), '/archive/episodes');
});

test('defaultSortFor: each list opens on a key its rows carry', () => {
  assert.equal(defaultSortFor('calibration'), 'his_trigger_date');
  assert.equal(defaultSortFor('screener'), 'scan_date');
  assert.ok(CALIBRATION_SORT_OPTIONS.some(([key]) => key === defaultSortFor('calibration')));
});

test('isCalibration: only the calibration filter', () => {
  assert.equal(isCalibration('calibration'), true);
  assert.equal(isCalibration('curated'), false);
  assert.equal(isCalibration(undefined), false);
});

test('calibrationResult: names the barrier label the wire carries', () => {
  assert.equal(calibrationResult({ barrier_label: 'win', win_barrier: '2.5R' }), 'win (2.5R)');
  assert.equal(calibrationResult({ barrier_label: 'win', win_barrier: '15pct' }), 'win (+15%)');
  assert.equal(calibrationResult({ barrier_label: 'loss' }), 'stopped');
  assert.equal(calibrationResult({ barrier_label: 'timeout' }), 'timed out');
  assert.equal(calibrationResult({ barrier_label: null, bars_to_date: 12 }), 'open');
  assert.equal(calibrationResult({ barrier_label: null, bars_to_date: null }), 'not measured');
  assert.equal(calibrationResult(undefined), 'not measured');
});
