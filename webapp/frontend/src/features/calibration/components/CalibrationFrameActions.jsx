// The instance actions at the far END of the command band's second line: "+
// Add instance" (always there, inert until a chart is up) and, once a buy is
// placed, the eve-of-buy snapshot lock. The group is pushed to the right edge
// and the conditional button sits LEFT of the fixed one, so its arrival grows
// the group leftward into empty space — it never moves Save, "+ Add instance"
// or any tool (operator ruling: the buttons never move mid-mark). Dumb strip —
// state in the parent.
function CalibrationFrameActions({ chartData, loading, eveOfBuyAsOf, onLockSnapshot, onAddInstance }) {
  return (
    <div className="ccb-group ccb-frame-actions">
      {/* Lock the snapshot to the session before the buy (request 6): the
          grade then asks "would last night's scan have surfaced it?". Only
          shown once a buy is placed and the as-of isn't already there. The
          date rides in the title, keeping the button short. */}
      {chartData && eveOfBuyAsOf && eveOfBuyAsOf !== chartData.as_of_session && (
        <button type="button" onClick={onLockSnapshot} disabled={loading}
                title={`Set the engine snapshot to ${eveOfBuyAsOf} — the session before your buy (Chrollo scans after the close). Your marks come with it.`}
                style={{ borderColor: 'var(--trigger)' }}>
          Snapshot → buy eve
        </button>
      )}
      {/* Start another setup on this ticker at a new date (request 7) —
          clears the draft + date, keeps the ticker, leaves saved setups be. */}
      <button type="button" onClick={onAddInstance} disabled={!chartData || loading}
              title="Add another instance of a setup on this ticker at a new date — your saved setups are untouched.">
        + Add instance
      </button>
    </div>
  );
}

export default CalibrationFrameActions;
