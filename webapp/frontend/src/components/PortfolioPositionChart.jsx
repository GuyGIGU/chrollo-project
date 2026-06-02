import React, { useEffect, useRef, useState } from 'react';
import { createChart, BarSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import { API_BASE } from '../api';
import { fmtMoney, fmtNum, pnlColor } from './portfolioFormat';

const chartOptions = (width, height) => ({
  width,
  height,
  layout: {
    background: { type: 'solid', color: '#1c1f2a' },
    textColor: '#7f879a',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 11,
  },
  grid: {
    vertLines: { color: 'rgba(47, 52, 71, 0.28)' },
    horzLines: { color: 'rgba(47, 52, 71, 0.28)' },
  },
  rightPriceScale: {
    borderColor: '#2f3447',
    scaleMargins: { top: 0.08, bottom: 0.24 },
  },
  timeScale: {
    borderColor: '#2f3447',
    timeVisible: false,
    fixLeftEdge: true,
    fixRightEdge: true,
  },
});
const overlayStyle = {
  position: 'fixed',
  inset: 0,
  zIndex: 2000,
  background: 'rgba(10, 12, 18, 0.78)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 18,
};
const chartShellStyle = {
  width: 'min(1120px, 96vw)',
  maxHeight: '88vh',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  background: 'var(--bg-panel)',
  overflow: 'hidden',
  boxShadow: '0 24px 70px rgba(0,0,0,0.42)',
};

const buildLevel = (candles, value) => {
  const price = Number(value);
  if (!Number.isFinite(price) || price <= 0) return [];
  return candles.map((candle) => ({ time: candle.time, value: price }));
};

const usePositionChartData = (symbol) => {
  const [state, setState] = useState({ loading: false, error: '', data: null });

  useEffect(() => {
    if (!symbol) return undefined;
    const controller = new AbortController();
    setState({ loading: true, error: '', data: null });

    fetch(`${API_BASE}/market-data/chart/${encodeURIComponent(symbol)}?days=180`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Chart data unavailable');
        if (!response.headers.get('content-type')?.includes('application/json')) {
          throw new Error('Restart the backend to enable live chart data.');
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.candles?.length) throw new Error('Chart data unavailable');
        setState({ loading: false, error: '', data });
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setState({ loading: false, error: error.message, data: null });
      });

    return () => controller.abort();
  }, [symbol]);

  return state;
};

const PositionChartCanvas = ({ symbol, data, position }) => {
  const containerRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !data?.candles?.length) return undefined;
    container.innerHTML = '';

    const chart = createChart(container, chartOptions(container.clientWidth || 760, container.clientHeight || 310));
    const candles = data.candles;
    const candleSeries = chart.addSeries(BarSeries, {
      upColor: '#d8dbe5',
      downColor: '#d8dbe5',
      thinBars: false,
    });
    candleSeries.setData(candles);

    const volumeSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume' });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    volumeSeries.setData(data.volumes || []);

    const avgLine = chart.addSeries(LineSeries, {
      color: '#d4b85a',
      lineWidth: 1,
      lineStyle: 2,
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });
    avgLine.setData(buildLevel(candles, position?.avg_cost ?? position?.average_cost));

    chart.timeScale().fitContent();

    const handleResize = () => chart.applyOptions({ width: container.clientWidth || 760 });
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      container.innerHTML = '';
    };
  }, [symbol, data, position]);

  return <div ref={containerRef} style={{ height: 310, minHeight: 260, position: 'relative' }} />;
};

const PositionChartHeader = ({ symbol, position, onClose }) => {
  const qty = Number(position?.position ?? position?.quantity ?? 0);
  const value = Number(position?.market_value);
  const unrealized = Number(position?.unrealized_pnl);
  const price = Number(position?.market_price);

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12, padding: '13px 15px', borderBottom: '1px solid var(--border-color)' }}>
      <div>
        <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 800, textTransform: 'uppercase' }}>Position Chart</div>
        <div style={{ color: 'var(--accent-blue)', fontSize: 22, fontWeight: 850 }}>{symbol || '-'}</div>
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>Qty {fmtNum(qty, 0)}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>Market {Number.isFinite(price) ? fmtMoney(price) : '-'}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>Value {Number.isFinite(value) ? fmtMoney(value) : '-'}</div>
      <div style={{ color: pnlColor(unrealized), fontSize: 11, fontWeight: 800 }}>Open P&L {Number.isFinite(unrealized) ? fmtMoney(unrealized) : '-'}</div>
      <button
        type="button"
        onClick={onClose}
        title="Close chart"
        style={{
          marginLeft: 'auto',
          width: 30,
          height: 30,
          borderRadius: 6,
          border: '1px solid var(--border-color)',
          background: 'transparent',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          fontWeight: 900,
        }}
      >
        x
      </button>
    </div>
  );
};

const PortfolioPositionChart = ({ selectedSymbol, position, open, onClose }) => {
  const { loading, error, data } = usePositionChartData(open ? selectedSymbol : '');

  useEffect(() => {
    if (!open) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div style={overlayStyle} onClick={onClose}>
      <section
        style={chartShellStyle}
        onClick={(event) => event.stopPropagation()}
        title="Real daily OHLCV data from the market-data endpoint."
      >
        <PositionChartHeader symbol={selectedSymbol} position={position} onClose={onClose} />
        {!selectedSymbol && <div style={{ padding: 28, color: 'var(--text-muted)', textAlign: 'center' }}>Select a position to load its chart.</div>}
        {selectedSymbol && loading && <div style={{ padding: 28, color: 'var(--text-muted)', textAlign: 'center' }}>Loading chart data...</div>}
        {selectedSymbol && error && <div style={{ padding: 28, color: 'var(--text-muted)', textAlign: 'center' }}>{error}</div>}
        {selectedSymbol && data && <PositionChartCanvas symbol={selectedSymbol} data={data} position={position} />}
      </section>
    </div>
  );
};

export default PortfolioPositionChart;
