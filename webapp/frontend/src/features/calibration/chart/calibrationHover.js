import { CHART_COLORS } from '../../../shared/charts/chartTheme';
import { chartTimeToIso } from '../model/calibrationMarking';

// Hovered-bar highlight for the calibration marking layer (operator ask,
// 2026-07-11): while a placement tool is armed, the bar under the cursor
// wears a translucent mythril band so the operator sees exactly which bar a
// click will bind to — clicks snap to the hovered bar's wick, and without
// the band the binding target is a guess. Idle = no band (reading mode).
//
// A lightweight-charts series primitive: retained, attached once in onReady,
// repainted via requestUpdate on crosshair moves — never a chart rebuild.
export function attachHoverHighlight(chart, series) {
  let hoverTime = null; // raw chart time of the hovered bar (for coordinates)
  let hoverKey = null;  // ISO form (for cheap change detection)
  let armed = false;
  let requestUpdate = () => {};

  const renderer = {
    draw: (target) => {
      if (!armed || hoverTime == null) return;
      target.useMediaCoordinateSpace(({ context, mediaSize }) => {
        const x = chart.timeScale().timeToCoordinate(hoverTime);
        if (x == null) return;
        const width = Math.max(chart.timeScale().options().barSpacing ?? 6, 3);
        context.fillStyle = CHART_COLORS.markingWash;
        context.fillRect(x - width / 2, 0, width, mediaSize.height);
      });
    },
  };
  const paneView = { renderer: () => renderer, zOrder: () => 'bottom' };
  const primitive = {
    paneViews: () => [paneView],
    attached: ({ requestUpdate: request }) => { requestUpdate = request; },
    detached: () => {},
  };
  series.attachPrimitive(primitive);

  const onMove = (param) => {
    const key = param?.time != null ? chartTimeToIso(param.time) : null;
    if (key !== hoverKey) {
      hoverKey = key;
      hoverTime = param?.time ?? null;
      requestUpdate();
    }
  };
  chart.subscribeCrosshairMove(onMove);

  return {
    setArmed(value) {
      if (armed !== value) {
        armed = value;
        requestUpdate();
      }
    },
    detach() {
      chart.unsubscribeCrosshairMove(onMove);
      series.detachPrimitive(primitive);
    },
  };
}
