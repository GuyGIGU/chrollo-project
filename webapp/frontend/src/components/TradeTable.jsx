import React, { useState, useEffect, useMemo, useCallback } from 'react';
import useSSE from '../hooks/useSSE';
import useIBKRStatus from '../hooks/useIBKRStatus';
import { API_BASE } from '../api';
import { isOptionSymbol, inferDirection } from '../App';

// Editable text-input cells in tab order. Side is a toggle (not in this list).
const EDITABLE_FIELDS = ['opening_date', 'ticker', 'entry_price', 'stop_loss', 'quantity'];

const todayIso = () => new Date().toISOString().split('T')[0];

const emptyDraft = () => ({
  opening_date: todayIso(),
  direction: 'LONG',
  ticker: '',
  entry_price: '',
  stop_loss: '',
  quantity: '',
});

const parseActions = (json) => {
  if (!json) return [];
  try {
    const arr = JSON.parse(json);
    return Array.isArray(arr) ? arr : [];
  } catch { return []; }
};

const fmtMoney = (v, dp = 2) => {
  if (v == null || !Number.isFinite(Number(v))) return '—';
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
};
const fmtInt = (v) => {
  if (v == null || !Number.isFinite(Number(v))) return '—';
  return Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 });
};
const fmtDateShort = (s) => {
  if (!s) return '—';
  // YYYY-MM-DD → MMM-DD
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return s;
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[Number(m[2]) - 1]} ${Number(m[3])}`;
};

const TradeTable = ({
  trades = [],
  draftRow,
  setDraftRow,
  onDetailClick,
  onTradeUpdate,
}) => {
  const [yfPrices, setYfPrices] = useState({});
  const [editingCell, setEditingCell] = useState(null); // {tradeId|'draft', field}
  const [cellDraft, setCellDraft] = useState('');
  const [expandedFills, setExpandedFills] = useState(() => new Set());
  // Local fills buffer while editing a trade's actions (keyed by trade id)
  const [fillsBuffer, setFillsBuffer] = useState({}); // {tradeId: [actions]}

  const ibkrStatus = useIBKRStatus(10000);
  const ibkrConnected = !!ibkrStatus?.connected;
  const { data: portfolioSnap } = useSSE(
    ibkrStatus?.available ? `${API_BASE}/stream/portfolio` : null,
    { enabled: !!ibkrStatus?.available },
  );

  const ibkrPriceMap = useMemo(() => {
    const map = {};
    for (const p of portfolioSnap?.positions || []) {
      if (!p?.symbol) continue;
      const px = p.market_price;
      if (px != null && Number.isFinite(Number(px))) {
        map[p.symbol.toUpperCase()] = Number(px);
      }
    }
    return map;
  }, [portfolioSnap]);

  // Live-price polling for open tickers w/o IBKR coverage (preserved behavior)
  const openTickers = useMemo(() => {
    const set = new Set();
    for (const t of trades) {
      if (!t.closing_date && (t.pnl == null) && t.ticker) {
        set.add(String(t.ticker).toUpperCase());
      }
    }
    return [...set];
  }, [trades]);
  const openTickersString = useMemo(() => openTickers.join(','), [openTickers]);
  useEffect(() => {
    if (openTickers.length === 0) return;
    const missing = openTickers.filter(tk => ibkrPriceMap[tk] == null);
    if (missing.length === 0) return;
    let cancelled = false;
    const fetchYf = () => {
      fetch(`${API_BASE}/live-prices/?tickers=${missing.join(',')}`)
        .then(r => r.ok ? r.json() : {})
        .then(data => { if (!cancelled) setYfPrices(prev => ({ ...prev, ...data })); })
        .catch(() => {});
    };
    fetchYf();
    const id = setInterval(fetchYf, ibkrConnected ? 60000 : 20000);
    return () => { cancelled = true; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openTickersString, ibkrConnected, ibkrPriceMap]);

  const priceFor = useCallback((ticker) => {
    const tk = String(ticker || '').toUpperCase();
    if (ibkrPriceMap[tk] != null) return { price: ibkrPriceMap[tk], source: 'ibkr' };
    if (yfPrices[tk] != null) return { price: yfPrices[tk], source: 'yf' };
    return { price: null, source: null };
  }, [ibkrPriceMap, yfPrices]);

  // ── Per-trade derived data ──────────────────────────────────────
  const deriveRow = useCallback((t) => {
    const direction = inferDirection(t);
    const isLong = direction === 'LONG';
    const isOpt = isOptionSymbol(t.ticker);
    const multiplier = isOpt ? 100 : 1;
    const openSide = isLong ? 'BUY' : 'SELL';
    const closeSide = isLong ? 'SELL' : 'BUY';

    const extras = parseActions(t.actions_json);
    const initialQty = Number(t.quantity) || 0;
    let openQty = initialQty;
    let openCash = (Number(t.entry_price) || 0) * initialQty * multiplier;
    let openFees = Number(t.commissions) || 0;
    let closeQty = 0;
    let closeCash = 0;
    let closeFees = 0;
    let lastCloseDate = null;
    let firstCloseDate = null;
    for (const a of extras) {
      const q = parseFloat(a.quantity) || 0;
      const p = parseFloat(a.price) || 0;
      const f = parseFloat(a.fee) || 0;
      if (a.type === openSide) {
        openQty += q;
        openCash += q * p * multiplier;
        openFees += f;
      } else if (a.type === closeSide) {
        closeQty += q;
        closeCash += q * p * multiplier;
        closeFees += f;
        if (a.date) {
          if (!firstCloseDate || a.date < firstCloseDate) firstCloseDate = a.date;
          if (!lastCloseDate || a.date > lastCloseDate) lastCloseDate = a.date;
        }
      }
    }
    const entryVwap = openQty > 0 ? openCash / (openQty * multiplier) : Number(t.entry_price) || null;
    const position = openQty - closeQty;
    const totalWorth = entryVwap != null ? entryVwap * openQty * multiplier : null;

    // Live price for held position
    const { price: livePrice, source: liveSource } = priceFor(t.ticker);

    // Current/Exit price column
    let currentExit = null;
    let currentExitSource = null;
    if (position > 0 && livePrice != null) {
      currentExit = livePrice;
      currentExitSource = liveSource;
    } else if (closeQty > 0) {
      currentExit = closeCash / (closeQty * multiplier);
      currentExitSource = 'fills';
    } else if (t.exit_price != null) {
      currentExit = Number(t.exit_price);
      currentExitSource = 'fills';
    }

    // P&L
    let pnl = null;
    if (closeQty > 0) {
      const realizedCloseCash = isLong ? closeCash : -closeCash;
      const realizedOpenCashClosed = isLong ? -(entryVwap * closeQty * multiplier) : (entryVwap * closeQty * multiplier);
      let realized = realizedCloseCash + realizedOpenCashClosed - openFees * (closeQty / Math.max(openQty, 1)) - closeFees;
      if (position > 0 && livePrice != null) {
        const unrealized = isLong
          ? (livePrice - entryVwap) * position * multiplier
          : (entryVwap - livePrice) * position * multiplier;
        pnl = realized + unrealized;
      } else {
        pnl = realized;
      }
    } else if (position > 0 && livePrice != null && entryVwap != null) {
      pnl = isLong
        ? (livePrice - entryVwap) * position * multiplier
        : (entryVwap - livePrice) * position * multiplier;
    } else if (t.pnl != null) {
      pnl = Number(t.pnl);
    }

    // Total Exit cash
    const totalExit = closeQty > 0 ? closeCash : null;
    const exitDate = position <= 0 && lastCloseDate ? lastCloseDate : (position <= 0 ? (t.closing_date || null) : null);

    // Stop %
    const stopVal = (t.stop_loss && Number(t.stop_loss) !== 0) ? Number(t.stop_loss) : null;
    const stopPct = (stopVal != null && entryVwap != null)
      ? Math.abs(entryVwap - stopVal) / entryVwap * 100
      : null;

    // R value
    const rDist = (stopVal != null && entryVwap != null) ? Math.abs(entryVwap - stopVal) : null;
    const rValue = (rDist && rDist > 0 && openQty && pnl != null)
      ? (pnl / (rDist * openQty * multiplier))
      : null;

    // Status
    let status = 'draft';
    if (position > 0 && closeQty === 0) status = 'open';
    else if (position > 0 && closeQty > 0) status = 'partial';
    else if (position <= 0 && closeQty > 0) {
      if (pnl > 0) status = 'win';
      else if (pnl < 0) status = 'loss';
      else status = 'wash';
    } else if (initialQty > 0) status = 'open';

    return {
      direction, isLong, isOpt, multiplier,
      entryVwap, openQty, position, totalWorth,
      currentExit, currentExitSource,
      pnl, totalExit, exitDate,
      stopVal, stopPct, rValue,
      status,
    };
  }, [priceFor]);

  // ── Cell editing ────────────────────────────────────────────────
  const beginEdit = (rowId, field, currentValue) => {
    setEditingCell({ rowId, field });
    setCellDraft(currentValue == null ? '' : String(currentValue));
  };
  const cancelEdit = () => { setEditingCell(null); setCellDraft(''); };

  const commitDraftCell = useCallback(async (field, raw) => {
    const next = { ...(draftRow || emptyDraft()), [field]: raw };
    setDraftRow(next);
    // Auto-submit when all required fields filled
    const ready = next.ticker && next.entry_price && next.stop_loss && next.quantity && next.opening_date;
    if (ready) {
      try {
        const payload = {
          opening_date: next.opening_date,
          direction: next.direction,
          ticker: next.ticker.toUpperCase().trim(),
          entry_price: parseFloat(next.entry_price),
          stop_loss: parseFloat(next.stop_loss),
          quantity: parseInt(next.quantity, 10),
          position_size: parseFloat(next.entry_price) * parseInt(next.quantity, 10),
        };
        const res = await fetch(`${API_BASE}/trades/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          setDraftRow(null);
          if (onTradeUpdate) onTradeUpdate();
        }
      } catch (err) {
        console.error('Draft save failed:', err);
      }
    }
  }, [draftRow, setDraftRow, onTradeUpdate]);

  const commitTradeCell = useCallback(async (trade, field, raw) => {
    // Coerce
    let value = raw;
    if (['entry_price', 'stop_loss'].includes(field)) value = parseFloat(raw);
    else if (field === 'quantity') value = parseInt(raw, 10);
    if (field !== 'ticker' && field !== 'opening_date' && field !== 'direction') {
      if (!Number.isFinite(value)) return;
    } else if (field === 'ticker') {
      value = String(raw).toUpperCase().trim();
      if (!value) return;
    }
    if (trade[field] === value) return; // no-op
    try {
      const body = { [field]: value };
      // Keep position_size consistent with entry × qty for manual edits
      if (field === 'entry_price' || field === 'quantity') {
        const e = field === 'entry_price' ? value : Number(trade.entry_price);
        const q = field === 'quantity' ? value : Number(trade.quantity);
        if (Number.isFinite(e) && Number.isFinite(q)) body.position_size = e * q;
      }
      const res = await fetch(`${API_BASE}/trades/${trade.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok && onTradeUpdate) onTradeUpdate();
    } catch (err) {
      console.error('Cell save failed:', err);
    }
  }, [onTradeUpdate]);

  const handleCellCommit = async () => {
    if (!editingCell) return;
    const { rowId, field } = editingCell;
    const raw = cellDraft;
    cancelEdit();
    if (rowId === 'draft') await commitDraftCell(field, raw);
    else {
      const trade = trades.find(t => t.id === rowId);
      if (trade) await commitTradeCell(trade, field, raw);
    }
  };

  const handleCellKey = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); handleCellCommit(); }
    else if (e.key === 'Escape') { e.preventDefault(); cancelEdit(); }
    else if (e.key === 'Tab') {
      e.preventDefault();
      const { rowId, field } = editingCell || {};
      const idx = EDITABLE_FIELDS.indexOf(field);
      const nextField = e.shiftKey
        ? EDITABLE_FIELDS[Math.max(0, idx - 1)]
        : EDITABLE_FIELDS[Math.min(EDITABLE_FIELDS.length - 1, idx + 1)];
      // Commit then move
      handleCellCommit().then(() => {
        if (nextField && nextField !== field) {
          let current = '';
          if (rowId === 'draft') current = draftRow?.[nextField] ?? '';
          else {
            const t = trades.find(t => t.id === rowId);
            current = t ? t[nextField] ?? '' : '';
          }
          setEditingCell({ rowId, field: nextField });
          setCellDraft(String(current));
        }
      });
    }
  };

  const toggleSide = async (trade) => {
    const next = inferDirection(trade) === 'LONG' ? 'SHORT' : 'LONG';
    await commitTradeCell(trade, 'direction', next);
  };

  const toggleDraftSide = () => {
    setDraftRow({ ...(draftRow || emptyDraft()), direction: (draftRow?.direction === 'SHORT') ? 'LONG' : 'SHORT' });
  };

  const cancelDraft = () => setDraftRow(null);

  // ── Fills sub-row ───────────────────────────────────────────────
  const toggleExpand = (tradeId) => {
    setExpandedFills(prev => {
      const next = new Set(prev);
      if (next.has(tradeId)) next.delete(tradeId);
      else {
        next.add(tradeId);
        // Initialize buffer if absent
        setFillsBuffer(b => {
          if (b[tradeId]) return b;
          const trade = trades.find(t => t.id === tradeId);
          if (!trade) return b;
          const initial = {
            id: 'initial',
            type: inferDirection(trade) === 'LONG' ? 'BUY' : 'SELL',
            date: trade.opening_date || '',
            quantity: trade.quantity || '',
            price: trade.entry_price || '',
            fee: trade.commissions || 0,
            isInitial: true,
          };
          return { ...b, [tradeId]: [initial, ...parseActions(trade.actions_json)] };
        });
      }
      return next;
    });
  };

  const updateFill = (tradeId, fillId, field, value) => {
    setFillsBuffer(prev => ({
      ...prev,
      [tradeId]: (prev[tradeId] || []).map(a => a.id === fillId ? { ...a, [field]: value } : a),
    }));
  };

  const addFill = (tradeId) => {
    setFillsBuffer(prev => ({
      ...prev,
      [tradeId]: [...(prev[tradeId] || []), { id: Date.now(), type: 'BUY', date: todayIso(), quantity: '', price: '', fee: 0 }],
    }));
  };

  const removeFill = (tradeId, fillId) => {
    if (fillId === 'initial') return; // protect the initial leg
    setFillsBuffer(prev => ({ ...prev, [tradeId]: (prev[tradeId] || []).filter(a => a.id !== fillId) }));
  };

  const toggleFillSide = (tradeId, fillId) => {
    setFillsBuffer(prev => ({
      ...prev,
      [tradeId]: (prev[tradeId] || []).map(a =>
        a.id === fillId ? { ...a, type: a.type === 'BUY' ? 'SELL' : 'BUY' } : a),
    }));
  };

  const saveFills = async (trade) => {
    const fills = fillsBuffer[trade.id] || [];
    if (fills.length === 0) return;
    const [first, ...rest] = fills;
    // Recompute pnl + exit + closing date
    const direction = inferDirection(trade);
    const closingType = direction === 'LONG' ? 'SELL' : 'BUY';
    let cashFlow = 0;
    let totalFees = 0;
    let hasClosing = false;
    for (const a of fills) {
      const q = parseFloat(a.quantity) || 0;
      const p = parseFloat(a.price) || 0;
      const f = parseFloat(a.fee) || 0;
      if (a.type === 'SELL') cashFlow += q * p;
      else if (a.type === 'BUY') cashFlow -= q * p;
      totalFees += f;
      if (a.type === closingType && q > 0) hasClosing = true;
    }
    const pnl = hasClosing ? cashFlow - totalFees : null;

    // Last closing fill → exit_price / closing_date
    let exit_price = null;
    let closing_date = null;
    for (let i = fills.length - 1; i >= 0; i--) {
      const a = fills[i];
      if (a.type === closingType && parseFloat(a.quantity) > 0) {
        exit_price = parseFloat(a.price) || null;
        closing_date = a.date || null;
        break;
      }
    }

    const payload = {
      opening_date: first.date || trade.opening_date,
      entry_price: parseFloat(first.price) || 0,
      quantity: parseInt(first.quantity, 10) || 0,
      commissions: parseFloat(first.fee) || 0,
      actions_json: rest.length > 0 ? JSON.stringify(rest.map(r => ({
        id: r.id, type: r.type, date: r.date, quantity: r.quantity, price: r.price, fee: r.fee,
      }))) : null,
      exit_price,
      closing_date,
      pnl,
    };
    try {
      const res = await fetch(`${API_BASE}/trades/${trade.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok && onTradeUpdate) onTradeUpdate();
    } catch (err) {
      console.error('Fills save failed:', err);
    }
  };

  // ── Rendering helpers ───────────────────────────────────────────
  const editableCell = (rowId, field, displayValue, opts = {}) => {
    const isEditing = editingCell && editingCell.rowId === rowId && editingCell.field === field;
    const editableClass = 'cell-editable';
    const cls = ['text', editableClass, opts.num ? 'num' : '', opts.divider ? 'col-divider' : '']
      .filter(Boolean).join(' ');

    if (isEditing) {
      return (
        <td className={cls}>
          <input
            autoFocus
            className={`cell-input ${opts.num ? 'num' : ''}`}
            type={opts.inputType || 'text'}
            step={opts.step}
            value={cellDraft}
            onChange={(e) => setCellDraft(e.target.value)}
            onBlur={handleCellCommit}
            onKeyDown={handleCellKey}
          />
        </td>
      );
    }

    const rawValue = opts.rawForEdit != null ? opts.rawForEdit : displayValue;
    return (
      <td
        className={cls}
        onClick={() => beginEdit(rowId, field, rawValue)}
      >
        <div className={`cell-shell ${opts.num ? 'num' : ''}`}>
          {displayValue || <span style={{ color: 'var(--text-faint)' }}>—</span>}
          {opts.sub && <span className="sub">{opts.sub}</span>}
        </div>
      </td>
    );
  };

  const computedCell = (content, opts = {}) => (
    <td className={['text', 'cell-computed', opts.num ? 'num' : '', opts.divider ? 'col-divider' : ''].filter(Boolean).join(' ')}>
      <div className={`cell-shell readonly ${opts.num ? 'num' : ''} ${opts.center ? 'center' : ''}`}>
        {content}
      </div>
    </td>
  );

  // ── Draft row ───────────────────────────────────────────────────
  const renderDraftRow = () => {
    if (!draftRow) return null;
    const rowId = 'draft';
    const isLong = draftRow.direction !== 'SHORT';
    return (
      <tr className="trade-row draft">
        {/* expand chevron — disabled until trade exists */}
        <td className="text"><div className="cell-shell readonly center">
          <button onClick={cancelDraft} title="Discard draft"
            style={{background:'transparent',border:'none',color:'var(--text-faint)',cursor:'pointer',fontSize:'13px'}}>×</button>
        </div></td>

        {editableCell(rowId, 'opening_date', fmtDateShort(draftRow.opening_date),
          { rawForEdit: draftRow.opening_date, inputType: 'date' })}

        {editableCell(rowId, 'ticker',
          draftRow.ticker ? <span className="symbol-cell">{draftRow.ticker}</span> : '',
          { rawForEdit: draftRow.ticker })}

        {/* Status: draft */}
        {computedCell(<span className="status-cell draft">DRAFT</span>)}

        {/* Side toggle */}
        <td className="text cell-editable">
          <div className="cell-shell center" onClick={toggleDraftSide}>
            <span className={`side-arrow ${isLong ? 'long' : 'short'}`}>{isLong ? '↑' : '↓'}</span>
          </div>
        </td>

        {editableCell(rowId, 'entry_price',
          draftRow.entry_price ? `$${fmtMoney(draftRow.entry_price)}` : '',
          { rawForEdit: draftRow.entry_price, num: true, inputType: 'number', step: '0.01' })}

        {editableCell(rowId, 'stop_loss',
          draftRow.stop_loss ? `$${fmtMoney(draftRow.stop_loss)}` : '',
          { rawForEdit: draftRow.stop_loss, num: true, inputType: 'number', step: '0.01' })}

        {editableCell(rowId, 'quantity',
          draftRow.quantity ? fmtInt(draftRow.quantity) : '',
          { rawForEdit: draftRow.quantity, num: true, inputType: 'number' })}

        {computedCell(
          (draftRow.entry_price && draftRow.quantity)
            ? `$${fmtMoney(Number(draftRow.entry_price) * Number(draftRow.quantity), 0)}`
            : '—',
          { num: true })}

        {/* EXECUTION group — all empty for draft */}
        {computedCell('—', { num: true, divider: true })}
        {computedCell('—', { num: true })}
        {computedCell('—', { num: true })}
        {computedCell('—', { num: true })}
        {computedCell('—')}

        <td className="text"><div className="cell-shell readonly center" /></td>
      </tr>
    );
  };

  // ── Main trade row ──────────────────────────────────────────────
  const renderTradeRow = (t) => {
    const d = deriveRow(t);
    const expanded = expandedFills.has(t.id);
    const rowId = t.id;

    return (
      <React.Fragment key={t.id}>
        <tr className="trade-row">
          <td className="text">
            <div className="cell-shell readonly center">
              <span className={`expand-chev ${expanded ? 'open' : ''}`} onClick={() => toggleExpand(t.id)} title="Show fills">▸</span>
            </div>
          </td>

          {editableCell(rowId, 'opening_date', fmtDateShort(t.opening_date),
            { rawForEdit: t.opening_date, inputType: 'date' })}

          {editableCell(rowId, 'ticker',
            <span className="symbol-cell">{t.ticker}</span>,
            { rawForEdit: t.ticker })}

          {computedCell(
            <span className={`status-cell ${d.status}`}>{d.status}</span>,
          )}

          <td className="text cell-editable">
            <div className="cell-shell center" onClick={() => toggleSide(t)}>
              <span className={`side-arrow ${d.isLong ? 'long' : 'short'}`}>{d.isLong ? '↑' : '↓'}</span>
            </div>
          </td>

          {editableCell(rowId, 'entry_price',
            t.entry_price != null ? `$${fmtMoney(t.entry_price)}` : '',
            { rawForEdit: t.entry_price, num: true, inputType: 'number', step: '0.01' })}

          {editableCell(rowId, 'stop_loss',
            d.stopVal != null ? `$${fmtMoney(d.stopVal)}` : '',
            {
              rawForEdit: t.stop_loss, num: true, inputType: 'number', step: '0.01',
              sub: d.stopPct != null ? `${d.stopPct.toFixed(1)}%` : null,
            })}

          {editableCell(rowId, 'quantity',
            t.quantity != null ? fmtInt(t.quantity) : '',
            { rawForEdit: t.quantity, num: true, inputType: 'number' })}

          {computedCell(d.totalWorth != null ? `$${fmtMoney(d.totalWorth, 0)}` : '—', { num: true })}

          {/* EXECUTION GROUP */}
          {computedCell(d.position != null ? fmtInt(d.position) : '—', { num: true, divider: true })}

          {computedCell(
            d.currentExit != null ? (
              <span>
                ${fmtMoney(d.currentExit)}
                {d.currentExitSource === 'ibkr' && <span className="sub">IBKR</span>}
                {d.currentExitSource === 'yf' && <span className="sub">LIVE</span>}
              </span>
            ) : '—',
            { num: true },
          )}

          {computedCell(
            d.pnl != null ? (
              <span style={{
                color: d.pnl > 0 ? 'var(--success)' : d.pnl < 0 ? 'var(--danger)' : 'var(--text-muted)',
                fontWeight: 600,
              }}>
                {d.pnl >= 0 ? '+' : '−'}${fmtMoney(Math.abs(d.pnl))}
                {d.rValue != null && (
                  <span className="sub" style={{
                    color: d.rValue > 0 ? 'var(--success)' : d.rValue < 0 ? 'var(--danger)' : 'var(--text-faint)',
                    opacity: 0.85,
                  }}>{d.rValue >= 0 ? '+' : ''}{d.rValue.toFixed(2)}R</span>
                )}
              </span>
            ) : '—',
            { num: true },
          )}

          {computedCell(d.totalExit != null ? `$${fmtMoney(d.totalExit, 0)}` : '—', { num: true })}

          {computedCell(fmtDateShort(d.exitDate))}

          <td className="text" style={{ cursor: 'pointer' }}
            onClick={() => onDetailClick && onDetailClick(t)}
            title="Open detail drawer">
            <div className="cell-shell readonly center" style={{ color: 'var(--text-muted)', letterSpacing: '2px' }}>⋯</div>
          </td>
        </tr>

        {expanded && renderFillsRow(t)}
      </React.Fragment>
    );
  };

  const renderFillsRow = (t) => {
    const fills = fillsBuffer[t.id] || [];
    return (
      <tr className="fills-row">
        <td colSpan={15}>
          <div className="fills-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                Fills · {t.ticker}
              </span>
              <button
                onClick={() => saveFills(t)}
                style={{
                  background: 'var(--accent-blue)', color: '#fff', border: 'none',
                  padding: '4px 14px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                  cursor: 'pointer', letterSpacing: '0.05em', textTransform: 'uppercase',
                }}
              >Save fills</button>
            </div>
            <div className="fills-head">
              <div></div>
              <div>Action</div>
              <div>Date</div>
              <div>Qty</div>
              <div>Price</div>
              <div>Fee</div>
              <div></div>
            </div>
            {fills.map((f) => (
              <div key={f.id} className="fill-row">
                <span style={{ fontSize: 9, color: 'var(--text-faint)', textAlign: 'center' }}>
                  {f.isInitial ? '◆' : ''}
                </span>
                <button
                  className={`fill-side-btn ${f.type === 'BUY' ? 'buy' : 'sell'}`}
                  onClick={() => toggleFillSide(t.id, f.id)}
                >{f.type}</button>
                <input className="fill-input" type="date" value={f.date || ''}
                  onChange={(e) => updateFill(t.id, f.id, 'date', e.target.value)} />
                <input className="fill-input" type="number" placeholder="0" value={f.quantity ?? ''}
                  onChange={(e) => updateFill(t.id, f.id, 'quantity', e.target.value)} />
                <input className="fill-input" type="number" step="0.01" placeholder="0.00" value={f.price ?? ''}
                  onChange={(e) => updateFill(t.id, f.id, 'price', e.target.value)} />
                <input className="fill-input" type="number" step="0.01" placeholder="0" value={f.fee ?? ''}
                  onChange={(e) => updateFill(t.id, f.id, 'fee', e.target.value)} />
                <button className="fill-del" onClick={() => removeFill(t.id, f.id)} disabled={f.isInitial}
                  title={f.isInitial ? 'Initial fill — edit via cells above' : 'Remove fill'}
                  style={{ opacity: f.isInitial ? 0.3 : 1 }}>×</button>
              </div>
            ))}
            <button className="fill-add" onClick={() => addFill(t.id)}>+ Add fill</button>
          </div>
        </td>
      </tr>
    );
  };

  // ── Header ──────────────────────────────────────────────────────
  return (
    <div style={{ marginTop: '1rem', overflowX: 'auto', paddingBottom: '1rem' }}>
      <table className="trade-table">
        <thead>
          <tr className="group-row">
            <th colSpan={9}>Plan</th>
            <th colSpan={6} className="group-execution">Execution</th>
          </tr>
          <tr className="col-row">
            <th></th>
            <th>Date</th>
            <th>Symbol</th>
            <th>Status</th>
            <th>Side</th>
            <th className="num">Entry</th>
            <th className="num">Stop</th>
            <th className="num">Qty</th>
            <th className="num">Total $</th>
            <th className="num col-divider">Pos</th>
            <th className="num">Current/Exit</th>
            <th className="num">P&amp;L</th>
            <th className="num">Total Exit</th>
            <th>Exit Date</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {renderDraftRow()}
          {trades.map(renderTradeRow)}
        </tbody>
      </table>

      {trades.length === 0 && !draftRow && (
        <div style={{
          marginTop: '2rem', background: 'var(--bg-panel)', border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)', padding: '2rem', textAlign: 'center',
          color: 'var(--text-muted)', fontSize: '12px', width: '50%', margin: '3rem auto',
        }}>
          No trades to display. Click <strong style={{ color: 'var(--text-main)' }}>+ New Trade</strong> to add one,
          or import an IBKR Activity Statement.
        </div>
      )}
    </div>
  );
};

export default TradeTable;
