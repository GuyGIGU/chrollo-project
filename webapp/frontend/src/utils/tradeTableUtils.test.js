import assert from 'node:assert/strict';
import test from 'node:test';
import { deriveTradeAlerts, deriveTradeRow } from './tradeTableUtils.js';

const baseTrade = {
  id: 1,
  opening_date: '2026-06-01',
  direction: 'LONG',
  ticker: 'MSFT',
  entry_price: 100,
  stop_loss: 90,
  quantity: 10,
  commissions: 0,
  pnl: null,
  actions_json: null,
};

const priceFor = (price) => () => ({ price, source: 'yf' });

const closeTo = (actual, expected) => {
  assert.ok(Math.abs(actual - expected) < 0.000001, `${actual} should equal ${expected}`);
};

test('deriveTradeRow calculates live stop distance and next target for a long trade', () => {
  const row = deriveTradeRow(
    {
      ...baseTrade,
      t1_price: 110,
      t2_price: 120,
    },
    priceFor(105),
  );

  closeTo(row.rValue, 0.5);
  closeTo(row.rToStop, 1.5);
  closeTo(row.distToStopPct, (105 - 90) / 105 * 100);
  assert.equal(row.nextTarget.label, 'T1');
  closeTo(row.distToTargetPct, (110 - 105) / 105 * 100);
  assert.equal(row.targetLadder[0].isNext, true);
});

test('deriveTradeRow advances the next target after prior targets are hit', () => {
  const row = deriveTradeRow(
    {
      ...baseTrade,
      t1_price: 110,
      t2_price: 120,
    },
    priceFor(112),
  );

  assert.equal(row.targetLadder[0].hit, true);
  assert.equal(row.targetLadder[0].isNext, false);
  assert.equal(row.nextTarget.label, 'T2');
  closeTo(row.distToTargetPct, (120 - 112) / 112 * 100);
});

test('deriveTradeRow calculates stop and target distance for a short trade', () => {
  const row = deriveTradeRow(
    {
      ...baseTrade,
      direction: 'SHORT',
      stop_loss: 110,
      t1_price: 90,
    },
    priceFor(95),
  );

  closeTo(row.rValue, 0.5);
  closeTo(row.rToStop, 1.5);
  closeTo(row.distToStopPct, (110 - 95) / 95 * 100);
  assert.equal(row.nextTarget.label, 'T1');
  closeTo(row.distToTargetPct, (95 - 90) / 95 * 100);
});

test('deriveTradeRow leaves live risk cockpit fields empty without a stop or targets', () => {
  const row = deriveTradeRow(
    {
      ...baseTrade,
      stop_loss: 0,
    },
    priceFor(105),
  );

  assert.equal(row.rValue, null);
  assert.equal(row.rToStop, null);
  assert.equal(row.distToStopPct, null);
  assert.equal(row.nextTarget, null);
  assert.deepEqual(row.targetLadder, []);
});

test('deriveTradeRow keeps R-to-stop price-based on a scaled-out (partial) position', () => {
  const row = deriveTradeRow(
    {
      ...baseTrade,
      actions_json: JSON.stringify([
        { side: 'SELL', quantity: 5, price: 110, date: '2026-06-05' },
      ]),
    },
    priceFor(105),
  );

  assert.equal(row.openQty, 5);
  assert.equal(row.status, 'partial');
  closeTo(row.rValue, 0.75);
  // Price-based: (105 - 90) / (100 - 90) = 1.5, independent of the +50 booked on
  // the partial. The retired `rValue + 1` would read 2.5 here (realized P&L leaks in).
  closeTo(row.rToStop, 1.5);
});

test('deriveTradeAlerts raises stop warnings by severity', () => {
  const warning = deriveTradeAlerts([baseTrade], priceFor(95));
  const danger = deriveTradeAlerts([baseTrade], priceFor(92));
  const breached = deriveTradeAlerts([baseTrade], priceFor(89));

  assert.equal(warning[0].level, 'warning');
  assert.equal(warning[0].kind, 'stop');
  assert.equal(danger[0].level, 'danger');
  assert.equal(breached[0].level, 'critical');
});

test('deriveTradeAlerts raises next-target proximity alerts', () => {
  const alerts = deriveTradeAlerts(
    [{
      ...baseTrade,
      t1_price: 110,
    }],
    priceFor(108),
  );

  assert.equal(alerts.length, 1);
  assert.equal(alerts[0].kind, 'target');
  assert.equal(alerts[0].targetLabel, 'T1');
});

test('deriveTradeAlerts raises target-hit alerts for the latest reached target', () => {
  const alerts = deriveTradeAlerts(
    [{
      ...baseTrade,
      t1_price: 110,
      t2_price: 120,
    }],
    priceFor(112),
  );

  assert.equal(alerts.length, 1);
  assert.equal(alerts[0].kind, 'target');
  assert.equal(alerts[0].targetLabel, 'T1');
  assert.equal(alerts[0].targetState, 'hit');
  assert.match(alerts[0].title, /hit T1/);
});

test('deriveTradeAlerts ignores closed trades and missing live quotes', () => {
  const closedAlerts = deriveTradeAlerts(
    [{
      ...baseTrade,
      actions_json: JSON.stringify([
        { side: 'SELL', quantity: 10, price: 101, date: '2026-06-10' },
      ]),
    }],
    priceFor(null),
  );
  const noQuoteAlerts = deriveTradeAlerts(
    [{
      ...baseTrade,
      t1_price: 110,
    }],
    priceFor(null),
  );

  assert.deepEqual(closedAlerts, []);
  assert.deepEqual(noQuoteAlerts, []);
});
