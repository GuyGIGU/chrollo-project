import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../api/base';
import { CHART_COLORS } from '../charts/chartTheme';
import { drawFixLayer, removeLayer } from './boxFixDraw';

// The fix he saved on this chart before (the latest for the ticker), fetched once per lens and drawn
// on the given live chart in the operator colour over the reader's read, never in its place; the
// backend's one sentence for it (`fixed.summary`, EC-28) is the lens's "✎ fixed" mark. `setFixed`
// takes the answer of a save so the mark and the drawing follow at once.
const latest = (fixes) => (Array.isArray(fixes) && fixes.length
  ? [...fixes].sort((a, b) => String(b.scan_day).localeCompare(String(a.scan_day)))[0] : null);

export const fixedLayer = (fix) => (fix
  ? { r: fix.resistance, rDay: fix.r_day, s: fix.support, sDay: fix.s_day, events: fix.events || [] } : null);

export default function useFixedBox(ticker, data, chartRef) {
  const [fixed, setFixed] = useState(null);
  const series = useRef([]);

  useEffect(() => {
    setFixed(null);
    if (!ticker) return undefined;
    let live = true;
    fetch(`${API_BASE}/calibration/box-fixes?ticker=${encodeURIComponent(ticker)}`)
      .then((response) => (response.ok ? response.json() : []))
      .then((body) => { if (live) setFixed(latest(body)); })
      .catch(() => {});
    return () => { live = false; };
  }, [ticker]);

  useEffect(() => {
    const chart = chartRef?.current;
    removeLayer(chart, series.current);
    series.current = chart && data?.candles?.length && fixed
      ? drawFixLayer(chart, data.candles, fixedLayer(fixed), CHART_COLORS.operator) : [];
  }, [fixed, chartRef, data]);

  return { fixed, setFixed };
}
