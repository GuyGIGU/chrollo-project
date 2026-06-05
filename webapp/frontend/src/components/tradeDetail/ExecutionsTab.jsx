import { useEffect, useState } from 'react';
import { API_BASE } from '../../api';

export default function ExecutionsTab({ tradeId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/trades/${tradeId}/executions`)
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (!cancelled) { setRows(Array.isArray(d) ? d : []); setLoading(false); } })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [tradeId]);

  if (loading) return <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Loading…</div>;
  if (rows.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
        No linked IBKR executions. Executions appear here once fills from TWS are auto-imported.
      </div>
    );
  }

  const th = { padding: '8px 10px', fontSize: 10, color: 'var(--text-muted)', textAlign: 'left', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' };
  const td = { padding: '8px 10px', fontSize: 12, color: 'var(--text-main, #e0e0e6)' };

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
          {rows.map((e) => {
            const realized = e.realized_pnl;
            const color = realized == null ? 'var(--text-muted)' : (realized > 0 ? 'var(--success)' : realized < 0 ? 'var(--danger)' : 'var(--text-muted)');
            const sideColor = e.side === 'BUY' ? 'var(--success)' : 'var(--danger)';
            return (
              <tr key={e.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <td style={{ ...td, color: 'var(--text-muted)' }}>{e.time ? new Date(e.time).toLocaleString() : '—'}</td>
                <td style={{ ...td, color: sideColor, fontWeight: 600 }}>{e.side}</td>
                <td style={td}>{e.quantity}</td>
                <td style={td}>${Number(e.price).toFixed(2)}</td>
                <td style={{ ...td, color: 'var(--text-muted)' }}>${Number(e.commission).toFixed(2)}</td>
                <td style={{ ...td, color, fontWeight: 600 }}>
                  {realized == null ? '—' : `$${Number(realized).toFixed(2)}`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
