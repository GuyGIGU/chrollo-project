import { MARK_EVENT_TYPES } from '../model/calibrationMarking';

// The marking tools of the calibration page (Task 11): the placement buttons,
// in their ruled order. All state lives in the parent's markingReducer — this
// is a dumb strip. Every setup is a box (the operator only pulls up real
// structure), so there is no verdict selector.

// Individual R and S tools (operator ask 2026-07-11): each click records the
// rail price AND the swing bar it was placed on (the anchor), and the box
// span derives from the anchors — Span stays as the explicit override.
const TOOL_LABELS = [
  ['rail-r', 'R'],
  ['rail-s', 'S'],
  ['span', 'Span'],
];

const EVENT_LABELS = { phase_c: '+Phase C', lps: '+LPS', spring_test: '+Spring test',
                       sos: '+SOS', mini_consolidation: '+Mini consol.',
                       last_supper: '+Last Supper' };

function CalibrationMarkingBar({ state, dispatch, disabled, onReMark }) {
  const { tool, draft } = state;
  const hasLps = draft.events.some((e) => e.event_type === 'lps');

  const toolButton = (value, label) => (
    <button
      key={value}
      type="button"
      disabled={disabled}
      aria-pressed={tool === value}
      onClick={() => dispatch({ type: 'tool', tool: value })}
    >
      {label}
    </button>
  );

  return (
    // The tools hold ZERO variable-width content (operator: "keep the button
    // order the same — it changes mid-mark"), so arming/enabling a tool can
    // never move one. Every transient readout (rails, events, buy, status,
    // legend) lives in the band's SECOND row (CalibrationDraftReadout), so its
    // width changes stay contained there and never reflow these buttons.
    <div className="ccb-group" role="group" aria-label="Marking tools">
      {TOOL_LABELS.map(([value, label]) => toolButton(value, label))}
      {MARK_EVENT_TYPES.map((t) => toolButton(`event:${t}`, EVENT_LABELS[t]))}

      {/* The Trigger (buy): assisted — arming it snaps to the LPS-high breakout.
          Inert until an LPS exists (it is anchored to the LPS end-bar). */}
      <button
        type="button"
        disabled={disabled || !hasLps}
        aria-pressed={tool === 'trigger'}
        title={hasLps
          ? 'Trigger (buy): snap to the breakout above the LPS high, then click a bar to adjust [b]'
          : 'Mark an LPS first — the Trigger is the breakout above the last LPS bar’s high'}
        onClick={() => dispatch({ type: 'tool', tool: 'trigger' })}
      >
        Trigger
      </button>

      <button type="button" disabled={disabled}
              title="Delete this setup's saved marks and start over"
              onClick={onReMark}>
        Re Mark
      </button>
    </div>
  );
}

export default CalibrationMarkingBar;
