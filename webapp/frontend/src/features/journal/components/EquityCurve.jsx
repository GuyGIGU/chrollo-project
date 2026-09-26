import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from 'recharts';
import { API_BASE } from '../../../api/base';
import { fx } from '../../../shared/formatting/format';

const fmt$ = (value) => {
  const fixed = fx(value, 2, null);
  return fixed == null ? '-' : `$${fixed}`;
};

export default function EquityCurve() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/analytics/equity-curve`)
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (!cancelled) { setData(Array.isArray(d) ? d : []); setLoading(false); } })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) return <div style={{ color: 'var(--text-muted)', fontSize: 11, padding: '0.5rem' }}>Loading equity curve...</div>;
  if (!data.length) return <div style={{ color: 'var(--text-muted)', fontSize: 11, padding: '0.5rem' }}>No closed trades yet.</div>;

  const chartData = data.map((pt, i) => ({
    idx: i + 1,
    date: pt.date?.slice(0, 10),
    cum: Number.isFinite(Number(pt.cumulative_pnl)) ? Number(pt.cumulative_pnl) : 0,
    pnl: Number.isFinite(Number(pt.pnl)) ? Number(pt.pnl) : 0,
    ticker: pt.ticker,
  }));

  const lastCum = chartData[chartData.length - 1]?.cum ?? 0;
  const lineColor = lastCum >= 0 ? 'var(--success, #3DD37A)' : 'var(--danger, #DE6E78)';
  const fillColor = lastCum >= 0 ? 'rgba(61,211,122,0.12)' : 'rgba(222,110,120,0.12)';

  return (
    <div className="instrument-well" style={{ width: '100%', height: '100%', minWidth: 0, minHeight: 120 }}>
      <ResponsiveContainer width="100%" height="100%" minWidth={220} minHeight={120}>
        <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
          <defs>
            <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={lineColor} stopOpacity={0.25} />
              <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis dataKey="idx" stroke="var(--text-faint)" fontSize={9} tickLine={false} axisLine={false} />
          <YAxis stroke="var(--text-faint)" fontSize={9} tickLine={false} axisLine={false} tickFormatter={fmt$} width={48} />
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.10)" strokeDasharray="3 3" />
          <Tooltip
            contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-color)', borderRadius: 6, fontSize: 11 }}
            labelStyle={{ color: 'var(--text-muted)' }}
            formatter={(val, name) => [fmt$(val), name === 'cum' ? 'Equity' : 'Trade P&L']}
            labelFormatter={(i) => {
              const pt = chartData[i - 1];
              return pt ? `#${i} - ${pt.date} - ${pt.ticker || ''}` : `#${i}`;
            }}
          />
          <Line type="monotone" dataKey="cum" stroke={lineColor} strokeWidth={1.8} dot={false} fill={fillColor} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
