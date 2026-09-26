import test from 'node:test';
import assert from 'node:assert/strict';
import {
  cacheKey,
  cacheKeysFor,
  classifyChartResponse,
  normalizeTicker,
} from './calibrationChartUtils.js';

test('normalizeTicker folds whitespace and case', () => {
  assert.equal(normalizeTicker('  klac '), 'KLAC');
  assert.equal(normalizeTicker(null), '');
});

test('cacheKey uses the normalized ticker', () => {
  assert.equal(cacheKey(' bodi ', '2026-04-15'), 'BODI|2026-04-15');
});

test('cacheKeysFor aliases the resolved session (Sunday and its Friday are one payload)', () => {
  const body = { ticker: 'KLAC', as_of_session: '2025-09-05' };
  assert.deepEqual(cacheKeysFor('KLAC|2025-09-07', body),
    ['KLAC|2025-09-07', 'KLAC|2025-09-05']);
  // Requested a real session: one key, no duplicate alias.
  assert.deepEqual(cacheKeysFor('KLAC|2025-09-05', body), ['KLAC|2025-09-05']);
  assert.deepEqual(cacheKeysFor('KLAC|2025-09-05', null), ['KLAC|2025-09-05']);
});

test('classifyChartResponse: real payload', () => {
  const out = classifyChartResponse(true, 200, { candles: [] });
  assert.equal(out.kind, 'chart');
});

test('classifyChartResponse: 200 without candles is the stale service, never a chart', () => {
  const out = classifyChartResponse(true, 200, '<!doctype html>');
  assert.equal(out.kind, 'failure');
  assert.equal(out.failure.class, 'service_stale');
});

test('classifyChartResponse: named failure detail passes through', () => {
  const detail = { class: 'no_data', message: 'vendor returned nothing' };
  const out = classifyChartResponse(false, 404, { detail });
  assert.deepEqual(out.failure, detail);
});

test('classifyChartResponse: unclassified failure keeps the status visible', () => {
  const out = classifyChartResponse(false, 500, null);
  assert.equal(out.failure.class, 'unknown');
  assert.match(out.failure.message, /500/);
});
