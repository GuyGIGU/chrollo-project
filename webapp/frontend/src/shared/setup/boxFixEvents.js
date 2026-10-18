// His events on a fixed box (Sat 18/10/2026: "lets widen it by letting me put events (spring,
// upthrust, sos, lps/former lps, span, mini consolidation.)"), as the fix page's tools: one button
// arms one tool, the clicks on the daily chart place it, and the list is saved beside the fix
// (useBoxFix.js does the clicks and the save, boxFixDraw.js the drawing). The MINI works exactly
// like the box (his word the same evening): Mini resistance and Mini support, each a click on a
// bar, and its own span, two clicks; without a span the mini runs from its earlier line's day to
// the chart's last day, as the box does. Pure: no DOM, no chart; node --test pins it. The
// vocabulary mirrors the backend's box_fixes.EVENT_KINDS.
import { snapRailPrice } from '../charts/chartGeometry.js';

export const EVENT_KINDS = ['spring', 'upthrust', 'sos', 'lps', 'former_lps', 'span', 'mini'];
export const EVENT_NAMES = {
  spring: 'spring', upthrust: 'upthrust', sos: 'SOS', lps: 'LPS', former_lps: 'former LPS', span: 'span', mini: 'mini',
};
// The tools the page offers, in its order: the box's two lines, the mini's two lines and span, the events.
export const TOOLS = ['rail-r', 'rail-s', 'mini-r', 'mini-s', 'mini-span', 'spring', 'upthrust', 'sos', 'lps', 'former_lps', 'span'];
export const TOOL_NAMES = {
  'rail-r': 'Resistance', 'rail-s': 'Support', 'mini-r': 'Mini resistance', 'mini-s': 'Mini support', 'mini-span': 'Mini span',
  spring: 'Spring', upthrust: 'Upthrust', sos: 'SOS', lps: 'LPS', former_lps: 'Former LPS', span: 'Span',
};
export const TOOL_HOW = {
  'rail-r': 'click the climax bar: the line lands on its high',
  'rail-s': 'click the reaction bar: the line lands on its low',
  'mini-r': "click the mini's top bar: the line lands on its high",
  'mini-s': "click the mini's bottom bar: the line lands on its low",
  'mini-span': "click the mini's first and last day (else it runs from its earlier line to the chart's edge)",
  spring: 'click its tip: the bar whose low poked under support',
  upthrust: 'click its top: the bar whose high ran over resistance',
  sos: 'click the launch low, then the top',
  lps: 'click its first and last day',
  former_lps: 'click its first and last day: the entry that already happened',
  span: 'click its first and last day, then name it',
};
// A spring and an upthrust point at ONE day (the tip, the top); the mini's lines are one click each.
const ONE_CLICK = new Set(['spring', 'upthrust', 'mini-r', 'mini-s']);

export const EMPTY_MINI = { r: null, rDay: null, s: null, sDay: null, spanStart: null, spanEnd: null };
export const EMPTY_EVENTS = { tool: null, anchor: null, events: [], mini: EMPTY_MINI };

// The marks seated from the fix he saved before: its events as they were, the mini as the mini's lines
// and span (the backend keeps the mini as one event: its band and its days).
export function marksFromFix(fix) {
  const events = [];
  let mini = EMPTY_MINI;
  for (const saved of fix?.events || []) {
    if (saved.kind === 'mini') {
      mini = { r: saved.band_high, rDay: saved.first_day, s: saved.band_low, sDay: saved.first_day,
               spanStart: saved.first_day, spanEnd: saved.last_day };
    } else {
      events.push({ kind: saved.kind, first_day: saved.first_day, last_day: saved.last_day, price: saved.price ?? null,
                    band_high: null, band_low: null, label: saved.label ?? null });
    }
  }
  return { tool: null, anchor: null, events, mini };
}

// A button arms its tool; the same button again, or null, disarms. A half-placed first click is dropped.
export function armTool(state, tool) {
  const next = tool && tool !== state.tool && TOOLS.includes(tool) ? tool : null;
  return { ...state, tool: next, anchor: null };
}

const ordered = (a, b) => (a <= b ? [a, b] : [b, a]);
const lowestLow = (candles, first, last) => {
  const lows = (candles || []).filter((c) => c.time >= first && c.time <= last && Number.isFinite(c.low)).map((c) => c.low);
  return lows.length ? Math.min(...lows) : null;
};
const event = (kind, first, last, price, label = null) => ({ kind, first_day: first, last_day: last, price, band_high: null, band_low: null, label });

// The mini's two lines, like the box's: the resistance on the bar's high, the support on its low,
// crossed lines swapped so the higher one is the resistance.
function miniLine(mini, which, date, bar) {
  const next = which === 'mini-r' ? { ...mini, r: bar.high, rDay: date } : { ...mini, s: bar.low, sDay: date };
  if (next.r != null && next.s != null && next.s > next.r) {
    return { ...next, r: next.s, rDay: next.sDay, s: next.r, sDay: next.rDay };
  }
  return next;
}

// One click with a tool armed. Returns the state; a placed event or line disarms the tool, a first
// click of a two-click tool is kept as the anchor. Days may be clicked in either order.
export function applyToolClick(state, { date, bar, price }, candles = []) {
  const tool = state.tool;
  if (!tool || !date || !bar || !Number.isFinite(bar.high) || !Number.isFinite(bar.low)) return state;
  const done = (patch) => ({ ...state, ...patch, tool: null, anchor: null });
  if (tool === 'mini-r' || tool === 'mini-s') return done({ mini: miniLine(state.mini, tool, date, bar) });
  if (tool === 'spring') return done({ events: [...state.events, event(tool, date, date, bar.low)] });
  if (tool === 'upthrust') return done({ events: [...state.events, event(tool, date, date, bar.high)] });
  if (state.anchor == null) {
    const snapped = snapRailPrice(Number.isFinite(price) ? price : (bar.high + bar.low) / 2, bar);
    return { ...state, anchor: { date, bar, snapped } };
  }
  const [first, last] = ordered(state.anchor.date, date);
  if (tool === 'mini-span') return done({ mini: { ...state.mini, spanStart: first, spanEnd: last } });
  if (tool === 'sos') {
    const top = date >= state.anchor.date ? bar : state.anchor.bar;
    return done({ events: [...state.events, event(tool, first, last, top.high)] });
  }
  return done({ events: [...state.events, event(tool, first, last, lowestLow(candles, first, last))] });
}

export function removeEvent(state, index) {
  return { ...state, events: state.events.filter((_, i) => i !== index) };
}

// One piece of the mini removed: a line, or its span.
export function removeMiniPart(state, part) {
  const mini = part === 'r' ? { ...state.mini, r: null, rDay: null }
    : part === 's' ? { ...state.mini, s: null, sDay: null }
      : { ...state.mini, spanStart: null, spanEnd: null };
  return { ...state, mini };
}

// His word for an event (a span's name, or a note on any): kept as typed, stripped on save.
export function labelEvent(state, index, label) {
  return { ...state, events: state.events.map((ev, i) => (i === index ? { ...ev, label } : ev)) };
}

// The mini as an event once both lines stand: from its span's first day, or its earlier line's
// day, to its span's last day, or the chart's last day. Null while a line is missing.
export function miniEvent(mini, lastDay) {
  if (mini?.r == null || mini?.s == null || !(mini.r > mini.s)) return null;
  const first = mini.spanStart ?? (mini.rDay <= mini.sDay ? mini.rDay : mini.sDay);
  const last = mini.spanEnd ?? lastDay ?? first;
  return { kind: 'mini', first_day: first, last_day: last, price: null, band_high: mini.r, band_low: mini.s, label: null };
}

// Every event the fix carries, the mini among them when it stands.
export function allEvents(state, lastDay) {
  const mini = miniEvent(state.mini, lastDay);
  return mini ? [...state.events, mini] : state.events;
}

const dayMonth = (day) => {
  const match = String(day ?? '').match(/^\d{4}-(\d{2})-(\d{2})/);
  return match ? `${match[2]}/${match[1]}` : '';
};

// What the page says while a tool is armed, or null.
export function toolPrompt(state) {
  const tool = state.tool;
  if (!tool) return null;
  if (ONE_CLICK.has(tool)) return TOOL_HOW[tool];
  if (state.anchor == null) {
    if (tool === 'sos') return 'click the SOS launch low';
    if (tool === 'mini-span') return "click the mini's first day";
    return `click the first day of the ${EVENT_NAMES[tool]}`;
  }
  if (tool === 'sos') return `launch ${dayMonth(state.anchor.date)}: now click the SOS top`;
  if (tool === 'mini-span') return `${dayMonth(state.anchor.date)}: now click the mini's last day`;
  return `${dayMonth(state.anchor.date)}: now click the last day of the ${EVENT_NAMES[tool]}`;
}

// One event as a chip: "spring 01/10 325.81", "LPS 14/10–16/10", "mini 05/10–09/10 342.50/339.00".
export function eventWords(ev) {
  const days = ev.first_day === ev.last_day ? dayMonth(ev.first_day) : `${dayMonth(ev.first_day)}–${dayMonth(ev.last_day)}`;
  const price = ev.kind === 'mini'
    ? `${ev.band_high.toFixed(2)}/${ev.band_low.toFixed(2)}`
    : ev.price != null ? ev.price.toFixed(2) : '';
  const label = ev.label ? ` "${ev.label.trim()}"` : '';
  return `${EVENT_NAMES[ev.kind]} ${days}${price ? ` ${price}` : ''}${label}`.trim();
}

// The request body of PUT /calibration/box-fixes/{id}/events: the list as a whole, his latest word.
export function eventsPayload(events) {
  return events.map((ev) => ({
    kind: ev.kind,
    first_day: ev.first_day,
    last_day: ev.last_day,
    price: ev.price ?? null,
    band_high: ev.band_high ?? null,
    band_low: ev.band_low ?? null,
    label: ev.label?.trim() || null,
  }));
}
