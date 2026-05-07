import React, { useMemo, useRef } from 'react';
import useSSE from '../hooks/useSSE';
import useIBKRStatus from '../hooks/useIBKRStatus';
import { API_BASE } from '../api';

const fmtMoney = (v, currency = 'USD') => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  const n = Number(v);
  const sign = n < 0 ? '-' : '';
  const abs = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${sign}$${abs}${currency && currency !== 'USD' ? ` ${currency}` : ''}`;
};

const fmtNum = (v, digits = 2) => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
};

const fmtTime = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  } catch {
    return iso;
  }
};

const pnlColor = (v) => {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return 'var(--text-muted)';
  return n > 0 ? 'var(--success)' : 'var(--danger)';
};

const pillStyle = (bg, color, border) => ({
  padding: '3px 10px',
  borderRadius: 'var(--radius-pill, 999px)',
  fontSize: '10px',
  fontWeight: 700,
  letterSpacing: '0.5px',
  background: bg,
  color: color,
  border: `1px solid ${border || color}`,
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  textTransform: 'uppercase',
});

const thStyle = {
  padding: '12px 14px',
  fontSize: '11px',
  fontWeight: 600,
  color: '#8b8b9c',
  textAlign: 'left',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
};

const tdStyle = {
  padding: '12px 14px',
  fontSize: '12px',
  color: 'var(--text-main)',
};

// ── StatusBar ────────────────────────────────────────────────────
const StatusBar = ({ status, sseStatus, lastUpdate, stale, dailyRestart, sessionCompetition, onReconnect }) => {
  const isLive = status?.mode === 'live';
  const available = !!status?.available;
  const connected = !!status?.connected;

  const modeBadge = isLive
    ? pillStyle('rgba(231, 76, 60, 0.12)', 'var(--danger)', 'var(--danger)')
    : pillStyle('rgba(109, 138, 199, 0.12)', 'var(--accent-blue)', 'var(--accent-blue)');

  let connBg = 'rgba(136, 136, 150, 0.15)';
  let connColor = 'var(--text-muted)';
  let connLabel = 'Offline';
  if (!available) { connLabel = 'Not installed'; }
  else if (sessionCompetition) { connBg = 'rgba(199, 107, 115, 0.15)'; connColor = 'var(--danger)'; connLabel = 'Session Conflict'; }
  else if (dailyRestart) { connBg = 'rgba(109, 138, 199, 0.12)'; connColor = 'var(--accent-blue)'; connLabel = 'Daily Restart'; }
  else if (connected) { connBg = 'var(--success-bg)'; connColor = 'var(--success)'; connLabel = 'Connected'; }
  else { connBg = 'rgba(202, 159, 60, 0.15)'; connColor = 'var(--accent-yellow, #ca9f3c)'; connLabel = 'Reconnecting…'; }

  return (
    <>
      {sessionCompetition && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '12px 16px',
          background: 'linear-gradient(135deg, rgba(199,107,115,0.12), rgba(199,107,115,0.06))',
          border: '1px solid rgba(199,107,115,0.35)',
          borderRadius: 'var(--radius-md, 10px)',
          marginBottom: 10,
          fontSize: 12,
          color: 'var(--danger)',
          fontWeight: 500,
        }}>
          <span style={{ fontSize: 18 }}>⚠️</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, marginBottom: 2 }}>Session conflict — another platform is using your IBKR login</div>
            <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>
              TradingView (or another app) connected to IBKR, which kicked this session.
              Auto-reconnect is paused so they don't keep fighting.
              Click Reconnect when you're done with the other platform.
            </div>
          </div>
          <button
            onClick={onReconnect}
            style={{
              padding: '6px 16px',
              borderRadius: 'var(--radius-sm, 6px)',
              border: '1px solid var(--accent-blue)',
              background: 'rgba(109, 138, 199, 0.15)',
              color: 'var(--accent-blue)',
              fontWeight: 600,
              fontSize: 12,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              fontFamily: 'inherit',
              transition: 'all 0.2s',
            }}
          >
            ↻ Reconnect
          </button>
        </div>
      )}
      {dailyRestart && !sessionCompetition && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 16px',
          background: 'linear-gradient(135deg, rgba(109,138,199,0.10), rgba(109,138,199,0.05))',
          border: '1px solid rgba(109,138,199,0.25)',
          borderRadius: 'var(--radius-md, 10px)',
          marginBottom: 10,
          fontSize: 12,
          color: 'var(--accent-blue)',
          fontWeight: 500,
          animation: 'pulse-subtle 2s ease-in-out infinite',
        }}>
          <span style={{ fontSize: 16 }}>🔄</span>
          <span>IB Gateway daily restart in progress — data is preserved and will resume automatically.</span>
        </div>
      )}
      {stale && !dailyRestart && !connected && !sessionCompetition && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 16px',
          background: 'rgba(202, 159, 60, 0.08)',
          border: '1px solid rgba(202, 159, 60, 0.25)',
          borderRadius: 'var(--radius-md, 10px)',
          marginBottom: 10,
          fontSize: 12,
          color: 'var(--accent-yellow, #ca9f3c)',
          fontWeight: 500,
        }}>
          <span style={{ fontSize: 16 }}>⚡</span>
          <span>Connection interrupted — showing last-known data. Reconnecting automatically…</span>
        </div>
      )}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 16px',
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-md, 10px)',
        marginBottom: 16,
      }}>
        <span style={modeBadge}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: isLive ? 'var(--danger)' : 'var(--accent-blue)',
            boxShadow: isLive ? '0 0 6px var(--danger)' : 'none',
          }}/>
          {isLive ? 'LIVE' : 'PAPER'}
        </span>
        <span style={pillStyle(connBg, connColor)}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: connColor,
            boxShadow: connected ? `0 0 6px ${connColor}` : 'none',
          }}/>
          IBKR {connLabel}
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
          Stream: {sseStatus === 'reconnecting' ? 'retrying…' : sseStatus}
        </span>
        {status?.host && (
          <span style={{ color: 'var(--text-muted)', fontSize: 11, marginLeft: 'auto' }}>
            {status.host}:{status.port} · client {status.client_id}
          </span>
        )}
        {lastUpdate && (
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
            Last update: {fmtTime(lastUpdate)}
          </span>
        )}
      </div>
    </>
  );
};

// ── AccountSummaryCard ───────────────────────────────────────────
const SummaryTile = ({ label, value, currency, color }) => (
  <div style={{
    background: 'var(--bg-panel)',
    border: '1px solid var(--border-color)',
    borderRadius: 'var(--radius-md, 10px)',
    padding: '14px 16px',
    minWidth: 160,
    flex: '1 1 160px',
  }}>
    <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 6 }}>
      {label}
    </div>
    <div style={{ color: color || 'var(--text-main)', fontSize: 18, fontWeight: 700 }}>
      {typeof value === 'number' ? fmtMoney(value, currency) : (value ?? '—')}
    </div>
  </div>
);

const AccountSummaryCard = ({ summary }) => {
  const values = summary?.values || {};
  const currency = summary?.currency || {};
  const tiles = [
    { k: 'NetLiquidation', label: 'Net Liquidation' },
    { k: 'TotalCashValue', label: 'Cash' },
    { k: 'AvailableFunds', label: 'Available Funds' },
    { k: 'BuyingPower', label: 'Buying Power' },
    { k: 'GrossPositionValue', label: 'Gross Position' },
    { k: 'UnrealizedPnL', label: 'Unrealized P&L', color: true },
    { k: 'RealizedPnL', label: 'Realized P&L', color: true },
    { k: 'DayTradesRemaining', label: 'DT Remaining', plain: true },
  ];
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
      {tiles.map(({ k, label, color, plain }) => (
        <SummaryTile
          key={k}
          label={label}
          value={plain ? values[k] : values[k]}
          currency={currency[k]}
          color={color ? pnlColor(values[k]) : undefined}
        />
      ))}
    </div>
  );
};

// ── LivePositionsTable ───────────────────────────────────────────
const LivePositionsTable = ({ positions }) => {
  const rows = positions || [];
  return (
    <section style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)', margin: '0 0 10px' }}>
        Live Positions ({rows.length})
      </h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', minWidth: 900, borderSpacing: 0 }}>
          <thead>
            <tr style={{ background: 'var(--bg-hover)' }}>
              <th style={{ ...thStyle, borderTopLeftRadius: 8, borderBottomLeftRadius: 8 }}>Symbol</th>
              <th style={thStyle}>Account</th>
              <th style={thStyle}>Qty</th>
              <th style={thStyle}>Avg Cost</th>
              <th style={thStyle}>Market Price</th>
              <th style={thStyle}>Market Value</th>
              <th style={thStyle}>Unrealized</th>
              <th style={{ ...thStyle, borderTopRightRadius: 8, borderBottomRightRadius: 8 }}>Realized</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p, i) => {
              const qty = p.position ?? p.quantity ?? 0;
              const avg = p.avg_cost ?? p.average_cost ?? null;
              const mktPrice = p.market_price ?? null;
              const mktVal = p.market_value ?? null;
              const unreal = p.unrealized_pnl ?? null;
              const realiz = p.realized_pnl ?? null;
              const key = `${p.account || ''}-${p.symbol}-${p.sec_type || ''}-${i}`;
              return (
                <tr key={key} style={{ background: 'var(--bg-main)' }}>
                  <td style={{ ...tdStyle, color: 'var(--accent-blue)', fontWeight: 600 }}>
                    {p.symbol}
                    {p.sec_type && p.sec_type !== 'STK' && (
                      <span style={{ fontSize: 9, color: 'var(--text-muted)', marginLeft: 6 }}>{p.sec_type}</span>
                    )}
                  </td>
                  <td style={{ ...tdStyle, color: 'var(--text-muted)' }}>{p.account || '—'}</td>
                  <td style={{ ...tdStyle, color: qty > 0 ? 'var(--success)' : (qty < 0 ? 'var(--danger)' : 'var(--text-muted)') }}>
                    {fmtNum(qty, 0)}
                  </td>
                  <td style={tdStyle}>{avg != null ? fmtMoney(avg) : '—'}</td>
                  <td style={tdStyle}>{mktPrice != null ? fmtMoney(mktPrice) : '—'}</td>
                  <td style={tdStyle}>{mktVal != null ? fmtMoney(mktVal) : '—'}</td>
                  <td style={{ ...tdStyle, color: pnlColor(unreal), fontWeight: 600 }}>{unreal != null ? fmtMoney(unreal) : '—'}</td>
                  <td style={{ ...tdStyle, color: pnlColor(realiz) }}>{realiz != null ? fmtMoney(realiz) : '—'}</td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr><td colSpan={8} style={{ ...tdStyle, color: 'var(--text-muted)', textAlign: 'center', padding: '24px 0' }}>No open positions.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};

// ── OpenOrdersTable ──────────────────────────────────────────────
const OpenOrdersTable = ({ orders }) => {
  const rows = orders || [];
  return (
    <section style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)', margin: '0 0 10px' }}>
        Open Orders ({rows.length})
      </h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', minWidth: 900, borderSpacing: 0 }}>
          <thead>
            <tr style={{ background: 'var(--bg-hover)' }}>
              <th style={{ ...thStyle, borderTopLeftRadius: 8, borderBottomLeftRadius: 8 }}>Symbol</th>
              <th style={thStyle}>Action</th>
              <th style={thStyle}>Type</th>
              <th style={thStyle}>Qty</th>
              <th style={thStyle}>Filled</th>
              <th style={thStyle}>Limit</th>
              <th style={thStyle}>Stop</th>
              <th style={thStyle}>TIF</th>
              <th style={{ ...thStyle, borderTopRightRadius: 8, borderBottomRightRadius: 8 }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o, i) => {
              const key = o.order_id || o.perm_id || `${o.symbol}-${i}`;
              const isBuy = (o.action || '').toUpperCase() === 'BUY';
              return (
                <tr key={key} style={{ background: 'var(--bg-main)' }}>
                  <td style={{ ...tdStyle, color: 'var(--accent-blue)', fontWeight: 600 }}>{o.symbol}</td>
                  <td style={{ ...tdStyle, color: isBuy ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>{o.action || '—'}</td>
                  <td style={tdStyle}>{o.order_type || '—'}</td>
                  <td style={tdStyle}>{fmtNum(o.total_quantity, 0)}</td>
                  <td style={tdStyle}>{fmtNum(o.filled ?? 0, 0)}</td>
                  <td style={tdStyle}>{o.lmt_price != null ? fmtMoney(o.lmt_price) : '—'}</td>
                  <td style={tdStyle}>{o.aux_price != null ? fmtMoney(o.aux_price) : '—'}</td>
                  <td style={{ ...tdStyle, color: 'var(--text-muted)' }}>{o.tif || '—'}</td>
                  <td style={tdStyle}>
                    <span style={pillStyle('rgba(109, 138, 199, 0.12)', 'var(--accent-blue)')}>
                      {o.status || '—'}
                    </span>
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr><td colSpan={9} style={{ ...tdStyle, color: 'var(--text-muted)', textAlign: 'center', padding: '24px 0' }}>No working orders.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};

// ── RecentExecutionsTable ────────────────────────────────────────
const RecentExecutionsTable = ({ executions }) => {
  const rows = (executions || []).slice().reverse();
  return (
    <section style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)', margin: '0 0 10px' }}>
        Recent Executions ({rows.length})
      </h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', minWidth: 900, borderSpacing: 0 }}>
          <thead>
            <tr style={{ background: 'var(--bg-hover)' }}>
              <th style={{ ...thStyle, borderTopLeftRadius: 8, borderBottomLeftRadius: 8 }}>Time</th>
              <th style={thStyle}>Symbol</th>
              <th style={thStyle}>Side</th>
              <th style={thStyle}>Qty</th>
              <th style={thStyle}>Price</th>
              <th style={thStyle}>Commission</th>
              <th style={{ ...thStyle, borderTopRightRadius: 8, borderBottomRightRadius: 8 }}>Realized</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e, i) => {
              const side = (e.side || '').toUpperCase();
              const isBuy = side === 'BOT' || side === 'BUY';
              const isSell = side === 'SLD' || side === 'SELL';
              const color = isBuy ? 'var(--success)' : (isSell ? 'var(--danger)' : 'var(--text-muted)');
              const key = e.exec_id || `${e.symbol}-${e.time}-${i}`;
              return (
                <tr key={key} style={{ background: 'var(--bg-main)' }}>
                  <td style={{ ...tdStyle, color: 'var(--text-muted)', fontSize: 11 }}>{fmtTime(e.time)}</td>
                  <td style={{ ...tdStyle, color: 'var(--accent-blue)', fontWeight: 600 }}>{e.symbol}</td>
                  <td style={{ ...tdStyle, color, fontWeight: 600 }}>{side || '—'}</td>
                  <td style={tdStyle}>{fmtNum(e.quantity, 0)}</td>
                  <td style={tdStyle}>{e.price != null ? fmtMoney(e.price) : '—'}</td>
                  <td style={{ ...tdStyle, color: 'var(--text-muted)' }}>{e.commission != null ? fmtMoney(e.commission) : '—'}</td>
                  <td style={{ ...tdStyle, color: pnlColor(e.realized_pnl) }}>{e.realized_pnl != null ? fmtMoney(e.realized_pnl) : '—'}</td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr><td colSpan={7} style={{ ...tdStyle, color: 'var(--text-muted)', textAlign: 'center', padding: '24px 0' }}>No recent fills.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};

// ── PortfolioTab ─────────────────────────────────────────────────
const PortfolioTab = () => {
  const status = useIBKRStatus(10000);
  const enabled = !!status?.available;
  const { data, status: sseStatus } = useSSE(
    enabled ? `${API_BASE}/stream/portfolio` : null,
    { enabled },
  );

  // Preserve last-known data during transient disconnects.
  // Only update the ref when we get a non-empty payload.
  const snapshotRef = useRef({});
  if (data && typeof data === 'object' && Object.keys(data).length > 0) {
    snapshotRef.current = data;
  }
  const snapshot = snapshotRef.current;

  const summary = snapshot.account_summary || { values: {}, currency: {} };
  const positions = snapshot.positions || [];
  const openOrders = snapshot.open_orders || [];
  const executions = snapshot.recent_executions || [];

  const isStale = useMemo(() => {
    if (snapshot.stale) return true;
    if (!status?.connected) return true;
    if (sseStatus === 'error' || sseStatus === 'closed') return true;
    return false;
  }, [status, sseStatus, snapshot.stale]);

  const dailyRestart = !!snapshot.daily_restart || !!status?.daily_restart;
  const sessionCompetition = !!snapshot.session_competition || !!status?.session_competition;

  const handleReconnect = async () => {
    try {
      const res = await fetch(`${API_BASE}/ibkr/reconnect`, { method: 'POST' });
      if (!res.ok) {
        const body = await res.text();
        alert(`Reconnect failed: ${body}`);
      }
    } catch (err) {
      alert(`Reconnect error: ${err.message || err}`);
    }
  };

  if (!status?.available) {
    return (
      <div style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-md, 10px)',
        padding: 32,
        textAlign: 'center',
        color: 'var(--text-muted)',
      }}>
        <div style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-main)' }}>IBKR integration unavailable</div>
        <div style={{ fontSize: 12 }}>
          Install <code>ib_async</code> and start TWS or IB Gateway, then restart the backend.
        </div>
      </div>
    );
  }

  return (
    <div style={{ opacity: isStale ? 0.85 : 1, transition: 'opacity 0.3s' }}>
      <StatusBar
        status={status}
        sseStatus={sseStatus}
        lastUpdate={snapshot.last_update}
        stale={isStale}
        dailyRestart={dailyRestart}
        sessionCompetition={sessionCompetition}
        onReconnect={handleReconnect}
      />
      <AccountSummaryCard summary={summary} />
      <LivePositionsTable positions={positions} />
      <OpenOrdersTable orders={openOrders} />
      <RecentExecutionsTable executions={executions} />
    </div>
  );
};

export default PortfolioTab;
