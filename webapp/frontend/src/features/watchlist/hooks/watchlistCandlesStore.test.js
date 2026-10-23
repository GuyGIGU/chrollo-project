import assert from 'node:assert/strict';
import test from 'node:test';
import {
  fetchTickerCandles, getCandleEnvelopes,
} from './watchlistCandlesStore.js';

// The candle store's transport state machine, with an injected global fetch —
// error retry-ability, serve-stale-then-revalidate
// reference keeping, and failure isolation. The store is a module singleton,
// so every test uses its OWN tickers.

let fetchCalls = [];
let fetchImpl = null;

globalThis.fetch = (...args) => {
  fetchCalls.push(String(args[0]));
  return fetchImpl(...args);
};

const jsonResponse = (body, ok = true, status = 200) => Promise.resolve({
  ok, status, json: () => Promise.resolve(body),
});

const envelope = (overrides = {}) => ({
  ticker: 'X', universe: 'us_stocks', status: 'ok', source: 'cache',
  price_series: 'as_traded', cache_last_modified: 'gen-1',
  last_bar_date: '2026-08-14',
  frames: {
    daily: { status: 'ok', forming_last_bar: false, candles: [{ time: '2026-08-14', close: 1 }], volumes: [] },
    weekly: { status: 'ok', forming_last_bar: false, candles: [], volumes: [] },
    monthly: { status: 'ok', forming_last_bar: true, candles: [], volumes: [] },
  },
  ...overrides,
});

test('envelope: an errored entry is retried by the next call (never wedged)', async () => {
  fetchImpl = () => Promise.reject(new Error('down'));
  await fetchTickerCandles('EAA');
  assert.equal(getCandleEnvelopes().EAA.status, 'error');
  fetchImpl = () => jsonResponse(envelope());
  await fetchTickerCandles('EAA');
  assert.equal(getCandleEnvelopes().EAA.status, 'ready');
});

test('envelope: a no-change revalidate keeps the SAME entry reference', async () => {
  fetchImpl = () => jsonResponse(envelope());
  await fetchTickerCandles('EBB');
  const first = getCandleEnvelopes().EBB;
  await fetchTickerCandles('EBB'); // revalidate — identical generation
  assert.equal(getCandleEnvelopes().EBB, first);
  fetchImpl = () => jsonResponse(envelope({ cache_last_modified: 'gen-2' }));
  await fetchTickerCandles('EBB'); // the panel moved — the entry is replaced
  assert.notEqual(getCandleEnvelopes().EBB, first);
});

test('envelope: a failed revalidate keeps serving the cached envelope', async () => {
  fetchImpl = () => jsonResponse(envelope());
  await fetchTickerCandles('ECC');
  fetchImpl = () => Promise.reject(new Error('blip'));
  await fetchTickerCandles('ECC');
  assert.equal(getCandleEnvelopes().ECC.status, 'ready');
});

test('envelope: a pin change replaces a ready entry fetched under another universe', async () => {
  fetchImpl = () => jsonResponse(envelope({ universe: 'us_stocks' }));
  await fetchTickerCandles('EDD');
  const unpinned = getCandleEnvelopes().EDD;
  fetchImpl = () => jsonResponse(envelope({ universe: 'us_sectors' }));
  await fetchTickerCandles('EDD', 'us_sectors');
  assert.notEqual(getCandleEnvelopes().EDD, unpinned);
  assert.equal(getCandleEnvelopes().EDD.universeKey, 'us_sectors');
});
