import { lazy, Suspense } from 'react';
import ErrorBoundary from '../components/ErrorBoundary';
import LoadingPanel from './LoadingPanel';

const ScreenerGrid = lazy(() => import('../components/ScreenerGrid'));

// Screener owns all its own state (scan runner, filters, modal pager) — no shell
// context needed. Kept key="screener" to preserve the existing remount-on-leave
// behavior the in-memory tab model had.
function ScreenerRoute() {
  return (
    <Suspense fallback={<LoadingPanel />}>
      <ErrorBoundary>
        <ScreenerGrid key="screener" />
      </ErrorBoundary>
    </Suspense>
  );
}

export default ScreenerRoute;
