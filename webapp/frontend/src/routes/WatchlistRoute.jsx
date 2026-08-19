import { lazy, Suspense } from 'react';
import ErrorBoundary from '../components/ErrorBoundary';
import LoadingPanel from './LoadingPanel';

const WatchlistPage = lazy(() => import('../components/watchlist/WatchlistPage'));

// Watchlist owns all its own state (selection, candle cache, overlay toggle) —
// no shell context needed. The ErrorBoundary keeps a crash in the chart surface
// from white-screening the app shell.
function WatchlistRoute() {
  return (
    <Suspense fallback={<LoadingPanel />}>
      <ErrorBoundary>
        <WatchlistPage key="watchlist" />
      </ErrorBoundary>
    </Suspense>
  );
}

export default WatchlistRoute;
