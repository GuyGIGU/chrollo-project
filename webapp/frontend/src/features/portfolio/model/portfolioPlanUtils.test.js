import assert from 'node:assert/strict';
import test from 'node:test';
import { buildPortfolioPlanMap, positionPlanKey } from './portfolioPlanUtils.js';
import { isOptionSymbol, optionUnderlyingSymbol } from '../../journal/model/tradeUtils.js';

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

const basePosition = {
  account: 'DU123',
  symbol: 'MSFT',
  sec_type: 'STK',
  currency: 'USD',
  exchange: 'SMART',
  quantity: 10,
  market_price: 105,
  market_value: 1050,
  avg_cost: 100,
};

const planFor = (position, trades, riskFor) => (
  buildPortfolioPlanMap([position], trades, riskFor).get(positionPlanKey(position))
);

const closeTo = (actual, expected) => {
  assert.ok(Math.abs(actual - expected) < 0.000001, `${actual} should equal ${expected}`);
};

test('buildPortfolioPlanMap links a live stock position and derives it via riskFor', () => {
  // The live overlay now comes from the backend (riskFor), not local price math.
  const riskFor = () => ({ status: 'open', rToStop: 1.5, rValue: 0.5, nextTarget: { label: 'T1' } });
  const plan = planFor(
    basePosition,
    [{
      ...baseTrade,
      t1_price: 110,
    }],
    riskFor,
  );

  assert.equal(plan.state, 'linked');
  assert.equal(plan.trade.id, 1);
  closeTo(plan.derived.rToStop, 1.5);
  closeTo(plan.derived.rValue, 0.5);
  assert.equal(plan.derived.nextTarget.label, 'T1');
});

test('buildPortfolioPlanMap marks broker positions with no journal plan', () => {
  const plan = planFor(
    {
      ...basePosition,
      symbol: 'AAPL',
    },
    [baseTrade],
  );

  assert.equal(plan.state, 'missing');
  assert.equal(plan.label, 'No plan');
});

test('buildPortfolioPlanMap does not guess when multiple open plans share a symbol', () => {
  const plan = planFor(
    basePosition,
    [
      baseTrade,
      {
        ...baseTrade,
        id: 2,
        opening_date: '2026-06-03',
      },
    ],
  );

  assert.equal(plan.state, 'multiple');
  assert.equal(plan.matches.length, 2);
});

test('buildPortfolioPlanMap ignores closed journal trades', () => {
  const plan = planFor(
    basePosition,
    [{
      ...baseTrade,
      closing_date: '2026-06-10',
      pnl: 50,
    }],
  );

  assert.equal(plan.state, 'missing');
});

test('buildPortfolioPlanMap flags a broker side that conflicts with the journal plan', () => {
  const plan = planFor(
    {
      ...basePosition,
      quantity: -10,
    },
    [baseTrade],
  );

  assert.equal(plan.state, 'linked');
  assert.equal(plan.directionMismatch, true);
  assert.equal(plan.brokerDirection, 'SHORT');
  assert.equal(plan.planDirection, 'LONG');
});

test('buildPortfolioPlanMap does not link option holdings to stock plans by underlying', () => {
  const plan = planFor(
    {
      ...basePosition,
      symbol: 'MSFT 260619C00300000',
      sec_type: 'OPT',
      quantity: 1,
    },
    [baseTrade],
  );

  assert.equal(plan.state, 'missing');
});

test('buildPortfolioPlanMap links option holdings to matching option journal plans', () => {
  const optionTrade = {
    ...baseTrade,
    ticker: 'MSFT 260619C00300000',
    quantity: 1,
    entry_price: 4,
    stop_loss: 2,
  };
  const plan = planFor(
    {
      ...basePosition,
      symbol: 'MSFT 260619C00300000',
      sec_type: 'OPT',
      quantity: 1,
      market_price: 5,
    },
    [optionTrade],
  );

  assert.equal(plan.state, 'linked');
  assert.equal(plan.trade.ticker, 'MSFT 260619C00300000');
});

test('buildPortfolioPlanMap infers option holdings when broker type is missing', () => {
  const optionTrade = {
    ...baseTrade,
    ticker: 'MSFT 260619C00300000',
    quantity: 1,
    entry_price: 4,
    stop_loss: 2,
  };
  const plan = planFor(
    {
      ...basePosition,
      symbol: 'MSFT 260619C00300000',
      sec_type: '',
      quantity: 1,
      market_price: 5,
    },
    [optionTrade],
  );

  assert.equal(plan.state, 'linked');
  assert.equal(plan.trade.ticker, 'MSFT 260619C00300000');
});

test('option symbol parsing extracts an underlying for chart lookups', () => {
  assert.equal(isOptionSymbol('MSFT 260619C00300000'), true);
  assert.equal(optionUnderlyingSymbol('MSFT 260619C00300000'), 'MSFT');
  assert.equal(isOptionSymbol('AAPL260619P00190000'), true);
  assert.equal(optionUnderlyingSymbol('AAPL260619P00190000'), 'AAPL');
});
