// The '?' sheet's key list (item 7): its calibration, card and big-chart sections
// are pinned to the vocabularies those keys actually use, so there the sheet can
// neither miss a key nor list a dead one.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { KEY_SECTIONS, keyLabel, keySectionsFor } from './keyMap.js';
import { HOTKEY_TOOLS } from '../../features/calibration/model/calibrationHotkeys.js';
import { CARD_KEYS } from '../../features/screener/model/cardNavigation.js';
import { LENS_ACTION_KEYS } from '../../shared/setup/lensActions.js';

const section = (id) => KEY_SECTIONS.find((s) => s.id === id);
const keysOf = (id) => section(id).rows.flatMap((row) => row.keys);

test('every calibration marking key is on the sheet, and every listed letter is a real one', () => {
  const listed = keysOf('calibration');
  for (const key of [...Object.keys(HOTKEY_TOOLS), 'e', 'Enter', 'Escape', 'ArrowUp', 'ArrowDown']) {
    assert.ok(listed.includes(key), `calibration key ${key} has no row`);
  }
  for (const key of listed.filter((k) => k.length === 1)) {
    assert.ok(Object.hasOwn(HOTKEY_TOOLS, key) || key === 'e', `row for ${key}, which nothing handles`);
  }
});

test('every card move is on the sheet, and every listed key is a real one', () => {
  const listed = keysOf('cards');
  // The focused card's own keys (ScreenerCard): Enter and Space open the big chart, W stars, L likes.
  const cardOwn = ['Enter', ' ', 'w', 'l'];
  for (const key of [...Object.keys(CARD_KEYS), ...cardOwn]) {
    assert.ok(listed.includes(key), `card key ${key} has no row`);
  }
  for (const key of listed) {
    assert.ok(Object.hasOwn(CARD_KEYS, key) || cardOwn.includes(key), `row for ${key}, which nothing handles`);
  }
  // ...and those four are the ones the card's handler really answers (a source check: no DOM harness).
  const card = readFileSync(new URL('../../shared/setup/ScreenerCard.jsx', import.meta.url), 'utf8');
  for (const key of cardOwn) {
    assert.ok(card.includes(`event.key === '${key}'`), `the card does not answer ${JSON.stringify(key)}`);
  }
});

test("the big chart's action keys are on the sheet, and every listed letter is a real one", () => {
  const listed = [...keysOf('lens'), ...keysOf('lens-screener')];
  for (const key of Object.keys(LENS_ACTION_KEYS)) {
    assert.ok(listed.includes(key), `lens key ${key} has no row`);
  }
  for (const key of listed.filter((k) => k.length === 1)) {
    assert.ok(Object.hasOwn(LENS_ACTION_KEYS, key), `row for ${key}, which nothing handles`);
  }
  // T works in every big chart (it needs only the ticker): its row is in the
  // section every lens page shows, not the Screener-only one.
  assert.ok(keysOf('lens').includes('t'), 'T is listed only where the Screener is');
  assert.ok(!keysOf('lens').includes('w') && !keysOf('lens').includes('l'), 'W/L listed where no lens draws a star or heart');
});

test('no key means two things in one section', () => {
  const global = keysOf('global');
  assert.equal(new Set(global).size, global.length, 'global');
  for (const { id } of KEY_SECTIONS.filter((s) => s.id !== 'global')) {
    const keys = [...global, ...keysOf(id)];
    assert.equal(new Set(keys).size, keys.length, id);
  }
});

test('keySectionsFor shows Everywhere plus this page', () => {
  const ids = (pathname) => keySectionsFor(pathname).map((s) => s.id);
  assert.deepEqual(ids('/screener'), ['global', 'cards', 'lens', 'lens-screener']);
  assert.deepEqual(ids('/calibration'), ['global', 'calibration']);
  assert.deepEqual(ids('/watchlist'), ['global', 'watchlist']);
  // Home and the Archive open a big chart too ('/' is Home itself, never every page).
  assert.deepEqual(ids('/'), ['global', 'lens']);
  assert.deepEqual(ids('/home'), ['global', 'lens']);
  assert.deepEqual(ids('/archive'), ['global', 'lens']);
  assert.deepEqual(ids('/portfolio'), ['global']);
});

test('keyLabel', () => {
  assert.equal(keyLabel('ArrowLeft'), '←');
  assert.equal(keyLabel('ArrowDown'), '↓');
  assert.equal(keyLabel('Escape'), 'Esc');
  assert.equal(keyLabel('Enter'), 'Enter');
  assert.equal(keyLabel('j'), 'J');
  assert.equal(keyLabel('/'), '/');
  assert.equal(keyLabel('?'), '?');
});
