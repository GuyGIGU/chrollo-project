import {
  MARK_EVENT_TYPES,
  MARK_VERDICTS,
  effectiveSpan,
  statusText,
} from '../utils/calibrationMarking';
import { CHART_FONT } from './chartTheme';

// The marking drawer for the calibration page (Task 11): verdict, placement
// tools, the live draft readout, and the one status line that says what the
// next click will do. Renders in a FIXED-height slot under the command band
// so arming a tool never shifts the chart pane. All state lives in the
// parent's markingReducer — this is a dumb strip.
const fx = (v, d) => ((v == null || !Number.isFinite(Number(v))) ? '—' : Number(v).toFixed(d));

// Individual R and S tools (operator ask 2026-07-11): each click records the
// rail price AND the swing bar it was placed on (the anchor), and the box
// span derives from the anchors — Span stays as the explicit override.
const TOOL_LABELS = [
  ['rail-r', 'R'],
  ['rail-s', 'S'],
  ['span', 'Span'],
];

const EVENT_LABELS = { phase_c: '+Phase C', lps: '+LPS', spring_test: '+Spring test' };

const KEY_LEGEND = 'r/s rail · x span · c/l/t event · b buy · ⏎ save · n/w negative · ,/. day · e engine';

function CalibrationMarkingBar({ state, dispatch, disabled, asOfSession }) {
  const { tool, draft } = state;
  const isBox = draft.verdict === 'box';
  const hasLps = draft.events.some((e) => e.event_type === 'lps');
  const span = effectiveSpan(draft, asOfSession);

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
    // A cohesive, WRAPPING group in the one command band (Task 8) — no longer a
    // clipping nowrap strip, so the full R/S/Span/event vocabulary always stays
    // visible instead of being cut off at the right edge.
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap',
                  minHeight: 30, fontSize: 12 }}>
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

      {/* The Trigger (buy): assisted — arming it snaps to the LPS-high breakout.
          Inert until an LPS exists (it is anchored to the LPS end-bar). */}
      <button
        type="button"
        disabled={disabled || !isBox || !hasLps}
        aria-pressed={tool === 'trigger'}
        title={hasLps
          ? 'Trigger (buy): snap to the breakout above the LPS high, then click a bar to adjust [b]'
          : 'Mark an LPS first — the Trigger is the breakout above the last LPS bar’s high'}
        onClick={() => dispatch({ type: 'tool', tool: 'trigger' })}
      >
        Trigger
      </button>

      <button type="button" disabled={disabled}
              onClick={() => dispatch({ type: 'clear' })}>
        Clear
      </button>

      {isBox && (
        // Rails with their anchor bars; the span line shows what WILL save
        // (anchor-derived unless x-drawn explicitly).
        <span style={{ color: 'var(--text-muted)', fontFamily: CHART_FONT,
                       fontVariantNumeric: 'tabular-nums', fontSize: 11,
                       whiteSpace: 'nowrap' }}>
          R {fx(draft.resistance, 2)}{draft.rAnchorDate ? `@${draft.rAnchorDate}` : ''}
          {' '}· S {fx(draft.support, 2)}{draft.sAnchorDate ? `@${draft.sAnchorDate}` : ''}
          {' '}· {span.start ?? '—'} → {span.end ?? '—'}
          {span.start && draft.boxStartDate == null ? ' (from anchors)' : ''}
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
      {isBox && draft.triggerDate && (
        // The buy, in its warm token: level @ date, with a one-click clear.
        <span style={{ color: 'var(--trigger)', fontFamily: CHART_FONT,
                       fontSize: 11, whiteSpace: 'nowrap' }}>
          Buy {fx(draft.triggerPrice, 2)}@{draft.triggerDate}
          <button type="button" aria-label="remove trigger"
                  onClick={() => dispatch({ type: 'set-trigger', date: null })}
                  style={{ marginLeft: 2 }}>
            ×
          </button>
        </span>
      )}

      <span style={{ marginLeft: 'auto', color: 'var(--text-faint)', whiteSpace: 'nowrap' }}>
        {/* Idle shows the key legend — the shortcuts ARE the fast path and
            were invisible before (operator never found them). */}
        {disabled ? 'load a chart to mark' : (statusText(state) || KEY_LEGEND)}
      </span>
    </div>
  );
}

export default CalibrationMarkingBar;
