import React, { useState, useEffect, useMemo } from 'react';
import useSSE from '../hooks/useSSE';
import useIBKRStatus from '../hooks/useIBKRStatus';
import { API_BASE } from '../api';

const TradeTable = ({ trades = [], onEditClick, onDetailClick }) => {
  const [yfPrices, setYfPrices] = useState({});

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

  const calculateHoldDays = (start, end) => {
    if (!start) return null;
    const s = new Date(start);
    const e = end ? new Date(end) : new Date();
    const diff = e.getTime() - s.getTime();
    if (diff < 0) return 0;
    return Math.ceil(diff / (1000 * 3600 * 24));
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

  return (
    <div style={{ marginTop: '1rem', overflowX: 'auto', paddingBottom: '1rem' }}>
      <table style={{ width: '100%', minWidth: '1000px', borderSpacing: 0 }}>
        <thead>
          <tr style={{ background: 'var(--bg-hover)' }}>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left', borderTopLeftRadius: '8px', borderBottomLeftRadius: '8px'}}>Date</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>Symbol</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>Status</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>Hold</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>Curr Prc</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>Target R</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>T1 Price</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>T2 Price</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>Qty</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>Entry</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>Exit</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>P&L ($)</th>
            <th style={{padding: '12px 14px', fontSize: '11px', fontWeight: '600', color: '#8b8b9c', textAlign: 'left'}}>P&L (%)</th>
            <th style={{padding: '12px 14px', borderTopRightRadius: '8px', borderBottomRightRadius: '8px'}}></th>
          </tr>
        </thead>
        <tbody style={{ borderSpacing: '0 8px' }}>
          
          {displayTrades.map((t) => {
            const isWin = t.pnl > 0;
            const isLoss = t.pnl < 0;
            const isWash = t.pnl === 0 && t.closing_date;
            const isOpen = !t.closing_date && (t.pnl === null || t.pnl === undefined);
            
            let statusStr = 'OPEN';
            if (isWin) statusStr = 'WIN';
            if (isLoss) statusStr = 'LOSS';
            if (isWash) statusStr = 'WASH';

            const entTot = (t.entry_price * t.quantity) || 0;
            const holdDays = calculateHoldDays(t.opening_date, t.closing_date);

            const rMultiplier = t.target_r || 3.0;
            const targets = calculateTargets(t.entry_price, t.stop_loss, rMultiplier, t.direction);

            // Unrealized P&L logic
            let currentPrice = null;
            let displayPnl = t.pnl;
            let isUnrealized = false;
            let priceSource = null;

            if (isOpen) {
              const { price, source } = priceFor(t.ticker);
              if (price != null) {
                currentPrice = price;
                priceSource = source;
                isUnrealized = true;
                if (t.direction === 'LONG') {
                  displayPnl = (currentPrice - t.entry_price) * t.quantity;
                } else {
                  displayPnl = (t.entry_price - currentPrice) * t.quantity;
                }
              }
            }

            const returnPct = (entTot > 0 && displayPnl != null) ? ((displayPnl / entTot) * 100) : null;
            const pnlColor = (displayPnl > 0) ? 'var(--success)' : ((displayPnl < 0) ? 'var(--danger)' : 'var(--text-muted)');

            return (
              <tr
                key={t.id}
                style={{
                  background: 'var(--bg-main)', 
                  cursor: 'pointer',
                  borderBottom: '1px solid rgba(42, 42, 54, 0.4)',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-panel)'}
                onMouseLeave={e => e.currentTarget.style.background = 'var(--bg-main)'}
                onClick={() => { if(onEditClick) onEditClick(t) }}
              >
                <td style={{padding: '12px 14px', fontSize: '11px', color: 'var(--text-muted)'}}>{t.opening_date}</td>
                
                <td style={{padding: '12px 14px', color: 'var(--accent-blue)', fontWeight: '600', fontSize: '12px'}}>
                   {t.ticker}
                   <span style={{fontSize: '9px', color: 'var(--text-muted)', border:'1px solid var(--border-color)', borderRadius:'2px', padding:'0 2px', marginLeft:'5px'}}>S</span>
                </td>
                
                <td style={{padding: '12px 14px'}}>
                  <span style={{
                    padding: '2px 8px', borderRadius: '12px', fontSize: '9px', fontWeight: 'bold', display: 'inline-flex', alignItems: 'center', gap: '4px',
                    background: isOpen ? 'rgba(255,255,255,0.1)' : (isWin ? 'var(--success-bg)' : (isLoss ? 'var(--danger-bg)' : 'rgba(202, 159, 60, 0.15)')),
                    color: isOpen ? '#fff' : (isWin ? 'var(--success)' : (isLoss ? 'var(--danger)' : 'var(--accent-yellow)')),
                  }}>
                    {statusStr}
                  </span>
                </td>
                
                <td style={{padding: '12px 14px', fontSize: '11px', color: 'var(--text-main)'}}>
                  {holdDays !== null ? `${holdDays}d` : '-'}
                </td>
                
                <td style={{padding: '12px 14px', fontSize: '12px', color: 'var(--accent-blue)', fontWeight: '500'}}>
                   {currentPrice ? `$${currentPrice.toFixed(2)}` : '-'}
                </td>
                
                <td style={{padding: '12px 14px', fontSize: '11px', color: 'var(--text-muted)'}}>{rMultiplier}R</td>
                
                <td style={{padding: '12px 14px', fontSize: '11px', color: 'var(--text-main)'}}>
                  {targets.t1 ? `$${targets.t1.toFixed(2)}` : '-'}
                </td>
                
                <td style={{padding: '12px 14px', fontSize: '11px', color: 'var(--text-main)'}}>
                  {targets.t2 ? `$${targets.t2.toFixed(2)}` : '-'}
                </td>

                <td style={{padding: '12px 14px', fontSize: '11px', color: 'var(--text-main)'}}>{t.quantity}</td>
                
                <td style={{padding: '12px 14px', fontSize: '11px', color: 'var(--text-muted)'}}>${Number(t.entry_price).toFixed(2)}</td>
                
                <td style={{padding: '12px 14px', fontSize: '11px', color: 'var(--text-muted)'}}>{(() => { const ex = deriveExitPrice(t); return ex != null ? '$' + ex.toFixed(2) : '-'; })()}</td>
                
                <td style={{padding: '12px 14px', fontSize: '12px', fontWeight: '600', color: pnlColor}}>
                  {isUnrealized && (
                    <span style={{
                      fontSize: '9px', opacity: 0.85, marginRight: '4px',
                      color: priceSource === 'ibkr' ? 'var(--accent-blue)' : 'var(--text-muted)',
                    }}>
                      {priceSource === 'ibkr' ? 'IBKR' : 'LIVE'}
                    </span>
                  )}
                  {displayPnl != null ? `$${Number(displayPnl).toFixed(2)}` : '-'}
                </td>
                
                <td style={{padding: '12px 14px', fontSize: '11px', color: pnlColor, fontWeight: '500'}}>
                  {returnPct != null ? `${returnPct.toFixed(2)}%` : '-'}
                </td>
                
                <td
                  style={{padding: '12px 14px', textAlign: 'right', color: 'var(--text-muted)', letterSpacing: '2px', cursor: 'pointer'}}
                  onClick={(e) => { e.stopPropagation(); if (onDetailClick) onDetailClick(t); }}
                  title="Open detail drawer"
                >•••</td>
              </tr>
            )
          })}

        </tbody>
      </table>

      {trades.length === 0 && (
        <div style={{
          marginTop: '2rem', background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px', width: '50%', margin: '3rem auto'
        }}>
          No trades yet. Use the <strong style={{color: 'var(--text-main)'}}>+ New Trade</strong> button to log your first trade.
        </div>
      )}
    </div>
  )
}

export default TradeTable;
