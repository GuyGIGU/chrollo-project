import { lazy, Suspense } from 'react';
import ErrorBoundary from '../../shared/components/ErrorBoundary';
import LoadingPanel from '../../app/routes/LoadingPanel';

const ArchiveTab = lazy(() => import('./components/ArchiveTab'));

function ArchiveRoute() {
  return (
    <Suspense fallback={<LoadingPanel />}>
      <ErrorBoundary>
        <ArchiveTab key="archive" />
      </ErrorBoundary>
    </Suspense>
  );
}

export default ArchiveRoute;
