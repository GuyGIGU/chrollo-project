import { lazy, Suspense } from 'react';
import { useOutletContext } from 'react-router-dom';
import ErrorBoundary from '../components/ErrorBoundary';
import LoadingPanel from './LoadingPanel';

const PortfolioTab = lazy(() => import('../components/PortfolioTab'));

function PortfolioRoute() {
  const { trades, onDetailClick, riskFor, riskSummary, ibkrActions } = useOutletContext();

  return (
    <Suspense fallback={<LoadingPanel />}>
      <ErrorBoundary>
        <PortfolioTab
          key="portfolio"
          trades={trades}
          onTradeDetailClick={onDetailClick}
          riskFor={riskFor}
          riskSummary={riskSummary}
          ibkrActions={ibkrActions}
        />
      </ErrorBoundary>
    </Suspense>
  );
}

export default PortfolioRoute;
