import { buildTradeAlerts, deriveTradeRow } from './tradeTableUtils.js';
import { inferDirection, isOptionSymbol } from './tradeUtils.js';

export const positionPlanKey = (position) => [
  position?.account || '',
  normalizePlanSymbol(position?.symbol),
  position?.sec_type || '',
  position?.currency || '',
  position?.exchange || '',
].join('|');

export const buildPortfolioPlanMap = (positions = [], trades = [], riskFor) => {
  const openTradesByInstrument = groupOpenTradesByInstrument(trades);
  const planMap = new Map();

  for (const position of positions || []) {
    const key = positionInstrumentKey(position);
    const matches = key ? openTradesByInstrument.get(key) || [] : [];
    planMap.set(positionPlanKey(position), buildPositionPlan(position, matches, riskFor));
  }

  return planMap;
};

export const normalizePlanSymbol = (value) => (
  String(value || '').trim().toUpperCase().replace(/\s+/g, ' ')
);

const groupOpenTradesByInstrument = (trades) => {
  const groups = new Map();
  for (const trade of trades || []) {
    if (!isOpenJournalTrade(trade)) continue;
    const key = tradeInstrumentKey(trade);
    if (!key) continue;
    const bucket = groups.get(key) || [];
    bucket.push(trade);
    groups.set(key, bucket);
  }
  return groups;
};

const positionInstrumentKey = (position) => {
  const symbol = normalizePlanSymbol(position?.symbol);
  if (!symbol) return '';
  return `${normalizeInstrumentType(position?.sec_type, symbol)}|${symbol}`;
};

const tradeInstrumentKey = (trade) => {
  const symbol = normalizePlanSymbol(trade?.ticker);
  if (!symbol) return '';
  return `${normalizeInstrumentType(null, symbol)}|${symbol}`;
};

const normalizeInstrumentType = (value, symbol) => {
  const secType = String(value || '').trim().toUpperCase();
  if (secType === 'OPT' || isOptionSymbol(symbol)) return 'OPT';
  return 'STK';
};

const isOpenJournalTrade = (trade) => {
  if (!trade?.ticker) return false;
  if (trade.closing_date || trade.pnl != null) return false;
  // Status is price-independent (ledger-derived) — no live price needed here.
  const derived = deriveTradeRow(trade);
  return derived.status === 'open' || derived.status === 'partial';
};

const buildPositionPlan = (position, matches, riskFor) => {
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
  // Live overlay from the server (it already prices off the same IBKR snapshot);
  // fall back to the price-independent derivation when no server row is available.
  const derived = riskFor ? riskFor(trade) : deriveTradeRow(trade);
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
