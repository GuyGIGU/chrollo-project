import { useEffect } from 'react';
import { createChart, BarSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import { buildHl2SmaData, hl2Sma20Options } from '../components/chartIndicators';

// Shared lifecycle for every lightweight-charts canvas in the app.
//
// This is the ONLY thing the five chart sites genuinely share: the imperative
// create→draw-base-series→teardown skeleton (Dodds Principle 8 — create-and-
// destroy paired in one effect, chart.remove() mandatory, chart never in
// useState). Everything that diverges per site — candle coloring, R/S levels,
// price lines, markers, the phase-overlay primitive, visible-range focus, and
// the resize strategy — is supplied by the caller through `onReady`/`onResize`,
// NOT through a combinatorial flag bag. chartOptions stays the caller's: each
// site's background / interactivity / autoSize is its identity, not noise.
//
// Spec fields:
//   chartOptions : object passed straight to createChart (required)
//   candles      : bar data for the base BarSeries (required to draw)
//   barOptions   : options for the base BarSeries (default: whitewashed bars)
//   volumes      : if showVolume, histogram volume data
//   showVolume   : draw the standard bottom-anchored volume histogram
//   volumeScaleTop : top scaleMargin for the volume pane (default 0.8)
//   showSma      : draw the hl2 SMA-20 line (chartIndicators)
//   onReady(chart, candleSeries) : draw everything site-specific here
//   onResize(chart, container)   : window-resize handler; omit for autoSize sites
//   resizeDelayMs : if set, also call onResize once after this delay (the
//                   existing 100ms post-mount nudge some sites use)
//   onError(err) : called if createChart/draw throws (site flips a fallback)
//   deps         : effect dependency array (default [containerRef])
//
// The base whitewashed bar color matches all five existing sites.
const DEFAULT_BAR_OPTIONS = { upColor: '#d8dbe5', downColor: '#d8dbe5', thinBars: false };

export default function useLightweightChart(containerRef, spec) {
  const {
    chartOptions,
    candles,
    barOptions = DEFAULT_BAR_OPTIONS,
    volumes,
    showVolume = false,
    volumeScaleTop = 0.8,
    showSma = false,
    onReady,
    onResize,
    resizeDelayMs,
    onError,
    deps = [containerRef],
  } = spec;

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !candles?.length) return undefined;

    container.innerHTML = '';
    let chart = null;
    let disposed = false;
    let handleResize = null;
    let resizeTimeout = null;

    const cleanup = () => {
      disposed = true;
      if (resizeTimeout) clearTimeout(resizeTimeout);
      if (handleResize) window.removeEventListener('resize', handleResize);
      if (chart) {
        try {
          chart.remove();
        } catch {
          /* safe to ignore — documented teardown race */
        }
      }
      if (container) container.innerHTML = '';
    };

    try {
      chart = createChart(container, chartOptions);

      const candleSeries = chart.addSeries(BarSeries, barOptions);
      candleSeries.setData(candles);

      if (showVolume) {
        const volumeSeries = chart.addSeries(HistogramSeries, {
          priceFormat: { type: 'volume' },
          priceScaleId: 'volume',
        });
        volumeSeries.priceScale().applyOptions({ scaleMargins: { top: volumeScaleTop, bottom: 0 } });
        volumeSeries.setData(volumes || []);
      }

      if (showSma) {
        const sma = buildHl2SmaData(candles);
        if (sma.length) {
          chart.addSeries(LineSeries, hl2Sma20Options).setData(sma);
        }
      }

      onReady?.(chart, candleSeries);

      if (onResize) {
        handleResize = () => {
          if (!disposed && container.isConnected) onResize(chart, container);
        };
        window.addEventListener('resize', handleResize);
        if (resizeDelayMs != null) resizeTimeout = setTimeout(handleResize, resizeDelayMs);
      }
    } catch (err) {
      cleanup();
      onError?.(err);
      return undefined;
    }

    return cleanup;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
