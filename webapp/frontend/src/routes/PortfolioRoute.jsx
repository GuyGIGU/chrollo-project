import { lazy, Suspense } from 'react';
import { useOutletContext } from 'react-router-dom';
import ErrorBoundary from '../components/ErrorBoundary';
import LoadingPanel from './LoadingPanel';

const PortfolioTab = lazy(() => import('../components/PortfolioTab'));

function PortfolioRoute() {
  const { trades, onDetailClick } = useOutletContext();

  return (
    <Suspense fallback={<LoadingPanel />}>
      <ErrorBoundary>
        <PortfolioTab key="portfolio" trades={trades} onTradeDetailClick={onDetailClick} />
      </ErrorBoundary>
    </Suspense>
  );
}

export default PortfolioRoute;
