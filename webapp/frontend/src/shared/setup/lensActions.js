// The big chart's own keys (operator 2026-10-03, suggestion #1): W stars, L
// likes, T opens TradingView, so he can walk the filtered list with Next and act
// on each chart without closing it. Pure, so node --test pins it; the lens
// toolbar (ScreenerModalToolbar.jsx) does the DOM side.
import { hasCommandModifier, isTypingTarget } from '../navigation/keyboardGuard.js';

export const LENS_ACTION_KEYS = { w: 'watch', l: 'like', t: 'tradingview' };

// Which lens action a keydown asks for, or null. A held key repeats (holding W
// must not flicker the star); Ctrl+W / Ctrl+L / Ctrl+T are the browser's; keys
// typed into the lens's "what's off?" box are text.
export function lensKeyAction(event) {
  if (!event || event.repeat || hasCommandModifier(event) || isTypingTarget(event.target)) return null;
  return LENS_ACTION_KEYS[String(event.key).toLowerCase()] ?? null;
}

// The ONE TradingView address: the lens's ↗ TV and Home's BridgeOut both build it here.
export const tradingViewUrl = (ticker) => `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(ticker)}`;
