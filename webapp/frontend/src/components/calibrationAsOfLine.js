import { CHART_COLORS } from './chartTheme';

// A faint vertical divider at the as-of session — the boundary between what the
// operator OBSERVED (bars <= as-of) and the FORWARD window (> as-of, where the
// Trigger/buy lives). A buy placed left of this line is invalid (the entry
// cannot precede the snapshot it is evaluated from), so simply SEEING the
// boundary is what keeps the buy on the right side (operator ask 2026-07-21).
//
// A lightweight-charts series primitive, same shape as the hover band
// (calibrationHover): attached once in onReady, repainted as the time scale
// moves. Dashed + neutral so it reads as a reference boundary, never a rail.
export function attachAsOfDivider(chart, series) {
  let asOfTime = null;     // raw chart time of the as-of session (null = hidden)
  let requestUpdate = () => {};

  const renderer = {
    draw: (target) => {
      if (asOfTime == null) return;
      target.useMediaCoordinateSpace(({ context, mediaSize }) => {
        const x = chart.timeScale().timeToCoordinate(asOfTime);
        if (x == null) return;
        context.save();
        context.strokeStyle = CHART_COLORS.asOfLine;
        context.lineWidth = 1;
        context.setLineDash([3, 3]);
        context.beginPath();
        context.moveTo(x + 0.5, 0);
        context.lineTo(x + 0.5, mediaSize.height);
        context.stroke();
        context.restore();
      });
    },
  };
  // Over the bars (not behind, like the hover wash): a boundary the operator
  // must actually see while placing a buy. Dashed + low alpha keeps it faint.
  const paneView = { renderer: () => renderer, zOrder: () => 'top' };
  // Re-request a paint as the visible range moves so the line stays glued to the
  // as-of session through pan/zoom (the coordinate changes even when the data
  // does not).
  const onRangeChange = () => requestUpdate();
  const primitive = {
    paneViews: () => [paneView],
    attached: ({ requestUpdate: request }) => {
      requestUpdate = request;
      chart.timeScale().subscribeVisibleLogicalRangeChange(onRangeChange);
    },
    detached: () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(onRangeChange);
    },
  };
  series.attachPrimitive(primitive);

  return {
    setAsOf(time) {
      if (time !== asOfTime) {
        asOfTime = time;
        requestUpdate();
      }
    },
    detach() {
      series.detachPrimitive(primitive);
    },
  };
}
