import { CHART_FONT } from './chartTheme';

// Every ticker the operator has calibrated so far (operator ask 2026-07-11):
// one dense strip, one chip per ticker with its mark count, click to reload
// that ticker at its latest-marked session. Dumb strip — data from the
// marks hook's summary.
function CalibrationTickerStrip({ summary, activeTicker, onPick }) {
  if (!summary.length) return null;
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap',
                  fontSize: 11, fontFamily: CHART_FONT }}>
      <span style={{ color: 'var(--text-faint)' }}>
        calibrated ({summary.length}):
      </span>
      {summary.map((row) => (
        <button
          key={row.ticker}
          type="button"
          aria-pressed={row.ticker === activeTicker}
          title={`${row.count} mark(s) — load ${row.ticker} @ ${row.latestAsOf}`}
          onClick={() => onPick(row.ticker, row.latestAsOf)}
        >
          {row.ticker}·{row.count}
        </button>
      ))}
    </div>
  );
}

export default CalibrationTickerStrip;
