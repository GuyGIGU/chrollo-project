import React, { useEffect, useRef, useState } from 'react';
import { createChart, BarSeries, LineSeries, HistogramSeries } from 'lightweight-charts';
import { TagRow } from './SetupTags';
import { ScoreBreakdownPills } from './ScoreBreakdown';

// Map archive row's score_* columns to the shape SetupTags expects.
const subScoresFromSetup = (s) => ({
  box_tightness:   s.score_box_tightness,
  touch_density:   s.score_touch_density,
  oscillation:     s.score_oscillation,
  atr_squeeze:     s.score_atr_squeeze,
  lps_tightness:   s.score_lps_tightness,
  vol_contraction: s.score_vol_contraction,
  base_age:        s.score_base_age,
  uptrend_bonus:   s.score_uptrend_bonus,
  rs_bonus:        s.score_rs_bonus,
  high_proximity:  s.score_high_proximity,
  breadth_bonus:   s.score_breadth_bonus,
  contraction:     s.score_contraction,
  ascending_support: s.score_ascending_support,
  adr:             s.score_adr,
});

const tierColor = (t) => ({ S: '#ff8c00', A: '#bb86fc', B: '#58a6ff', C: '#3fb950', D: '#8b949e' }[t] || '#8b949e');
const labelColor = (l) => ({ perfect: '#3fb950', good: '#58a6ff', noise: '#8b949e', miss: '#c76b73' }[l] || 'var(--text-muted)');
const QUALITY_LABELS = ['perfect', 'good', 'noise', 'miss'];
const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—';

// Renders the screener-style mini chart (candles + R/S/midline + base/LPS overlays + forward bars).
// Mirrors ScreenerCard's chart code so layout/style stays identical to the screener grid.
const ArchiveCard = React.memo(({ setup, chartData, onClick, onLabelChange }) => {
  const chartContainerRef = useRef(null);
  const [chartError, setChartError] = useState(false);

  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container || !chartData || !chartData.candles) return;

    container.innerHTML = '';
    let disposed = false;
    let chart = null;

    try {
      const w = container.clientWidth || 340;
      const h = container.clientHeight || 220;

      chart = createChart(container, {
        width: w,
        height: h,
        layout: { background: { type: 'solid', color: '#1c1c24' }, textColor: '#7b7b8f', fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
        grid: { vertLines: { color: 'rgba(42, 42, 54, 0.3)' }, horzLines: { color: 'rgba(42, 42, 54, 0.3)' } },
        crosshair: { mode: 0 },
        rightPriceScale: { borderColor: '#2a2a36', scaleMargins: { top: 0.1, bottom: 0.25 } },
        timeScale: { borderColor: '#2a2a36', timeVisible: false, fixLeftEdge: true, fixRightEdge: true },
        handleScroll: false,
        handleScale: false,
      });

      const candleSeries = chart.addSeries(BarSeries, { upColor: '#d1d4dc', downColor: '#d1d4dc', thinBars: false });

      const plotCandles = JSON.parse(JSON.stringify(chartData.candles));
      const forwardBars = chartData.forward_bars || 0;
      const baseEnd = plotCandles.length - 1 - forwardBars;

      if (chartData.base_len > 0) {
        const baseStart = Math.max(0, baseEnd - chartData.base_len + 1);

        if (chartData.r_anchor != null && chartData.s_anchor != null) {
          const rawBaseStart = baseEnd - chartData.base_len + 1;
          const rBar = rawBaseStart + chartData.r_anchor;
          const sBar = rawBaseStart + chartData.s_anchor;
          const limbStart = Math.min(rBar, sBar);
          const limbEnd = Math.max(rBar, sBar);
          for (let k = limbStart; k <= limbEnd; k++) {
            if (k >= 0 && k < plotCandles.length) plotCandles[k].color = '#555555';
          }
        } else {
          for (let k = baseStart; k <= baseEnd; k++) {
            if (k >= 0 && k < plotCandles.length) plotCandles[k].color = '#555555';
          }
        }

        if (chartData.lps_len > 0 && chartData.lps_offset !== undefined) {
          const lpsEnd = baseEnd - chartData.lps_offset;
          const lpsStart = Math.max(0, lpsEnd - chartData.lps_len + 1);
          for (let k = lpsStart; k <= lpsEnd; k++) {
            if (k >= 0 && k < plotCandles.length) plotCandles[k].color = '#e3b341';
          }
        }
      }
      candleSeries.setData(plotCandles);

      const volumeSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume' });
      volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      volumeSeries.setData(chartData.volumes);

      const rSeries = chart.addSeries(LineSeries, { color: '#4488ff', lineWidth: 2, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });
      const sSeries = chart.addSeries(LineSeries, { color: '#4488ff', lineWidth: 2, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });
      const midSeries = chart.addSeries(LineSeries, { color: 'rgba(139, 148, 158, 0.4)', lineWidth: 1, lineStyle: 2, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });

      const rData = []; const sData = []; const midData = [];
      const startIdx = Math.max(0, baseEnd - chartData.base_len + 1);
      const midValue = (chartData.R + chartData.S) / 2;
      for (let i = startIdx; i < chartData.candles.length; i++) {
        const t = chartData.candles[i].time;
        rData.push({ time: t, value: chartData.R });
        sData.push({ time: t, value: chartData.S });
        midData.push({ time: t, value: midValue });
      }
      rSeries.setData(rData); sSeries.setData(sData); midSeries.setData(midData);

      // Frame the chart on the ORIGINAL STRUCTURE — the base + its R/S — with
      // only a modest forward window. Previously the visible range ran all the
      // way to the last forward bar (scan_date + 45 cal days); when price made
      // a big post-scan move (e.g. JAZZ 168→90), the price axis auto-scaled to
      // that excursion and squished the tight base, leaving the R/S lines
      // "floating" detached at one edge. lightweight-charts auto-scales the
      // price axis to the *visible* range, so clamping the time window to the
      // base + a short lead-in + a few forward bars keeps the consolidation —
      // the actual trade structure — as the visual focus. The full forward
      // action remains available (scrollable) in the click-through modal.
      if (chartData.candles.length > 0) {
        const baseLen = chartData.base_len || 0;
        const LEAD_IN = 10;            // bars of pre-base context
        const FORWARD_CONTEXT = 12;    // bars after scan_date to show on the card
        const fromIdx = Math.max(0, baseEnd - baseLen - LEAD_IN);
        const toIdx = Math.min(chartData.candles.length - 1, baseEnd + FORWARD_CONTEXT);
        chart.timeScale().setVisibleRange({
          from: chartData.candles[fromIdx].time,
          to: chartData.candles[toIdx].time,
        });
      } else {
        chart.timeScale().fitContent();
      }
    } catch (err) {
      console.error(`[ArchiveCard] Chart init failed for ${setup.ticker}:`, err);
      setChartError(true);
      return;
    }

    const handleResize = () => {
      if (!disposed && container && container.isConnected && chart) {
        try { chart.applyOptions({ width: container.clientWidth }); } catch { /* detached */ }
      }
    };
    window.addEventListener('resize', handleResize);
    const resizeTimeout = setTimeout(handleResize, 80);

    return () => {
      disposed = true;
      clearTimeout(resizeTimeout);
      window.removeEventListener('resize', handleResize);
      if (chart) { try { chart.remove(); } catch { /* safe */ } }
      if (container) container.innerHTML = '';
    };
  }, [setup.id, setup.ticker, chartData]);

  const fwd = setup.fwd_return_20d;
  const fwdColor = fwd > 0 ? 'var(--success)' : fwd < 0 ? 'var(--danger)' : 'var(--text-muted)';

  return (
    <div
      onClick={() => onClick(setup)}
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        height: '340px',
        cursor: 'pointer',
        transition: 'border-color 0.2s',
      }}
      onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--accent-blue)'}
      onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border-color)'}
    >
      {/* Header */}
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: '8px',
        flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', minWidth: 0 }}>
          <span style={{ fontWeight: '700', fontSize: '15px', color: tierColor(setup.tier) }}>{setup.ticker}</span>
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{setup.scan_date}</span>
        </div>
        <div className="screener-card-score-meta">
          <div style={{ fontSize: '10px', color: 'var(--text-main)', display: 'flex', gap: '6px', alignItems: 'center', justifyContent: 'flex-end' }}>
            <span style={{ padding: '1px 6px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', whiteSpace: 'nowrap' }}>{setup.tier}</span>
            <span style={{ whiteSpace: 'nowrap' }}>{setup.score?.toFixed(1)}</span>
          </div>
          <ScoreBreakdownPills subScores={subScoresFromSetup(setup)} />
        </div>
      </div>

      {/* Chart */}
      {chartError ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
          Chart failed to load
        </div>
      ) : !chartData ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
          Loading chart…
        </div>
      ) : (
        <div ref={chartContainerRef} style={{ flex: 1, position: 'relative', pointerEvents: 'none' }}></div>
      )}

      {/* Footer: setup type + 20d return + label */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 14px',
        background: 'var(--bg-main)', borderTop: '1px solid var(--border-color)',
        fontSize: '11px', color: 'var(--text-muted)',
        gap: '8px',
      }}>
        <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span>{setup.setup_type}</span>
          <span>·</span>
          <span>20d:&nbsp;<span style={{ color: fwdColor, fontWeight: 600 }}>{pct(setup.fwd_return_20d)}</span></span>
          {setup.triggered === 1 && <span style={{ color: 'var(--success)' }}>✓</span>}
          {setup.triggered === 0 && <span style={{ color: 'var(--text-muted)' }}>✗</span>}
        </span>
        <select
          value={setup.quality_label || ''}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => onLabelChange(setup.id, e.target.value || null)}
          style={{
            background: 'var(--bg-main)', border: '1px solid var(--border-color)',
            borderRadius: '4px', color: labelColor(setup.quality_label),
            fontSize: '10px', padding: '2px 4px', fontFamily: 'inherit', cursor: 'pointer',
          }}
        >
          <option value="">—</option>
          {QUALITY_LABELS.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
      </div>
      <TagRow
        subScores={subScoresFromSetup(setup)}
        flags={{
          phaseDInner: setup.phase_d_inner === 1,
          rTouchVolZ: setup.r_touch_vol_z,
          sTouchVolZ: setup.s_touch_vol_z,
        }}
        style={{
          padding: '6px 10px',
          background: 'var(--bg-main)',
          borderTop: '1px solid var(--border-color)',
        }}
      />
    </div>
  );
});

export default ArchiveCard;
