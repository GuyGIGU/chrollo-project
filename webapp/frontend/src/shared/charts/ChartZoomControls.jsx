import { ZOOM_IN, ZOOM_OUT, zoomedRange } from './chartZoom';

// The four acts a lens chart answers to (Fri 17/10/2026, his TradingView words): zoom in, zoom
// out, back to the opening view, and fit the whole history on screen. Drawn as a small cluster
// over the pane's bottom-left corner, faint at rest. The wheel over the pane zooms too (the
// chart's own handleScale, no modifier: his nit the same day), so this cluster is for the
// trackpad and the exact steps. `chartRef` holds the live lightweight-charts instance (null
// between builds), `onHome` re-frames the chart the way it opened.

const zoomBy = (chart, factor) => {
  const scale = chart.timeScale();
  const next = zoomedRange(scale.getVisibleLogicalRange(), factor);
  if (next) scale.setVisibleLogicalRange(next);
};

export default function ChartZoomControls({ chartRef, onHome }) {
  const act = (fn) => () => { if (chartRef.current) fn(chartRef.current); };
  return (
    <div className="chart-zoom" role="group" aria-label="Chart zoom">
      <button type="button" className="chart-zoom-btn" aria-label="Zoom in" title="Zoom in (or wheel up over the chart)" onClick={act((chart) => zoomBy(chart, ZOOM_IN))}>+</button>
      <button type="button" className="chart-zoom-btn" aria-label="Zoom out" title="Zoom out (or wheel down over the chart)" onClick={act((chart) => zoomBy(chart, ZOOM_OUT))}>−</button>
      <button type="button" className="chart-zoom-btn" aria-label="Reset the view" title="Back to the view it opened on" onClick={act(() => onHome?.())}>⌂</button>
      <button type="button" className="chart-zoom-btn" aria-label="Fit all" title="Fit the whole history on screen" onClick={act((chart) => chart.timeScale().fitContent())}>⤢</button>
    </div>
  );
}
