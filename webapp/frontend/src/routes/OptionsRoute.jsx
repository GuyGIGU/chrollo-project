import { lazy, Suspense } from 'react';
import { useOutletContext } from 'react-router-dom';
import ErrorBoundary from '../components/ErrorBoundary';
import LoadingPanel from './LoadingPanel';

const TradeTable = lazy(() => import('../components/TradeTable'));

// Options = the same trade table scoped to option symbols, no draft-row path.
function OptionsRoute() {
  const { optionTrades, onDetailClick, onTradeUpdate, priceFor } = useOutletContext();

  return (
    <Suspense fallback={<LoadingPanel />}>
      <ErrorBoundary>
        <TradeTable
          trades={optionTrades}
          draftRow={null}
          setDraftRow={() => {}}
          onDetailClick={onDetailClick}
          onTradeUpdate={onTradeUpdate}
          priceFor={priceFor}
        />
      </ErrorBoundary>
    </Suspense>
  );
}

export default OptionsRoute;
