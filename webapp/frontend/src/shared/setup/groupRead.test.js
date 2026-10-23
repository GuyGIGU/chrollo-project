import assert from 'node:assert/strict';
import { test } from 'node:test';

import { groupCardText, groupCells, groupSentence, groupTitle, hasGroupRead } from './groupRead.js';

const HOTEL = { industry: 'REIT - Hotel & Motel', fired_tonight: 7, fired_10d: 8, members: 9 };

test('a row with a group reads it; an older payload and a name without an industry do not', () => {
  assert.equal(hasGroupRead({ group: HOTEL }), true);
  assert.equal(hasGroupRead({ group: null }), false);
  assert.equal(hasGroupRead({}), false);
  assert.equal(hasGroupRead({ group: { industry: '', fired_tonight: 1 } }), false);
});

test('the sentence and the card text are the counts in plain words', () => {
  assert.equal(groupSentence(HOTEL), '7 of 9 fired tonight, 8 in the last 10 days');
  assert.equal(groupSentence({ ...HOTEL, fired_10d: null }), '7 of 9 fired tonight');
  assert.equal(groupCardText(HOTEL), '7 of 9');
});

test('a missing count prints the one null guard, never NaN or undefined', () => {
  assert.equal(groupSentence({ industry: 'Steel' }), '—');
  assert.equal(groupCardText({ industry: 'Steel', fired_tonight: 2 }), '—');
  assert.equal(groupCardText(undefined), '—');
});

test('the grid cells name the industry and the counts, and say they are shown only', () => {
  const cells = groupCells({ group: HOTEL });
  assert.deepEqual(cells.map((c) => c.k), ['Group', 'Group fired']);
  assert.equal(cells[0].v, 'REIT - Hotel & Motel');
  assert.equal(cells[1].v, '7 of 9 tonight · 8 in 10d');
  assert.match(cells[1].title, /Shown only/);
  assert.match(groupTitle(HOTEL), /^REIT - Hotel & Motel: 7 of 9 fired tonight, 8 in the last 10 days/);
});
