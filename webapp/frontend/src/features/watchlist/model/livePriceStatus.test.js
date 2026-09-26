// The watchlist's live-price status moved here from the Action Center (it is a
// watchlist concern the Action Center reads); its assertions moved with it.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { livePriceStatus } from './livePriceStatus.js';

test('the price status folds in the watchlist load state', () => {
  // An unloaded watchlist yields an empty ticker set that looks exactly like a
  // genuinely empty one — the trap the Action Center used to fall into.
  assert.equal(livePriceStatus('loading', '', 'loading'), 'loading');
  assert.equal(livePriceStatus('idle', '', 'loading'), 'loading');
  assert.equal(livePriceStatus('error', '', 'loading'), 'error');
  assert.equal(livePriceStatus('ready', '', 'loading'), 'idle');   // confirmed empty
  assert.equal(livePriceStatus('ready', 'AAPL', 'loading'), 'loading');
  assert.equal(livePriceStatus('ready', 'AAPL', 'ready'), 'ready');
  assert.equal(livePriceStatus('ready', 'AAPL', 'error'), 'error');
});
