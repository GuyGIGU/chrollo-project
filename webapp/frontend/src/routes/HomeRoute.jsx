import { lazy, Suspense } from 'react';
import { useOutletContext } from 'react-router-dom';
import ErrorBoundary from '../components/ErrorBoundary';
import LoadingPanel from './LoadingPanel';

// Home = the command-center orient surface. Thin route: reads shell-owned trade
// data via outlet context and composes the zones in HomeView. The new index.
const HomeView = lazy(() => import('../components/home/HomeView'));

function HomeRoute() {
  const { trades, stats, priceFor, scanStatus } = useOutletContext();
  return (
    <Suspense fallback={<LoadingPanel />}>
      <ErrorBoundary>
        <HomeView trades={trades} stats={stats} priceFor={priceFor} scanStatus={scanStatus} />
      </ErrorBoundary>
    </Suspense>
  );
}

export default HomeRoute;
