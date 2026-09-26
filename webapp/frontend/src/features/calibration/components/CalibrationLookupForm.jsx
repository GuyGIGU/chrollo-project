import { CHART_FONT } from '../../../shared/charts/chartTheme';
import { fx } from '../../../shared/formatting/format';

// The lookup group of the calibration command band: ticker + as-of + Load, and
// once a chart is up the engine peek, the eve-of-buy snapshot lock, "+ Add
// instance" and the loaded frame's provenance. Its own <form>, so Enter here
// submits the lookup — and only the lookup. Dumb strip — all state in the parent.
function CalibrationLookupForm({
  ticker, onTicker,
  asOf, onAsOf, dateInputRef,
  loading, chartData,
  engineOn, onToggleEngine,
  eveOfBuyAsOf, onLockSnapshot,
  onAddInstance, onSubmit,
}) {
  return (
    <form className="ccb-group" onSubmit={onSubmit}
          style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.08em',
                     textTransform: 'uppercase', color: 'var(--text-faint)' }}>
        Calibration
      </span>
      <input
        value={ticker}
        onChange={(e) => onTicker(e.target.value.toUpperCase())}
        placeholder="Ticker"
        aria-label="Ticker"
        style={{ width: 110, fontFamily: 'inherit' }}
      />
      <input
        type="date"
        value={asOf}
        onChange={(e) => onAsOf(e.target.value)}
        aria-label="As-of date"
        ref={dateInputRef}
      />
      <button type="submit" disabled={loading || !ticker.trim() || !asOf}>
        {loading ? 'Loading…' : 'Load'}
      </button>
      {chartData && (
        <>
          <button type="button" aria-pressed={engineOn}
                  onClick={onToggleEngine}
                  title="Overlay the engine's read of this frame (the agreement harness's own lens) [e]. Mark FIRST, peek after — anchoring on the engine corrupts the ground truth.">
            Engine
          </button>
          {/* Lock the snapshot to the session before the buy (request 6): the
              grade then asks "would last night's scan have surfaced it?". Only
              shown once a buy is placed and the as-of isn't already there. */}
          {eveOfBuyAsOf && eveOfBuyAsOf !== chartData.as_of_session && (
            <button type="button" onClick={onLockSnapshot} disabled={loading}
                    title={`Set the engine snapshot to ${eveOfBuyAsOf} — the session before your buy (Chrollo scans after the close). Your marks come with it.`}
                    style={{ borderColor: 'var(--trigger)' }}>
              Snapshot → buy eve ({eveOfBuyAsOf})
            </button>
          )}
          {/* Start another setup on this ticker at a new date (request 7) —
              clears the draft + date, keeps the ticker, leaves saved setups be. */}
          <button type="button" onClick={onAddInstance} disabled={loading}
                  title="Add another instance of a setup on this ticker at a new date — your saved setups are untouched.">
            + Add instance
          </button>
          {/* Provenance figures change on every load — mono + tabular so
              the eye can hold position across adjacent sessions. */}
          <span style={{ color: 'var(--text-muted)', fontFamily: CHART_FONT,
                         fontVariantNumeric: 'tabular-nums', fontSize: 11,
                         whiteSpace: 'nowrap' }}>
            {chartData.ticker} @ {chartData.as_of_session} · close {fx(chartData.anchor_close, 2)}
            {' '}· {chartData.bar_count} bars · {chartData.data_regime}
          </span>
        </>
      )}
    </form>
  );
}

export default CalibrationLookupForm;
