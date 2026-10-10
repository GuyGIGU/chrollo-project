import { lazy, Suspense } from 'react';
import { useOutletContext } from 'react-router-dom';
import ErrorBoundary from '../../shared/components/ErrorBoundary';
import LoadingPanel from '../../shared/components/LoadingPanel';
import useDocumentTitle from '../../shared/hooks/useDocumentTitle';

const PortfolioTab = lazy(() => import('./components/PortfolioTab'));

function PortfolioRoute() {
  useDocumentTitle('Portfolio');
  const { trades, onDetailClick, riskFor, riskSummary, ibkrStatus, ibkrActions } = useOutletContext();

  return (
    <Suspense fallback={<LoadingPanel />}>
      <ErrorBoundary>
        <PortfolioTab
          key="portfolio"
          trades={trades}
          onTradeDetailClick={onDetailClick}
          riskFor={riskFor}
          riskSummary={riskSummary}
          ibkrStatus={ibkrStatus}
          ibkrActions={ibkrActions}
        />
      </ErrorBoundary>
    </Suspense>
  );
}

export default PortfolioRoute;
