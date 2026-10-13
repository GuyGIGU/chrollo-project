// The big chart's W / L / T keys and its one TradingView address (operator
// 2026-10-03, suggestion #1).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { LENS_ACTION_KEYS, lensKeyAction, tradingViewUrl } from './lensActions.js';

const ev = (over = {}) => ({
  key: 'w', repeat: false, target: { tagName: 'DIV' },
  ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...over,
});

test('W, L, T and F map to the four acts, in either case', () => {
  assert.equal(lensKeyAction(ev({ key: 'w' })), 'watch');
  assert.equal(lensKeyAction(ev({ key: 'W', shiftKey: true })), 'watch');
  assert.equal(lensKeyAction(ev({ key: 'l' })), 'like');
  assert.equal(lensKeyAction(ev({ key: 'L' })), 'like');
  assert.equal(lensKeyAction(ev({ key: 't' })), 'tradingview');
  assert.equal(lensKeyAction(ev({ key: 'f' })), 'fundamentals');
  assert.equal(lensKeyAction(ev({ key: 'F', shiftKey: true })), 'fundamentals');
  assert.deepEqual(Object.values(LENS_ACTION_KEYS).sort(), ['fundamentals', 'like', 'tradingview', 'watch']);
});

test('a held key does not repeat the act (holding W must not flicker the star)', () => {
  assert.equal(lensKeyAction(ev({ repeat: true })), null);
});

test("Ctrl / Cmd / Alt + W, L, T are the browser's", () => {
  for (const mod of ['ctrlKey', 'metaKey', 'altKey']) {
    for (const key of ['w', 'l', 't']) {
      assert.equal(lensKeyAction(ev({ key, [mod]: true })), null, `${mod}+${key}`);
    }
  }
});

test('keys typed into a field (the "what\'s off?" box) are text', () => {
  for (const tagName of ['INPUT', 'TEXTAREA', 'SELECT']) {
    assert.equal(lensKeyAction(ev({ target: { tagName } })), null, tagName);
  }
  assert.equal(lensKeyAction(ev({ target: { tagName: 'DIV', isContentEditable: true } })), null);
  assert.equal(lensKeyAction(ev({ target: { tagName: 'BUTTON' } })), 'watch', 'a focused button is not a field');
});

test('any other key, or no event at all, is nothing', () => {
  for (const key of ['j', 'Enter', 'Escape', 'ArrowRight', ' ', 'Tab']) {
    assert.equal(lensKeyAction(ev({ key })), null, key);
  }
  assert.equal(lensKeyAction(null), null);
  assert.equal(lensKeyAction(undefined), null);
});

test('tradingViewUrl encodes the symbol', () => {
  assert.equal(tradingViewUrl('DOCU'), 'https://www.tradingview.com/chart/?symbol=DOCU');
  assert.equal(tradingViewUrl('BRK.B'), 'https://www.tradingview.com/chart/?symbol=BRK.B');
  assert.equal(tradingViewUrl('^GSPC'), 'https://www.tradingview.com/chart/?symbol=%5EGSPC');
});

test("Home's BridgeOut builds its link here, not inline", () => {
  const src = readFileSync(new URL('../../features/home/components/BridgeOut.jsx', import.meta.url), 'utf8');
  assert.match(src, /import \{ tradingViewUrl \} from '[./]+shared\/setup\/lensActions'/);
  assert.match(src, /href=\{tradingViewUrl\(ticker\)\}/);
  assert.doesNotMatch(src, /tradingview\.com/i);
});
