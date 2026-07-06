import { LineSeries } from 'lightweight-charts';
import { boxRailSpecs, buildLevelData } from './chartGeometry';
import { RAIL_STYLE } from './chartTheme';

// The ONE structure drawer for the setup box: R/S rails, dashed midline, and
// the inner box, drawn identically on the screener mini card and the modal.
// Geometry comes from boxRailSpecs (pure, unit-tested); styling from the
// chartTheme palette. This module is chart-coupled (imports lightweight-charts)
// and is kept out of chartGeometry so that stays Node-testable.
export const addBoxRails = (chart, data) => {
  const candles = data.candles || [];
  for (const spec of boxRailSpecs(data)) {
    // spec.endIndex is set only for the inner box (bounded to the coil); the
    // parent R/S/mid leave it undefined and buildLevelData runs them to the edge.
    chart
      .addSeries(LineSeries, RAIL_STYLE[spec.kind])
      .setData(buildLevelData(candles, spec.startIndex, spec.value, spec.endIndex));
  }
};
