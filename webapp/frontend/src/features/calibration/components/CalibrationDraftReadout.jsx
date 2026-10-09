import { effectiveSpan, statusText } from '../model/calibrationMarking';
import { CHART_FONT } from '../../../shared/charts/chartTheme';
import { fx } from '../../../shared/formatting/format';

// The live draft readout of the calibration command band: the rails / span,
// the events and the buy as drawn so far, then — at the END, in its own
// ellipsizing cell — what the next click will do. The band's whole third line
// (2026-10-02), one fixed-height line: the tokens sit left-aligned in their own
// lane (sideways scroll only if a draft ever outgrows a full line), so the
// status changing width as tools arm never slides a token or its ×, and
// nothing here can push a button or grow the band mid-mark.
// Dumb strip — all state in the parent's markingReducer.

const KEY_LEGEND = 'r/s rail · x span · c/l/t/o/m/u event · b buy · ⏎ save · e engine';

const TOKEN = { color: 'var(--text-muted)', fontFamily: CHART_FONT, fontSize: 11,
                whiteSpace: 'nowrap' };

function CalibrationDraftReadout({ state, dispatch, disabled, asOfSession }) {
  const { draft } = state;
  const span = effectiveSpan(draft, asOfSession);
  return (
    <div className="ccb-readout" aria-label="Draft marks">
      <div className="ccb-readout-tokens">
      {/* Rails with their anchor bars; the span line shows what WILL save
          (anchor-derived unless x-drawn explicitly). */}
      <span style={{ ...TOKEN, fontVariantNumeric: 'tabular-nums' }}>
        R {fx(draft.resistance, 2)}{draft.rAnchorDate ? `@${draft.rAnchorDate}` : ''}
        {' '}· S {fx(draft.support, 2)}{draft.sAnchorDate ? `@${draft.sAnchorDate}` : ''}
        {' '}· {span.start ?? '—'} → {span.end ?? '—'}
        {span.start && draft.boxStartDate == null ? ' (from anchors)' : ''}
      </span>
      {draft.events.map((ev, i) => (
        <span key={`${ev.event_type}-${ev.start_date}-${i}`} style={TOKEN}>
          {ev.event_type} {ev.start_date}→{ev.end_date}
          {ev.band_high != null
            ? ` [${fx(ev.band_low, 2)}–${fx(ev.band_high, 2)}]` : ''}
          <button type="button" aria-label={`remove ${ev.event_type}`}
                  onClick={() => dispatch({ type: 'remove-event', index: i })}>
            ×
          </button>
        </span>
      ))}
      {draft.triggerDate && (
        // The buy, in its warm token: level @ date, with a one-click clear.
        <span style={{ ...TOKEN, color: 'var(--trigger)' }}>
          Buy {fx(draft.triggerPrice, 2)}@{draft.triggerDate}
          <button type="button" aria-label="remove trigger"
                  onClick={() => dispatch({ type: 'set-trigger', date: null })}>
            ×
          </button>
        </span>
      )}
      </div>
      {/* What the next click does, in a cell of its own at the end. Idle shows
          the key legend: the shortcuts ARE the fast path and were invisible
          before (operator never found them). */}
      <span className="ccb-readout-status"
            title={disabled ? undefined : (statusText(state) || KEY_LEGEND)}>
        {disabled ? 'load a chart to mark' : (statusText(state) || KEY_LEGEND)}
      </span>
    </div>
  );
}

export default CalibrationDraftReadout;
