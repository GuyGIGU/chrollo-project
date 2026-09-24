import { lazy, Suspense } from 'react';
import { useOutletContext } from 'react-router-dom';
import ErrorBoundary from '../../shared/components/ErrorBoundary';
import LoadingPanel from '../../shared/components/LoadingPanel';

// Home = the command-center orient surface. Thin route: reads shell-owned trade
// data via outlet context and composes the zones in HomeView. The new index.
const HomeView = lazy(() => import('./components/HomeView'));

function HomeRoute() {
  const { trades, stats, riskFor, riskStatus, scanStatus } = useOutletContext();
  return (
    <Suspense fallback={<LoadingPanel />}>
      <ErrorBoundary>
        <HomeView trades={trades} stats={stats} riskFor={riskFor} riskStatus={riskStatus} scanStatus={scanStatus} />
      </ErrorBoundary>
    </Suspense>
  );
}

export default HomeRoute;
