import React, { useEffect, useRef, useState } from 'react';
import { createChart, BarSeries, LineSeries, HistogramSeries } from 'lightweight-charts';

// Weekly + monthly price charts for the modal — the same Trend+Box read the daily
// engine does, one and two timeframes up. Candles are resampled on the backend
// (output/dashboard.py) from the full daily history; the blue rails are the
// higher-timeframe consolidation box when one is in view.

const chartOptions = (width, height) => ({
  width,
  height,
  autoSize: true,
  layout: {
    background: { type: 'solid', color: '#141721' },
    textColor: '#747c8f',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 10,
  },
  grid: {
    vertLines: { color: 'rgba(47, 52, 71, 0.13)' },
    horzLines: { color: 'rgba(47, 52, 71, 0.13)' },
  },
  crosshair: { mode: 0 },
  rightPriceScale: { borderColor: 'rgba(47, 52, 71, 0.56)', scaleMargins: { top: 0.1, bottom: 0.22 } },
  timeScale: { borderColor: 'rgba(47, 52, 71, 0.56)', timeVisible: false, fixLeftEdge: true, fixRightEdge: true },
});

function TfChart({ candles, volumes, boxR, boxS }) {
  const containerRef = useRef(null);
  const [chartError, setChartError] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;
    container.innerHTML = '';
    setChartError(false);
    let chart = null;
    try {
      chart = createChart(container, chartOptions(container.clientWidth || 360, container.clientHeight || 190));
      const candleSeries = chart.addSeries(BarSeries, {
        upColor: '#26a69a', downColor: '#ef5350',
        lastValueVisible: false, priceLineVisible: false, thinBars: false,
      });
      candleSeries.setData(candles || []);

      if (volumes?.length) {
        const volumeSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'tfvol' });
        volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
        volumeSeries.setData(volumes);
      }

      const cand = candles || [];
      const r = Number(boxR);
      const s = Number(boxS);
      if (cand.length && Number.isFinite(r) && Number.isFinite(s)) {
        const level = { color: '#2457b8', lineWidth: 2, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false };
        chart.addSeries(LineSeries, level).setData(cand.map(k => ({ time: k.time, value: r })));
        chart.addSeries(LineSeries, level).setData(cand.map(k => ({ time: k.time, value: s })));
      }
      chart.timeScale().fitContent();
    } catch (err) {
      console.error('[TimeframeChart] init failed:', err);
      setChartError(true);
      return undefined;
    }
    return () => {
      if (chart) { try { chart.remove(); } catch { /* safe to ignore */ } }
      if (container) container.innerHTML = '';
    };
  }, [candles, volumes, boxR, boxS]);

  if (chartError) {
    return <div style={{ alignItems: 'center', color: 'var(--text-muted)', display: 'flex', flex: 1, fontSize: 11, justifyContent: 'center' }}>Chart unavailable</div>;
  }
  return <div ref={containerRef} style={{ flex: 1, minHeight: 0, position: 'relative' }} />;
}

// The plain-language read for one timeframe (no jargon labels).
function readState(data, tf) {
  const trendState = data[`htf_${tf}_trend_state`];
  const inConsol = data[`htf_${tf}_in_consol`];
  const phase = data[`htf_${tf}_phase`];
  const reaccum = data[`htf_${tf}_reaccum`];
  const stage2 = data[`htf_${tf}_stage2`];
  const trend = trendState === 'up' ? { sym: '▲', col: '#3fb950' }
    : trendState === 'down' ? { sym: '▼', col: '#f85149' }
      : trendState === 'neutral' ? { sym: '▬', col: '#8b949e' }
        : { sym: '·', col: 'var(--text-faint)' };
  let text = 'No base in view';
  let col = 'var(--text-faint)';
  if (reaccum) { text = `Re-accumulation${phase ? ` · Phase ${phase}` : ''}`; col = '#ff9f43'; }
  else if (inConsol) { text = `Consolidating${phase ? ` · Phase ${phase}` : ''}`; col = '#58a6ff'; }
  else if (stage2) { text = 'Stage-2 uptrend'; col = '#3fb950'; }
  else if (trendState == null || trendState === 'unknown') { text = 'Not enough history'; }
  else if (trendState === 'down') { text = 'Downtrend'; col = '#f85149'; }
  else { text = 'Neutral'; }
  return { trend, text, col, nested: data[`htf_${tf}_daily_nested`] };
}

function TfPanel({ label, tf, data }) {
  const candles = data[tf === 'w' ? 'weekly_candles' : 'monthly_candles'] || [];
  const volumes = data[tf === 'w' ? 'weekly_volumes' : 'monthly_volumes'] || [];
  const { trend, text, col, nested } = readState(data, tf);
  return (
    <div style={{ background: 'var(--bg-main)', display: 'flex', flex: 1, flexDirection: 'column', minWidth: 0 }}>
      <div style={{ alignItems: 'center', borderBottom: '1px solid var(--border-color)', display: 'flex', gap: 8, padding: '5px 10px' }}>
        <span style={{ color: 'var(--text-main)', fontSize: 12, fontWeight: 700 }}>{label}</span>
        <span style={{ color: trend.col, fontSize: 12, lineHeight: 1 }}>{trend.sym}</span>
        <span style={{ color: col, fontSize: 11, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{text}</span>
        {nested ? <span title="The daily base sits inside this box (tight alignment)" style={{ color: '#ff9f43', fontSize: 10, marginLeft: 'auto' }}>⊂ nested</span> : null}
      </div>
      {candles.length
        ? <TfChart candles={candles} volumes={volumes} boxR={data[`htf_${tf}_box_r`]} boxS={data[`htf_${tf}_box_s`]} />
        : <div style={{ alignItems: 'center', color: 'var(--text-faint)', display: 'flex', flex: 1, fontSize: 11, justifyContent: 'center' }}>No {label.toLowerCase()} data yet (needs more history)</div>}
    </div>
  );
}

// The weekly + monthly two-up row. Hidden entirely for rows that predate the
// higher-timeframe read (no resampled candles in the payload).
const TimeframeCharts = ({ data }) => {
  if (!data || (!data.weekly_candles?.length && !data.monthly_candles?.length)) return null;
  return (
    <div style={{ background: 'var(--border-color)', borderTop: '1px solid var(--border-color)', display: 'flex', flex: '0 0 auto', gap: 1, height: 210 }}>
      <TfPanel label="Weekly" tf="w" data={data} />
      <TfPanel label="Monthly" tf="m" data={data} />
    </div>
  );
};

export default TimeframeCharts;
