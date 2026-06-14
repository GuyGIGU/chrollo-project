import { useState } from 'react';
import { API_BASE } from '../api';
import { inferDirection } from '../utils/tradeUtils';
import { parseActions, summarizeFillLedger, todayIso } from '../utils/tradeTableUtils';

export default function useTradeFills({ commitTradeCell, onTradeUpdate, trades }) {
  const [expandedFills, setExpandedFills] = useState(() => new Set());
  const [fillsBuffer, setFillsBuffer] = useState({});

  const toggleExpand = (tradeId) => {
    setExpandedFills(previous => {
      const next = new Set(previous);
      if (next.has(tradeId)) {
        next.delete(tradeId);
        return next;
      }

      next.add(tradeId);
      seedFills(tradeId);
      return next;
    });
  };

  const seedFills = (tradeId) => {
    setFillsBuffer(previous => {
      if (previous[tradeId]) return previous;
      const trade = trades.find(item => item.id === tradeId);
      if (!trade) return previous;

      const openSide = inferDirection(trade) === 'LONG' ? 'BUY' : 'SELL';
      const closeSide = openSide === 'BUY' ? 'SELL' : 'BUY';
      const rawActions = parseActions(trade.actions_json);
      const parsed = rawActions.map(action => normalizeFill(action, openSide, closeSide));
      if (actionsAreComplete(rawActions)) {
        return { ...previous, [tradeId]: parsed };
      }

      return {
        ...previous,
        [tradeId]: [buildInitialFill(trade, openSide), ...parsed],
      };
    });
  };

  const updateFill = (tradeId, fillId, field, value) => {
    setFillsBuffer(previous => ({
      ...previous,
      [tradeId]: (previous[tradeId] || []).map(action =>
        action.id === fillId ? { ...action, [field]: value } : action),
    }));
  };

  const addFill = (trade) => {
    const tradeId = trade.id;
    setFillsBuffer(previous => ({
      ...previous,
      [tradeId]: [
        ...(previous[tradeId] || []),
        {
          id: Date.now(),
          type: getNextFillSide(trade, previous[tradeId] || []),
          date: todayIso(),
          quantity: '',
          price: '',
          fee: 0,
        },
      ],
    }));
  };

  const removeFill = (tradeId, fillId) => {
    if (fillId === 'initial') return;
    setFillsBuffer(previous => ({
      ...previous,
      [tradeId]: (previous[tradeId] || []).filter(action => action.id !== fillId),
    }));
  };

  const toggleFillSide = (tradeId, fillId) => {
    setFillsBuffer(previous => ({
      ...previous,
      [tradeId]: (previous[tradeId] || []).map(action =>
        action.id === fillId ? { ...action, type: action.type === 'BUY' ? 'SELL' : 'BUY' } : action),
    }));
  };

  const saveFills = async (trade) => {
    const fills = fillsBuffer[trade.id] || [];
    if (fills.length === 0) return;
    const direction = inferDirection(trade);
    const summary = summarizeFills(fills, direction);
    const payload = {
      opening_date: summary.openingDate || trade.opening_date,
      entry_price: summary.entryPrice,
      quantity: summary.quantity,
      commissions: summary.commissions,
      actions_json: JSON.stringify(fills.map((fill, index) => toSavedFill(fill, index === 0))),
      exit_price: summary.exitPrice,
      closing_date: summary.closingDate,
      pnl: summary.pnl,
    };

    try {
      const response = await fetch(`${API_BASE}/trades/${trade.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (response.ok) onTradeUpdate?.();
    } catch (error) {
      console.error('Fills save failed:', error);
    }
  };

  return {
    addFill,
    expandedFills,
    fillsBuffer,
    removeFill,
    saveFills,
    toggleExpand,
    toggleFillSide,
    updateFill,
    updateStopLoss: commitTradeCell,
  };
}

const buildInitialFill = (trade, openSide) => ({
  id: 'initial',
  type: openSide,
  date: trade.opening_date || '',
  quantity: trade.quantity || '',
  price: trade.entry_price || '',
  fee: trade.commissions || 0,
  isInitial: true,
});

const actionsAreComplete = (fills) => (
  fills.some(fill => {
    const role = String(fill.role || '').toUpperCase();
    const type = String(fill.type || '').toUpperCase();
    return fill.exec_id || fill.isInitial || role === 'ENTRY' || role === 'EXIT' || type === 'ENTRY' || type === 'EXIT';
  })
);

const normalizeFill = (fill, openSide, closeSide) => {
  const role = String(fill.role || '').toUpperCase();
  const rawType = String(fill.side || fill.type || '').toUpperCase();
  const type = rawType === 'SELL'
    ? 'SELL'
    : rawType === 'BUY'
      ? 'BUY'
      : role === 'EXIT' || rawType === 'EXIT'
        ? closeSide
        : openSide;

  return {
    ...fill,
    role: role || (type === openSide ? 'ENTRY' : 'EXIT'),
    type,
  };
};

const getNextFillSide = (trade, fills) => {
  const direction = inferDirection(trade);
  const openSide = direction === 'LONG' ? 'BUY' : 'SELL';
  const closeSide = openSide === 'BUY' ? 'SELL' : 'BUY';
  const summary = summarizeFills(fills, direction);
  return summary.position > 0 ? closeSide : openSide;
};

const summarizeFills = (fills, direction) => {
  const ledger = summarizeFillLedger(fills, direction);
  const isClosed = ledger.openQty > 0 && ledger.position <= 0;
  return {
    closingDate: isClosed ? ledger.closingDate : null,
    commissions: ledger.commissions,
    entryPrice: ledger.entryPrice || 0,
    exitPrice: ledger.exitPrice,
    openingDate: ledger.openingDate,
    pnl: isClosed ? ledger.realizedPnl : null,
    position: ledger.position,
    quantity: Math.round(ledger.openQty),
  };
};

const toSavedFill = (fill, isInitial) => ({
  id: fill.id,
  type: fill.type,
  side: fill.type,
  role: fill.role || (isInitial ? 'ENTRY' : undefined),
  date: fill.date,
  quantity: fill.quantity,
  price: fill.price,
  fee: fill.fee,
  isInitial: isInitial || undefined,
});
