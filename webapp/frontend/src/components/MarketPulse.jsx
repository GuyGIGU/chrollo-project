import { useEffect, useState } from 'react';
import { LineSeries } from 'lightweight-charts';
import CandleChart from './CandleChart';
import { buildCloseSma } from './chartIndicators';
import { baseChartOptions } from './chartTheme';
import { API_BASE } from '../api';
import { STATE_META } from './marketRegimeFormat';

// The market hero: the regime read promoted into a real OHLC chart on OUR chart
// model (lightweight-charts BarSeries, like every other chart in the app) — not
// unreadable overlaid % lines. One index at a time (bars can't legibly overlay),
// switchable via the tabs, with Finviz-style SMA 50/200 overlays + volume. The
// long window (≈18mo) lets SMA 200 render; the view focuses the recent ~6mo.
const INDICES = [
  { sym: 'SPY', label: 'S&P 500' },
  { sym: 'QQQ', label: 'Nasdaq 100' },
  { sym: 'IWM', label: 'Russell 2000' },
];
const DAYS = 400;
const VISIBLE_BARS = 130;
const SMA50 = { color: '#f0a35e', lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false };
const SMA200 = { color: '#7c8cf8', lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false };

const signed = (v) => (v == null || !Number.isFinite(v) ? '—' : `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(2)}%`);
const chgColor = (v) => (v == null ? 'var(--text-faint)' : v >= 0 ? 'var(--success)' : 'var(--danger)');

const chartOptions = (container) => {
  const base = baseChartOptions('mini', container.clientWidth || 600, container.clientHeight || 300);
  return {
    ...base,
    autoSize: true,
    crosshair: { mode: 1 },
    rightPriceScale: { ...base.rightPriceScale, scaleMargins: { top: 0.08, bottom: 0.26 } },
    timeScale: { ...base.timeScale, timeVisible: false, fixLeftEdge: true, fixRightEdge: true },
    handleScroll: false,
    handleScale: false,
  };
};

// Bars colored green/red by direction (Finviz convention), matching the
// backend's green/red volume tint already returned by /market-data/chart.
const barOptions = { upColor: '#5fb882', downColor: '#ee6352', thinBars: false, lastValueVisible: true, priceLineVisible: false };

function useIndices() {
  const [bySym, setBySym] = useState({});
  const [legend, setLegend] = useState([]);
  const [status, setStatus] = useState('loading');

  useEffect(() => {
    let mounted = true;
    setStatus('loading');
    // SEQUENTIAL fetch: the backend candle path (yfinance) is not thread-safe
    // across concurrent symbol downloads — parallel requests cross-contaminate.
    (async () => {
      const data = {};
      const leg = [];
      for (const idx of INDICES) {
        let res = null;
        try {
          const r = await fetch(`${API_BASE}/market-data/chart/${idx.sym}?days=${DAYS}`);
          res = r.ok ? await r.json() : null;
        } catch { res = null; }
        const candles = res?.candles || [];
        data[idx.sym] = { candles, volumes: res?.volumes || [] };
        if (candles.length >= 2) {
          const last = candles[candles.length - 1].close;
          const prev = candles[candles.length - 2].close;
          leg.push({ ...idx, last, chg: prev ? (last / prev - 1) * 100 : null });
        } else {
          leg.push({ ...idx, last: candles[0]?.close ?? null, chg: null });
        }
      }
      if (!mounted) return;
      setBySym(data);
      setLegend(leg);
      setStatus(Object.values(data).some((d) => d.candles.length) ? 'ready' : 'error');
    })();
    return () => { mounted = false; };
  }, []);

  return { bySym, legend, status };
}

export default function MarketPulse({ marketContext }) {
  const { bySym, legend, status } = useIndices();
  const [active, setActive] = useState('SPY');

  const state = marketContext?.regime?.state || 'UNKNOWN';
  const meta = STATE_META[state] || STATE_META.UNKNOWN;
  const activeData = bySym[active];
  const activeLeg = legend.find((l) => l.sym === active);
  const candles = activeData?.candles || [];

  const onReady = (chart) => {
    const s50 = buildCloseSma(candles, 50);
    const s200 = buildCloseSma(candles, 200);
    if (s50.length) chart.addSeries(LineSeries, SMA50).setData(s50);
    if (s200.length) chart.addSeries(LineSeries, SMA200).setData(s200);
    const n = candles.length;
    if (n > VISIBLE_BARS) chart.timeScale().setVisibleLogicalRange({ from: n - VISIBLE_BARS, to: n - 1 });
    else chart.timeScale().fitContent();
  };

  return (
    <section className="mp-card instrument-tile">
      <div className="mp-head">
        <div className="mp-title">
          <span className="mp-eyebrow">Markets · {meta.label}</span>
          <div className="mp-quote">
            <strong className="mp-quote-name">{activeLeg?.label || active}</strong>
            <span className="mp-quote-px">{activeLeg?.last != null ? activeLeg.last.toFixed(2) : '—'}</span>
            <span className="mp-quote-chg" style={{ color: chgColor(activeLeg?.chg) }}>{signed(activeLeg?.chg)}</span>
          </div>
        </div>
        <div className="mp-tabs">
          {(legend.length ? legend : INDICES.map((i) => ({ ...i, chg: null }))).map((l) => (
            <button
              key={l.sym}
              type="button"
              className={`mp-tab ${l.sym === active ? 'active' : ''}`}
              onClick={() => setActive(l.sym)}
              title={l.label}
            >
              <span className="mp-tab-sym">{l.sym}</span>
              <span className="mp-tab-chg" style={{ color: chgColor(l.chg) }}>{signed(l.chg)}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="mp-chart instrument-well">
        {status === 'loading' && <div className="mp-chart-msg">Loading…</div>}
        {status === 'error' && <div className="mp-chart-msg">Index data unavailable.</div>}
        {status === 'ready' && candles.length > 0 && (
          <CandleChart
            key={active}
            spec={{
              chartOptions,
              candles,
              barOptions,
              volumes: activeData.volumes,
              showVolume: true,
              volumeScaleTop: 0.82,
              onReady,
              onError: (err) => console.error('[MarketPulse] chart init failed:', err),
              deps: [active, candles],
            }}
            candles={candles}
            style={{ position: 'absolute', inset: 0 }}
            errorFallback={<div className="mp-chart-msg">Chart failed to load.</div>}
          />
        )}
      </div>

      <div className="mp-malegend">
        <span><i style={{ background: SMA50.color }} />SMA 50</span>
        <span><i style={{ background: SMA200.color }} />SMA 200</span>
        <span className="mp-malegend-note">daily · {DAYS}d history</span>
      </div>
    </section>
  );
}
