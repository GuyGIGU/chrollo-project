import { useState } from 'react';
import { API_BASE } from '../api';
import { inferDirection } from '../utils/tradeUtils';
import { parseActions, todayIso } from '../utils/tradeTableUtils';

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
      const parsed = parseActions(trade.actions_json).map(action => ({
        ...action,
        type: (action.side || action.type || '').toUpperCase() === 'SELL' ? 'SELL' : 'BUY',
      }));
      if (parsed.some(action => action.type === openSide)) {
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

  const addFill = (tradeId) => {
    setFillsBuffer(previous => ({
      ...previous,
      [tradeId]: [
        ...(previous[tradeId] || []),
        { id: Date.now(), type: 'BUY', date: todayIso(), quantity: '', price: '', fee: 0 },
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
    const [first, ...rest] = fills;
    const direction = inferDirection(trade);
    const closingType = direction === 'LONG' ? 'SELL' : 'BUY';
    const { hasClosing, pnl } = calculateFillPnl(fills, closingType);
    const closingFill = [...fills].reverse().find(fill =>
      fill.type === closingType && parseFloat(fill.quantity) > 0);
    const payload = {
      opening_date: first.date || trade.opening_date,
      entry_price: parseFloat(first.price) || 0,
      quantity: parseInt(first.quantity, 10) || 0,
      commissions: parseFloat(first.fee) || 0,
      actions_json: rest.length > 0 ? JSON.stringify(rest.map(toSavedFill)) : null,
      exit_price: closingFill ? parseFloat(closingFill.price) || null : null,
      closing_date: closingFill ? closingFill.date || null : null,
      pnl: hasClosing ? pnl : null,
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

const calculateFillPnl = (fills, closingType) => {
  let cashFlow = 0;
  let totalFees = 0;
  let hasClosing = false;
  for (const fill of fills) {
    const quantity = parseFloat(fill.quantity) || 0;
    const price = parseFloat(fill.price) || 0;
    const fee = parseFloat(fill.fee) || 0;
    if (fill.type === 'SELL') cashFlow += quantity * price;
    else if (fill.type === 'BUY') cashFlow -= quantity * price;
    totalFees += fee;
    if (fill.type === closingType && quantity > 0) hasClosing = true;
  }
  return { hasClosing, pnl: cashFlow - totalFees };
};

const toSavedFill = (fill) => ({
  id: fill.id,
  type: fill.type,
  date: fill.date,
  quantity: fill.quantity,
  price: fill.price,
  fee: fill.fee,
});
