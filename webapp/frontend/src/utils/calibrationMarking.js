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
    // Rail ANCHORS (operator ask 2026-07-11): each rail remembers the BAR it
    // was placed on, and firstRail names the one marked first — together they
    // say which root swing the operator was aiming at (the engine's own
    // chronological-pair anchor concept), and they derive the box span so a
    // span never has to be drawn by hand again.
    rAnchorDate: null,
    sAnchorDate: null,
    firstRail: null,
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

export function draftComplete(draft) {
  if (draft.verdict !== 'box') return true; // negatives carry NO geometry
  if (draft.resistance == null || draft.support == null) return false;
  // The span is either drawn explicitly (x tool) or derivable from the two
  // rail anchors (start = earlier anchor, end = the as-of session).
  return (draft.boxStartDate != null && draft.boxEndDate != null)
    || (draft.rAnchorDate != null && draft.sAnchorDate != null);
}

// The span the mark will actually save: an explicit x-drawn span wins;
// otherwise it derives from the anchors — start at the earlier-anchored
// swing, end at the as-of session (the same geometry the engine projects).
export function effectiveSpan(draft, asOfSession) {
  let start = draft.boxStartDate;
  if (start == null && draft.rAnchorDate != null && draft.sAnchorDate != null) {
    start = draft.rAnchorDate <= draft.sAnchorDate
      ? draft.rAnchorDate : draft.sAnchorDate;
  }
  const end = draft.boxEndDate ?? (start != null ? (asOfSession ?? null) : null);
  return { start: start ?? null, end };
}

const orderedDates = (a, b) => (a <= b ? [a, b] : [b, a]);

function withRail(draft, which, price, date) {
  const anchorKey = which === 'resistance' ? 'rAnchorDate' : 'sAnchorDate';
  const next = { ...draft, [which]: price, [anchorKey]: date ?? null };
  if (next.firstRail == null) next.firstRail = which;
  if (next.resistance != null && next.support != null
      && next.support > next.resistance) {
    // Rails may be clicked in either order — R is always the upper one, and
    // the anchor dates (plus the first-marked label) travel WITH their
    // prices, so "which extreme he marked first" survives the normalization.
    [next.resistance, next.support] = [next.support, next.resistance];
    [next.rAnchorDate, next.sAnchorDate] = [next.sAnchorDate, next.rAnchorDate];
    next.firstRail = next.firstRail === 'resistance' ? 'support' : 'resistance';
  }
  return next;
}

function applyClick(state, { date, price, bar }) {
  const { tool, spanAnchor, draft } = state;
  if (tool === 'idle' || draft.verdict !== 'box') return state;
  const railPrice = snapRailPrice(price, bar);

  if (tool === 'rail-r') {
    return { ...state, tool: 'idle',
             draft: withRail(draft, 'resistance', railPrice, date) };
  }
  if (tool === 'rail-s') {
    return { ...state, tool: 'idle',
             draft: withRail(draft, 'support', railPrice, date) };
  }
  if (tool === 'span') {
    // Explicit span override — the usual span DERIVES from the rail anchors.
    if (spanAnchor == null) return { ...state, spanAnchor: date };
    const [start, end] = orderedDates(spanAnchor, date);
    return { ...state, tool: 'idle', spanAnchor: null,
             draft: { ...draft, boxStartDate: start, boxEndDate: end } };
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
  // The click carries two facts: the wick = the rail price, the bar = the
  // swing anchor the operator is aiming at.
  resistance: 'click the resistance swing bar',
  support: 'click the support swing bar',
};

export function statusText(state) {
  const { tool, spanAnchor, draft } = state;
  if (draft.verdict !== 'box') return 'negative verdict — no geometry to draw';
  if (tool === 'idle') return draftComplete(draft) ? 'draft complete' : '';
  if (tool === 'rail-r') return NEED_TEXT.resistance;
  if (tool === 'rail-s') return NEED_TEXT.support;
  if (tool === 'span') {
    return spanAnchor == null ? 'click the box START bar' : 'click the box END bar';
  }
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
    rAnchorDate: mark.r_anchor_date ?? null,
    sAnchorDate: mark.s_anchor_date ?? null,
    firstRail: mark.first_rail ?? null,
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
  const span = effectiveSpan(draft, chartData.as_of_session);
  return {
    ticker: chartData.ticker,
    as_of_date: chartData.as_of_session,
    label: (label || '').trim().toLowerCase(),
    verdict: draft.verdict,
    resistance: isBox ? draft.resistance : null,
    support: isBox ? draft.support : null,
    box_start_date: isBox ? span.start : null,
    box_end_date: isBox ? span.end : null,
    r_anchor_date: isBox ? draft.rAnchorDate : null,
    s_anchor_date: isBox ? draft.sAnchorDate : null,
    first_rail: isBox ? draft.firstRail : null,
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
