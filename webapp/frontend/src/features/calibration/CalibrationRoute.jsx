import { lazy, Suspense } from 'react';
import ErrorBoundary from '../../shared/components/ErrorBoundary';
import LoadingPanel from '../../shared/components/LoadingPanel';

const CalibrationTab = lazy(() => import('./components/CalibrationTab'));

function CalibrationRoute() {
  return (
    <Suspense fallback={<LoadingPanel />}>
      <ErrorBoundary>
        <CalibrationTab key="calibration" />
      </ErrorBoundary>
    </Suspense>
  );
}

export default CalibrationRoute;
