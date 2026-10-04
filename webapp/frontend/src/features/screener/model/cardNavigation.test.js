// Screener card keys (item 7): which key is a card move, and where it lands.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cardMove, gridColumnCount, nextCardIndex } from './cardNavigation.js';

test("cardMove: arrows and J/K are card moves; W, L, Enter, Space stay the card's own", () => {
  assert.equal(cardMove('ArrowRight'), 'next');
  assert.equal(cardMove('ArrowLeft'), 'prev');
  assert.equal(cardMove('ArrowDown'), 'down');
  assert.equal(cardMove('ArrowUp'), 'up');
  assert.equal(cardMove('j'), 'next');
  assert.equal(cardMove('J'), 'next', 'Caps Lock or Shift still moves');
  assert.equal(cardMove('k'), 'prev');
  assert.equal(cardMove('K'), 'prev');
  for (const key of ['w', 'W', 'l', 'L', 'Enter', ' ', 'h', '/', '?', 'Escape', 'toString']) {
    assert.equal(cardMove(key), null, JSON.stringify(key));
  }
});

// 8 cards, 3 columns:  0 1 2 / 3 4 5 / 6 7
test('left/right and J/K step one card and stop at the ends', () => {
  assert.equal(nextCardIndex('next', 0, 8, 3), 1);
  assert.equal(nextCardIndex('prev', 0, 8, 3), 0);
  assert.equal(nextCardIndex('next', 7, 8, 3), 7);
  assert.equal(nextCardIndex('prev', 5, 8, 3), 4);
});

test('up/down move a whole row', () => {
  assert.equal(nextCardIndex('down', 1, 8, 3), 4);
  assert.equal(nextCardIndex('up', 4, 8, 3), 1);
  assert.equal(nextCardIndex('up', 2, 8, 3), 2);
});

test('down into a short last row lands on its last card', () => {
  assert.equal(nextCardIndex('down', 5, 8, 3), 7);
  assert.equal(nextCardIndex('down', 4, 8, 3), 7);
  assert.equal(nextCardIndex('down', 6, 8, 3), 6);
  assert.equal(nextCardIndex('down', 7, 8, 3), 7);
  // 7 cards:  0 1 2 / 3 4 5 / 6
  assert.equal(nextCardIndex('down', 4, 7, 3), 6);
});

test('no card focused: the first key lands on the first card on screen', () => {
  assert.equal(nextCardIndex('next', -1, 8, 3, 5), 5);
  assert.equal(nextCardIndex('up', -1, 8, 3, 5), 5);
  assert.equal(nextCardIndex('down', -1, 8, 3), 0);
  assert.equal(nextCardIndex('next', -1, 8, 3, 99), 7);
});

test('a missing column count is one column; an empty grid goes nowhere', () => {
  assert.equal(nextCardIndex('down', 0, 3, 0), 1);
  assert.equal(nextCardIndex('down', 0, 3, NaN), 1);
  assert.equal(nextCardIndex('next', 0, 0, 3), null);
});

test('gridColumnCount counts the resolved tracks', () => {
  assert.equal(gridColumnCount('618px 618px 618px'), 3);
  assert.equal(gridColumnCount('620px 620px 620px 620px'), 4);
  assert.equal(gridColumnCount('  590px   590px '), 2);
  assert.equal(gridColumnCount('none'), 1);
  assert.equal(gridColumnCount(''), 1);
  assert.equal(gridColumnCount(undefined), 1);
});
