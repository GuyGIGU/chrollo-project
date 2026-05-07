import React, { useEffect, useRef } from 'react';
import { createChart, BarSeries, LineSeries, HistogramSeries } from 'lightweight-charts';

const ScreenerModal = ({ ticker, data, onClose, onPrev, onNext, footer = null }) => {
  const chartContainerRef = useRef(null);

  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container) return;

    // Always clear before creating
    container.innerHTML = '';

    let disposed = false;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: { background: { type: 'solid', color: '#1c1c24' }, textColor: '#7b7b8f', fontFamily: "'JetBrains Mono', monospace", fontSize: 13 },
      grid: { vertLines: { color: 'rgba(42, 42, 54, 0.4)' }, horzLines: { color: 'rgba(42, 42, 54, 0.4)' } },
      crosshair: { mode: 1 }, 
      rightPriceScale: { borderColor: '#2a2a36', scaleMargins: { top: 0.1, bottom: 0.25 } },
      timeScale: { borderColor: '#2a2a36', timeVisible: true, fixLeftEdge: false, fixRightEdge: false },
      handleScroll: true,
      handleScale: true,
    });

    const candleSeries = chart.addSeries(BarSeries, { upColor: '#d1d4dc', downColor: '#d1d4dc', thinBars: false });
    
    let plotCandles = JSON.parse(JSON.stringify(data.candles));
    const forwardBars = data.forward_bars || 0;
    const baseEnd = plotCandles.length - 1 - forwardBars;

    if (data.base_len > 0) {
      const baseStart = Math.max(0, baseEnd - data.base_len + 1);
      
      // If we have specific anchors, highlight the limb. Otherwise, highlight the whole base
      if (data.r_anchor !== undefined && data.s_anchor !== undefined && data.r_anchor !== null) {
        const rawBaseStart = baseEnd - data.base_len + 1;
        const rBar = rawBaseStart + data.r_anchor;
        const sBar = rawBaseStart + data.s_anchor;
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
      
      if (data.lps_len > 0 && data.lps_offset !== undefined) {
        const lpsEnd = baseEnd - data.lps_offset;
        const lpsStart = Math.max(0, lpsEnd - data.lps_len + 1);
        for (let k = lpsStart; k <= lpsEnd; k++) {
          if (k >= 0 && k < plotCandles.length) plotCandles[k].color = '#e3b341'; // Yellow highlight
        }
      }
    }
    candleSeries.setData(plotCandles);

    const volumeSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume' });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    volumeSeries.setData(data.volumes);

    const rSeries = chart.addSeries(LineSeries, { color: '#4488ff', lineWidth: 2, crosshairMarkerVisible: false });
    const sSeries = chart.addSeries(LineSeries, { color: '#4488ff', lineWidth: 2, crosshairMarkerVisible: false });
    const midSeries = chart.addSeries(LineSeries, { color: 'rgba(139, 148, 158, 0.4)', lineWidth: 1, lineStyle: 2, crosshairMarkerVisible: false });

    const rData = []; const sData = []; const midData = [];
    const startIdx = Math.max(0, baseEnd - data.base_len + 1);
    const midValue = (data.R + data.S) / 2;
    for (let i = startIdx; i < data.candles.length; i++) {
        const t = data.candles[i].time;
        rData.push({ time: t, value: data.R }); 
        sData.push({ time: t, value: data.S });
        midData.push({ time: t, value: midValue });
    }
    rSeries.setData(rData); sSeries.setData(sData); midSeries.setData(midData);

    // Optional annotations: trigger price line + MFE/MAE markers on the
    // forward bars. Only renders the pieces that exist in the payload, so
    // live screener charts (no annotations) stay unchanged.
    const ann = data.annotations || {};
    if (ann.trigger_price) {
      candleSeries.createPriceLine({
        price: ann.trigger_price,
        color: '#e3b341',
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: 'Trigger',
      });
    }
    const markers = [];
    if (ann.trigger_date) {
      markers.push({
        time: ann.trigger_date, position: 'belowBar',
        color: '#3fb950', shape: 'arrowUp', text: 'TRIG',
      });
    }
    if (ann.mfe_20d_date && ann.mfe_20d != null) {
      markers.push({
        time: ann.mfe_20d_date, position: 'aboveBar',
        color: '#3fb950', shape: 'circle',
        text: `MFE ${(ann.mfe_20d * 100).toFixed(1)}%`,
      });
    }
    if (ann.mae_20d_date && ann.mae_20d != null) {
      markers.push({
        time: ann.mae_20d_date, position: 'belowBar',
        color: '#c76b73', shape: 'circle',
        text: `MAE ${(ann.mae_20d * 100).toFixed(1)}%`,
      });
    }
    if (markers.length > 0) {
      // Sort by time — lightweight-charts requires markers in chronological order.
      markers.sort((a, b) => a.time.localeCompare(b.time));
      candleSeries.setMarkers(markers);
    }

    const displayStart = Math.max(0, baseEnd - Math.max(80, data.base_len + 30));
    chart.timeScale().setVisibleRange({
      from: data.candles[displayStart].time,
      to: data.candles[data.candles.length - 1].time,
    });

    const handleResize = () => {
      if (!disposed && container && container.isConnected) {
        try {
          chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
        } catch { /* detached */ }
      }
    };

    window.addEventListener('resize', handleResize);
    const resizeTimeout = setTimeout(handleResize, 100);

    return () => {
      disposed = true;
      clearTimeout(resizeTimeout);
      window.removeEventListener('resize', handleResize);
      try {
        chart.remove();
      } catch {
        // Canvas already detached — safe to ignore
      }
      if (container) container.innerHTML = '';
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]); // Re-create chart when ticker changes

  const getTierColor = (tier) => {
    switch(tier) {
      case 'S': return '#ff8c00';
      case 'A': return '#bb86fc';
      case 'B': return '#58a6ff';
      case 'C': return '#3fb950';
      default: return '#8b949e';
    }
  };

  const getBadgeBg = (tier) => {
    switch(tier) {
      case 'S': return 'rgba(255,140,0,0.15)';
      case 'A': return 'rgba(187,134,252,0.15)';
      case 'B': return 'rgba(88,166,255,0.15)';
      case 'C': return 'rgba(63,185,80,0.15)';
      default: return 'rgba(139,148,158,0.15)';
    }
  }

  const currentPrice = data.candles[data.candles.length - 1].close;

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(10, 10, 15, 0.95)',
      backdropFilter: 'blur(4px)',
      zIndex: 5000,
      display: 'flex', flexDirection: 'column',
      padding: '40px'
    }} onClick={onClose}>
      
      <div style={{
        background: 'var(--bg-main)',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        flex: 1, display: 'flex', flexDirection: 'column',
        boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
        overflow: 'hidden', margin: '0 auto', width: '100%', maxWidth: '1400px'
      }} onClick={(e) => e.stopPropagation()}>
        
        {/* Header */}
        <div style={{
          padding: '16px 24px', borderBottom: '1px solid var(--border-color)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: 'var(--bg-panel)'
        }}>
          
          <div style={{display: 'flex', alignItems: 'center', gap: '16px'}}>
            <span style={{fontSize: '24px', fontWeight: '700', fontFamily: "'JetBrains Mono', monospace", color: getTierColor(data.tier)}}>
              {ticker}
            </span>
            <span style={{
              padding: '2px 8px', borderRadius: '10px', fontWeight: '700', fontSize: '11px',
              color: getTierColor(data.tier), border: `1px solid ${getTierColor(data.tier)}55`,
              background: getBadgeBg(data.tier)
            }}>
              {data.tier} TIER
            </span>
            <div style={{display: 'flex', gap: '16px', fontSize: '13px', color: 'var(--text-main)', fontFamily: "'JetBrains Mono', monospace", marginLeft: '12px'}}>
                <span><strong>Setup:</strong> {data.setup}</span>
                <span><strong>Score:</strong> {data.score}</span>
                <span><strong>Curr:</strong> ${currentPrice}</span>
                <span><strong>Base:</strong> {data.base_len}d</span>
                <span><strong>R:</strong> ${data.R}</span>
                <span><strong>S:</strong> ${data.S}</span>
            </div>
          </div>

          <div style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
            <button onClick={onPrev} style={{
              padding: '6px 16px', borderRadius: '6px', border: '1px solid var(--border-color)', 
              background: 'var(--bg-main)', color: 'var(--text-main)', cursor: 'pointer', outline: 'none', fontFamily: 'inherit'
            }}>◀ Prev</button>
            <button onClick={onNext} style={{
              padding: '6px 16px', borderRadius: '6px', border: '1px solid var(--border-color)', 
              background: 'var(--bg-main)', color: 'var(--text-main)', cursor: 'pointer', outline: 'none', fontFamily: 'inherit'
            }}>Next ▶</button>
            <button onClick={onClose} style={{
              background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', 
              fontSize: '30px', marginLeft: '16px', padding: '0 8px'
            }}>×</button>
          </div>

        </div>

        {/* Chart Canvas Area */}
        {/* minHeight: 0 lets flex:1 actually shrink so the footer (if present)
            isn't pushed off-screen. Without it the chart insists on its content
            height and overflows. */}
        <div ref={chartContainerRef} style={{ flex: 1, minHeight: 0, position: 'relative' }}></div>

        {footer}
      </div>
    </div>
  );
};

export default ScreenerModal;
