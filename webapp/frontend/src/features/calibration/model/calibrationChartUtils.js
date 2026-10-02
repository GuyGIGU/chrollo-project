// Pure decision logic for the calibration chart lookup (node --test'able —
// Council Review 2026-07-11, finding 13 tail). No fetch, no React: the hook
// owns IO and state; THIS module owns the judgments a regression would
// silently break.

export const normalizeTicker = (t) => (t || '').trim().toUpperCase();

export const cacheKey = (ticker, asOf) => `${normalizeTicker(ticker)}|${asOf}`;

// Every key a successful payload answers: the requested key, plus the
// resolved-session alias (a Sunday and its Friday are ONE payload). A
// preserved copy served only because the vendor was throttling or failing
// answers NO key: the sitting cache would otherwise pin the frozen bars for the
// rest of the sitting, and the next lookup must ask the vendor again (review
// 2026-10-02). A copy served because the vendor has no data at all (SKYT) is the
// chart, and caches like any other.
export function cacheKeysFor(requestKey, body) {
  if (body?.source === 'preserved' && body?.preserved_reason !== 'no_data') return [];
  const keys = [requestKey];
  const resolved = body?.as_of_session && `${body.ticker}|${body.as_of_session}`;
  if (resolved && resolved !== requestKey) keys.push(resolved);
  return keys;
}

// One judgment for "what did the backend actually say": a real chart payload,
// a named failure, the stale-service SPA catch-all (a 200 that isn't a chart
// — the running service predates the endpoint), or an unclassified failure.
export function classifyChartResponse(ok, status, body) {
  if (ok) {
    if (Array.isArray(body?.candles)) return { kind: 'chart', body };
    return {
      kind: 'failure',
      failure: {
        class: 'service_stale',
        message: 'the running dashboard service does not know /calibration yet',
      },
    };
  }
  const detail = body?.detail;
  return {
    kind: 'failure',
    failure: detail?.class
      ? detail
      : { class: 'unknown', message: `lookup failed (${status})` },
  };
}

// The chart's OPENING frame (operator ask 2026-10-02: "when loading a ticker
// please make sure it already is zoomed in on the area of where the date was
// selected"). The old open showed the whole ~620-bar window at 2-3 px a bar.
// Now a fresh lookup opens on the last CALIBRATION_VIEW_BARS trading days up to
// the as-of bar — his TradingView habit, ~190 trading days on a big pane — and
// keeps a dozen forward bars past the line so the near breakout and the buy
// flag stay on screen. A SAVED setup (the rail row for this ticker + as-of)
// also widens the left edge to show its whole box plus about a month of
// approach, and the right edge to its buy when that lies further out.
// Candles skip non-finite rows, so every bar is found BY DATE, never derived
// from bar_count. Returns {from, to} logical indexes, or null when the as-of
// bar is unknown (the caller falls back to fitContent).
export const CALIBRATION_VIEW_BARS = 180;
const FORWARD_BARS = 12;
const APPROACH_BARS = 25;
const TRIGGER_PAD_BARS = 3;

// Index of the last bar dated on or before `iso`; -1 when every bar is later.
// ISO 'YYYY-MM-DD' string compare === chronological.
function lastBarOnOrBefore(candles, iso) {
  let found = -1;
  for (let i = 0; i < candles.length && candles[i].time <= iso; i += 1) found = i;
  return found;
}

export function initialVisibleRange(candles, asOfSession, { boxStart = null, triggerDate = null } = {}) {
  if (!Array.isArray(candles) || !candles.length || !asOfSession) return null;
  const asOfIdx = lastBarOnOrBefore(candles, asOfSession);
  if (asOfIdx < 0) return null;
  let from = asOfIdx - (CALIBRATION_VIEW_BARS - 1);
  if (boxStart) from = Math.min(from, lastBarOnOrBefore(candles, boxStart) - APPROACH_BARS);
  let to = asOfIdx + FORWARD_BARS;
  if (triggerDate) {
    const triggerIdx = lastBarOnOrBefore(candles, triggerDate);
    if (triggerIdx > to) to = triggerIdx + TRIGGER_PAD_BARS;
  }
  return { from: Math.max(0, from), to };
}
