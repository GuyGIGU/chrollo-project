import { lazy, Suspense, useCallback, useMemo, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import AppSidebar from './AppSidebar';
import AppTopbar from './AppTopbar';
import ErrorBoundary from './ErrorBoundary';
import TradeRiskAlerts from './tradeTable/TradeRiskAlerts';
import useDashboardData from '../hooks/useDashboardData';
import useIBKRStatus from '../hooks/useIBKRStatus';
import useIbkrActions from '../hooks/useIbkrActions';
import useLiveRisk from '../hooks/useLiveRisk';
import usePortfolioSnapshot from '../hooks/usePortfolioSnapshot';
import { API_BASE } from '../api';
import logoUrl from '../assets/4114b5469d3aaf9d583d8ad081a8d178.jpg';
import { buildHealthPill, buildScanStatusText } from '../utils/appFormat';
import { deriveTradeAlerts } from '../utils/tradeTableUtils';
import { isOptionSymbol } from '../utils/tradeUtils';

const CalculatorModal = lazy(() => import('./CalculatorModal'));
const TradeDetailDrawer = lazy(() => import('./TradeDetailDrawer'));

const ModalFallback = () => null;

// Map the current path to the in-app tab key the topbar/title helpers expect.
const tabFromPath = (pathname) => {
  if (pathname === '/' || pathname.startsWith('/home')) return 'home';
  if (pathname.startsWith('/dashboard')) return 'dashboard';
  if (pathname.startsWith('/options')) return 'options';
  if (pathname.startsWith('/portfolio')) return 'portfolio';
  if (pathname.startsWith('/archive')) return 'archive';
  if (pathname.startsWith('/screener')) return 'screener';
  return 'home';
};

// AppShell owns the persistent frame (sidebar + topbar + risk-alert strip) and
// all cross-cutting state that outlives any single route: the trade-detail
// drawer, the calculator modal, the draft trade row, the trade filter, CSV
// import, and the dashboard/IBKR/live-price hooks. Routes render in the Outlet
// and read what they need through outlet context. The active nav highlight is
// derived from the URL (NavLink in AppSidebar), so there is one source of truth
// for "where am I".
function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const activeTab = tabFromPath(location.pathname);

  const ibkrStatus = useIBKRStatus(10000);
  const ibkrActions = useIbkrActions(ibkrStatus);
  const { trades, stats, scanStatus, health, fetchDashboardData } = useDashboardData();

  const [tradeFilter, setTradeFilter] = useState(null);
  const [isCalcModalOpen, setCalcModalOpen] = useState(false);
  const [draftRow, setDraftRow] = useState(null);
  const [detailTrade, setDetailTrade] = useState(null);
  const [importingCsv, setImportingCsv] = useState(false);
  const csvInputRef = useRef(null);

  // Single portfolio-SSE owner for the trade-detail drawer's Broker link +
  // portfolio-risk-%. Threaded to the drawer via props so the drawer no longer
  // opens its own /stream/portfolio EventSource. Gated on IBKR-available AND a
  // drawer being open, preserving the exact stream lifecycle the drawer had when
  // it mounted the snapshot itself (only while rendered, only when available).
  const { snapshot: portfolioSnapshot } = usePortfolioSnapshot(
    Boolean(ibkrStatus?.available) && Boolean(detailTrade),
  );

  const sortedTrades = useMemo(() => sortTrades(trades), [trades]);
  const stockTrades = useMemo(
    () => sortedTrades.filter(trade => !isOptionSymbol(trade.ticker)),
    [sortedTrades],
  );
  const optionTrades = useMemo(
    () => sortedTrades.filter(trade => isOptionSymbol(trade.ticker)),
    [sortedTrades],
  );
  const healthPill = useMemo(() => buildHealthPill(health), [health]);
  const scanStatusText = useMemo(() => buildScanStatusText(scanStatus), [scanStatus]);

  const { riskFor, summary: riskSummary, status: riskStatus } = useLiveRisk(trades);
  const riskAlerts = useMemo(
    () => deriveTradeAlerts(trades, riskFor),
    [riskFor, trades],
  );

  const startNewTrade = () => {
    if (activeTab !== 'dashboard') navigate('/dashboard');
    setDraftRow({
      opening_date: new Date().toISOString().split('T')[0],
      direction: 'LONG',
      ticker: '',
      entry_price: '',
      stop_loss: '',
      quantity: '',
    });
  };

  const handleTradeUpdated = useCallback((updatedTrade) => {
    if (updatedTrade?.id) setDetailTrade(updatedTrade);
    fetchDashboardData();
  }, [fetchDashboardData]);

  const handleCsvImport = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setImportingCsv(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_BASE}/ibkr/import-csv`, { method: 'POST', body: form });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(`Import failed: ${body.detail || res.statusText}`);
      } else {
        alert(
          `Imported ${body.imported} new fills (${body.skipped} duplicates skipped` +
          `${body.matched_live ? `, ${body.matched_live} matched live fills` : ''}).\n` +
          `Trade logs rebuilt for ${body.trade_logs_rebuilt} symbols.`,
        );
        fetchDashboardData();
      }
    } catch (error) {
      alert(`Import error: ${error.message || error}`);
    } finally {
      setImportingCsv(false);
    }
  };

  const outletContext = {
    stats,
    trades,
    stockTrades,
    optionTrades,
    tradeFilter,
    onTradeFilterChange: setTradeFilter,
    draftRow,
    setDraftRow,
    onDetailClick: setDetailTrade,
    onTradeUpdate: fetchDashboardData,
    riskFor,
    riskSummary,
    riskStatus,
    scanStatus,
  };

  return (
    <div className="app-layout">
      <AppSidebar
        logoUrl={logoUrl}
        onOpenCalculator={() => setCalcModalOpen(true)}
        onNewTrade={startNewTrade}
        csvInputRef={csvInputRef}
        importingCsv={importingCsv}
        onCsvImport={handleCsvImport}
      />

      <main className="main-content">
        <AppTopbar
          activeTab={activeTab}
          healthPill={healthPill}
          scanStatus={scanStatus}
          scanStatusText={scanStatusText}
          stockTradeCount={stockTrades.length}
          optionTradeCount={optionTrades.length}
          ibkrStatus={ibkrStatus}
          ibkrActions={ibkrActions}
        />
        <ErrorBoundary>
          <div className="content-scroll">
            <TradeRiskAlerts alerts={riskAlerts} trades={trades} onDetailClick={setDetailTrade} />
            <Outlet context={outletContext} />
          </div>
        </ErrorBoundary>
      </main>

      <ErrorBoundary>
        <Suspense fallback={<ModalFallback />}>
          {isCalcModalOpen && <CalculatorModal onClose={() => setCalcModalOpen(false)} />}
          {detailTrade && (
            <TradeDetailDrawer
              key={detailTrade.id}
              trade={detailTrade}
              onClose={() => setDetailTrade(null)}
              onTradeUpdate={handleTradeUpdated}
              riskFor={riskFor}
              snapshot={portfolioSnapshot}
            />
          )}
        </Suspense>
      </ErrorBoundary>
    </div>
  );
}

function sortTrades(trades) {
  return [...trades].sort((a, b) => {
    const firstDate = a.opening_date || '';
    const secondDate = b.opening_date || '';
    if (firstDate !== secondDate) return firstDate < secondDate ? 1 : -1;
    return (b.id || 0) - (a.id || 0);
  });
}

export default AppShell;
