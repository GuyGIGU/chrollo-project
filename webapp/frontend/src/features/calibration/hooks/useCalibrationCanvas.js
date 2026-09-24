import { useEffect, useMemo, useRef } from 'react';
import { CrosshairMode } from 'lightweight-charts';
import { baseChartOptions } from '../../../shared/charts/chartTheme';
import { attachCalibrationDraw } from '../chart/calibrationDraw';
import { attachHoverHighlight } from '../chart/calibrationHover';
import { attachAsOfDivider } from '../chart/calibrationAsOfLine';
import { chartTimeToIso, effectiveSpan, placementRefusal } from '../model/calibrationMarking';

// Owns chart attachment, click placement, retained overlays and teardown.
// The page owns lookup/draft/save state; a draft edit never rebuilds this chart.
export default function useCalibrationCanvas({
  chartData, marking, savedForFrame, engineOn, engineRead,
  dispatchMarking, setPlaceNotice,
}) {
  const chartApiRef = useRef(null);
  const markingRef = useRef(marking);
  markingRef.current = marking;
  // Bars by date, for snap-to-extreme rail placement.
  const barsByDate = useMemo(() => {
    const map = new Map();
    for (const c of chartData?.candles ?? []) map.set(c.time, c);
    return map;
  }, [chartData]);
  const barsRef = useRef(barsByDate);
  barsRef.current = barsByDate;

  // Retained redraw, deliberately dependency-free: it runs after every
  // commit (including the child chart effect's rebuilds), the draw is
  // idempotent and cheap, and no state combination can leave the chart
  // stale. Mythril while drawing; the reserved operator hue once the draft
  // IS a saved mark being corrected (Task 13 color doctrine).
  useEffect(() => {
    const api = chartApiRef.current;
    if (!api) return;
    api.draw.update({
      draft: marking.draft,
      // The span the draft's rails bind to (bounded, not edge-to-edge) — the
      // same geometry the mark will save. Null until both rails exist.
      draftSpan: effectiveSpan(marking.draft, chartData?.as_of_session),
      spanAnchor: marking.spanAnchor,
      committed: marking.editingId != null,
      saved: savedForFrame,
      engine: engineOn ? engineRead : null,
      candles: chartData?.candles ?? [],
    });
    api.hover.setArmed(marking.tool !== 'idle');
  });

  const spec = useMemo(() => ({
    chartOptions: (container) => {
      const base = baseChartOptions('modal', container.clientWidth, container.clientHeight);
      return {
        ...base,
        // ResizeObserver-backed sizing (matches the mini/pulse charts): the pane
        // tracks its container through flex settling, rail-width changes and
        // window resizes on its own — no stale first-paint height, no jank when
        // zooming, no manual resize handler.
        autoSize: true,
        handleScroll: true,
        handleScale: true,
        // Reserve the bottom band for the volume histogram and autoscale the
        // price to the visible bars. Without a bottom margin the candles fill
        // the whole pane and the volume is hidden underneath (operator: "the
        // chart is cropped, leaving out the volume").
        rightPriceScale: { ...base.rightPriceScale,
                           scaleMargins: { top: 0.08, bottom: 0.22 }, autoScale: true },
        // Normal, not the library-default Magnet: Magnet snaps the crosshair
        // to each bar's CLOSE, so the line the operator sees jumps away from
        // the mouse while clicks land at the true pointer position — the
        // "cursor follows at some margin" placement bug (operator, 2026-07-11).
        crosshair: { mode: CrosshairMode.Normal },
      };
    },
    candles: chartData?.candles,
    volumes: chartData?.volumes,
    showVolume: true,
    volumeScaleTop: 0.82,
    onReady: (chart, series) => {
      // The marking controller: click placement + retained draft drawing.
      // The handler reads the CURRENT marking state through a ref (onReady
      // runs once per chart build; the tool changes many times per build).
      const draw = attachCalibrationDraw(chart, series);
      const hover = attachHoverHighlight(chart, series);
      const asOfLine = attachAsOfDivider(chart, series);
      asOfLine.setAsOf(chartData?.as_of_session ?? null);
      chartApiRef.current = { series, draw, hover, asOfLine };
      const onClick = (param) => {
        const st = markingRef.current;
        if (st.tool === 'idle') return;
        if (!param?.point || param.time == null) return;
        const price = series.coordinateToPrice(param.point.y);
        const date = chartTimeToIso(param.time);
        if (price == null || !Number.isFinite(price) || !date) return;
        // Placement guard — refuse a click that can't be a valid mark with a
        // plain reason AT CLICK TIME, never let it fail later at Save with a
        // cryptic "after as_of_date" (operator, 2026-07-21). The rule lives in
        // one pure, tested helper that mirrors marks_validity (EC-3), so the
        // client pre-check can't drift from the backend gate.
        const asOf = chartData?.as_of_session;
        const lpsEnd = (st.draft.events || [])
          .filter((e) => e.event_type === 'lps' && e.end_date)
          .map((e) => e.end_date)
          .reduce((a, b) => (a >= b ? a : b), null);
        const refusal = placementRefusal(st.tool, date, asOf, lpsEnd);
        if (refusal) { setPlaceNotice(refusal); return; }
        setPlaceNotice(null);
        dispatchMarking({ type: 'chart-click', date,
                          price: Number(price.toFixed(4)),
                          bar: barsRef.current.get(date) });
      };
      chart.subscribeClick(onClick);
      // Open the view at the as-of divider: the chart reads as the stock "up
      // until that point" — how the setup looked in real time — while still
      // revealing a dozen forward bars past the line so the near breakout and
      // the auto-snapped buy stay on-screen (the placement guard keeps geometry
      // LEFT of the divider, so a little forward context can't invite a
      // misplaced mark) (operator ask 2026-07-21). Ending here (rather than
      // fitContent over the whole [-900d,+45d] window) also lets the price
      // autoscale to the observed bars, so the base is not squashed by the
      // forward breakout. A rebuild only happens on a NEW frame (deps:
      // [chartData]), so this never fights a manual zoom mid-mark.
      const observedLast = chartData?.bar_count ? chartData.bar_count - 1 : null;
      if (observedLast != null) {
        chart.timeScale().setVisibleLogicalRange({ from: 0, to: observedLast + 12 });
      } else {
        chart.timeScale().fitContent();
      }
      return () => {
        chart.unsubscribeClick(onClick);
        hover.detach();
        draw.detach();
        asOfLine.detach();
        chartApiRef.current = null;
      };
    },
    deps: [chartData],
  }), [chartData, dispatchMarking, setPlaceNotice]);

  return spec;
}
