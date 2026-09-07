import ErrorBoundary from '../ErrorBoundary';
import MarketPulse from '../MarketPulse';
import RegimePanel from '../RegimePanel';
import ActionCenter from './ActionCenter';
import WatchlistZone from './WatchlistZone';
import OpenBookZone from './OpenBookZone';
import JournalPulseZone from './JournalPulseZone';
import EdgePulse from './EdgePulse';
import usePollingInterval from '../../hooks/usePollingInterval';
import useScreenerData from '../../hooks/useScreenerData';
import useLivePrices from '../../hooks/useLivePrices';
import { revalidateScreenerUniverse } from '../../hooks/screenerStore';

// The orient surface as one aligned dashboard: a single grid carries every
// panel so their column edges line up (strip over watch/regime over the
// performance row) — the fix for the "scattered/draggable" look. Reading order
// top→bottom: market context → watchlist/regime → book/performance/edge.
// (Finviz plan Task 13: Fresh Setups deleted — the Action Center's Fresh S-tier
// group and the Screener grid carry that job; the scan-freshness statement
// moved into the Action Center header.) Each panel owns its own status +
// ErrorBoundary so one dead source degrades only itself.
export default function HomeView({ trades, stats, riskFor, riskStatus, scanStatus }) {
  const { screenerData, status: screenerStatus } = useScreenerData();
  // Cheap 5-minute freshness tick: polls the slim /screener-summary and only
  // re-downloads the full 13MB artifact when a new scan actually landed.
  usePollingInterval(revalidateScreenerUniverse, 300000, { immediate: false });
  // ONE watchlist live-price poll for the whole Home surface; both the Action
  // Center and the Watchlist zone read this same map (was a duplicate poller each).
  const { prices, priceErr, priceStatus } = useLivePrices();
  const marketContext = screenerData?.market_context;

  return (
    <div className="home-view">
      <ErrorBoundary>
        <ActionCenter
          screenerData={screenerData}
          trades={trades}
          riskFor={riskFor}
          prices={prices}
          scanStatus={scanStatus}
          riskStatus={riskStatus}
          priceStatus={priceStatus}
          screenerStatus={screenerStatus}
        />
      </ErrorBoundary>

      <div className="home-grid">
        <div className="ga-pulse"><ErrorBoundary><MarketPulse marketContext={marketContext} /></ErrorBoundary></div>
        <div className="ga-watch"><WatchlistZone screenerData={screenerData} prices={prices} priceErr={priceErr} /></div>
        <div className="ga-regime"><ErrorBoundary><RegimePanel marketContext={marketContext} /></ErrorBoundary></div>
        <div className="ga-book"><OpenBookZone trades={trades} riskFor={riskFor} status={riskStatus} /></div>
        <div className="ga-journal"><JournalPulseZone stats={stats} trades={trades} /></div>
        <div className="ga-edge"><EdgePulse /></div>
      </div>
    </div>
  );
}
