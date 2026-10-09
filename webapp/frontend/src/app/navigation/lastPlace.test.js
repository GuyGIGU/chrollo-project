// The top nav returns to a surface's last address (operator 2026-10-03, "never
// lose your place"): leave the screener on page 2 of tier A, come back through
// the nav, and land on page 2 of tier A. The memory is module state, so each
// test uses pathnames no other test touches.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { goesNowhere, placeFor, rememberPlace } from './lastPlace.js';

test('a surface never visited links to its bare path', () => {
  assert.equal(placeFor('/archive', { pathname: '/watchlist', search: '' }), '/archive');
});

test('another surface links back to the address it was left at', () => {
  rememberPlace('/screener', '?tier=A&p=2');
  assert.equal(placeFor('/screener', { pathname: '/watchlist', search: '' }), '/screener?tier=A&p=2');
});

test('the tab you are on points at where you are now, not at the memory', () => {
  rememberPlace('/calibration', '?old=1');
  assert.equal(placeFor('/calibration', { pathname: '/calibration', search: '?now=1' }), '/calibration?now=1');
});

// On the ETF board's XLK drill-down, a click on the Screener tab (the tab he is on) replaced the
// entry with no state, so the drill-down's Back found no tag and left a duplicate board behind it.
test('a plain click on the tab you are on goes nowhere; a new-tab click and other tabs still go', () => {
  const here = { pathname: '/screener', search: '?u=sectors&dd=XLK' };
  const plain = { button: 0 };
  assert.equal(goesNowhere(plain, '/screener', here), true);
  assert.equal(goesNowhere(plain, '/watchlist', here), false);
  for (const modified of [{ button: 1 }, { button: 0, ctrlKey: true }, { button: 0, metaKey: true },
    { button: 0, shiftKey: true }, { button: 0, altKey: true }]) {
    assert.equal(goesNowhere(modified, '/screener', here), false, JSON.stringify(modified));
  }
});

// No DOM harness, so the top nav's own handler is pinned as source (like uiScale.test.js).
test('the top nav swallows the click that goes nowhere, before the leave guard is asked', () => {
  const bar = readFileSync(new URL('../components/AppTopbar.jsx', import.meta.url), 'utf8');
  const handler = bar.slice(bar.indexOf('const handleClick = (event) => {'));
  assert.match(handler, /^const handleClick = \(event\) => \{\s*if \(goesNowhere\(event, to, location\)\) \{\s*event\.preventDefault\(\);\s*return;\s*\}\s*if \(!shouldInterceptNavClick\(/);
  assert.match(bar, /<NavLink\s+to=\{target\}[^>]*\bonClick=\{handleClick\}/);
});
