import test from 'node:test';
import assert from 'node:assert/strict';
import { createGlanceCache } from './glanceCache.js';

test('a repeat hover is free — the loader runs once per key', async () => {
  const cache = createGlanceCache();
  let calls = 0;
  const load = () => cache.load('a', () => { calls += 1; return 'first'; });

  assert.equal(await load(), 'first');
  assert.equal(await load(), 'first');
  assert.equal(calls, 1);
});

test('concurrent hovers on one key share a single in-flight request', async () => {
  const cache = createGlanceCache();
  let calls = 0;
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  const loader = () => { calls += 1; return gate; };

  // The in-flight entry is registered SYNCHRONOUSLY (the loader itself runs a
  // microtask later, which is what turns a synchronous throw into a rejection),
  // so a second hover arriving in the same tick still joins rather than racing.
  const a = cache.load('k', loader);
  const b = cache.load('k', loader);
  assert.equal(a, b, 'both hovers must receive the very same promise');

  release('value');
  assert.deepEqual(await Promise.all([a, b]), ['value', 'value']);
  assert.equal(calls, 1);
});

test('a failed load is not cached, so a later hover may retry', async () => {
  const cache = createGlanceCache();
  let calls = 0;
  const loader = () => {
    calls += 1;
    return calls === 1 ? Promise.reject(new Error('boom')) : 'recovered';
  };

  await assert.rejects(() => cache.load('k', loader));
  assert.equal(cache.has('k'), false);
  assert.equal(await cache.load('k', loader), 'recovered');
  assert.equal(calls, 2);
});

test('eviction drops the OLDEST entry one at a time, never the whole map', async () => {
  const cache = createGlanceCache(3);
  for (const key of ['a', 'b', 'c', 'd']) {
    await cache.load(key, () => key.toUpperCase());
  }
  assert.equal(cache.size(), 3);
  assert.equal(cache.has('a'), false);   // oldest evicted
  assert.equal(cache.has('b'), true);    // the rest of the sweep survives
  assert.equal(cache.has('d'), true);
});

test('re-reading a key refreshes its recency', async () => {
  const cache = createGlanceCache(2);
  await cache.load('a', () => 'A');
  await cache.load('b', () => 'B');
  cache.get('a');                        // touch: 'a' is now the newest
  await cache.load('c', () => 'C');
  assert.equal(cache.has('a'), true);
  assert.equal(cache.has('b'), false);   // 'b' became the oldest, not 'a'
});

test('a synchronous throw inside the loader rejects rather than escaping', async () => {
  const cache = createGlanceCache();
  await assert.rejects(() => cache.load('k', () => { throw new Error('sync'); }));
  assert.equal(cache.size(), 0);
});

test('clear empties both resolved entries and in-flight promises', async () => {
  const cache = createGlanceCache();
  await cache.load('a', () => 'A');
  cache.clear();
  assert.equal(cache.size(), 0);
  let calls = 0;
  await cache.load('a', () => { calls += 1; return 'again'; });
  assert.equal(calls, 1);
});
