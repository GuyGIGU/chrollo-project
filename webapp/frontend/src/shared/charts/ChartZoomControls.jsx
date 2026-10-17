import { useEffect } from 'react';
import { ZOOM_IN, ZOOM_OUT, wheelFactor, zoomedRange } from './chartZoom';

// The four acts a lens chart answers to (Fri 17/10/2026, his TradingView words): zoom in, zoom
// out, back to the opening view, and fit the whole history on screen. Drawn as a small cluster
// over the pane's bottom-left corner, faint at rest; Ctrl+wheel (Cmd on a Mac) over the pane zooms
// the same way, while a bare wheel still scrolls the lens page. `chartRef` holds the live
// lightweight-charts instance (null between builds), `frameRef` the pane element that takes the
// wheel, `onHome` re-frames the chart the way it opened.

const zoomBy = (chart, factor) => {
  const scale = chart.timeScale();
  const next = zoomedRange(scale.getVisibleLogicalRange(), factor);
  if (next) scale.setVisibleLogicalRange(next);
};

export default function ChartZoomControls({ chartRef, frameRef, onHome }) {
  useEffect(() => {
    const frame = frameRef?.current;
    if (!frame) return undefined;
    const onWheel = (event) => {
      if (!(event.ctrlKey || event.metaKey) || !chartRef.current) return;
      event.preventDefault();
      zoomBy(chartRef.current, wheelFactor(event.deltaY));
    };
    frame.addEventListener('wheel', onWheel, { passive: false });
    return () => frame.removeEventListener('wheel', onWheel);
  }, [chartRef, frameRef]);

  const act = (fn) => () => { if (chartRef.current) fn(chartRef.current); };
  return (
    <div className="chart-zoom" role="group" aria-label="Chart zoom">
      <button type="button" className="chart-zoom-btn" aria-label="Zoom in" title="Zoom in (Ctrl + wheel up)" onClick={act((chart) => zoomBy(chart, ZOOM_IN))}>+</button>
      <button type="button" className="chart-zoom-btn" aria-label="Zoom out" title="Zoom out (Ctrl + wheel down)" onClick={act((chart) => zoomBy(chart, ZOOM_OUT))}>−</button>
      <button type="button" className="chart-zoom-btn" aria-label="Reset the view" title="Back to the view it opened on" onClick={act(() => onHome?.())}>⌂</button>
      <button type="button" className="chart-zoom-btn" aria-label="Fit all" title="Fit the whole history on screen" onClick={act((chart) => chart.timeScale().fitContent())}>⤢</button>
    </div>
  );
}
