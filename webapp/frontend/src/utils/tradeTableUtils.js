import { inferDirection, isOptionSymbol } from './tradeUtils';

export const EDITABLE_FIELDS = ['opening_date', 'ticker', 'entry_price', 'stop_loss', 'quantity'];
export const DEFAULT_PAGE_SIZE = 20;

export const todayIso = () => new Date().toISOString().split('T')[0];

export const emptyDraft = () => ({
  opening_date: todayIso(),
  direction: 'LONG',
  ticker: '',
  entry_price: '',
  stop_loss: '',
  quantity: '',
});

export const parseActions = (json) => {
  if (!json) return [];
  try {
    const actions = JSON.parse(json);
    return Array.isArray(actions) ? actions : [];
  } catch {
    return [];
  }
};

export const fmtMoney = (value, digits = 2) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
};

export const fmtInt = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return Number(value).toLocaleString('en-US', { maximumFractionDigits: 0 });
};

export const fmtDateShort = (value) => {
  if (!value) return '-';
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return value;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[Number(match[2]) - 1]} ${Number(match[3])}`;
};

export const summarizeFillLedger = (fills, direction, multiplier = 1) => {
  const isLong = direction === 'LONG';
  const openSide = isLong ? 'BUY' : 'SELL';
  const closeSide = isLong ? 'SELL' : 'BUY';
  const EPS = 1e-9;

  let position = 0;
  let openCost = 0;
  let openFees = 0;
  let cycleOpenQty = 0;
  let cycleOpenCash = 0;
  let cycleCloseQty = 0;
  let cycleCloseCash = 0;
  let cycleRealizedPnl = 0;
  let cycleOpeningDate = null;
  let cycleClosingDate = null;
  let lastCycleOpenQty = 0;
  let lastCycleEntry = null;
  let lastCycleOpeningDate = null;
  let lastCycleClosingDate = null;
  let realizedPnl = 0;
  let commissions = 0;
  let anyClose = false;

  for (const fill of fills) {
    const rawSide = String(fill.side || '').toUpperCase();
    const rawType = String(fill.type || '').toUpperCase();
    const rawRole = String(fill.role || '').toUpperCase();
    const side = rawSide === 'BUY' || rawSide === 'SELL'
      ? rawSide
      : rawType === 'BUY' || rawType === 'SELL'
        ? rawType
        : rawType === 'ENTRY' || rawRole === 'ENTRY'
          ? openSide
          : rawType === 'EXIT' || rawRole === 'EXIT'
            ? closeSide
            : '';
    const quantity = parseFloat(fill.quantity) || 0;
    const price = parseFloat(fill.price) || 0;
    const fee = parseFloat(fill.fee) || 0;
    const date = String(fill.date || '').slice(0, 10);
    if (quantity <= 0 || price <= 0) {
      commissions += fee;
      continue;
    }

    commissions += fee;

    if (side === openSide) {
      if (position <= EPS) {
        position = 0;
        openCost = 0;
        openFees = 0;
        cycleOpenQty = 0;
        cycleOpenCash = 0;
        cycleCloseQty = 0;
        cycleCloseCash = 0;
        cycleRealizedPnl = 0;
        cycleOpeningDate = null;
        cycleClosingDate = null;
      }
      position += quantity;
      openCost += quantity * price * multiplier;
      openFees += fee;
      cycleOpenQty += quantity;
      cycleOpenCash += quantity * price * multiplier;
      if (date && (!cycleOpeningDate || date < cycleOpeningDate)) cycleOpeningDate = date;
    } else if (side === closeSide) {
      const closedQty = Math.min(quantity, position);
      cycleCloseQty += closedQty;
      cycleCloseCash += closedQty * price * multiplier;
      anyClose = anyClose || closedQty > 0;
      if (date && (!cycleClosingDate || date > cycleClosingDate)) cycleClosingDate = date;

      if (closedQty > 0 && position > EPS) {
        const avgCost = openCost / position;
        const gross = isLong
          ? (price * multiplier - avgCost) * closedQty
          : (avgCost - price * multiplier) * closedQty;
        const openFeeShare = openFees * (closedQty / position);
        const fillPnl = gross - openFeeShare - fee;
        realizedPnl += fillPnl;
        cycleRealizedPnl += fillPnl;
        openFees -= openFeeShare;
        openCost -= avgCost * closedQty;
        position -= closedQty;
      } else {
        realizedPnl -= fee;
        cycleRealizedPnl -= fee;
      }

      if (position <= EPS) {
        lastCycleOpenQty = cycleOpenQty;
        lastCycleEntry = cycleOpenQty > 0 ? cycleOpenCash / (cycleOpenQty * multiplier) : lastCycleEntry;
        lastCycleOpeningDate = cycleOpeningDate;
        lastCycleClosingDate = cycleClosingDate;
        position = 0;
        openCost = 0;
        openFees = 0;
      }
    }
  }

  const currentEntry = position > EPS ? openCost / (position * multiplier) : lastCycleEntry;
  return {
    anyClose,
    commissions,
    currentOpenFees: openFees,
    entryPrice: currentEntry,
    exitPrice: cycleCloseQty > 0 ? cycleCloseCash / (cycleCloseQty * multiplier) : null,
    openingDate: position > EPS ? cycleOpeningDate : lastCycleOpeningDate,
    closingDate: position <= EPS && anyClose ? lastCycleClosingDate : null,
    openQty: position > EPS ? position : lastCycleOpenQty,
    position,
    activeCycleRealizedPnl: cycleRealizedPnl,
    realizedPnl,
    cycleCloseCash,
    cycleCloseQty,
  };
};

export const deriveTradeRow = (trade, priceFor) => {
  const direction = inferDirection(trade);
  const isLong = direction === 'LONG';
  const multiplier = isOptionSymbol(trade.ticker) ? 100 : 1;
  const openSide = isLong ? 'BUY' : 'SELL';
  const closeSide = isLong ? 'SELL' : 'BUY';
  const rawActions = parseActions(trade.actions_json);
  const actions = rawActions.map(action => ({
    ...action,
    side: normalizeActionSide(action, openSide, closeSide),
  }));
  const includesOpener = actions.some(action => action.side === openSide);
  const initialQty = Number(trade.quantity) || 0;
  const fallbackActions = includesOpener ? actions : [
    {
      side: openSide,
      quantity: initialQty,
      price: Number(trade.entry_price) || 0,
      fee: Number(trade.commissions) || 0,
      date: trade.opening_date,
    },
    ...actions,
  ];
  const ledger = summarizeFillLedger(fallbackActions, direction, multiplier);

  const entryVwap = ledger.entryPrice != null ? ledger.entryPrice : (Number(trade.entry_price) || null);
  const position = ledger.position;
  const openQty = ledger.openQty;
  const totalWorth = entryVwap != null && openQty ? entryVwap * openQty * multiplier : null;
  const { price: livePrice, source: liveSource } = priceFor(trade.ticker);
  const { currentExit, currentExitSource } = getExitPrice({
    closeCash: ledger.cycleCloseCash,
    closeQty: ledger.cycleCloseQty,
    livePrice,
    liveSource,
    multiplier,
    position,
    trade,
  });
  const pnl = calculatePnl({
    entryVwap,
    isLong,
    ledger,
    livePrice,
    multiplier,
    position,
    trade,
  });
  const stopVal = trade.stop_loss && Number(trade.stop_loss) !== 0 ? Number(trade.stop_loss) : null;
  const stopPct = stopVal != null && entryVwap != null
    ? Math.abs(entryVwap - stopVal) / entryVwap * 100
    : null;
  const riskDistance = stopVal != null && entryVwap != null ? Math.abs(entryVwap - stopVal) : null;
  const rValue = riskDistance && riskDistance > 0 && openQty && pnl != null
    ? pnl / (riskDistance * openQty * multiplier)
    : null;
  const status = getStatus({ closeQty: ledger.cycleCloseQty, hasClosed: ledger.anyClose, initialQty, pnl, position });

  return {
    direction,
    entryVwap,
    exitDate: position <= 0 && ledger.closingDate ? ledger.closingDate : (position <= 0 ? trade.closing_date || null : null),
    isLong,
    multiplier,
    openQty,
    pnl,
    position,
    rValue,
    status,
    stopPct,
    stopVal,
    totalExit: ledger.cycleCloseQty > 0 ? ledger.cycleCloseCash : null,
    totalWorth,
    currentExit,
    currentExitSource,
  };
};

const normalizeActionSide = (action, openSide, closeSide) => {
  const rawSide = String(action.side || '').toUpperCase();
  const rawType = String(action.type || '').toUpperCase();
  const rawRole = String(action.role || '').toUpperCase();
  if (rawSide === 'BUY' || rawSide === 'SELL') return rawSide;
  if (rawType === 'BUY' || rawType === 'SELL') return rawType;
  if (rawType === 'ENTRY' || rawRole === 'ENTRY') return openSide;
  if (rawType === 'EXIT' || rawRole === 'EXIT') return closeSide;
  return rawType;
};

const getExitPrice = ({ closeCash, closeQty, livePrice, liveSource, multiplier, position, trade }) => {
  if (position > 0 && livePrice != null) {
    return { currentExit: livePrice, currentExitSource: liveSource };
  }
  if (closeQty > 0) {
    return { currentExit: closeCash / (closeQty * multiplier), currentExitSource: 'fills' };
  }
  if (trade.exit_price != null) {
    return { currentExit: Number(trade.exit_price), currentExitSource: 'fills' };
  }
  return { currentExit: null, currentExitSource: null };
};

const calculatePnl = ({
  entryVwap, isLong, ledger, livePrice, multiplier, position, trade,
}) => {
  if (position > 0 && livePrice != null && entryVwap != null) {
    const unrealized = isLong
      ? (livePrice - entryVwap) * position * multiplier
      : (entryVwap - livePrice) * position * multiplier;
    return ledger.activeCycleRealizedPnl + unrealized - ledger.currentOpenFees;
  }
  if (position > 0) {
    return ledger.activeCycleRealizedPnl !== 0 ? ledger.activeCycleRealizedPnl : null;
  }
  if (ledger.anyClose) return ledger.realizedPnl;
  return trade.pnl != null ? Number(trade.pnl) : null;
};

const getStatus = ({ closeQty, hasClosed, initialQty, pnl, position }) => {
  if (position > 0 && closeQty > 0) return 'partial';
  if (position > 0) return 'open';
  if (hasClosed) return pnl != null && pnl > 0 ? 'win' : 'loss';
  if (initialQty > 0) return 'open';
  return 'draft';
};
