import assert from 'node:assert/strict';
import test from 'node:test';
import {
  fetchBatchCandles, fetchTickerCandles, getBatchCells, getCandleEnvelopes,
  revalidateBatchCandles,
} from './watchlistCandlesStore.js';

// The candle store's transport state machine, with an injected global fetch —
// the review's finding 3 battery: terminal cells for unechoed names (the
// infinite-loop guard), error retry-ability, serve-stale-then-revalidate
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

test('batch: an unechoed name gets a TERMINAL cell, never a refetch invitation', async () => {
  // The server drops grammar-failing names from the response; the asked-for
  // name must land as a recorded outcome so the plan cannot loop on it.
  fetchImpl = () => jsonResponse({ tickers: {
    BAA: { status: 'ok', candles: [{ time: 't', close: 1 }], volumes: [] },
  } });
  await fetchBatchCandles(['BAA', 'BDROP']);
  assert.equal(getBatchCells().BAA.status, 'ok');
  assert.deepEqual(getBatchCells().BDROP,
    { status: 'error', candles: [], volumes: [] });
  // And fetchBatchCandles never re-asks a celled name (loop guard).
  fetchCalls = [];
  await fetchBatchCandles(['BAA', 'BDROP']);
  assert.deepEqual(fetchCalls, []);
});

test('batch: a failed batch marks only the asked names, and revalidate retries them', async () => {
  fetchImpl = () => jsonResponse({ tickers: {
    BPRE: { status: 'ok', candles: [{ time: 't', close: 2 }], volumes: [] },
  } });
  await fetchBatchCandles(['BPRE']);
  fetchImpl = () => Promise.reject(new Error('down'));
  await fetchBatchCandles(['BERR']);
  assert.equal(getBatchCells().BERR.status, 'error');
  assert.equal(getBatchCells().BPRE.status, 'ok'); // untouched by the failure
  // The retry path: revalidate re-asks errored cells and heals them.
  fetchImpl = () => jsonResponse({ tickers: {
    BERR: { status: 'ok', candles: [{ time: 't', close: 3 }], volumes: [] },
  } });
  await revalidateBatchCandles(['BERR']);
  assert.equal(getBatchCells().BERR.status, 'ok');
});

test('batch: a no-change revalidate keeps cell references; pins ride the wire', async () => {
  const cell = { status: 'ok', candles: [{ time: 't9', close: 9 }], volumes: [] };
  fetchImpl = () => jsonResponse({ tickers: { BREF: cell } });
  await fetchBatchCandles(['BREF']);
  const first = getBatchCells().BREF;
  fetchCalls = [];
  await revalidateBatchCandles(['BREF'], { BREF: 'us_sectors' });
  assert.equal(getBatchCells().BREF, first); // identical generation
  assert.match(fetchCalls[0], /pins=BREF%3Aus_sectors/);
});
