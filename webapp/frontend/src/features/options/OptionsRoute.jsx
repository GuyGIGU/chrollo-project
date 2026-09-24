import { lazy, Suspense } from 'react';
import { useOutletContext } from 'react-router-dom';
import ErrorBoundary from '../../shared/components/ErrorBoundary';
import LoadingPanel from '../../app/routes/LoadingPanel';

const TradeTable = lazy(() => import('../journal/components/TradeTable'));

// Options = the same trade table scoped to option symbols, no draft-row path.
function OptionsRoute() {
  const { optionTrades, onDetailClick, onTradeUpdate, riskFor } = useOutletContext();

  return (
    <Suspense fallback={<LoadingPanel />}>
      <ErrorBoundary>
        <TradeTable
          trades={optionTrades}
          draftRow={null}
          setDraftRow={() => {}}
          onDetailClick={onDetailClick}
          onTradeUpdate={onTradeUpdate}
          riskFor={riskFor}
        />
      </ErrorBoundary>
    </Suspense>
  );
}

export default OptionsRoute;
