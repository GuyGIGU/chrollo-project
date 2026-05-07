import React, { useState, useEffect, useMemo } from 'react';
import useSSE from '../hooks/useSSE';
import useIBKRStatus from '../hooks/useIBKRStatus';
import { API_BASE } from '../api';
import { isOptionSymbol, inferDirection } from '../App';

const TradeTable = ({ trades = [], onEditClick, onDetailClick, onTradeUpdate }) => {
  const [yfPrices, setYfPrices] = useState({});

  // Inline R-multiplier editing. Track the slot too (t1 vs t2) so only one input
  // renders at a time — otherwise both T1 and T2 chips become autoFocus inputs and
  // they steal focus from each other, firing onBlur immediately.
  const [editingR, setEditingR] = useState(null); // { tradeId, slot } | null
  const [rDraft, setRDraft] = useState('');
  const [rSaving, setRSaving] = useState(false);

  const beginEditR = (trade, slot) => {
    setEditingR({ tradeId: trade.id, slot });
    setRDraft(String(trade.target_r ?? 3));
  };

  const cancelEditR = () => {
    setEditingR(null);
    setRDraft('');
  };

  const commitEditR = async (tradeId) => {
    const next = parseFloat(rDraft);
    if (!Number.isFinite(next) || next <= 0) {
      cancelEditR();
      return;
    }
    setRSaving(true);
    try {
      const res = await fetch(`${API_BASE}/trades/${tradeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_r: next }),
      });
      if (!res.ok) throw new Error(await res.text());
      if (onTradeUpdate) onTradeUpdate();
    } catch (err) {
      console.error('Failed to update target_r:', err);
    } finally {
      setRSaving(false);
      cancelEditR();
    }
  };

  const displayTrades = trades;

  const ibkrStatus = useIBKRStatus(10000);
  const ibkrConnected = !!ibkrStatus?.connected;

  const { data: portfolioSnap } = useSSE(
    ibkrStatus?.available ? `${API_BASE}/stream/portfolio` : null,
    { enabled: !!ibkrStatus?.available },
  );

  const ibkrPriceMap = useMemo(() => {
    const map = {};
    const positions = portfolioSnap?.positions || [];
    for (const p of positions) {
      if (!p?.symbol) continue;
      const px = p.market_price;
      if (px != null && Number.isFinite(Number(px))) {
        map[p.symbol.toUpperCase()] = Number(px);
      }
    }
    return map;
  }, [portfolioSnap]);

  const openTickers = useMemo(() => {
    const set = new Set();
    for (const t of displayTrades) {
      if (!t.closing_date && (t.pnl === null || t.pnl === undefined) && t.ticker) {
        set.add(String(t.ticker).toUpperCase());
      }
    }
    return [...set];
  }, [displayTrades]);

  const openTickersString = useMemo(() => openTickers.join(','), [openTickers]);

  useEffect(() => {
    if (openTickers.length === 0) return;
    const missing = openTickers.filter(tk => ibkrPriceMap[tk] == null);
    if (missing.length === 0) return;

    let cancelled = false;
    const fetchYf = () => {
      fetch(`${API_BASE}/live-prices/?tickers=${missing.join(',')}`)
        .then(res => res.ok ? res.json() : {})
        .then(data => { if (!cancelled) setYfPrices(prev => ({ ...prev, ...data })); })
        .catch(err => console.error('Failed to fetch live prices:', err));
    };
    fetchYf();
    const id = setInterval(fetchYf, ibkrConnected ? 60000 : 20000);
    return () => { cancelled = true; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openTickersString, ibkrConnected, ibkrPriceMap]);

  const priceFor = (ticker) => {
    const tk = String(ticker || '').toUpperCase();
    if (ibkrPriceMap[tk] != null) return { price: ibkrPriceMap[tk], source: 'ibkr' };
    if (yfPrices[tk] != null) return { price: yfPrices[tk], source: 'yf' };
    return { price: null, source: null };
  };

  const deriveExitPrice = (t) => {
    if (t.exit_price != null) return Number(t.exit_price);
    if (!t.actions_json) return null;
    let extras = [];
    try { extras = JSON.parse(t.actions_json) || []; } catch { return null; }
    const closingType = t.direction === 'LONG' ? 'SELL' : 'BUY';
    for (let i = extras.length - 1; i >= 0; i--) {
      const a = extras[i];
      const qty = parseFloat(a.quantity) || 0;
      const price = parseFloat(a.price);
      if (a.type === closingType && qty > 0 && Number.isFinite(price)) return price;
    }
    return null;
  };

  const calculateTargets = (entry, stop, r, direction) => {
    if (!entry || !stop || !r) return { t1: null, t2: null };
    const rDist = Math.abs(entry - stop);
    if (rDist === 0) return { t1: null, t2: null };

    if (direction === 'LONG') {
      return {
        t1: entry + (rDist * r),
        t2: entry + (rDist * r * 2)
      };
    } else {
      return {
        t1: entry - (rDist * r),
        t2: entry - (rDist * r * 2)
      };
    }
  };

  // True once price has reached/crossed `level` in the trade's favourable direction.
  const reachedLevel = (current, level, direction) => {
    if (current == null || level == null) return false;
    return direction === 'LONG' ? current >= level : current <= level;
  };

  return (
    <div style={{ marginTop: '1rem', overflowX: 'auto', paddingBottom: '1rem' }}>
      <table className="trade-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Ticker</th>
            <th>Entry</th>
            <th>Stop</th>
            <th>Qty</th>
            <th>Current / Exit</th>
            <th>Trade $</th>
            <th>T1</th>
            <th>T2</th>
            <th>Exit Date</th>
            <th>P&L</th>
            <th>R</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {displayTrades.map((t) => {
            const isOpen = !t.closing_date && (t.pnl === null || t.pnl === undefined);
            const isOpt = isOptionSymbol(t.ticker);
            const direction = inferDirection(t);
            const isLong = direction === 'LONG';

            const rMultiplier = t.target_r || 3.0;
            const targets = calculateTargets(t.entry_price, t.stop_loss, rMultiplier, direction);

            // Unrealized P&L: use live price for open trades.
            let currentPrice = null;
            let displayPnl = t.pnl;
            let priceSource = null;

            if (isOpen) {
              const { price, source } = priceFor(t.ticker);
              if (price != null) {
                currentPrice = price;
                priceSource = source;
                displayPnl = isLong
                  ? (currentPrice - t.entry_price) * t.quantity
                  : (t.entry_price - currentPrice) * t.quantity;
              }
            }

            const exitPrice = !isOpen ? deriveExitPrice(t) : null;
            // Single "Current / Exit" column: live price for open, exit price for closed.
            const outcomePrice = isOpen ? currentPrice : exitPrice;
            const outcomeMove = (outcomePrice != null && t.entry_price)
              ? (isLong ? outcomePrice >= t.entry_price : outcomePrice <= t.entry_price)
              : null;

            // Notional ("Trade $") — entry × quantity, ×100 for option contracts.
            const multiplier = isOpt ? 100 : 1;
            const notional = (t.entry_price && t.quantity)
              ? Number(t.entry_price) * Number(t.quantity) * multiplier
              : null;

            const entTot = (t.entry_price * t.quantity * multiplier) || 0;
            const returnPct = (entTot > 0 && displayPnl != null) ? ((displayPnl / entTot) * 100) : null;
            const pnlColor = (displayPnl > 0) ? 'var(--success)' : ((displayPnl < 0) ? 'var(--danger)' : 'var(--text-muted)');

            // Stop + entry-to-stop %.
            const stopVal = (t.stop_loss && Number(t.stop_loss) !== 0) ? Number(t.stop_loss) : null;
            const stopPctFromEntry = (stopVal != null && t.entry_price)
              ? Math.abs(Number(t.entry_price) - stopVal) / Number(t.entry_price) * 100
              : null;

            // R: dynamic — uses current price for open, exit for closed.
            const rDist = (stopVal != null && t.entry_price) ? Math.abs(Number(t.entry_price) - stopVal) : null;
            const rValue = (rDist && rDist > 0 && t.quantity && displayPnl != null)
              ? (displayPnl / (rDist * Number(t.quantity) * multiplier))
              : null;
            const rColor = rValue == null ? 'var(--text-muted)'
              : rValue > 0 ? 'var(--success)'
              : rValue < 0 ? 'var(--danger)' : 'var(--text-muted)';

            // Target-hit ticks for open rows.
            const t1Hit = isOpen && reachedLevel(currentPrice, targets.t1, direction);
            const t2Hit = isOpen && reachedLevel(currentPrice, targets.t2, direction);

            // T1 = R, T2 = 2R.
            const t1RLabel = `${rMultiplier}R`;
            const t2RLabel = `${rMultiplier * 2}R`;

            const renderRChip = (slot, label) => {
              const isEditingThisSlot = editingR && editingR.tradeId === t.id && editingR.slot === slot;
              if (isEditingThisSlot) {
                return (
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    autoFocus
                    disabled={rSaving}
                    className="r-chip-input"
                    value={rDraft}
                    onChange={e => setRDraft(e.target.value)}
                    onClick={e => e.stopPropagation()}
                    onKeyDown={e => {
                      if (e.key === 'Enter') commitEditR(t.id);
                      if (e.key === 'Escape') cancelEditR();
                    }}
                    onBlur={() => commitEditR(t.id)}
                  />
                );
              }
              return (
                <span
                  className="r-chip"
                  title="Click to change this trade's R-multiplier (affects both T1 and T2)"
                  onClick={(e) => { e.stopPropagation(); beginEditR(t, slot); }}
                >{label}</span>
              );
            };

            return (
              <tr
                key={t.id}
                className="trade-row"
                onClick={() => { if(onEditClick) onEditClick(t) }}
              >
                {/* Date */}
                <td style={{color: 'var(--text-muted)'}}>{t.opening_date}</td>

                {/* Type (LONG/SHORT) */}
                <td>
                  <span className={`type-pill ${isLong ? 'long' : 'short'}`}>{isLong ? 'LONG' : 'SHORT'}</span>
                </td>

                {/* Ticker + STK/OPT */}
                <td style={{color: 'var(--accent-blue)', fontWeight: 600, fontSize: '12px'}}>
                  {t.ticker}
                  <span className={`asset-pill ${isOpt ? 'opt' : 'stk'}`}>{isOpt ? 'OPT' : 'STK'}</span>
                </td>

                {/* Entry */}
                <td style={{color: 'var(--text-main)'}}>${Number(t.entry_price).toFixed(2)}</td>

                {/* Stop + entry-to-stop % */}
                <td>
                  {stopVal != null ? (
                    <div className="cell-stack">
                      <span style={{color: 'var(--text-main)'}}>${stopVal.toFixed(2)}</span>
                      <span className="secondary">
                        {stopPctFromEntry != null ? `${stopPctFromEntry.toFixed(2)}% risk` : ''}
                      </span>
                    </div>
                  ) : (
                    <span style={{color: 'var(--text-faint)'}} title="Stop not set">—</span>
                  )}
                </td>

                {/* Qty */}
                <td style={{color: 'var(--text-main)'}}>{t.quantity}</td>

                {/* Current / Exit Price */}
                <td>
                  {outcomePrice != null ? (
                    <span className={outcomeMove === true ? '' : outcomeMove === false ? '' : ''}
                          style={{
                            color: outcomeMove === true ? 'var(--success)'
                                 : outcomeMove === false ? 'var(--danger)'
                                 : 'var(--text-main)',
                            fontWeight: 500,
                          }}>
                      ${outcomePrice.toFixed(2)}
                      {isOpen && priceSource && (
                        <span style={{
                          fontSize: '8px', marginLeft: 5, opacity: 0.7,
                          color: priceSource === 'ibkr' ? 'var(--accent-blue)' : 'var(--text-muted)',
                        }}>{priceSource === 'ibkr' ? 'IBKR' : 'LIVE'}</span>
                      )}
                    </span>
                  ) : (
                    <span style={{color: 'var(--text-faint)'}}>—</span>
                  )}
                </td>

                {/* Trade $ (notional) */}
                <td style={{color: 'var(--text-main)'}}>
                  {notional != null
                    ? `$${notional.toLocaleString('en-US', {maximumFractionDigits: 0})}`
                    : '—'}
                </td>

                {/* T1 */}
                <td>
                  <div className="cell-stack">
                    <span style={{color: t1Hit ? 'var(--success)' : 'var(--text-main)'}}>
                      {targets.t1 ? `$${targets.t1.toFixed(2)}` : '—'}
                      {t1Hit && <span title="Current price reached T1" style={{marginLeft: 4}}>✓</span>}
                    </span>
                    {renderRChip('t1', t1RLabel)}
                  </div>
                </td>

                {/* T2 */}
                <td>
                  <div className="cell-stack">
                    <span style={{color: t2Hit ? 'var(--success)' : 'var(--text-main)'}}>
                      {targets.t2 ? `$${targets.t2.toFixed(2)}` : '—'}
                      {t2Hit && <span title="Current price reached T2" style={{marginLeft: 4}}>✓</span>}
                    </span>
                    {renderRChip('t2', t2RLabel)}
                  </div>
                </td>

                {/* Exit Date */}
                <td style={{color: 'var(--text-muted)'}}>
                  {t.closing_date || <span style={{color: 'var(--text-faint)'}}>—</span>}
                </td>

                {/* P&L combined ($ + %) */}
                <td>
                  <div className="cell-stack">
                    <span style={{color: pnlColor, fontWeight: 600, fontSize: '12px'}}>
                      {displayPnl != null
                        ? `${displayPnl >= 0 ? '+' : '-'}$${Math.abs(Number(displayPnl)).toFixed(2)}`
                        : '—'}
                    </span>
                    <span className="secondary" style={{color: pnlColor, opacity: 0.85}}>
                      {returnPct != null
                        ? `${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(2)}%`
                        : ''}
                    </span>
                  </div>
                </td>

                {/* R */}
                <td
                  style={{color: rColor, fontWeight: 600}}
                  title={rValue == null && !stopVal ? 'Set a stop to see R' : 'P&L in initial-risk units (entry → stop distance)'}
                >
                  {rValue != null
                    ? `${rValue >= 0 ? '+' : ''}${rValue.toFixed(2)}R`
                    : <span style={{color: 'var(--text-faint)', fontWeight: 400}}>—</span>}
                </td>

                {/* Detail drawer */}
                <td
                  style={{textAlign: 'right', color: 'var(--text-muted)', letterSpacing: '2px', cursor: 'pointer'}}
                  onClick={(e) => { e.stopPropagation(); if (onDetailClick) onDetailClick(t); }}
                  title="Open detail drawer"
                >•••</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {trades.length === 0 && (
        <div style={{
          marginTop: '2rem', background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px', width: '50%', margin: '3rem auto'
        }}>
          No trades to display. Log a trade with <strong style={{color: 'var(--text-main)'}}>+ New Trade</strong>, or import an IBKR Activity Statement.
        </div>
      )}
    </div>
  )
}

export default TradeTable;
