import { fmtNum } from '../../../shared/formatting/format.js';
import { inferDirection, isOptionSymbol } from './tradeUtils.js';

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

// Money here is a plain grouped number (no $ sign) — the trade-table dialect.
export const fmtMoney = (value, digits = 2) => fmtNum(value, digits);

export { fmtInt, fmtDateShort } from '../../../shared/formatting/format.js';

export const deriveTradeAlerts = (trades = [], riskFor) => (
  trades
    .flatMap(trade => buildTradeAlerts(trade, riskFor(trade)))
    .sort(compareAlerts)
);

export const buildTradeAlerts = (trade, derived) => {
  if (!trade || !derived || (derived.status !== 'open' && derived.status !== 'partial')) return [];
  if (!(derived.position > 0)) return [];

  const alerts = [];
  const ticker = String(trade.ticker || '').toUpperCase();
  const tradeId = trade.id ?? ticker;

  if (derived.rToStop != null) {
    const stopAlert = stopAlertFor({ derived, ticker, tradeId });
    if (stopAlert) alerts.push(stopAlert);
  }

  const targetAlert = targetAlertFor({ derived, ticker, tradeId });
  const targetHitAlert = targetHitAlertFor({ derived, ticker, tradeId });
  if (targetHitAlert) alerts.push(targetHitAlert);
  if (targetAlert) alerts.push(targetAlert);

  return alerts;
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
    riskQty: position > EPS ? cycleOpenQty : lastCycleOpenQty,
    activeCycleRealizedPnl: cycleRealizedPnl,
    realizedPnl,
    cycleCloseCash,
    cycleCloseQty,
  };
};

// Price-INDEPENDENT derivation: status, realized/stored P&L, the fill ledger
// (partials/VWAP/fees), the R basis, and the target prices. The live overlay
// (live price, unrealized P&L, distance-to-stop, stop tone) is owned by the
// backend (`GET /live-risk` → `useLiveRisk`/`riskFor`); this function is the
// fallback for closed/draft trades the server doesn't price. Live-price fields
// resolve to null here by construction (no live price in), so a closed row is
// byte-identical to before and an open row degrades cleanly to "no quote".
export const deriveTradeRow = (trade) => {
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
  const riskQty = ledger.riskQty || openQty || initialQty;
  const totalWorth = entryVwap != null && openQty ? entryVwap * openQty * multiplier : null;
  const livePrice = null;
  const liveSource = null;
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
  // Two stop bases: the working stop (current stop_loss) drives distance + tone
  // (what will actually execute); the R basis anchors 1R to planned_stop when
  // recorded (the original risk), falling back to the working stop. Never
  // fabricated — both resolve to null when no stop is recorded.
  const workingStop = trade.stop_loss && Number(trade.stop_loss) !== 0 ? Number(trade.stop_loss) : null;
  const plannedStop = trade.planned_stop && Number(trade.planned_stop) !== 0 ? Number(trade.planned_stop) : null;
  const rBasisStop = plannedStop != null ? plannedStop : workingStop;
  const stopVal = workingStop;
  const stopPct = workingStop != null && entryVwap != null
    ? Math.abs(entryVwap - workingStop) / entryVwap * 100
    : null;
  const workingDistance = workingStop != null && entryVwap != null ? Math.abs(entryVwap - workingStop) : null;
  const riskDistance = rBasisStop != null && entryVwap != null ? Math.abs(entryVwap - rBasisStop) : null;
  const rValue = riskDistance && riskDistance > 0 && riskQty && pnl != null
    ? pnl / (riskDistance * riskQty * multiplier)
    : null;
  const distToStop = currentExit != null && workingStop != null
    ? (isLong ? currentExit - workingStop : workingStop - currentExit)
    : null;
  const distToStopPct = distToStop != null && currentExit
    ? distToStop / currentExit * 100
    : null;
  // R-to-stop is price-based against the WORKING stop (NOT rValue + 1): on a
  // scaled-out position rValue folds in realized P&L/fees that don't cancel, so
  // rValue + 1 drifts. distToStop / workingDistance is exact for full and partial.
  const rToStop = distToStop != null && workingDistance ? distToStop / workingDistance : null;
  const stopRiskTone = riskToneFor(rToStop);
  const pnlPct = pnl != null && totalWorth ? pnl / totalWorth * 100 : null;
  const targetLadder = buildTargetLadder({ currentExit, isLong, riskDistance, trade });
  const nextTarget = targetLadder.find(target => target.isNext) || null;
  const distToTargetPct = nextTarget?.distToTargetPct ?? null;
  const status = getStatus({ closeQty: ledger.cycleCloseQty, hasClosed: ledger.anyClose, initialQty, pnl, position });

  return {
    distToStopPct,
    distToStopR: rToStop,
    distToTargetPct,
    direction,
    entryVwap,
    exitDate: position <= 0 && ledger.closingDate ? ledger.closingDate : (position <= 0 ? trade.closing_date || null : null),
    isLong,
    multiplier,
    nextTarget,
    openQty,
    pnl,
    pnlPct,
    position,
    riskDistance,
    riskQty,
    rValue,
    rToStop,
    status,
    stopPct,
    stopRiskTone,
    stopVal,
    plannedStopVal: rBasisStop,
    targetLadder,
    totalExit: ledger.cycleCloseQty > 0 ? ledger.cycleCloseCash : null,
    totalWorth,
    currentExit,
    currentExitSource,
  };
};

const buildTargetLadder = ({ currentExit, isLong, riskDistance, trade }) => {
  const targets = [1, 2, 3, 4, 5]
    .map(index => {
      const price = finitePositive(trade[`t${index}_price`]);
      if (price == null) return null;
      const qty = finitePositive(trade[`t${index}_qty`]);
      const signedDistance = currentExit != null
        ? (isLong ? price - currentExit : currentExit - price)
        : null;
      const hit = currentExit != null
        ? (isLong ? currentExit >= price : currentExit <= price)
        : false;
      return {
        index,
        label: `T${index}`,
        price,
        qty,
        hit,
        isNext: false,
        distToTargetPct: signedDistance != null && currentExit
          ? signedDistance / currentExit * 100
          : null,
        rToTarget: signedDistance != null && riskDistance
          ? signedDistance / riskDistance
          : null,
      };
    })
    .filter(Boolean);

  const nextIndex = targets.find(target => !target.hit)?.index ?? null;
  return targets.map(target => ({
    ...target,
    isNext: target.index === nextIndex,
  }));
};

const finitePositive = (value) => {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) && numberValue > 0 ? numberValue : null;
};

const riskToneFor = (rToStop) => {
  if (rToStop == null || !Number.isFinite(Number(rToStop))) return null;
  if (rToStop <= 0) return 'breached';
  if (rToStop <= 0.25) return 'danger';
  if (rToStop <= 0.5) return 'warning';
  return null;
};

const stopAlertFor = ({ derived, ticker, tradeId }) => {
  if (derived.rToStop <= 0) {
    return {
      id: `${tradeId}:stop:breached`,
      kind: 'stop',
      level: 'critical',
      ticker,
      title: `${ticker} through stop`,
      detail: `Stop ${formatAlertMoney(derived.stopVal)} - ${formatAlertR(derived.rToStop)} to stop`,
      tradeId,
      sortRank: 0,
    };
  }
  if (derived.rToStop <= 0.25) {
    return {
      id: `${tradeId}:stop:danger`,
      kind: 'stop',
      level: 'danger',
      ticker,
      title: `${ticker} near stop`,
      detail: `${formatAlertPct(derived.distToStopPct)} / ${formatAlertR(derived.rToStop)} to stop`,
      tradeId,
      sortRank: 1,
    };
  }
  if (derived.rToStop <= 0.5) {
    return {
      id: `${tradeId}:stop:warning`,
      kind: 'stop',
      level: 'warning',
      ticker,
      title: `${ticker} stop getting close`,
      detail: `${formatAlertPct(derived.distToStopPct)} / ${formatAlertR(derived.rToStop)} to stop`,
      tradeId,
      sortRank: 2,
    };
  }
  return null;
};

const targetAlertFor = ({ derived, ticker, tradeId }) => {
  const target = derived.nextTarget;
  if (!target) return null;
  const rToTarget = target.rToTarget;
  const pctToTarget = target.distToTargetPct;
  const hasR = Number.isFinite(rToTarget);
  const hasPct = Number.isFinite(pctToTarget);
  if ((!hasR && !hasPct) || (hasR && rToTarget < 0) || (hasPct && pctToTarget < 0)) return null;
  if (!((hasR && rToTarget <= 0.25) || (hasPct && pctToTarget <= 1))) return null;

  return {
    id: `${tradeId}:target:${target.label}`,
    kind: 'target',
    level: 'target',
    ticker,
    title: `${ticker} near ${target.label}`,
    detail: `${formatAlertPct(target.distToTargetPct)} / ${formatAlertR(target.rToTarget)} away`,
    tradeId,
    sortRank: 4,
    targetLabel: target.label,
  };
};

const targetHitAlertFor = ({ derived, ticker, tradeId }) => {
  const hitTargets = (derived.targetLadder || []).filter(target => target.hit);
  const target = hitTargets[hitTargets.length - 1];
  if (!target) return null;

  const next = derived.nextTarget;
  const nextDetail = next
    ? `${next.label} ${formatAlertPct(next.distToTargetPct)} / ${formatAlertR(next.rToTarget)} away`
    : 'Ladder complete';

  return {
    id: `${tradeId}:target-hit:${target.label}`,
    kind: 'target',
    level: 'target',
    ticker,
    title: `${ticker} hit ${target.label}`,
    detail: `${formatAlertMoney(target.price)} reached - ${nextDetail}`,
    tradeId,
    sortRank: 3,
    targetLabel: target.label,
    targetState: 'hit',
  };
};

const compareAlerts = (first, second) => {
  if (first.sortRank !== second.sortRank) return first.sortRank - second.sortRank;
  return first.ticker.localeCompare(second.ticker);
};

const formatAlertMoney = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `$${fmtMoney(value)}`;
};

const formatAlertPct = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `${Number(value).toFixed(1)}%`;
};

const formatAlertR = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `${Number(value).toFixed(2)}R`;
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
