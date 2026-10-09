// Where the big chart sits in the list it walks, and where Prev/Next land
// (operator 2026-10-03, suggestion #1). Pure, so node --test pins it;
// ScreenerGrid keeps the last index the lens ticker had and steps with it.

// { n, total } with n 1-based ("12 / 37"); n is null once the ticker has dropped
// out of the list ("– / 36"), so the counter keeps its slot and the star beside it
// never slides out from under the pointer. null only for an empty list.
export function lensPosition(tickers, ticker) {
  if (tickers.length === 0) return null;
  const index = tickers.indexOf(ticker);
  return { n: index < 0 ? null : index + 1, total: tickers.length };
}

// Prev/Next go somewhere only when another setup is in the list. One match that
// IS the chart on screen has nowhere to go; one match after the chart dropped out
// is still a step away (two starred, he un-stars the one on screen).
export function canStepLens(tickers, ticker) {
  return tickers.some((t) => t !== ticker);
}

// The ticker Prev (delta -1) or Next (+1) lands on; null for an empty list. In
// the list it wraps. DROPPED OUT of it (on the Watchlist tier he un-stars the
// chart with W, so the filtered list loses it while the lens stays open), Next
// lands on the setup that slid into his old slot and Prev on the one before it.
export function stepTicker(tickers, ticker, lastIndex, delta) {
  const count = tickers.length;
  if (count === 0) return null;
  const index = tickers.indexOf(ticker);
  if (index >= 0) return tickers[(index + delta + count) % count];
  const slot = lastIndex ?? 0;
  if (delta > 0) return tickers[slot < count ? slot : 0];
  const before = Math.min(slot, count) - 1;   // a slot past the end has the last setup before it
  return tickers[before < 0 ? count - 1 : before];
}
