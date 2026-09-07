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

export const MARK_EVENT_TYPES = ['phase_c', 'lps', 'spring_test', 'sos',
                                 'mini_consolidation', 'last_supper'];
// A mini-consolidation is a small BOX, so its two clicks are CORNERS (bar AND
// price) instead of a bare span. EC-3: this mirrors marks_validity._BAND_TYPES —
// the write-side rule and the draw-side shape must never drift.
export const BAND_EVENT_TYPES = ['mini_consolidation'];
export const MARK_VERDICTS = ['box', 'no_structure', 'engine_wrong'];

// The operator's BUY: the breakout above the High of the LPS's FINAL bar — a
// FORWARD-of-as-of point, one per box, meaningful only with an LPS on the draft.
const hasLpsEvent = (draft) => (draft.events || []).some((e) => e.event_type === 'lps');

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
    // The Trigger (the buy). triggerSource distinguishes the ASSISTED snap (re-
    // derived from the LPS end-bar) from a MANUAL placement (left alone when the
    // LPS moves). UI-only — never persisted (the mark stores just date + price).
    triggerDate: null,
    triggerPrice: null,
    triggerSource: null,
  };
}

export function initialMarkingState(draft = null, frameKey = null, editingId = null,
                                    pristine = true) {
  // bandAnchorPrice rides ALONGSIDE spanAnchor (which stays a bare date for
  // every tool) so a band's first corner keeps its price without making the
  // anchor polymorphic for the draw layer.
  // `pristine` = nothing has been drawn since this draft was seated. It is what
  // separates "unsaved work" from "a saved mark auto-loaded for correction",
  // which carries a fully populated draft the operator has not touched — the
  // unsaved-work guard must nag on the first and never on the second (council
  // review 2026-09-07, finding 8).
  return { frameKey, tool: 'idle', spanAnchor: null, bandAnchorPrice: null,
           draft: draft ?? emptyDraft(), editingId, pristine };
}

// Is there work on this draft that leaving the page would destroy? Drawn
// geometry, or a chosen negative verdict — but only once the operator has
// actually touched the seated draft. This is the ONE condition the calibration
// page arms its unsaved-work guard on (reload/close AND in-app navigation), so
// the two exits can never protect different things.
export function draftHasUnsavedWork(state) {
  if (!state || state.pristine) return false;
  return draftStarted(state.draft) || state.draft.verdict !== 'box';
}

// Rails snap to the clicked BAR's extreme — the operator measures wick to
// wick, and a rail a few pixels off the wick is noise, not information. The
// nearer of high/low to the click wins; without bar data the raw price stands.
export function snapRailPrice(price, bar) {
  if (!bar || !Number.isFinite(bar.high) || !Number.isFinite(bar.low)) return price;
  return Math.abs(bar.high - price) <= Math.abs(bar.low - price) ? bar.high : bar.low;
}

// The assisted Trigger snap: the buy is the breakout above the High of the LPS's
// FINAL (chronologically last) bar — NOT the LPS zone's max-High — and its date
// is the first frozen session strictly after that end-bar whose High clears the
// level. No as-of filter (relaxed 2026-07-22): the snap lands on the real
// historical breakout the moment the LPS is marked, wherever it is relative to
// the snapshot. Returns { date, price } or null (no LPS, no bar for the LPS end,
// or no clearing bar in the frame). Pure — `candles` is the ordered bar list
// [{ time, high, ... }] the chart already holds; node-testable.
export function snapTrigger(draft, candles) {
  if (draft.verdict !== 'box' || !hasLpsEvent(draft)) return null;
  const lpsEnd = (draft.events || [])
    .filter((e) => e.event_type === 'lps' && e.end_date)
    .map((e) => e.end_date)
    .reduce((a, b) => (a >= b ? a : b), null);
  if (lpsEnd == null) return null;
  const list = candles || [];
  const endBar = list.find((b) => b.time === lpsEnd);
  if (!endBar || !Number.isFinite(endBar.high)) return null;
  const level = endBar.high;
  for (const b of list) {
    if (b.time <= lpsEnd) continue;                        // strictly after the last LPS bar
    if (Number.isFinite(b.high) && b.high > level) {
      return { date: b.time, price: Number(level.toFixed(4)) };
    }
  }
  return null; // no breakout above the LPS high in the frame
}

// The identity a draft binds to — mirrors the mark→frame binding contract.
export function frameKeyOf(chartData) {
  if (!chartData) return null;
  return `${chartData.ticker}|${chartData.as_of_session}|${chartData.frame_digest}`;
}

// A create that lands on an existing identity (ticker, as-of, label) is a
// CORRECTION, but resolving it silently to an in-place PUT would let a stray
// negative keystroke or an empty-label second box clobber prior ground truth
// with no confirmation. So a duplicate is surfaced, never auto-applied: the
// backend names the existing row's id in the 409, and this reads it out so the
// UI can offer a one-click, EXPLICIT "update the existing mark" — the operator
// confirms the overwrite, it is never inferred. Returns the existing id, or
// null when the response is not a recoverable duplicate. Pure (node-testable);
// the hook owns the fetch, this owns the decision.
export function duplicateConflictId(body, editingId) {
  if (editingId) return null;   // an explicit edit is already a deliberate PUT
  const detail = body?.detail;
  if (detail?.class !== 'duplicate_mark') return null;
  return Number.isInteger(detail.existing_id) ? detail.existing_id : null;
}

export function draftComplete(draft) {
  if (draft.verdict !== 'box') return true; // negatives carry NO geometry
  if (draft.resistance == null || draft.support == null) return false;
  // The span is either drawn explicitly (x tool) or derivable from the two
  // rail anchors (start = earlier anchor, end = the as-of session).
  return (draft.boxStartDate != null && draft.boxEndDate != null)
    || (draft.rAnchorDate != null && draft.sAnchorDate != null);
}

// Has the operator begun THIS draft? A pristine draft — a fresh frame, or the
// empty draft a save leaves behind — carries nothing drawn, so the save-bar's
// "needs resistance · support · span" readout must stay SILENT until real work
// exists; otherwise a completed-and-saved setup reads as "incomplete" while its
// marks sit right there on the chart (operator, 2026-07-21). Any placed rail,
// anchor, span, event or trigger counts as started.
export function draftStarted(draft) {
  return draft.resistance != null || draft.support != null
    || draft.rAnchorDate != null || draft.sAnchorDate != null
    || draft.boxStartDate != null || draft.boxEndDate != null
    || (Array.isArray(draft.events) && draft.events.length > 0)
    || draft.triggerDate != null;
}

// The ITEMIZED form of draftComplete: which pieces a Save still needs, in the
// operator's priority order (rails before span). Empty === ready (draftComplete
// is true). Negatives carry no geometry, so they are always ready ([]). Powers
// the command band's always-visible "what's still needed" readout so a disabled
// Save is never a silent dead-end.
export function saveNeeds(draft) {
  if (draft.verdict !== 'box') return [];
  const needs = [];
  if (draft.resistance == null) needs.push('resistance');
  if (draft.support == null) needs.push('support');
  const spanKnown = (draft.boxStartDate != null && draft.boxEndDate != null)
    || (draft.rAnchorDate != null && draft.sAnchorDate != null);
  if (!spanKnown) needs.push('span');
  return needs;
}

// The client-side placement pre-check: is a click a valid place for this tool's
// mark? Returns the plain refusal reason, or null when allowed. It mirrors the
// server's grammar so a bad click is refused AT CLICK TIME with a reason, never
// left to fail later at Save. The backend (`marks_validity`) is the real gate —
// this is only the friendly pre-check, so the two MUST NOT DRIFT (EC-3): keep it
// in lockstep with `_validate_trigger` (the buy's ONLY rule is "strictly after
// the last LPS bar" — no as_of floor, relaxed 2026-07-22) and the
// `box_end / event-end / rail-anchor <= as_of` rule in `_validate_box_geometry`
// / `_validate_event`. A geometry mark ON the as-of session is valid (the
// operator observed that bar); only STRICTLY past it is refused. `lpsEnd` is the
// latest LPS end_date on the draft (null if none).
export function placementRefusal(tool, date, asOf, lpsEnd) {
  if (tool === 'trigger') {
    // The buy may sit before, on, or after the as-of — the operator marks the
    // real breakout day and locks the snapshot separately. Its only rule:
    // strictly after the last LPS bar.
    if (lpsEnd && date <= lpsEnd) return 'The buy must be after your last LPS bar.';
    return null;
  }
  // Every other mark is something OBSERVED by as-of, so it lands at or left of
  // the divider — never in the forward window.
  if (asOf && date > asOf) return 'That bar is past the as-of line — only the buy can be placed after it.';
  return null;
}

// The latest OBSERVED date a draft carries — everything that must sit at or left
// of the as-of line: the two rail anchors, an explicit box_end, and every event's
// end_date. The Trigger is NOT included (the buy may sit after the snapshot).
// Powers the "dialed back too far" guard: moving the as-of BEFORE this date would
// push a mark into the forward window and invalidate it. Null if nothing observed.
export function latestObservedDate(draft) {
  const dates = [draft.rAnchorDate, draft.sAnchorDate, draft.boxEndDate];
  for (const e of draft.events || []) dates.push(e.end_date);
  const observed = dates.filter((d) => typeof d === 'string' && d.length === 10);
  return observed.length ? observed.reduce((a, b) => (a >= b ? a : b)) : null;
}

// Prepare a draft to travel to a DIFFERENT snapshot (as-of) — the date-change
// carry and the eve-of-buy lock. Only an EXPLICIT box_end past the new as-of needs
// dropping (it re-derives to the new as-of); rails, LPS and the Trigger travel
// UNCHANGED — the buy is unconstrained by as-of (relaxed), so the operator's exact
// entry is preserved. Pure. (Callers only carry when the new as-of is >= every
// observed date, so no rail/LPS is ever left stranded past the line.)
export function trimDraftForAsOf(draft, targetAsOf) {
  if (draft.boxEndDate != null && draft.boxEndDate > targetAsOf) {
    return { ...draft, boxEndDate: null };
  }
  return draft;
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
  if (tool === 'trigger') {
    // Manual override of the assisted snap: the click sets the buy DATE; the
    // level stays the snapped LPS-high if one is set, else the clicked bar's
    // High (the trigger is a high-breakout). Marked 'manual' so a later LPS
    // re-draw leaves it alone (the operator placed it deliberately).
    const level = draft.triggerPrice != null
      ? draft.triggerPrice
      : Number(((bar && Number.isFinite(bar.high)) ? bar.high : price).toFixed(4));
    return { ...state, tool: 'idle',
             draft: { ...draft, triggerDate: date, triggerPrice: level,
                      triggerSource: 'manual' } };
  }
  if (tool.startsWith('event:')) {
    const eventType = tool.slice('event:'.length);
    const isBand = BAND_EVENT_TYPES.includes(eventType);
    if (spanAnchor == null) {
      return { ...state, spanAnchor: date,
               bandAnchorPrice: isBand ? railPrice : null };
    }
    const [start, end] = orderedDates(spanAnchor, date);
    const event = { event_type: eventType, start_date: start, end_date: end,
                    tip_date: null, tip_price: null,
                    band_high: null, band_low: null, source: 'operator' };
    if (isBand) {
      // Corners may be clicked in either order, exactly like the rails.
      const first = state.bandAnchorPrice;
      event.band_high = Math.max(first, railPrice);
      event.band_low = Math.min(first, railPrice);
    }
    return { ...state, tool: 'idle', spanAnchor: null, bandAnchorPrice: null,
             draft: { ...draft, events: [...draft.events, event] } };
  }
  return state;
}

// The reducer proper is wrapped so `pristine` is DERIVED from whether the draft
// object actually moved, rather than remembered branch by branch — a new action
// cannot forget to mark the draft dirty.
export function markingReducer(state, action) {
  const next = reduceMarking(state, action);
  if (next === state) return state;
  if (RESEATS.has(action.type)) return next;      // seats its own pristine
  return next.draft === state.draft ? next : { ...next, pristine: false };
}

// Actions that SEAT a draft rather than edit the current one; each decides its
// own pristine ('load' carries the stashed frame's, the other two start clean).
const RESEATS = new Set(['load', 'edit-mark', 'clear']);

function reduceMarking(state, action) {
  switch (action.type) {
    case 'load':
      // `pristine` rides with the stashed draft: returning to a frame whose
      // cached draft already had drawn work must resume as unsaved work.
      return initialMarkingState(action.draft, action.frameKey, action.editingId ?? null,
                                 action.pristine ?? true);
    case 'edit-mark':
      // A saved mark loaded for correction (EC-9: editable ground truth) —
      // the draft becomes the mark's geometry and Save turns into a PUT.
      return initialMarkingState(draftFromMark(action.mark), state.frameKey,
                                 action.mark.id);
    case 'tool': {
      // The Trigger tool is inert until an LPS exists on the draft — it is
      // structurally anchored to the LPS end-bar, so there is nothing to snap to
      // without one (the button/key stay no-ops, never a half-formed trigger).
      if (action.tool === 'trigger' && !hasLpsEvent(state.draft)) {
        return { ...state, tool: 'idle', spanAnchor: null, bandAnchorPrice: null };
      }
      // Re-selecting the active tool disarms it (toggle); switching always
      // drops a half-placed span anchor.
      const tool = state.tool === action.tool ? 'idle' : action.tool;
      return { ...state, tool, spanAnchor: null, bandAnchorPrice: null };
    }
    case 'set-trigger': {
      // The assisted snap (or a clear). Trigger is box-only; a null date clears
      // both fields. Source defaults to 'assisted' (the re-derivable kind).
      if (state.draft.verdict !== 'box') return state;
      const { date = null, price = null, source = 'assisted' } = action;
      const draft = date == null
        ? { ...state.draft, triggerDate: null, triggerPrice: null, triggerSource: null }
        : { ...state.draft, triggerDate: date, triggerPrice: price, triggerSource: source };
      return { ...state, draft };
    }
    case 'verdict': {
      if (action.verdict === state.draft.verdict) return state;
      // Negative verdicts carry NO geometry/events (the shared validity
      // contract) — switching away from 'box' drops everything drawn.
      const draft = action.verdict === 'box'
        ? { ...state.draft, verdict: 'box' }
        : { ...emptyDraft(), verdict: action.verdict };
      return { ...state, tool: 'idle', spanAnchor: null, bandAnchorPrice: null, draft };
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

// Per-type click prompts — presentational copy only (EC-28), naming what the
// operator is actually pointing at. Types absent here use the generic
// START/END bar wording.
const EVENT_PROMPTS = {
  sos: ['click the SOS launch low', 'click the SOS swing top'],
  mini_consolidation: ['click one CORNER of the mini consolidation',
                       'click the OPPOSITE corner'],
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
  if (tool === 'trigger') {
    return draft.triggerDate
      ? 'snapped to the LPS-high breakout — click a bar to move the buy'
      : 'no breakout above the LPS high in the forward window — click a bar to place the buy';
  }
  if (tool.startsWith('event:')) {
    const type = tool.slice('event:'.length);
    const prompts = EVENT_PROMPTS[type];
    if (prompts) return spanAnchor == null ? prompts[0] : prompts[1];
    const name = type.replaceAll('_', ' ');
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
      band_high: e.band_high ?? null, band_low: e.band_low ?? null,
      source: e.source ?? 'operator',
    })),
    // A loaded trigger is treated as MANUAL (fixed): editing an existing setup
    // must not silently re-derive the operator's banked buy on a re-render.
    triggerDate: mark.trigger_date ?? null,
    triggerPrice: mark.trigger_price ?? null,
    triggerSource: mark.trigger_date != null ? 'manual' : null,
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
    // The Trigger (buy) — box-only, and only the date/price persist (the
    // assisted/manual source is UI-only). A negative carries no trigger.
    trigger_date: isBox ? (draft.triggerDate ?? null) : null,
    trigger_price: isBox ? (draft.triggerPrice ?? null) : null,
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
