// The lookup group of the calibration command band: ticker + as-of + Load. Its
// own <form>, so Enter here submits the lookup — and only the lookup. The
// engine peek and the instance actions moved to their own spots in the band,
// and the loaded frame's provenance into the chart pane (operator ask
// 2026-10-02: the band "got to much dead space"). Dumb strip — all state in
// the parent.
function CalibrationLookupForm({
  ticker, onTicker,
  asOf, onAsOf, dateInputRef,
  loading, onSubmit,
}) {
  return (
    <form className="ccb-group" onSubmit={onSubmit}>
      <input
        value={ticker}
        onChange={(e) => onTicker(e.target.value.toUpperCase())}
        placeholder="Ticker"
        aria-label="Ticker"
        style={{ width: 96, fontFamily: 'inherit' }}
      />
      <input
        type="date"
        value={asOf}
        onChange={(e) => onAsOf(e.target.value)}
        aria-label="As-of date"
        ref={dateInputRef}
      />
      {/* A fixed width, so "Loading…" never nudges the tools beside it. */}
      <button type="submit" disabled={loading || !ticker.trim() || !asOf}
              style={{ minWidth: 76 }}>
        {loading ? 'Loading…' : 'Load'}
      </button>
    </form>
  );
}

export default CalibrationLookupForm;
