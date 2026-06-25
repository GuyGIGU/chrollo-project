import React, { useEffect, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { API_BASE } from '../api';

const fx = (value, digits = 2) => (
  value == null || !Number.isFinite(Number(value)) ? '-' : Number(value).toFixed(digits)
);
const fmt$ = (value) => fx(value) === '-' ? '-' : `$${fx(value)}`;
const fmtPct = (value) => fx(value) === '-' ? '-' : `${fx(value)}%`;

export default function DrawdownChart() {
  const [data, setData] = useState({ series: [], max_drawdown: 0, max_drawdown_pct: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/analytics/drawdown`)
      .then(r => r.ok ? r.json() : { series: [] })
      .then(d => { if (!cancelled) { setData(d || { series: [] }); setLoading(false); } })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) return <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '1rem' }}>Loading drawdown...</div>;
  if (!data.series?.length) return <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '1rem' }}>No closed trades yet.</div>;

  const chartData = data.series.map((pt, i) => ({
    idx: i + 1,
    date: pt.date?.slice(0, 10),
    dd: Number.isFinite(Number(pt.drawdown)) ? Number(pt.drawdown) : 0,
    ddPct: Number.isFinite(Number(pt.drawdown_pct)) ? Number(pt.drawdown_pct) : 0,
  }));

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', padding: '0 4px 6px' }}>
        <span>Max DD: <strong style={{ color: 'var(--danger, #ef4444)' }}>{fmt$(data.max_drawdown)}</strong></span>
        <span>Max DD %: <strong style={{ color: 'var(--danger, #ef4444)' }}>{fmtPct(data.max_drawdown_pct)}</strong></span>
      </div>
      <div style={{ width: '100%', height: 200, minWidth: 0, minHeight: 180 }}>
        <ResponsiveContainer width="100%" height="100%" minWidth={220} minHeight={180}>
          <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--danger, #ef4444)" stopOpacity={0.1} />
                <stop offset="100%" stopColor="var(--danger, #ef4444)" stopOpacity={0.4} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="idx" stroke="var(--text-muted, #8b8b9c)" fontSize={10} tickLine={false} />
            <YAxis stroke="var(--text-muted, #8b8b9c)" fontSize={10} tickLine={false} tickFormatter={fmt$} />
            <Tooltip
              contentStyle={{ background: '#242430', border: '1px solid #3f3f52', borderRadius: 6, fontSize: 12 }}
              formatter={(val) => [fmt$(val), 'Drawdown']}
              labelFormatter={(i) => chartData[i - 1]?.date || `#${i}`}
            />
            <Area type="monotone" dataKey="dd" stroke="var(--danger, #ef4444)" strokeWidth={1.5} fill="url(#ddGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
