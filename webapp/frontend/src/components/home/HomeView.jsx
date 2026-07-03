import ErrorBoundary from '../ErrorBoundary';
import MarketPulse from '../MarketPulse';
import RegimePanel from '../RegimePanel';
import ActionCenter from './ActionCenter';
import FreshSetupsZone from './FreshSetupsZone';
import WatchlistZone from './WatchlistZone';
import OpenBookZone from './OpenBookZone';
import JournalPulseZone from './JournalPulseZone';
import EdgePulse from './EdgePulse';
import usePollingInterval from '../../hooks/usePollingInterval';
import useScreenerData from '../../hooks/useScreenerData';
import { revalidateScreenerUniverse } from '../../hooks/screenerStore';

// The orient surface as one aligned dashboard: a single grid carries every
// panel so their column edges line up (chart+regime over the tile row over the
// performance row) — the fix for the "scattered/draggable" look. Reading order
// top→bottom: market context → ideas/watch/open risk → performance/edge.
// Regime + Fresh Setups read ONE scan source so they can't desync; each panel
// owns its own status + ErrorBoundary so one dead source degrades only itself.
export default function HomeView({ trades, stats, riskFor, riskStatus, scanStatus }) {
  const { screenerData } = useScreenerData();
  // Cheap 5-minute freshness tick: polls the slim /screener-summary and only
  // re-downloads the full 13MB artifact when a new scan actually landed.
  usePollingInterval(revalidateScreenerUniverse, 300000, { immediate: false });
  const marketContext = screenerData?.market_context;

  return (
    <div className="home-view">
      <ErrorBoundary>
        <ActionCenter screenerData={screenerData} trades={trades} riskFor={riskFor} />
      </ErrorBoundary>

      <div className="home-grid">
        <div className="ga-pulse"><ErrorBoundary><MarketPulse marketContext={marketContext} /></ErrorBoundary></div>
        <div className="ga-regime"><ErrorBoundary><RegimePanel marketContext={marketContext} /></ErrorBoundary></div>
        <div className="ga-fresh"><FreshSetupsZone screenerData={screenerData} scanStatus={scanStatus} /></div>
        <div className="ga-watch"><WatchlistZone screenerData={screenerData} /></div>
        <div className="ga-book"><OpenBookZone trades={trades} riskFor={riskFor} status={riskStatus} /></div>
        <div className="ga-journal"><JournalPulseZone stats={stats} trades={trades} /></div>
        <div className="ga-edge"><EdgePulse /></div>
      </div>
    </div>
  );
}
