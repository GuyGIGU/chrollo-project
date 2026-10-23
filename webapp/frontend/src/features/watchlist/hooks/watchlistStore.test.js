import assert from 'node:assert/strict';
import test from 'node:test';
import { fetchWatchlist, getWatchlistRecords, restoreWatchlist, toggleWatchlist } from './watchlistStore.js';

const response = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
const deferred = () => {
  let resolve;
  const promise = new Promise((finish) => { resolve = finish; });
  return { promise, resolve };
};
const saved = (ticker, id) => ({ ticker, id, pinned: true, save_date: '2026-10-23' });

test('different tickers reconcile their own saved records even when responses arrive out of order', async () => {
  const requests = [];
  globalThis.fetch = (url) => {
    const pending = deferred();
    requests.push({ ticker: String(url).split('/').at(-1), ...pending });
    return pending.promise;
  };
  const first = toggleWatchlist('PARALLELA');
  const second = toggleWatchlist('PARALLELB');
  toggleWatchlist('PARALLELA'); // One in-flight request per ticker.
  assert.equal(requests.length, 2);
  requests[1].resolve(response(saved('PARALLELB', 2)));
  await second;
  requests[0].resolve(response(saved('PARALLELA', 1)));
  await first;
  assert.deepEqual(getWatchlistRecords().filter((row) => row.ticker.startsWith('PARALLEL'))
    .sort((a, b) => a.id - b.id), [saved('PARALLELA', 1), saved('PARALLELB', 2)]);
});

test('a GET issued during a save cannot overwrite its confirmed pin after the save finishes', async () => {
  const write = deferred();
  const read = deferred();
  globalThis.fetch = (_url, options) => options?.method === 'POST' ? write.promise : read.promise;
  const saving = toggleWatchlist('PINNED');
  const loading = fetchWatchlist();
  write.resolve(response(saved('PINNED', 3)));
  await saving;
  read.resolve(response([])); // Server snapshot predates the save.
  await loading;
  assert.deepEqual(getWatchlistRecords().find((row) => row.ticker === 'PINNED'), saved('PINNED', 3));
});

test('Undo while the removal is still saving waits for it, then saves the ticker again', async () => {
  const removal = deferred();
  const methods = [];
  globalThis.fetch = (_url, options) => {
    methods.push(options?.method);
    return options?.method === 'DELETE' ? removal.promise : Promise.resolve(response(saved('UNDONE', 5)));
  };
  await toggleWatchlist('UNDONE');
  const removing = toggleWatchlist('UNDONE');
  const undo = restoreWatchlist('UNDONE');
  removal.resolve(response(null, 204));
  await removing;
  await undo;
  assert.deepEqual(methods, ['POST', 'DELETE', 'POST']);
  assert.deepEqual(getWatchlistRecords().find((row) => row.ticker === 'UNDONE'), saved('UNDONE', 5));
});

test('Undo after a failed removal does not save a second time', async () => {
  const methods = [];
  globalThis.fetch = async (_url, options) => {
    methods.push(options?.method);
    return options?.method === 'DELETE' ? response(null, 500) : response(saved('KEPT', 6));
  };
  await toggleWatchlist('KEPT');
  const removing = toggleWatchlist('KEPT');
  await restoreWatchlist('KEPT');
  await removing;
  assert.deepEqual(methods, ['POST', 'DELETE']);
  assert.equal(getWatchlistRecords().some((row) => row.ticker === 'KEPT'), true);
});

test('a DELETE 404 confirms removal and does not resurrect the star', async () => {
  globalThis.fetch = async () => response(null, 404);
  await toggleWatchlist('PINNED');
  assert.equal(getWatchlistRecords().some((row) => row.ticker === 'PINNED'), false);
});
