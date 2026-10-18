// The big chart's own keys (operator 2026-10-03, suggestion #1): W stars, L
// likes, T opens TradingView, so he can walk the filtered list with Next and act
// on each chart without closing it. F flips the panel under the chart to the
// fundamentals page and back (Tue 13/10/2026, his "show the fundamental card as a
// second page"), as it flips a card. B arms "fix the box" (Fri 17/10/2026). WHILE
// THE FIX IS ARMED the letters place his events instead (Sat 18/10/2026: S spring,
// U upthrust, O SOS, L LPS, F former LPS, P span, M mini), so L and F are the
// like and the page only outside the fix. Pure, so node --test pins it; the lens
// toolbar (ScreenerModalToolbar.jsx) does the DOM side of W/L/T, the lens
// (ScreenerModal.jsx) the page's and the events'.
import { hasCommandModifier, isTypingTarget } from '../navigation/keyboardGuard.js';
import { EVENT_TAG } from './boxFixEvents.js';

export const LENS_ACTION_KEYS = { w: 'watch', l: 'like', t: 'tradingview', f: 'fundamentals', b: 'fixbox' };
// The event each letter arms while the fix is on: 'event:spring', 'event:lps', ...
export const LENS_EVENT_KEYS = Object.fromEntries(Object.entries(EVENT_TAG).map(([kind, tag]) => [tag.toLowerCase(), `event:${kind}`]));

// Which lens action a keydown asks for, or null. A held key repeats (holding W
// must not flicker the star); Ctrl+W / Ctrl+L / Ctrl+T are the browser's; keys
// typed into the lens's "what's off?" box are text. `fixing` says the fix is
// armed: then a letter that names an event arms that event.
export function lensKeyAction(event, { fixing = false } = {}) {
  if (!event || event.repeat || hasCommandModifier(event) || isTypingTarget(event.target)) return null;
  const key = String(event.key).toLowerCase();
  if (fixing && key in LENS_EVENT_KEYS) return LENS_EVENT_KEYS[key];
  return LENS_ACTION_KEYS[key] ?? null;
}

// The ONE TradingView address: the lens's ↗ TV and Home's BridgeOut both build it here.
export const tradingViewUrl = (ticker) => `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(ticker)}`;
