// Pure marking-state machine for the calibration page (Calibration at Scale,
// Task 11) — node --test'able: no chart, no React, no fetch. ONE state value
// drives the whole marking layer:
//
//   { frameKey, tool, spanAnchor, draft }
//
// The chart click handler dispatches into markingReducer; the draw layer
// renders whatever the draft says; the bar renders the tool + status. Drafts
// are structurally keyed to the frame they were drawn on (frameKey =
// ticker|session|digest) so a draft can never bleed across frames — the same
// corpus-integrity rule the backend enforces with frame_digest.

export const MARK_EVENT_TYPES = ['phase_c', 'lps', 'spring_test'];
export const MARK_VERDICTS = ['box', 'no_structure', 'engine_wrong'];

export function emptyDraft() {
  return {
    verdict: 'box',
    resistance: null,
    support: null,
    boxStartDate: null,
    boxEndDate: null,
    events: [],
  };
}

export function initialMarkingState(draft = null, frameKey = null, editingId = null) {
  return { frameKey, tool: 'idle', spanAnchor: null,
           draft: draft ?? emptyDraft(), editingId };
}

// Rails snap to the clicked BAR's extreme — the operator measures wick to
// wick, and a rail a few pixels off the wick is noise, not information. The
// nearer of high/low to the click wins; without bar data the raw price stands.
export function snapRailPrice(price, bar) {
  if (!bar || !Number.isFinite(bar.high) || !Number.isFinite(bar.low)) return price;
  return Math.abs(bar.high - price) <= Math.abs(bar.low - price) ? bar.high : bar.low;
}

// The identity a draft binds to — mirrors the mark→frame binding contract.
export function frameKeyOf(chartData) {
  if (!chartData) return null;
  return `${chartData.ticker}|${chartData.as_of_session}|${chartData.frame_digest}`;
}

// What the progressive 'box' tool still needs, in placement order.
export function nextBoxNeed(draft) {
  if (draft.resistance == null) return 'resistance';
  if (draft.support == null) return 'support';
  if (draft.boxStartDate == null || draft.boxEndDate == null) return 'span';
  return null;
}

export function draftComplete(draft) {
  if (draft.verdict !== 'box') return true; // negatives carry NO geometry
  return draft.resistance != null && draft.support != null
    && draft.boxStartDate != null && draft.boxEndDate != null;
}

const orderedDates = (a, b) => (a <= b ? [a, b] : [b, a]);

function withRail(draft, which, price) {
  const next = { ...draft, [which]: price };
  if (next.resistance != null && next.support != null
      && next.support > next.resistance) {
    // Rails may be clicked in either order — R is always the upper one.
    const r = next.support;
    next.support = next.resistance;
    next.resistance = r;
  }
  return next;
}

function applyClick(state, { date, price, bar }) {
  const { tool, spanAnchor, draft } = state;
  if (tool === 'idle' || draft.verdict !== 'box') return state;
  const railPrice = snapRailPrice(price, bar);

  if (tool === 'rail-r') {
    return { ...state, tool: 'idle', draft: withRail(draft, 'resistance', railPrice) };
  }
  if (tool === 'rail-s') {
    return { ...state, tool: 'idle', draft: withRail(draft, 'support', railPrice) };
  }
  if (tool === 'span') {
    if (spanAnchor == null) return { ...state, spanAnchor: date };
    const [start, end] = orderedDates(spanAnchor, date);
    return { ...state, tool: 'idle', spanAnchor: null,
             draft: { ...draft, boxStartDate: start, boxEndDate: end } };
  }
  if (tool === 'box') {
    const need = nextBoxNeed(draft);
    if (need === 'resistance') return { ...state, draft: withRail(draft, 'resistance', railPrice) };
    if (need === 'support') return { ...state, draft: withRail(draft, 'support', railPrice) };
    if (need === 'span') {
      if (spanAnchor == null) return { ...state, spanAnchor: date };
      const [start, end] = orderedDates(spanAnchor, date);
      return { ...state, tool: 'idle', spanAnchor: null,
               draft: { ...draft, boxStartDate: start, boxEndDate: end } };
    }
    return { ...state, tool: 'idle' };
  }
  if (tool.startsWith('event:')) {
    if (spanAnchor == null) return { ...state, spanAnchor: date };
    const eventType = tool.slice('event:'.length);
    const [start, end] = orderedDates(spanAnchor, date);
    const event = { event_type: eventType, start_date: start, end_date: end,
                    tip_date: null, tip_price: null, source: 'operator' };
    return { ...state, tool: 'idle', spanAnchor: null,
             draft: { ...draft, events: [...draft.events, event] } };
  }
  return state;
}

export function markingReducer(state, action) {
  switch (action.type) {
    case 'load':
      return initialMarkingState(action.draft, action.frameKey, action.editingId ?? null);
    case 'edit-mark':
      // A saved mark loaded for correction (EC-9: editable ground truth) —
      // the draft becomes the mark's geometry and Save turns into a PUT.
      return initialMarkingState(draftFromMark(action.mark), state.frameKey,
                                 action.mark.id);
    case 'tool': {
      // Re-selecting the active tool disarms it (toggle); switching always
      // drops a half-placed span anchor.
      const tool = state.tool === action.tool ? 'idle' : action.tool;
      return { ...state, tool, spanAnchor: null };
    }
    case 'verdict': {
      if (action.verdict === state.draft.verdict) return state;
      // Negative verdicts carry NO geometry/events (the shared validity
      // contract) — switching away from 'box' drops everything drawn.
      const draft = action.verdict === 'box'
        ? { ...state.draft, verdict: 'box' }
        : { ...emptyDraft(), verdict: action.verdict };
      return { ...state, tool: 'idle', spanAnchor: null, draft };
    }
    case 'remove-event': {
      const events = state.draft.events.filter((_, i) => i !== action.index);
      return { ...state, draft: { ...state.draft, events } };
    }
    case 'clear':
      return initialMarkingState(null, state.frameKey);
    case 'chart-click':
      return applyClick(state, action);
    default:
      return state;
  }
}

const NEED_TEXT = {
  resistance: 'click the resistance rail',
  support: 'click the support rail',
};

export function statusText(state) {
  const { tool, spanAnchor, draft } = state;
  if (draft.verdict !== 'box') return 'negative verdict — no geometry to draw';
  if (tool === 'idle') return draftComplete(draft) ? 'draft complete' : '';
  if (tool === 'rail-r') return NEED_TEXT.resistance;
  if (tool === 'rail-s') return NEED_TEXT.support;
  if (tool === 'span' || (tool === 'box' && nextBoxNeed(draft) === 'span')) {
    return spanAnchor == null ? 'click the box START bar' : 'click the box END bar';
  }
  if (tool === 'box') return NEED_TEXT[nextBoxNeed(draft)] ?? 'draft complete';
  if (tool.startsWith('event:')) {
    const name = tool.slice('event:'.length).replace('_', ' ');
    return spanAnchor == null ? `click the ${name} START bar` : `click the ${name} END bar`;
  }
  return '';
}

// Draft <-> saved-mark converters (pure; the save payload is built here so
// the provenance-echo rule has ONE home the tests can pin).

export function draftFromMark(mark) {
  return {
    verdict: mark.verdict,
    resistance: mark.resistance ?? null,
    support: mark.support ?? null,
    boxStartDate: mark.box_start_date ?? null,
    boxEndDate: mark.box_end_date ?? null,
    events: (mark.events ?? []).map((e) => ({
      event_type: e.event_type, start_date: e.start_date, end_date: e.end_date,
      tip_date: e.tip_date ?? null, tip_price: e.tip_price ?? null,
      source: e.source ?? 'operator',
    })),
  };
}

// The save payload: geometry from the draft, IDENTITY AND PROVENANCE from the
// chart payload the operator is looking at — as_of_date is the RESOLVED
// session (the frozen-frame key) and frame_digest/data_regime/config/anchor
// are echoed verbatim (the mark→frame binding contract, server-verified).
export function markPayloadFromDraft(draft, chartData, { label = '', note = '' } = {}) {
  const isBox = draft.verdict === 'box';
  return {
    ticker: chartData.ticker,
    as_of_date: chartData.as_of_session,
    label: (label || '').trim().toLowerCase(),
    verdict: draft.verdict,
    resistance: isBox ? draft.resistance : null,
    support: isBox ? draft.support : null,
    box_start_date: isBox ? draft.boxStartDate : null,
    box_end_date: isBox ? draft.boxEndDate : null,
    rails_source: 'operator',
    knowable_from_date: null,
    note: (note || '').trim() || null,
    data_regime: chartData.data_regime,
    engine_config_version: chartData.engine_config_version,
    anchor_close: chartData.anchor_close,
    frame_digest: chartData.frame_digest,
    events: isBox ? draft.events : [],
  };
}

// lightweight-charts hands click times back in whatever form the series data
// used — ISO string, BusinessDay object, or a unix timestamp. One judgment.
export function chartTimeToIso(time) {
  if (typeof time === 'string') return time;
  if (time && typeof time === 'object') {
    const pad = (n) => String(n).padStart(2, '0');
    return `${time.year}-${pad(time.month)}-${pad(time.day)}`;
  }
  if (typeof time === 'number') {
    return new Date(time * 1000).toISOString().slice(0, 10);
  }
  return null;
}
