// His events on a fixed box (Sat 18/10/2026: "lets widen it by letting me put events (spring,
// upthrust, sos, lps/former lps, span, mini consolidation.)"): while "fix the box" is armed a
// letter arms one event, the clicks on the daily chart place it, and the list is saved beside
// the fix (useBoxFix.js does the clicks and the save, boxFixDraw.js the drawing). Pure: no DOM,
// no chart; node --test pins it. The vocabulary mirrors the backend's box_fixes.EVENT_KINDS.
import { snapRailPrice } from '../charts/chartGeometry.js';

export const EVENT_KINDS = ['spring', 'upthrust', 'sos', 'lps', 'former_lps', 'span', 'mini'];
export const EVENT_NAMES = {
  spring: 'spring', upthrust: 'upthrust', sos: 'SOS', lps: 'LPS', former_lps: 'former LPS', span: 'span', mini: 'mini',
};
// The letter on the chart's marker and on the key: his list (S spring, U upthrust, O SOS, L LPS,
// F former LPS, P span, M mini); the calibration page's own L, O and M where it has them.
export const EVENT_TAG = { spring: 'S', upthrust: 'U', sos: 'O', lps: 'L', former_lps: 'F', span: 'P', mini: 'M' };
// A spring and an upthrust point at ONE day (the tip, the top); the rest are a stretch of days.
const ONE_CLICK = new Set(['spring', 'upthrust']);

export const EMPTY_EVENTS = { tool: null, anchor: null, events: [] };

// A letter arms its event; the same letter again, or null, disarms. A half-placed first click is dropped.
export function armEvent(state, kind) {
  const tool = kind && kind !== state.tool && EVENT_KINDS.includes(kind) ? kind : null;
  return { ...state, tool, anchor: null };
}

const ordered = (a, b) => (a <= b ? [a, b] : [b, a]);
const lowestLow = (candles, first, last) => {
  const lows = (candles || []).filter((c) => c.time >= first && c.time <= last && Number.isFinite(c.low)).map((c) => c.low);
  return lows.length ? Math.min(...lows) : null;
};

// One click while an event is armed. A spring lands on its tip (the bar's low), an upthrust on its
// top (the bar's high). The SOS takes two clicks, the launch low then the top (its price the top's
// high); an LPS, a former LPS and a span take their first and last day (their price the lowest low
// of those days); the mini takes two corners, each snapping to the nearer end of its bar, the
// higher the mini's resistance. Days may be clicked in either order. A placed event disarms the tool.
export function applyEventClick(state, { date, bar, price }, candles = []) {
  const kind = state.tool;
  if (!kind || !date || !bar || !Number.isFinite(bar.high) || !Number.isFinite(bar.low)) return state;
  const place = (event) => ({ tool: null, anchor: null, events: [...state.events, event] });
  if (kind === 'spring') return place({ kind, first_day: date, last_day: date, price: bar.low, band_high: null, band_low: null, label: null });
  if (kind === 'upthrust') return place({ kind, first_day: date, last_day: date, price: bar.high, band_high: null, band_low: null, label: null });
  const snapped = snapRailPrice(Number.isFinite(price) ? price : (bar.high + bar.low) / 2, bar);
  if (state.anchor == null) return { ...state, anchor: { date, bar, snapped } };
  const [first, last] = ordered(state.anchor.date, date);
  if (kind === 'mini') {
    const [hi, lo] = state.anchor.snapped >= snapped ? [state.anchor.snapped, snapped] : [snapped, state.anchor.snapped];
    if (hi === lo) return { ...state, anchor: null };
    return place({ kind, first_day: first, last_day: last, price: null, band_high: hi, band_low: lo, label: null });
  }
  if (kind === 'sos') {
    const top = date >= state.anchor.date ? bar : state.anchor.bar;
    return place({ kind, first_day: first, last_day: last, price: top.high, band_high: null, band_low: null, label: null });
  }
  return place({ kind, first_day: first, last_day: last, price: lowestLow(candles, first, last), band_high: null, band_low: null, label: null });
}

export function removeEvent(state, index) {
  return { ...state, events: state.events.filter((_, i) => i !== index) };
}

// His word for an event (a span's name, or a note on any): kept as typed, stripped on save.
export function labelEvent(state, index, label) {
  return { ...state, events: state.events.map((event, i) => (i === index ? { ...event, label } : event)) };
}

const dayMonth = (day) => {
  const match = String(day ?? '').match(/^\d{4}-(\d{2})-(\d{2})/);
  return match ? `${match[2]}/${match[1]}` : '';
};

// What the strip says while an event is armed.
export function eventPrompt(state) {
  const kind = state.tool;
  if (!kind) return null;
  if (kind === 'spring') return "click the spring's tip: the bar whose low poked under support";
  if (kind === 'upthrust') return "click the upthrust's top: the bar whose high ran over resistance";
  if (state.anchor == null) {
    if (kind === 'sos') return 'click the SOS launch low';
    if (kind === 'mini') return 'click one corner of the mini';
    return `click the first day of the ${EVENT_NAMES[kind]}`;
  }
  if (kind === 'sos') return `launch ${dayMonth(state.anchor.date)}: now click the SOS top`;
  if (kind === 'mini') return `corner ${state.anchor.snapped.toFixed(2)} on ${dayMonth(state.anchor.date)}: now click the opposite corner`;
  return `${dayMonth(state.anchor.date)}: now click the last day of the ${EVENT_NAMES[kind]}`;
}

// One event as a chip: "spring 01/10 325.81", "LPS 14/10–16/10", "mini 05/10–09/10 342.50/339.00".
export function eventWords(event) {
  const days = event.first_day === event.last_day ? dayMonth(event.first_day) : `${dayMonth(event.first_day)}–${dayMonth(event.last_day)}`;
  const price = event.kind === 'mini'
    ? `${event.band_high.toFixed(2)}/${event.band_low.toFixed(2)}`
    : event.price != null ? event.price.toFixed(2) : '';
  const label = event.label ? ` "${event.label.trim()}"` : '';
  return `${EVENT_NAMES[event.kind]} ${days}${price ? ` ${price}` : ''}${label}`.trim();
}

// The request body of PUT /calibration/box-fixes/{id}/events: the list as a whole, his latest word.
export function eventsPayload(events) {
  return events.map((event) => ({
    kind: event.kind,
    first_day: event.first_day,
    last_day: event.last_day,
    price: event.price ?? null,
    band_high: event.band_high ?? null,
    band_low: event.band_low ?? null,
    label: event.label?.trim() || null,
  }));
}
