import { useRef, useState } from 'react';
import useLightweightChart from '../hooks/useLightweightChart';

// Thin presentational wrapper around useLightweightChart: owns the canvas
// container ref, the chart-error fallback, and the empty-data fallback that
// three of the five sites repeated by hand. Everything site-specific is still
// supplied through the spec (chartOptions, onReady, onResize, ...) and the
// surrounding shell (modal, section header, card frame) stays in the caller —
// CandleChart is composed INTO those shells, it does not own them.
//
// Props:
//   spec          : the useLightweightChart spec (see that hook). spec.candles
//                   is ALWAYS what gets drawn (e.g. the colored bar array);
//                   onError is wired internally to flip the error fallback while
//                   still running any caller onError.
//   candles       : the empty/error GATE only — the raw (uncolored) payload used
//                   to decide whether to render emptyFallback. It is NOT drawn;
//                   spec.candles is. Defaults to spec.candles when omitted.
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
  // The gate uses the raw `candles` prop (presence of data); drawing always
  // uses spec.candles so a colored bar array is never silently discarded.
  const gateCandles = candles ?? spec.candles;

  useLightweightChart(containerRef, {
    ...spec,
    // Clear a prior error in lockstep with the rebuild (driven by the hook's
    // own deps array — no second effect mirroring spec.deps), so a recovered
    // payload always clears the fallback regardless of what deps the caller set.
    onRebuildStart: () => {
      setChartError(false);
      spec.onRebuildStart?.();
    },
    onError: (err) => {
      setChartError(true);
      spec.onError?.(err);
    },
  });

  if (chartError && errorFallback) return errorFallback;
  if (!gateCandles?.length && emptyFallback) return emptyFallback;

  return <div ref={containerRef} className={className} style={style} />;
}

export default CandleChart;
