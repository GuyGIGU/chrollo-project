import assert from 'node:assert/strict';
import test from 'node:test';
import { buildTradeAlerts, deriveTradeAlerts, deriveTradeRow } from './tradeTableUtils.js';

// `deriveTradeRow` is now PRICE-INDEPENDENT: it derives status, the fill ledger
// (partials / VWAP / realized P&L), the R basis and the target prices from the
// stored trade alone. The live-price overlay (live price, unrealized P&L,
// R-multiple, distance-to-stop, stop tone) is owned by the backend single source
// of truth and verified in `tests/test_trade_risk.py` (Python parity test).
// `buildTradeAlerts` / `deriveTradeAlerts` operate on whatever derived row the
// `riskFor` accessor supplies, so they are exercised here with injected rows.

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

const closeTo = (actual, expected) => {
  assert.ok(Math.abs(actual - expected) < 0.000001, `${actual} should equal ${expected}`);
};

test('deriveTradeRow derives an open status + price-independent stop geometry', () => {
  const row = deriveTradeRow({ ...baseTrade, t1_price: 110 });
  assert.equal(row.status, 'open');
  closeTo(row.stopPct, 10);          // |100 - 90| / 100 * 100
  closeTo(row.riskDistance, 10);     // |100 - 90|
  closeTo(row.stopVal, 90);
  assert.equal(row.currentExit, null);   // no live price client-side
  assert.equal(row.rToStop, null);
  assert.equal(row.targetLadder[0].price, 110);
});

test('deriveTradeRow anchors riskDistance to planned_stop when recorded', () => {
  const row = deriveTradeRow({ ...baseTrade, stop_loss: 95, planned_stop: 90 });
  closeTo(row.stopVal, 95);          // the working stop drives distance + tone
  closeTo(row.plannedStopVal, 90);
  closeTo(row.riskDistance, 10);     // entry 100 -> planned 90 = original 1R risk
});

test('deriveTradeRow books realized P&L and a win on a fully closed cycle', () => {
  const row = deriveTradeRow({
    ...baseTrade,
    actions_json: JSON.stringify([{ side: 'SELL', quantity: 10, price: 115, date: '2026-06-09' }]),
  });
  assert.equal(row.status, 'win');
  closeTo(row.pnl, 150);             // (115 - 100) * 10
  closeTo(row.rValue, 1.5);          // 150 / (10 * 10)
  assert.equal(row.position, 0);
});

test('deriveTradeRow tracks a scaled-out (partial) position', () => {
  const row = deriveTradeRow({
    ...baseTrade,
    actions_json: JSON.stringify([{ side: 'SELL', quantity: 5, price: 110, date: '2026-06-05' }]),
  });
  assert.equal(row.status, 'partial');
  assert.equal(row.openQty, 5);
  closeTo(row.pnl, 50);              // realized on the 5 sold: (110 - 100) * 5
});

test('deriveTradeRow leaves R fields empty without a stop', () => {
  const row = deriveTradeRow({ ...baseTrade, stop_loss: 0 });
  assert.equal(row.stopVal, null);
  assert.equal(row.riskDistance, null);
  assert.equal(row.rValue, null);
});

// The live overlay row (server-shaped) drives the alert thresholds.
const liveRow = (over) => ({
  status: 'open', position: 10, rToStop: null, stopVal: 90, distToStopPct: null,
  nextTarget: null, targetLadder: [], ...over,
});

test('buildTradeAlerts raises stop alerts by severity from the live row', () => {
  const warn = buildTradeAlerts(baseTrade, liveRow({ rToStop: 0.4, distToStopPct: 4 }));
  const danger = buildTradeAlerts(baseTrade, liveRow({ rToStop: 0.2, distToStopPct: 2 }));
  const breached = buildTradeAlerts(baseTrade, liveRow({ rToStop: -0.1, distToStopPct: -1 }));
  assert.equal(warn[0].level, 'warning');
  assert.equal(danger[0].level, 'danger');
  assert.equal(breached[0].level, 'critical');
});

test('deriveTradeAlerts pulls each trade row through riskFor', () => {
  const riskFor = () => liveRow({ rToStop: -0.1, distToStopPct: -1 });
  const alerts = deriveTradeAlerts([baseTrade], riskFor);
  assert.equal(alerts.length, 1);
  assert.equal(alerts[0].kind, 'stop');
  assert.equal(alerts[0].level, 'critical');
});
