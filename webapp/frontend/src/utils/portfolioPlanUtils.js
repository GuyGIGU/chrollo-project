import { buildTradeAlerts, deriveTradeRow } from './tradeTableUtils.js';
import { inferDirection } from './tradeUtils.js';

const nullPriceFor = () => ({ price: null, source: null });

export const positionPlanKey = (position) => [
  position?.account || '',
  normalizePlanSymbol(position?.symbol),
  position?.sec_type || '',
  position?.currency || '',
  position?.exchange || '',
].join('|');

export const buildPortfolioPlanMap = (positions = [], trades = []) => {
  const openTradesBySymbol = groupOpenTradesBySymbol(trades);
  const planMap = new Map();

  for (const position of positions || []) {
    const symbol = normalizePlanSymbol(position?.symbol);
    const matches = symbol ? openTradesBySymbol.get(symbol) || [] : [];
    planMap.set(positionPlanKey(position), buildPositionPlan(position, matches));
  }

  return planMap;
};

export const normalizePlanSymbol = (value) => (
  String(value || '').trim().toUpperCase().replace(/\s+/g, ' ')
);

const groupOpenTradesBySymbol = (trades) => {
  const groups = new Map();
  for (const trade of trades || []) {
    if (!isOpenJournalTrade(trade)) continue;
    const symbol = normalizePlanSymbol(trade.ticker);
    if (!symbol) continue;
    const bucket = groups.get(symbol) || [];
    bucket.push(trade);
    groups.set(symbol, bucket);
  }
  return groups;
};

const isOpenJournalTrade = (trade) => {
  if (!trade?.ticker) return false;
  if (trade.closing_date || trade.pnl != null) return false;
  const derived = deriveTradeRow(trade, nullPriceFor);
  return derived.status === 'open' || derived.status === 'partial';
};

const buildPositionPlan = (position, matches) => {
  if (!matches.length) {
    return {
      state: 'missing',
      label: 'No plan',
      matches: [],
    };
  }
  if (matches.length > 1) {
    return {
      state: 'multiple',
      label: `${matches.length} plans`,
      matches,
    };
  }

  const trade = matches[0];
  const price = finiteNumber(position?.market_price);
  const derived = deriveTradeRow(trade, () => ({ price, source: price == null ? null : 'ibkr' }));
  const brokerDirection = positionDirection(position);
  const planDirection = inferDirection(trade);

  return {
    state: 'linked',
    label: 'Linked',
    trade,
    matches,
    derived,
    alerts: buildTradeAlerts(trade, derived),
    brokerDirection,
    planDirection,
    directionMismatch: brokerDirection != null && brokerDirection !== planDirection,
  };
};

const positionDirection = (position) => {
  const qty = finiteNumber(position?.position ?? position?.quantity);
  if (qty == null || qty === 0) return null;
  return qty < 0 ? 'SHORT' : 'LONG';
};

const finiteNumber = (value) => {
  if (value == null || value === '') return null;
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
};
