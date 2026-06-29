import ErrorBoundary from '../ErrorBoundary';
import MarketPulse from '../MarketPulse';
import RegimePanel from '../RegimePanel';
import FreshSetupsZone from './FreshSetupsZone';
import WatchlistZone from './WatchlistZone';
import OpenBookZone from './OpenBookZone';
import JournalPulseZone from './JournalPulseZone';
import EdgePulse from './EdgePulse';
import usePollingInterval from '../../hooks/usePollingInterval';
import useScreenerData from '../../hooks/useScreenerData';

// The orient surface as one aligned dashboard: a single grid carries every
// panel so their column edges line up (chart+regime over the tile row over the
// performance row) — the fix for the "scattered/draggable" look. Reading order
// top→bottom: market context → ideas/watch/open risk → performance/edge.
// Regime + Fresh Setups read ONE scan source so they can't desync; each panel
// owns its own status + ErrorBoundary so one dead source degrades only itself.
export default function HomeView({ trades, stats, priceFor, scanStatus }) {
  const { screenerData, fetchScreener } = useScreenerData();
  usePollingInterval(fetchScreener, 300000, { immediate: false });
  const marketContext = screenerData?.market_context;

  return (
    <div className="home-view">
      <div className="home-grid">
        <div className="ga-pulse"><ErrorBoundary><MarketPulse marketContext={marketContext} /></ErrorBoundary></div>
        <div className="ga-regime"><ErrorBoundary><RegimePanel marketContext={marketContext} /></ErrorBoundary></div>
        <div className="ga-fresh"><FreshSetupsZone screenerData={screenerData} scanStatus={scanStatus} /></div>
        <div className="ga-watch"><WatchlistZone screenerData={screenerData} /></div>
        <div className="ga-book"><OpenBookZone trades={trades} priceFor={priceFor} /></div>
        <div className="ga-journal"><JournalPulseZone stats={stats} trades={trades} /></div>
        <div className="ga-edge"><EdgePulse /></div>
      </div>
    </div>
  );
}
