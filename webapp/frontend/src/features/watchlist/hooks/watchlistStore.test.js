import assert from 'node:assert/strict';
import test from 'node:test';
import { fetchWatchlist, getWatchlistRecords, markWatch, restoreWatchlist, toggleWatchlist } from './watchlistStore.js';

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

test('a typed-in save sends its side, and the optimistic row carries it', async () => {
  const save = deferred();
  let body = null;
  globalThis.fetch = (_url, options) => { body = JSON.parse(options.body); return save.promise; };
  const saving = toggleWatchlist('SHORTY', { universe: 'us_stocks', scanDate: '2026-10-23', side: 'S' });
  assert.deepEqual(body, { universe: 'us_stocks', scan_date: '2026-10-23', side: 'S' });
  assert.equal(getWatchlistRecords().find((row) => row.ticker === 'SHORTY').side, 'S');
  save.resolve(response({ ...saved('SHORTY', 7), side: 'S', ready: 0 }));
  await saving;
});

test('quick ready clicks write in order and the last answer stands', async () => {
  globalThis.fetch = async () => response({ ...saved('MARKED', 8), ready: 0 });
  await toggleWatchlist('MARKED');
  const writes = [];
  globalThis.fetch = (_url, options) => {
    const pending = deferred();
    writes.push({ body: JSON.parse(options.body), ...pending });
    return pending.promise;
  };
  const first = markWatch('MARKED', { ready: 1 });
  const second = markWatch('MARKED', { ready: 2 });
  assert.equal(getWatchlistRecords().find((row) => row.ticker === 'MARKED').ready, 2); // optimistic
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(writes.length, 1); // the second waits for the first
  writes[0].resolve(response({ ...saved('MARKED', 8), ready: 1 }));
  await first;
  assert.equal(getWatchlistRecords().find((row) => row.ticker === 'MARKED').ready, 2); // a stale answer never lands
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(writes.map((write) => write.body), [{ ready: 1 }, { ready: 2 }]);
  writes[1].resolve(response({ ...saved('MARKED', 8), ready: 2 }));
  await second;
  assert.equal(getWatchlistRecords().find((row) => row.ticker === 'MARKED').ready, 2);
});

test('a mark clicked while the star is still saving waits for the save', async () => {
  const save = deferred();
  const methods = [];
  globalThis.fetch = (_url, options) => {
    methods.push(options?.method);
    return options?.method === 'POST' ? save.promise : Promise.resolve(response({ ...saved('EARLY', 10), ready: 1 }));
  };
  const saving = toggleWatchlist('EARLY');
  const marking = markWatch('EARLY', { ready: 1 });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(methods, ['POST']); // a PATCH now would find no row yet
  save.resolve(response({ ...saved('EARLY', 10), ready: 0 }));
  await saving;
  await marking;
  assert.deepEqual(methods, ['POST', 'PATCH']);
  assert.equal(getWatchlistRecords().find((row) => row.ticker === 'EARLY').ready, 1);
});

test('a GET issued while a mark is saving cannot put the old mark back', async () => {
  globalThis.fetch = async () => response({ ...saved('POLLED', 11), ready: 0 });
  await toggleWatchlist('POLLED');
  const mark = deferred();
  const read = deferred();
  globalThis.fetch = (_url, options) => (options?.method === 'PATCH' ? mark.promise : read.promise);
  const marking = markWatch('POLLED', { ready: 2 });
  await new Promise((resolve) => setTimeout(resolve, 0));
  const loading = fetchWatchlist();
  mark.resolve(response({ ...saved('POLLED', 11), ready: 2 }));
  await marking;
  read.resolve(response([{ ...saved('POLLED', 11), ready: 0 }])); // read before the mark landed
  await loading;
  assert.equal(getWatchlistRecords().find((row) => row.ticker === 'POLLED').ready, 2);
});

test('a refused mark puts the previous mark back', async () => {
  globalThis.fetch = async () => response({ ...saved('REFUSED', 9), side: 'L', ready: 1 });
  await toggleWatchlist('REFUSED');
  globalThis.fetch = async () => response(null, 404);
  await markWatch('REFUSED', { side: 'S' });
  const row = getWatchlistRecords().find((r) => r.ticker === 'REFUSED');
  assert.deepEqual([row.side, row.ready], ['L', 1]);
});
