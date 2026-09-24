import { useRef } from 'react';
import useDailyStructureChart from '../../../shared/charts/useDailyStructureChart';
import { CANDLE_REASON_COPY } from '../presentation/watchlistChartData';
import TimeframeMainChart from '../../../shared/charts/TimeframeMainChart';

// The three-pane cluster mirroring the operator's TradingView layout: Monthly
// top-left and Weekly bottom-left in a narrow stacked column, the big Daily
// pane owning the rest. Consumes the ATOMIC pane bundle from resolvePaneData
// — one artifact rendered wholesale per pane, never a field-level merge — so
// the structure coloring's index arithmetic always runs against the exact
// candle array it shipped with. The bundle is memoized by the page: a
// selection swap rebuilds these three panes (the modal's existing contract);
// unrelated re-renders (price polls, hovers) change nothing here.

// Sibling-pane component so the rich hook is never called conditionally: the
// cluster renders DailyPane only when there is a payload to draw.
function DailyPane({ ticker, data }) {
  const containerRef = useRef(null);
  useDailyStructureChart(containerRef, ticker, data);
  return (
    <div className="wl-daily-pane instrument-well">
      <span className="wl-pane-mark">D</span>
      <div className="wl-daily-canvas" ref={containerRef} />
    </div>
  );
}

function HtfPane({ label, frame }) {
  return (
    <div className="wl-htf-pane instrument-well">
      <span className="wl-pane-mark">{label === 'MONTHLY' ? 'M' : 'W'}</span>
      <TimeframeMainChart
        box={frame.box}
        candles={frame.candles}
        label={label}
        volumes={frame.volumes}
      />
    </div>
  );
}

function WatchlistChartCluster({ pane, ticker }) {
  if (!pane.daily) {
    // Zone-isolated: only the chart cluster says so — with the ticker's name
    // and the ACTUAL reason — while the rail, strip, and toggle stay alive.
    // The frame stays in place; loading is never a page takeover.
    return (
      <div className="wl-cluster-void">
        {ticker} — {CANDLE_REASON_COPY[pane.reason] || CANDLE_REASON_COPY.error}
      </div>
    );
  }
  return (
    <div className="wl-chart-cluster">
      <div className="wl-htf-col">
        <HtfPane frame={pane.monthly} label="MONTHLY" />
        <HtfPane frame={pane.weekly} label="WEEKLY" />
      </div>
      <DailyPane data={pane.daily} ticker={ticker} />
    </div>
  );
}

export default WatchlistChartCluster;
