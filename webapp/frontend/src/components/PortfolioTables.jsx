import React from 'react';
import { fmtMoney, fmtNum, fmtPct, fmtTime, pnlColor } from './portfolioFormat';
const thStyle = {
  padding: '11px 12px',
  fontSize: 10,
  fontWeight: 800,
  color: 'var(--text-muted)',
  textAlign: 'left',
  textTransform: 'uppercase',
};
const tdStyle = {
  padding: '12px',
  fontSize: 12,
  color: 'var(--text-main)',
  borderBottom: '1px solid rgba(255,255,255,0.045)',
  whiteSpace: 'nowrap',
};

const pillStyle = (color, background) => ({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: 46,
  padding: '3px 8px',
  borderRadius: 5,
  color,
  background,
  fontSize: 10,
  fontWeight: 800,
  textTransform: 'uppercase',
});
const orderPrice = (value) => {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) && numberValue > 0 ? fmtMoney(numberValue) : '-';
};

const Section = ({ title, count, children }) => (
  <section style={{ marginBottom: 22 }}>
    <h3 style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)', margin: '0 0 9px' }}>
      {title} ({count})
    </h3>
    <div style={{ overflowX: 'auto', border: '1px solid var(--border-color)', borderRadius: 8, background: 'var(--bg-panel)' }}>
      {children}
    </div>
  </section>
);

const Table = ({ minWidth, headers, children, empty, colSpan }) => (
  <table style={{ width: '100%', minWidth, borderSpacing: 0, borderCollapse: 'separate' }}>
    <thead>
      <tr style={{ background: 'rgba(255,255,255,0.035)' }}>
        {headers.map((header) => <th key={header} style={thStyle}>{header}</th>)}
      </tr>
    </thead>
    <tbody>
      {children}
      {empty && (
        <tr>
          <td colSpan={colSpan} style={{ ...tdStyle, color: 'var(--text-muted)', textAlign: 'center', padding: '24px 0' }}>
            {empty}
          </td>
        </tr>
      )}
    </tbody>
  </table>
);

const positionStats = (position, netLiquidation) => {
  const qty = Number(position.position ?? position.quantity ?? 0);
  const marketValue = Number(position.market_value);
  const avg = Number(position.avg_cost ?? position.average_cost);
  const price = Number(position.market_price);
  const costBasis = Math.abs(qty * avg);
  const unrealized = Number(position.unrealized_pnl);

  return {
    qty,
    side: qty < 0 ? 'Short' : 'Long',
    marketValue: Number.isFinite(marketValue) ? marketValue : null,
    weight: netLiquidation > 0 && Number.isFinite(marketValue) ? Math.abs(marketValue) / netLiquidation * 100 : null,
    pnlPct: costBasis > 0 && Number.isFinite(unrealized) ? unrealized / costBasis * 100 : null,
    avg: Number.isFinite(avg) ? avg : null,
    price: Number.isFinite(price) ? price : null,
    unrealized: Number.isFinite(unrealized) ? unrealized : null,
  };
};

export const LivePositionsTable = ({ positions, netLiquidation, selectedSymbol, onSelectSymbol }) => {
  const rows = (positions || []).slice().sort((a, b) => Math.abs(Number(b.market_value) || 0) - Math.abs(Number(a.market_value) || 0));

  return (
    <Section title="Live Positions" count={rows.length}>
      <Table
        minWidth={980}
        headers={['Symbol', 'Side', 'Qty', 'Weight', 'Avg Cost', 'Market', 'Value', 'Unrealized', 'P&L %']}
        empty={rows.length === 0 ? 'No open positions.' : null}
        colSpan={9}
      >
        {rows.map((position, index) => {
          const stats = positionStats(position, netLiquidation);
          const key = `${position.account || ''}-${position.symbol}-${position.sec_type || ''}-${index}`;
          const sideColor = stats.qty < 0 ? 'var(--danger)' : 'var(--success)';
          const active = selectedSymbol === position.symbol;
          const rowBackground = active ? 'rgba(88, 166, 255, 0.12)' : (index % 2 ? 'rgba(255,255,255,0.012)' : 'transparent');
          return (
            <tr
              key={key}
              onClick={() => onSelectSymbol?.(position.symbol)}
              title="Click to load this position's chart."
              style={{ background: rowBackground, cursor: 'pointer' }}
            >
              <td style={{ ...tdStyle, color: 'var(--accent-blue)', fontWeight: 800 }}>
                {position.symbol}
                {position.sec_type && position.sec_type !== 'STK' && <span style={{ color: 'var(--text-muted)', fontSize: 9, marginLeft: 6 }}>{position.sec_type}</span>}
              </td>
              <td style={tdStyle}><span style={pillStyle(sideColor, stats.qty < 0 ? 'var(--danger-bg)' : 'var(--success-bg)')}>{stats.side}</span></td>
              <td style={{ ...tdStyle, color: sideColor, fontWeight: 700 }}>{fmtNum(stats.qty, 0)}</td>
              <td style={tdStyle}>{fmtPct(stats.weight)}</td>
              <td style={tdStyle}>{stats.avg == null ? '-' : fmtMoney(stats.avg)}</td>
              <td style={tdStyle}>{stats.price == null ? '-' : fmtMoney(stats.price)}</td>
              <td style={tdStyle}>{stats.marketValue == null ? '-' : fmtMoney(stats.marketValue)}</td>
              <td style={{ ...tdStyle, color: pnlColor(stats.unrealized), fontWeight: 700 }}>{stats.unrealized == null ? '-' : fmtMoney(stats.unrealized)}</td>
              <td style={{ ...tdStyle, color: pnlColor(stats.pnlPct), fontWeight: 700 }}>{fmtPct(stats.pnlPct)}</td>
            </tr>
          );
        })}
      </Table>
    </Section>
  );
};

export const OpenOrdersTable = ({ orders }) => {
  const rows = orders || [];

  return (
    <Section title="Open Orders" count={rows.length}>
      <Table
        minWidth={920}
        headers={['Symbol', 'Action', 'Type', 'Qty', 'Filled', 'Remaining', 'Limit', 'Stop', 'Status']}
        empty={rows.length === 0 ? 'No working orders.' : null}
        colSpan={9}
      >
        {rows.map((order, index) => {
          const key = order.order_id || order.perm_id || `${order.symbol}-${index}`;
          const action = (order.action || '').toUpperCase();
          const isBuy = action === 'BUY';
          const limit = order.limit_price ?? order.lmt_price;
          const stop = order.stop_price ?? order.aux_price;
          return (
            <tr key={key} style={{ background: index % 2 ? 'rgba(255,255,255,0.012)' : 'transparent' }}>
              <td style={{ ...tdStyle, color: 'var(--accent-blue)', fontWeight: 800 }}>{order.symbol}</td>
              <td style={{ ...tdStyle, color: isBuy ? 'var(--success)' : 'var(--danger)', fontWeight: 800 }}>{action || '-'}</td>
              <td style={tdStyle}>{order.order_type || '-'}</td>
              <td style={tdStyle}>{fmtNum(order.total_quantity, 0)}</td>
              <td style={tdStyle}>{fmtNum(order.filled ?? 0, 0)}</td>
              <td style={tdStyle}>{fmtNum(order.remaining ?? 0, 0)}</td>
              <td style={tdStyle}>{orderPrice(limit)}</td>
              <td style={tdStyle}>{orderPrice(stop)}</td>
              <td style={tdStyle}><span style={pillStyle('var(--accent-blue)', 'var(--accent-blue-soft)')}>{order.status || '-'}</span></td>
            </tr>
          );
        })}
      </Table>
    </Section>
  );
};

export const RecentExecutionsTable = ({ executions }) => {
  const rows = (executions || []).slice().reverse();

  return (
    <Section title="Recent Executions" count={rows.length}>
      <Table
        minWidth={860}
        headers={['Time', 'Symbol', 'Side', 'Qty', 'Price', 'Commission', 'Realized']}
        empty={rows.length === 0 ? 'No recent fills.' : null}
        colSpan={7}
      >
        {rows.map((execution, index) => {
          const side = (execution.side || '').toUpperCase();
          const isBuy = side === 'BOT' || side === 'BUY';
          const isSell = side === 'SLD' || side === 'SELL';
          const color = isBuy ? 'var(--success)' : (isSell ? 'var(--danger)' : 'var(--text-muted)');
          const key = execution.exec_id || `${execution.symbol}-${execution.time}-${index}`;
          return (
            <tr key={key} style={{ background: index % 2 ? 'rgba(255,255,255,0.012)' : 'transparent' }}>
              <td style={{ ...tdStyle, color: 'var(--text-muted)', fontSize: 11 }}>{fmtTime(execution.time)}</td>
              <td style={{ ...tdStyle, color: 'var(--accent-blue)', fontWeight: 800 }}>{execution.symbol}</td>
              <td style={{ ...tdStyle, color, fontWeight: 800 }}>{side || '-'}</td>
              <td style={tdStyle}>{fmtNum(execution.quantity, 0)}</td>
              <td style={tdStyle}>{execution.price != null ? fmtMoney(execution.price) : '-'}</td>
              <td style={{ ...tdStyle, color: 'var(--text-muted)' }}>{execution.commission != null ? fmtMoney(execution.commission) : '-'}</td>
              <td style={{ ...tdStyle, color: pnlColor(execution.realized_pnl), fontWeight: 700 }}>{execution.realized_pnl != null ? fmtMoney(execution.realized_pnl) : '-'}</td>
            </tr>
          );
        })}
      </Table>
    </Section>
  );
};
