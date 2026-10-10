import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { ANALYTICS_OPEN_KEY, beginLatestCall, readAnalyticsOpen, writeAnalyticsOpen } from './analyticsFold.js';

const memoryStorage = () => {
  const map = new Map();
  return {
    map,
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => { map.set(key, value); },
  };
};

const throwing = () => ({
  getItem: () => { throw new Error('storage blocked'); },
  setItem: () => { throw new Error('quota exceeded'); },
});

test('collapsed by default: nothing stored reads as closed', () => {
  assert.equal(readAnalyticsOpen(memoryStorage()), false);
});

test('only the stored open flag reads as open', () => {
  const storage = memoryStorage();
  storage.map.set(ANALYTICS_OPEN_KEY, '1');
  assert.equal(readAnalyticsOpen(storage), true);
  storage.map.set(ANALYTICS_OPEN_KEY, '0');
  assert.equal(readAnalyticsOpen(storage), false);
});

test('a write is read back, under the one key', () => {
  const storage = memoryStorage();
  writeAnalyticsOpen(true, storage);
  assert.deepEqual([...storage.map.keys()], [ANALYTICS_OPEN_KEY]);
  assert.equal(readAnalyticsOpen(storage), true);
  writeAnalyticsOpen(false, storage);
  assert.equal(readAnalyticsOpen(storage), false);
});

test('blocked or full storage never throws', () => {
  assert.equal(readAnalyticsOpen(throwing()), false);
  assert.doesNotThrow(() => writeAnalyticsOpen(true, throwing()));
});

// Chrome with site data blocked throws on the window.localStorage GETTER, before
// any method is reached; the accessor must sit inside the try, not in a default
// parameter.
test('a localStorage accessor that throws (site data blocked) is caught too', () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    get() { throw new Error('SecurityError: access denied'); },
  });
  try {
    assert.equal(readAnalyticsOpen(), false);
    assert.doesNotThrow(() => writeAnalyticsOpen(true));
  } finally {
    if (original) Object.defineProperty(globalThis, 'localStorage', original);
    else delete globalThis.localStorage;
  }
});

// The fold is opened while Update Forward Returns runs: the opening fetch reads the
// archive before the update commits, the refresh after it reads the finished one,
// and the opening fetch lands LAST. It must write nothing.
test('only the newest analytics fetch may write', () => {
  const generation = { current: 0 };
  const opening = beginLatestCall(generation);
  assert.equal(opening(), true);
  const refresh = beginLatestCall(generation);
  assert.equal(opening(), false, 'the superseded opening fetch would put the older numbers back');
  assert.equal(refresh(), true);
});

// The hook has no test of its own: every write it makes (both panels and the
// 'done' that ends the loading state) waits on that check.
test('useArchiveAnalytics checks it is the newest call before every write', () => {
  const src = readFileSync(new URL('../hooks/useArchiveAnalytics.js', import.meta.url), 'utf8');
  assert.match(src, /const isLatest = beginLatestCall\(generation\);/);
  for (const write of ['setCalibration(', 'setEquityCurve(', "setStatus('done')"]) {
    const total = src.split(write).length - 1;
    const guarded = src.split(`if (isLatest()) ${write}`).length - 1;
    assert.ok(total >= 1 && guarded === total, `${write} is written without the newest-call check`);
  }
});
