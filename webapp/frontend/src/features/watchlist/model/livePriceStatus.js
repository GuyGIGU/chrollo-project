// The 'prices' source's status, composed from the two things that can leave the
// trigger groups empty. An unloaded WATCHLIST yields an empty ticker set indistinguishable
// from a genuinely empty one — the trap finding 9 was about. `useLivePrices`
// owns the polling; this helper composes only source load states.
export function livePriceStatus(watchlistStatus, tickersKey, fetchStatus) {
  if (watchlistStatus === 'error') return 'error';
  if (watchlistStatus !== 'ready') return 'loading';
  if (!tickersKey) return 'idle';   // confirmed-empty watchlist: nothing to price
  return fetchStatus;
}

