// Council review 2026-09-07, finding 10: a dismissed risk alert stayed silenced
// for the whole session on an id that RECURS, so the second — real — breach
// never showed on a live-money surface. The episode rule below is the fix; these
// pin it.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  DISMISS_MAX_MS,
  SNOOZE_MS,
  isMuted,
  pruneDismissed,
  selectActiveAlerts,
} from './alertMuting.js';

const stopAlert = (tradeId = 7, level = 'breached') => ({
  id: `${tradeId}:stop:${level}`,
  tradeId,
  title: 'AAPL through stop',
});

const T0 = 1_700_000_000_000;

test('a dismissed alert is hidden while it keeps firing', () => {
  const alert = stopAlert();
  const dismissed = { [alert.id]: T0 };
  assert.deepEqual(selectActiveAlerts([alert], dismissed, {}, T0 + 1000), []);
  // still firing one minute later -> the dismissal survives the prune
  assert.equal(pruneDismissed(dismissed, [alert], T0 + 60_000), dismissed);
});

test('the SECOND breach after a dismissal is visible again', () => {
  const alert = stopAlert();
  let dismissed = { [alert.id]: T0 };

  // Price recovers: the alert stops firing. The episode is over.
  dismissed = pruneDismissed(dismissed, [], T0 + 60_000);
  assert.deepEqual(dismissed, {});

  // Price breaches again — SAME id, minted fresh by tradeTableUtils.
  const reBreach = stopAlert();
  assert.equal(reBreach.id, alert.id, 'the id must recur, or this test proves nothing');
  assert.deepEqual(
    selectActiveAlerts([reBreach], dismissed, {}, T0 + 120_000).map((a) => a.id),
    [reBreach.id],
  );
});

test('a dismissal expires on its own backstop even while the alert keeps firing', () => {
  const alert = stopAlert();
  const dismissed = { [alert.id]: T0 };
  assert.equal(isMuted(alert.id, dismissed, {}, T0 + DISMISS_MAX_MS - 1), true);
  assert.equal(isMuted(alert.id, dismissed, {}, T0 + DISMISS_MAX_MS), false);
  assert.deepEqual(pruneDismissed(dismissed, [alert], T0 + DISMISS_MAX_MS), {});
});

test('pruning one dismissal leaves the others alone', () => {
  const kept = stopAlert(7);
  const gone = stopAlert(9);
  const dismissed = { [kept.id]: T0, [gone.id]: T0 };
  assert.deepEqual(pruneDismissed(dismissed, [kept], T0 + 1000), { [kept.id]: T0 });
});

test('snooze keeps its own time-based contract', () => {
  const alert = stopAlert();
  const snoozed = { [alert.id]: T0 + SNOOZE_MS };
  assert.equal(isMuted(alert.id, {}, snoozed, T0 + SNOOZE_MS - 1), true);
  assert.equal(isMuted(alert.id, {}, snoozed, T0 + SNOOZE_MS), false);
  // and a snooze is NOT an episode dismissal — pruning never touches it
  assert.deepEqual(pruneDismissed({}, [], T0), {});
});
