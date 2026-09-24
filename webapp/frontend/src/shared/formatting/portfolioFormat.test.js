import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  emptyValue,
  fmtMoney,
  fmtNum,
  fmtPct,
  fmtTime,
  pnlColor,
  summaryCurrency,
  summaryValue,
} from './portfolioFormat.js';

// The portfolio dialect over the shared formatters, and the two readers of the
// IBKR account summary (a direct `values`/`currency` map, else the per-currency
// `raw` buckets).

test('money, numbers and percents keep the portfolio dialect', () => {
  assert.equal(emptyValue, '—');
  assert.equal(fmtMoney(1234.5), '$1,234.50');
  assert.equal(fmtMoney(-5, 'CAD'), '-$5.00 CAD');
  assert.equal(fmtMoney(null), emptyValue);
  assert.equal(fmtNum(1234.567), '1,234.57');
  assert.equal(fmtNum(3, 0), '3');
  assert.equal(fmtPct(12.34), '12.3%');
  assert.equal(fmtPct(undefined), emptyValue);
});

test('fmtTime reads epoch seconds and milliseconds alike, and passes junk through', () => {
  const expected = new Date(1700000000 * 1000).toLocaleString();
  assert.equal(fmtTime(1700000000), expected);
  assert.equal(fmtTime(1700000000000), expected);
  assert.equal(fmtTime(null), emptyValue);
  assert.equal(fmtTime('not a date'), 'not a date');
});

test('pnlColor: gain, loss, and flat or missing', () => {
  assert.equal(pnlColor(5), 'var(--success)');
  assert.equal(pnlColor('-5'), 'var(--danger)');
  assert.equal(pnlColor(0), 'var(--text-muted)');
  assert.equal(pnlColor('abc'), 'var(--text-muted)');
});

test('summaryValue: the direct value wins, else raw buckets sum, else the first text', () => {
  assert.equal(summaryValue({ values: { NetLiquidation: 0 } }, 'NetLiquidation'), 0);
  const raw = {
    USD: { NetLiquidation: { value: '100' }, AccountType: { value: 'INDIVIDUAL' } },
    EUR: { NetLiquidation: { value: 50 }, AccountType: { value: 'IRA' } },
  };
  assert.equal(summaryValue({ values: { NetLiquidation: null }, raw }, 'NetLiquidation'), 150);
  assert.equal(summaryValue({ raw }, 'AccountType'), 'INDIVIDUAL');
  assert.equal(summaryValue({ raw: { USD: { Cash: { value: '' } } } }, 'Cash'), '');
  assert.equal(summaryValue(undefined, 'NetLiquidation'), undefined);
});

test('summaryCurrency: the direct currency, else the first raw bucket that names one', () => {
  assert.equal(summaryCurrency({ currency: { NetLiquidation: 'USD' } }, 'NetLiquidation'), 'USD');
  const raw = { A: { NetLiquidation: { value: 1 } }, B: { NetLiquidation: { currency: 'EUR' } } };
  assert.equal(summaryCurrency({ raw }, 'NetLiquidation'), 'EUR');
  assert.equal(summaryCurrency({}, 'NetLiquidation'), undefined);
});
