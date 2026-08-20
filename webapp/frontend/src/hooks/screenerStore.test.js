import assert from 'node:assert/strict';
import test from 'node:test';
import {
  fetchScreenerEarnings, fetchScreenerUniverse, getScreenerEarnings, getScreenerPayload,
} from './screenerStore.js';

// The screener store's EC-41 arrival contract, with an injected global fetch:
// a same-generation revalidate keeps the OLD payload reference (zero chart
// rebuilds), a new scan replaces it, and a non-ok earnings answer does not
// poison the negative cache. The store is a module singleton, so every test
// uses its OWN universe/tickers.

let fetchCalls = [];
let fetchImpl = null;

globalThis.fetch = (...args) => {
  fetchCalls.push(String(args[0]));
  return fetchImpl(...args);
};

const jsonResponse = (body, ok = true, status = 200) => Promise.resolve({
  ok, status, json: () => Promise.resolve(body),
  text: () => Promise.resolve(''),
});

const payload = (overrides = {}) => ({
  scanned_at: '2026-08-19T21:00:00', ordered_tickers: ['MAN'], setups: {},
  ...overrides,
});

// setTimeout, not setImmediate: these files lint under the browser globals.
const flush = () => new Promise((resolve) => { setTimeout(resolve, 0); });

test('payload: a same-generation arrival keeps the SAME payload reference', async () => {
  fetchImpl = () => jsonResponse(payload());
  await fetchScreenerUniverse('gen_keep');
  const first = getScreenerPayload('gen_keep');
  await fetchScreenerUniverse('gen_keep'); // revalidate — scanned_at unchanged
  assert.equal(getScreenerPayload('gen_keep'), first);
  fetchImpl = () => jsonResponse(payload({ scanned_at: '2026-08-20T21:00:00' }));
  await fetchScreenerUniverse('gen_keep'); // a new scan landed — replaced
  assert.notEqual(getScreenerPayload('gen_keep'), first);
});

test('earnings: a non-ok answer leaves the batch re-askable', async () => {
  fetchImpl = () => jsonResponse({}, false, 500);
  fetchScreenerEarnings(['EARN_A']);
  await flush();
  assert.equal(getScreenerEarnings().EARN_A, undefined);
  fetchCalls = [];
  fetchImpl = () => jsonResponse({ EARN_A: { date: '2026-09-01', days_until: 12 } });
  fetchScreenerEarnings(['EARN_A']); // the negative cache must not swallow this
  await flush();
  assert.equal(fetchCalls.length, 1);
  assert.equal(getScreenerEarnings().EARN_A.days_until, 12);
});
