// Council review 2026-09-07, finding 9: the Action Center said
// "✓ Nothing needs action right now" on its first paint, before any of its three
// sources had answered, and again when one of them had FAILED. These pin the
// rule that the all-clear is reachable ONLY from a fully-answered read.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  actionCenterReadiness,
  countLabel,
  emptyStateLine,
  partialReadNote,
} from './actionCenterState.js';
import { livePriceStatus } from '../../watchlist/model/livePriceStatus.js';

const ALL_ANSWERED = { risk: 'ready', prices: 'ready', screener: 'ready' };
const ALL_CLEAR = '✓ Nothing needs action right now — no open risk, triggers, or fresh S-tier setups.';

test('the first paint — nothing has answered — never claims safety', () => {
  // The literal initial statuses: useLiveRisk starts 'idle', useLivePrices
  // 'loading' (watchlist not yet fetched), screenerStore 'loading'.
  const readiness = actionCenterReadiness({ risk: 'idle', prices: 'loading', screener: 'loading' });
  assert.equal(readiness.ready, false);
  const line = emptyStateLine(readiness);
  assert.notEqual(line.text, ALL_CLEAR);
  assert.match(line.text, /^Reading /);
  assert.equal(countLabel(0, readiness), 'checking…');
});

test('a failed source says it cannot say, not that all is clear', () => {
  const readiness = actionCenterReadiness({ ...ALL_ANSWERED, prices: 'error' });
  assert.deepEqual(readiness.failed, ['live prices']);
  const line = emptyStateLine(readiness);
  assert.notEqual(line.text, ALL_CLEAR);
  assert.match(line.text, /Cannot say/);
  assert.equal(line.color, 'var(--danger)');
  assert.equal(countLabel(0, readiness), 'cannot say');
});

test('the all-clear is reachable only when every source answered', () => {
  const readiness = actionCenterReadiness(ALL_ANSWERED);
  assert.equal(readiness.ready, true);
  assert.equal(emptyStateLine(readiness).text, ALL_CLEAR);
  assert.equal(countLabel(0, readiness), 'all clear');
  assert.equal(partialReadNote(readiness), null);
});

test('the legitimately-empty statuses count as answered', () => {
  // A stale-but-served risk read, an empty watchlist, a scan that matched
  // nothing (or has never run) are ANSWERS, not silence.
  for (const statuses of [
    { risk: 'stale', prices: 'idle', screener: 'empty' },
    { risk: 'ready', prices: 'idle', screener: 'never_scanned' },
  ]) {
    assert.equal(actionCenterReadiness(statuses).ready, true, JSON.stringify(statuses));
  }
});

test('a count from a partial read is marked as a floor, not a total', () => {
  const partial = actionCenterReadiness({ ...ALL_ANSWERED, screener: 'loading' });
  assert.equal(countLabel(3, partial), '3+ need a look');
  assert.equal(partialReadNote(partial), 'still reading the latest scan');
  const whole = actionCenterReadiness(ALL_ANSWERED);
  assert.equal(countLabel(3, whole), '3 need a look');
  assert.equal(countLabel(1, whole), '1 needs a look');
});

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
