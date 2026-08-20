import { useEffect, useState } from 'react';
import { API_BASE } from '../../api';
import { fmtInt } from '../../utils/tradeTableUtils';
import { fmtNum } from '../../utils/format';

export default function ExecutionsTab({ tradeId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/trades/${tradeId}/executions`)
      .then(response => response.ok ? response.json() : [])
      .then((data) => {
        if (!cancelled) {
          setRows(Array.isArray(data) ? data : []);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [tradeId]);

  if (loading) return <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Loading...</div>;
  if (rows.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
        No linked IBKR executions.
      </div>
    );
  }

  const th = {
    color: 'var(--text-muted)',
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: '0.5px',
    padding: '8px 10px',
    textAlign: 'left',
    textTransform: 'uppercase',
  };
  const td = {
    color: 'var(--text-main, #e0e0e6)',
    fontSize: 12,
    padding: '8px 10px',
  };

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
            <th style={th}>Time</th>
            <th style={th}>Side</th>
            <th style={th}>Qty</th>
            <th style={th}>Price</th>
            <th style={th}>Comm</th>
            <th style={th}>Realized</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((execution) => {
            const realized = finiteNumber(execution.realized_pnl);
            const color = realized == null
              ? 'var(--text-muted)'
              : realized > 0
                ? 'var(--success)'
                : realized < 0
                  ? 'var(--danger)'
                  : 'var(--text-muted)';
            const sideColor = execution.side === 'BUY' ? 'var(--success)' : 'var(--danger)';
            return (
              <tr key={execution.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <td style={{ ...td, color: 'var(--text-muted)' }}>{execution.time ? new Date(execution.time).toLocaleString() : '—'}</td>
                <td style={{ ...td, color: sideColor, fontWeight: 600 }}>{execution.side || '—'}</td>
                <td style={td}>{fmtInt(execution.quantity)}</td>
                <td style={td}>{money(execution.price)}</td>
                <td style={{ ...td, color: 'var(--text-muted)' }}>{money(execution.commission)}</td>
                <td style={{ ...td, color, fontWeight: 600 }}>{money(realized)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const money = (value) => {
  const grouped = fmtNum(value, 2, null);
  return grouped == null ? '—' : `$${grouped}`;
};

const finiteNumber = (value) => {
  if (value == null || value === '') return null;
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
};
