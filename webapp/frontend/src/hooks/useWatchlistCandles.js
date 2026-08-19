import { useSyncExternalStore } from 'react';
import {
  getBatchCells,
  getCandleEnvelopes,
  subscribeCandlesStore,
} from './watchlistCandlesStore';

// Read-side hooks over the shared candle store. Fetching stays imperative
// (fetchTickerCandles / fetchBatchCandles called from the page's effects) so
// these stay pure subscriptions — panes derive their data from
// "map + selected ticker" every render, never hold chart data in state.
export function useCandleEnvelopes() {
  return useSyncExternalStore(subscribeCandlesStore, getCandleEnvelopes);
}

export function useBatchCells() {
  return useSyncExternalStore(subscribeCandlesStore, getBatchCells);
}
