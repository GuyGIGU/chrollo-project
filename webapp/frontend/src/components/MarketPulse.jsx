import { useEffect, useState } from 'react';
import { LineSeries } from 'lightweight-charts';
import CandleChart from './CandleChart';
import { buildCloseSma } from './chartIndicators';
import { CHART_FRAMING, marketFetchDays, marketFocusLogicalRange } from './chartGeometry';
import { baseChartOptions } from './chartTheme';
import { API_BASE } from '../api';
import { STATE_META } from './marketRegimeFormat';

// The market read as three side-by-side index panes (Finviz's strip), not one
// tabbed chart: the point of the row is seeing SPY/QQQ/IWM at once, so the tab
// state, its keyed remount, and the active-legend lookup are all DELETED rather
// than reworked. Every pane is the same component with the same framing, because
// side-by-side panes invite comparison and unequal geometry would misrepresent
// relative behavior.
const INDICES = [
  { sym: 'SPY', label: 'S&P 500' },
  { sym: 'QQQ', label: 'Nasdaq 100' },
  { sym: 'IWM', label: 'Russell 2000' },
];

const MARKET = CHART_FRAMING.market;
const VISIBLE_BARS = MARKET.visibleBars;
// Fetch depth is DERIVED from the visible window plus SMA200's warm-up, never
// hand-picked: at 400 days the 200-bar average only began mid-pane, so the
// overlay read as a data bug. chartGeometry.test.js pins the relationship.
const DAYS = marketFetchDays(VISIBLE_BARS, MARKET.smaWarmupBars);

const SMA50 = { color: '#f0a35e', lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false };
const SMA200 = { color: '#7c8cf8', lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false };

const signed = (v) => (v == null || !Number.isFinite(v) ? '—' : `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(2)}%`);
const chgColor = (v) => (v == null ? 'var(--text-faint)' : v >= 0 ? 'var(--success)' : 'var(--danger)');

const chartOptions = (container) => {
  const base = baseChartOptions('mini', container.clientWidth || 380, container.clientHeight || 180);
  return {
    ...base,
    autoSize: true,
    crosshair: { mode: 1 },
    rightPriceScale: { ...base.rightPriceScale, scaleMargins: MARKET.scaleMargins },
    // No time axis in the strip: at a glance the dates add nothing.
    timeScale: { ...base.timeScale, visible: false, timeVisible: false, fixLeftEdge: true, fixRightEdge: true },
    handleScroll: false,
    handleScale: false,
  };
};

// Bars colored green/red by direction (Finviz convention), matching the
// backend's green/red volume tint already returned by /market-data/chart.
const barOptions = { upColor: '#5fb882', downColor: '#ee6352', thinBars: false, lastValueVisible: true, priceLineVisible: false };

// ONE sequential orchestrator for the whole strip. The provider's candle path is
// not thread-safe across concurrent symbol downloads, so panes must NEVER fetch
// for themselves — that constraint is why this hook stays in the parent. Each
// symbol publishes as it lands, so SPY paints while QQQ/IWM are still in flight
// instead of the row waiting on the slowest of three calls.
function useIndices() {
  const [bySym, setBySym] = useState(() =>
    Object.fromEntries(INDICES.map((i) => [i.sym, { status: 'loading', candles: [], volumes: [], last: null, chg: null }])),
  );

  useEffect(() => {
    let mounted = true;
    (async () => {
      for (const idx of INDICES) {
        let res = null;
        try {
          const r = await fetch(`${API_BASE}/market-data/chart/${idx.sym}?days=${DAYS}`);
          res = r.ok ? await r.json() : null;
        } catch { res = null; }
        if (!mounted) return;

        const candles = res?.candles || [];
        const last = candles.length ? candles[candles.length - 1].close : null;
        const prev = candles.length >= 2 ? candles[candles.length - 2].close : null;
        setBySym((previous) => ({
          ...previous,
          [idx.sym]: {
            status: candles.length ? 'ready' : 'error',
            candles,
            volumes: res?.volumes || [],
            last,
            chg: prev ? (last / prev - 1) * 100 : null,
          },
        }));
      }
    })();
    return () => { mounted = false; };
  }, []);

  return bySym;
}

// One pane. Presentational only — it receives its data and never fetches.
function IndexPane({ label, sym, entry }) {
  const { candles, volumes, status, last, chg } = entry;

  const onReady = (chart) => {
    const s50 = buildCloseSma(candles, 50);
    const s200 = buildCloseSma(candles, 200);
    if (s50.length) chart.addSeries(LineSeries, SMA50).setData(s50);
    if (s200.length) chart.addSeries(LineSeries, SMA200).setData(s200);
    const range = marketFocusLogicalRange(candles, VISIBLE_BARS);
    if (range) chart.timeScale().setVisibleLogicalRange(range);
    else chart.timeScale().fitContent();
  };

  return (
    <div className="mp-pane">
      <div className="mp-pane-head">
        <span className="mp-pane-sym" title={label}>{sym}</span>
        <span className="mp-pane-px">{last != null ? last.toFixed(2) : '—'}</span>
        <span className="mp-pane-chg" style={{ color: chgColor(chg) }}>{signed(chg)}</span>
      </div>
      <div className="mp-pane-chart instrument-well">
        {status === 'loading' && <div className="mp-chart-msg">Loading…</div>}
        {status === 'error' && <div className="mp-chart-msg">Unavailable</div>}
        {status === 'ready' && candles.length > 0 && (
          <CandleChart
            spec={{
              chartOptions,
              candles,
              barOptions,
              volumes,
              showVolume: true,
              volumeScaleTop: MARKET.volumeScaleTop,
              onReady,
              onError: (err) => console.error(`[MarketPulse] chart init failed for ${sym}:`, err),
              deps: [sym, candles],
            }}
            candles={candles}
            style={{ position: 'absolute', inset: 0 }}
            errorFallback={<div className="mp-chart-msg">Chart failed.</div>}
          />
        )}
      </div>
    </div>
  );
}

export default function MarketPulse({ marketContext }) {
  const bySym = useIndices();
  const state = marketContext?.regime?.state || 'UNKNOWN';
  const meta = STATE_META[state] || STATE_META.UNKNOWN;

  return (
    <section className="mp-card instrument-tile">
      <div className="mp-strip-head">
        <span className="mp-eyebrow">Markets · {meta.label}</span>
        {/* The SMA key is rendered ONCE for the row, not three times. */}
        <span className="mp-malegend">
          <span><i style={{ background: SMA50.color }} />SMA 50</span>
          <span><i style={{ background: SMA200.color }} />SMA 200</span>
          <span className="mp-malegend-note">daily · {DAYS}d</span>
        </span>
      </div>

      <div className="mp-panes">
        {INDICES.map((idx) => (
          <IndexPane key={idx.sym} sym={idx.sym} label={idx.label} entry={bySym[idx.sym]} />
        ))}
      </div>
    </section>
  );
}
