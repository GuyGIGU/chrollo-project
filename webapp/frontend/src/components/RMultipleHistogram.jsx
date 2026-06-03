import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, ReferenceLine } from 'recharts';
import { API_BASE } from '../api';

export default function RMultipleHistogram() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/analytics/r-multiple-histogram`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (!cancelled) { setData(d); setLoading(false); } })
      .catch(() => { if (!cancelled) setLoading(false); });
  }, []);

  if (loading) return <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '1rem' }}>Loading R-multiple…</div>;
  if (!data || !data.series?.length) return <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '1rem' }}>No eligible trades (need entry, stop, and closed P&L).</div>;

  const chartData = data.series.map(b => ({
    label: `${b.bin_start >= 0 ? '+' : ''}${b.bin_start.toFixed(1)}R`,
    count: b.count,
    mid: (b.bin_start + b.bin_end) / 2,
  }));

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', padding: '0 4px 6px' }}>
        <span>Avg R: <strong style={{ color: data.avg_r >= 0 ? 'var(--success, #22c55e)' : 'var(--danger, #ef4444)' }}>{data.avg_r.toFixed(2)}R</strong></span>
        <span>Total: {data.total}{data.skipped > 0 && <> • skipped {data.skipped}</>}</span>
      </div>
      <div style={{ width: '100%', height: 200, minWidth: 0, minHeight: 180 }}>
        <ResponsiveContainer width="100%" height="100%" minWidth={220} minHeight={180}>
          <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="label" stroke="var(--text-muted, #8b8b9c)" fontSize={9} tickLine={false} interval={1} />
            <YAxis stroke="var(--text-muted, #8b8b9c)" fontSize={10} tickLine={false} allowDecimals={false} />
            <ReferenceLine x={chartData.find(d => d.mid === 0)?.label} stroke="rgba(255,255,255,0.3)" />
            <Tooltip
              contentStyle={{ background: '#242430', border: '1px solid #3f3f52', borderRadius: 6, fontSize: 12 }}
              formatter={(val) => [val, 'Trades']}
            />
            <Bar dataKey="count">
              {chartData.map((d, i) => (
                <Cell key={i} fill={d.mid >= 0 ? 'var(--success, #22c55e)' : 'var(--danger, #ef4444)'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
