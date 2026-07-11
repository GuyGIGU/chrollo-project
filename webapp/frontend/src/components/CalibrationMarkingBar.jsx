import {
  MARK_EVENT_TYPES,
  MARK_VERDICTS,
  statusText,
} from '../utils/calibrationMarking';
import { CHART_FONT } from './chartTheme';

// The marking drawer for the calibration page (Task 11): verdict, placement
// tools, the live draft readout, and the one status line that says what the
// next click will do. Renders in a FIXED-height slot under the command band
// so arming a tool never shifts the chart pane. All state lives in the
// parent's markingReducer — this is a dumb strip.
const fx = (v, d) => ((v == null || !Number.isFinite(Number(v))) ? '—' : Number(v).toFixed(d));

// ONE box tool (place R → S → span, then click-near-a-rail adjusts it) —
// the separate R/S/Span buttons duplicated the same grammar and read as
// different features (operator feedback 2026-07-11). Keys r/s/x still arm
// the surgical single-placement tools; the legend below teaches them.
const TOOL_LABELS = [
  ['box', 'Mark box'],
];

const EVENT_LABELS = { phase_c: '+Phase C', lps: '+LPS', spring_test: '+Spring test' };

const KEY_LEGEND = 'b box · r/s rail · x span · c/l/t event · ⏎ save · n/w negative · ,/. day · e engine';

function CalibrationMarkingBar({ state, dispatch, disabled }) {
  const { tool, draft } = state;
  const isBox = draft.verdict === 'box';

  const toolButton = (value, label) => (
    <button
      key={value}
      type="button"
      disabled={disabled || !isBox}
      aria-pressed={tool === value}
      onClick={() => dispatch({ type: 'tool', tool: value })}
    >
      {label}
    </button>
  );

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'nowrap',
                  minHeight: 30, fontSize: 12, overflow: 'hidden' }}>
      <select
        value={draft.verdict}
        disabled={disabled}
        aria-label="Mark verdict"
        onChange={(e) => dispatch({ type: 'verdict', verdict: e.target.value })}
      >
        {MARK_VERDICTS.map((v) => <option key={v} value={v}>{v}</option>)}
      </select>

      {TOOL_LABELS.map(([value, label]) => toolButton(value, label))}
      {MARK_EVENT_TYPES.map((t) => toolButton(`event:${t}`, EVENT_LABELS[t]))}

      <button type="button" disabled={disabled}
              onClick={() => dispatch({ type: 'clear' })}>
        Clear
      </button>

      {isBox && (
        <span style={{ color: 'var(--text-muted)', fontFamily: CHART_FONT,
                       fontVariantNumeric: 'tabular-nums', fontSize: 11,
                       whiteSpace: 'nowrap' }}>
          R {fx(draft.resistance, 2)} · S {fx(draft.support, 2)}
          {' '}· {draft.boxStartDate ?? '—'} → {draft.boxEndDate ?? '—'}
        </span>
      )}
      {draft.events.map((ev, i) => (
        <span key={`${ev.event_type}-${ev.start_date}-${i}`}
              style={{ color: 'var(--text-muted)', fontFamily: CHART_FONT,
                       fontSize: 11, whiteSpace: 'nowrap' }}>
          {ev.event_type} {ev.start_date}→{ev.end_date}
          <button type="button" aria-label={`remove ${ev.event_type}`}
                  onClick={() => dispatch({ type: 'remove-event', index: i })}
                  style={{ marginLeft: 2 }}>
            ×
          </button>
        </span>
      ))}

      <span style={{ marginLeft: 'auto', color: 'var(--text-faint)', whiteSpace: 'nowrap' }}>
        {/* Idle shows the key legend — the shortcuts ARE the fast path and
            were invisible before (operator never found them). */}
        {disabled ? 'load a chart to mark' : (statusText(state) || KEY_LEGEND)}
      </span>
    </div>
  );
}

export default CalibrationMarkingBar;
