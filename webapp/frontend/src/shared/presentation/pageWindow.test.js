// The one pager's slot rule (2026-10-03 UI pass, item 8): seven fixed slots past
// seven pages, so the pager never changes width and Next never moves; a gap
// stands for two or more hidden pages, never one.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PAGE_GAP, pageWindow } from './pageWindow.js';

const G = PAGE_GAP;

test('seven pages or fewer shows every page', () => {
  assert.deepEqual(pageWindow(1, 1), [1]);
  assert.deepEqual(pageWindow(3, 7), [1, 2, 3, 4, 5, 6, 7]);
  assert.deepEqual(pageWindow(7, 7), [1, 2, 3, 4, 5, 6, 7]);
});

test('a middle page shows one neighbour each side between two gaps', () => {
  assert.deepEqual(pageWindow(10, 20), [1, G, 9, 10, 11, G, 20]);
});

test('the start run ends at page 4; page 5 already opens the middle window', () => {
  assert.deepEqual(pageWindow(4, 20), [1, 2, 3, 4, 5, G, 20]);
  assert.deepEqual(pageWindow(5, 20), [1, G, 4, 5, 6, G, 20]);
});

test('the end run starts at N-3; N-4 is still the middle window', () => {
  assert.deepEqual(pageWindow(17, 20), [1, G, 16, 17, 18, 19, 20]);
  assert.deepEqual(pageWindow(16, 20), [1, G, 15, 16, 17, G, 20]);
});

test('past seven pages: always seven slots, first and last, the page, and no one-page gap', () => {
  for (let n = 8; n <= 60; n += 1) {
    for (let p = 1; p <= n; p += 1) {
      const slots = pageWindow(p, n);
      const at = `pageWindow(${p}, ${n}) = [${slots.join(', ')}]`;
      assert.equal(slots.length, 7, `${at}: not seven slots`);
      assert.equal(slots[0], 1, `${at}: first slot is not page 1`);
      assert.equal(slots[6], n, `${at}: last slot is not page ${n}`);
      assert.ok(slots.includes(p), `${at}: the current page is missing`);
      const numbers = slots.filter((slot) => slot !== G);
      for (let i = 1; i < numbers.length; i += 1) {
        assert.ok(numbers[i] > numbers[i - 1], `${at}: pages not strictly increasing`);
      }
      slots.forEach((slot, i) => {
        if (slot !== G) return;
        assert.ok(slots[i + 1] - slots[i - 1] >= 3, `${at}: a gap hides fewer than two pages`);
      });
    }
  }
});
