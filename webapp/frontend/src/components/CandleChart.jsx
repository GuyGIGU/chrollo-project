import { useEffect, useRef, useState } from 'react';
import useLightweightChart from '../hooks/useLightweightChart';

// Thin presentational wrapper around useLightweightChart: owns the canvas
// container ref, the chart-error fallback, and the empty-data fallback that
// three of the five sites repeated by hand. Everything site-specific is still
// supplied through the spec (chartOptions, onReady, onResize, ...) and the
// surrounding shell (modal, section header, card frame) stays in the caller —
// CandleChart is composed INTO those shells, it does not own them.
//
// Props:
//   spec          : the useLightweightChart spec (see that hook). `onError` is
//                   wired internally to flip the error fallback; a caller
//                   onError still runs.
//   candles       : convenience — when absent/empty, render emptyFallback
//                   (also forwarded into the spec so the hook no-ops).
//   className     : class on the canvas container div
//   style         : style on the canvas container div
//   errorFallback : node shown if createChart/draw throws
//   emptyFallback : node shown when there are no candles
function CandleChart({
  spec,
  candles,
  className,
  style,
  errorFallback = null,
  emptyFallback = null,
}) {
  const containerRef = useRef(null);
  const [chartError, setChartError] = useState(false);
  const resolvedCandles = candles ?? spec.candles;

  // Reset the error flag whenever the inputs that drive a rebuild change, so a
  // recovered payload clears a prior failure.
  useEffect(() => {
    setChartError(false);
  }, spec.deps ?? [containerRef]); // eslint-disable-line react-hooks/exhaustive-deps

  useLightweightChart(containerRef, {
    ...spec,
    candles: resolvedCandles,
    onError: (err) => {
      setChartError(true);
      spec.onError?.(err);
    },
  });

  if (chartError && errorFallback) return errorFallback;
  if (!resolvedCandles?.length && emptyFallback) return emptyFallback;

  return <div ref={containerRef} className={className} style={style} />;
}

export default CandleChart;
