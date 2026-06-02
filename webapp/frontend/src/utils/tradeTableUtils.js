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

export const deriveTradeRow = (trade, priceFor) => {
  const direction = inferDirection(trade);
  const isLong = direction === 'LONG';
  const multiplier = isOptionSymbol(trade.ticker) ? 100 : 1;
  const openSide = isLong ? 'BUY' : 'SELL';
  const closeSide = isLong ? 'SELL' : 'BUY';
  const rawActions = parseActions(trade.actions_json);
  const actions = rawActions.map(action => ({
    ...action,
    side: (action.side || action.type || '').toUpperCase(),
  }));
  const includesOpener = actions.some(action => action.side === openSide);
  const initialQty = Number(trade.quantity) || 0;

  let openQty = includesOpener ? 0 : initialQty;
  let openCash = includesOpener ? 0 : (Number(trade.entry_price) || 0) * initialQty * multiplier;
  let openFees = includesOpener ? 0 : Number(trade.commissions) || 0;
  let closeQty = 0;
  let closeCash = 0;
  let closeFees = 0;
  let lastCloseDate = null;

  for (const action of actions) {
    const quantity = parseFloat(action.quantity) || 0;
    const price = parseFloat(action.price) || 0;
    const fee = parseFloat(action.fee) || 0;

    if (action.side === openSide) {
      openQty += quantity;
      openCash += quantity * price * multiplier;
      openFees += fee;
    } else if (action.side === closeSide) {
      closeQty += quantity;
      closeCash += quantity * price * multiplier;
      closeFees += fee;
      if (action.date) {
        const day = String(action.date).slice(0, 10);
        if (!lastCloseDate || day > lastCloseDate) lastCloseDate = day;
      }
    }
  }

  const entryVwap = openQty > 0 ? openCash / (openQty * multiplier) : Number(trade.entry_price) || null;
  const position = openQty - closeQty;
  const totalWorth = entryVwap != null ? entryVwap * openQty * multiplier : null;
  const { price: livePrice, source: liveSource } = priceFor(trade.ticker);
  const { currentExit, currentExitSource } = getExitPrice({
    closeCash,
    closeQty,
    livePrice,
    liveSource,
    multiplier,
    position,
    trade,
  });
  const pnl = calculatePnl({
    closeCash,
    closeFees,
    closeQty,
    entryVwap,
    isLong,
    livePrice,
    multiplier,
    openFees,
    openQty,
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
  const status = getStatus({ closeQty, initialQty, pnl, position });

  return {
    direction,
    entryVwap,
    exitDate: position <= 0 && lastCloseDate ? lastCloseDate : (position <= 0 ? trade.closing_date || null : null),
    isLong,
    multiplier,
    openQty,
    pnl,
    position,
    rValue,
    status,
    stopPct,
    stopVal,
    totalExit: closeQty > 0 ? closeCash : null,
    totalWorth,
    currentExit,
    currentExitSource,
  };
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
  closeCash, closeFees, closeQty, entryVwap, isLong, livePrice, multiplier,
  openFees, openQty, position, trade,
}) => {
  if (closeQty > 0) {
    const realizedCloseCash = isLong ? closeCash : -closeCash;
    const openedCash = entryVwap * closeQty * multiplier;
    const realizedOpenCashClosed = isLong ? -openedCash : openedCash;
    const realized = realizedCloseCash + realizedOpenCashClosed
      - openFees * (closeQty / Math.max(openQty, 1)) - closeFees;
    if (position > 0 && livePrice != null) {
      const unrealized = isLong
        ? (livePrice - entryVwap) * position * multiplier
        : (entryVwap - livePrice) * position * multiplier;
      return realized + unrealized;
    }
    return realized;
  }
  if (position > 0 && livePrice != null && entryVwap != null) {
    return isLong
      ? (livePrice - entryVwap) * position * multiplier
      : (entryVwap - livePrice) * position * multiplier;
  }
  return trade.pnl != null ? Number(trade.pnl) : null;
};

const getStatus = ({ closeQty, initialQty, pnl, position }) => {
  if (position > 0) return 'open';
  if (closeQty > 0) return pnl != null && pnl > 0 ? 'win' : 'loss';
  if (initialQty > 0) return 'open';
  return 'draft';
};
