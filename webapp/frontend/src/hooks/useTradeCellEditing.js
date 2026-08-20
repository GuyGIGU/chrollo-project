import { useCallback, useState } from 'react';
import { API_BASE } from '../api';
import { toast } from '../components/ui/feedback';
import { inferDirection } from '../utils/tradeUtils';
import { EDITABLE_FIELDS, emptyDraft } from '../utils/tradeTableUtils';

export default function useTradeCellEditing({ draftRow, onTradeUpdate, setDraftRow, trades }) {
  const [editingCell, setEditingCell] = useState(null);
  const [cellDraft, setCellDraft] = useState('');

  const beginEdit = (rowId, field, currentValue) => {
    setEditingCell({ rowId, field });
    setCellDraft(currentValue == null ? '' : String(currentValue));
  };

  const cancelEdit = () => {
    setEditingCell(null);
    setCellDraft('');
  };

  const commitDraftCell = useCallback(async (field, raw) => {
    const next = { ...(draftRow || emptyDraft()), [field]: raw };
    setDraftRow(next);
    const ready = next.ticker && next.entry_price && next.stop_loss && next.quantity && next.opening_date;
    if (!ready) return true;

    try {
      const quantity = parseInt(next.quantity, 10);
      const entryPrice = parseFloat(next.entry_price);
      const response = await fetch(`${API_BASE}/trades/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          opening_date: next.opening_date,
          direction: next.direction,
          ticker: next.ticker.toUpperCase().trim(),
          entry_price: entryPrice,
          stop_loss: parseFloat(next.stop_loss),
          quantity,
          position_size: entryPrice * quantity,
        }),
      });
      if (response.ok) {
        setDraftRow(null);
        onTradeUpdate?.();
        return true;
      }
      toast(`Trade save failed (HTTP ${response.status})`, { tone: 'danger' });
    } catch (error) {
      console.error('Draft save failed:', error);
      toast('Trade save failed — network error.', { tone: 'danger' });
    }
    return false;
  }, [draftRow, onTradeUpdate, setDraftRow]);

  const commitTradeCell = useCallback(async (trade, field, raw) => {
    const value = coerceTradeValue(field, raw);
    if (value == null || trade[field] === value) return true;

    try {
      const body = { [field]: value };
      if (field === 'entry_price' || field === 'quantity') {
        const entry = field === 'entry_price' ? value : Number(trade.entry_price);
        const quantity = field === 'quantity' ? value : Number(trade.quantity);
        if (Number.isFinite(entry) && Number.isFinite(quantity)) body.position_size = entry * quantity;
      }
      const response = await fetch(`${API_BASE}/trades/${trade.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (response.ok) {
        onTradeUpdate?.();
        return true;
      }
      toast(`Cell save failed (HTTP ${response.status})`, { tone: 'danger' });
    } catch (error) {
      console.error('Cell save failed:', error);
      toast('Cell save failed — network error.', { tone: 'danger' });
    }
    return false;
  }, [onTradeUpdate]);

  // Optimistic close: the cell exits edit mode immediately, but a failed write
  // restores the draft so the operator's keystrokes are never silently lost.
  const handleCellCommit = async () => {
    if (!editingCell) return true;
    const { rowId, field } = editingCell;
    const raw = cellDraft;
    cancelEdit();
    let committed = true;
    if (rowId === 'draft') {
      committed = await commitDraftCell(field, raw);
    } else {
      const trade = trades.find(item => item.id === rowId);
      if (trade) committed = await commitTradeCell(trade, field, raw);
    }
    if (!committed) beginEdit(rowId, field, raw);
    return committed;
  };

  const handleCellKey = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleCellCommit();
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      cancelEdit();
      return;
    }
    if (event.key !== 'Tab') return;

    event.preventDefault();
    const { rowId, field } = editingCell || {};
    const index = EDITABLE_FIELDS.indexOf(field);
    const nextField = event.shiftKey
      ? EDITABLE_FIELDS[Math.max(0, index - 1)]
      : EDITABLE_FIELDS[Math.min(EDITABLE_FIELDS.length - 1, index + 1)];
    handleCellCommit().then((committed) => {
      if (committed && nextField && nextField !== field) beginEdit(rowId, nextField, getCellValue(rowId, nextField, draftRow, trades));
    });
  };

  const toggleSide = async (trade) => {
    const next = inferDirection(trade) === 'LONG' ? 'SHORT' : 'LONG';
    await commitTradeCell(trade, 'direction', next);
  };

  const toggleDraftSide = () => {
    setDraftRow({
      ...(draftRow || emptyDraft()),
      direction: draftRow?.direction === 'SHORT' ? 'LONG' : 'SHORT',
    });
  };

  return {
    beginEdit,
    cancelDraft: () => setDraftRow(null),
    cellDraft,
    commitTradeCell,
    editingCell,
    handleCellCommit,
    handleCellKey,
    setCellDraft,
    toggleDraftSide,
    toggleSide,
  };
}

const coerceTradeValue = (field, raw) => {
  if (field === 'entry_price' || field === 'stop_loss') {
    const value = parseFloat(raw);
    return Number.isFinite(value) ? value : null;
  }
  if (field === 'quantity') {
    const value = parseInt(raw, 10);
    return Number.isFinite(value) ? value : null;
  }
  if (field === 'ticker') {
    const value = String(raw).toUpperCase().trim();
    return value || null;
  }
  return raw;
};

const getCellValue = (rowId, field, draftRow, trades) => {
  if (rowId === 'draft') return draftRow?.[field] ?? '';
  const trade = trades.find(item => item.id === rowId);
  return trade ? trade[field] ?? '' : '';
};
