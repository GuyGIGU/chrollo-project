import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from 'recharts';
import { API_BASE } from '../api';

const fmt$ = (v) => (v == null ? '—' : `$${Number(v).toFixed(2)}`);

export default function EquityCurve() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/analytics/equity-curve`)
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (!cancelled) { setData(d); setLoading(false); } })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) return <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '1rem' }}>Loading equity curve…</div>;
  if (!data.length) return <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '1rem' }}>No closed trades yet.</div>;

  const chartData = data.map((pt, i) => ({
    idx: i + 1,
    date: pt.date?.slice(0, 10),
    cum: pt.cumulative_pnl,
    pnl: pt.pnl,
    ticker: pt.ticker,
  }));

  const lastCum = chartData[chartData.length - 1]?.cum ?? 0;
  const lineColor = lastCum >= 0 ? 'var(--success, #22c55e)' : 'var(--danger, #ef4444)';

  return (
    <div style={{ width: '100%', height: 240 }}>
      <ResponsiveContainer>
        <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis dataKey="idx" stroke="var(--text-muted, #8b8b9c)" fontSize={10} tickLine={false} />
          <YAxis stroke="var(--text-muted, #8b8b9c)" fontSize={10} tickLine={false} tickFormatter={fmt$} />
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.2)" />
          <Tooltip
            contentStyle={{ background: '#242430', border: '1px solid #3f3f52', borderRadius: 6, fontSize: 12 }}
            labelStyle={{ color: '#8b8b9c' }}
            formatter={(val, name) => [fmt$(val), name === 'cum' ? 'Equity' : 'Trade P&L']}
            labelFormatter={(i) => {
              const pt = chartData[i - 1];
              return pt ? `#${i} • ${pt.date} • ${pt.ticker || ''}` : `#${i}`;
            }}
          />
          <Line type="monotone" dataKey="cum" stroke={lineColor} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
