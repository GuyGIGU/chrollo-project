import { lazy, Suspense, useCallback, useMemo, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import AppTopbar from './AppTopbar';
import ErrorBoundary from '../../shared/components/ErrorBoundary';
import FeedbackHost from './FeedbackHost';
import { toast } from '../../shared/components/feedback';
import TradeRiskAlerts from '../../features/journal/components/tradeTable/TradeRiskAlerts';
import useDashboardData from '../../features/journal/hooks/useDashboardData';
import useIBKRStatus from '../../features/ibkr/hooks/useIBKRStatus';
import useIbkrActions from '../../features/ibkr/hooks/useIbkrActions';
import useLiveRisk from '../../features/journal/hooks/useLiveRisk';
import usePortfolioSnapshot from '../../features/portfolio/hooks/usePortfolioSnapshot';
import useScanHistory from '../../features/screener/hooks/useScanHistory';
import { API_BASE } from '../../api/base';
import logoUrl from '../../assets/4114b5469d3aaf9d583d8ad081a8d178.jpg';
import { buildHealthPill, buildScanStatusText } from '../../shared/formatting/appFormat';
import { confirmLeaveWithDialog } from '../../shared/navigation/leaveGuard';
import { deriveTradeAlerts } from '../../features/journal/model/tradeTableUtils';
import { isOptionSymbol } from '../../features/journal/model/tradeUtils';

const CalculatorModal = lazy(() => import('../../features/journal/components/CalculatorModal'));
const TradeDetailDrawer = lazy(() => import('../../features/journal/components/TradeDetailDrawer'));
const ScanHistoryModal = lazy(() => import('../../features/screener/components/ScanHistoryModal'));

const ModalFallback = () => null;

// Map the current path to the in-app tab key the topbar/title helpers expect.
const tabFromPath = (pathname) => {
  if (pathname === '/' || pathname.startsWith('/home')) return 'home';
  if (pathname.startsWith('/dashboard')) return 'dashboard';
  if (pathname.startsWith('/options')) return 'options';
  if (pathname.startsWith('/portfolio')) return 'portfolio';
  if (pathname.startsWith('/archive')) return 'archive';
  if (pathname.startsWith('/calibration')) return 'calibration';
  if (pathname.startsWith('/screener')) return 'screener';
  return 'home';
};

// AppShell owns the persistent frame (top nav bar + risk-alert strip) and all
// cross-cutting state that outlives any single route: the trade-detail drawer,
// the calculator modal, the draft trade row, the trade filter, CSV import, and
// the dashboard/IBKR/live-price hooks. Routes render in the Outlet and read what
// they need through outlet context. The active nav highlight is derived from the
// URL (NavLink in AppTopbar), so there is one source of truth for "where am I".
function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const activeTab = tabFromPath(location.pathname);

  const ibkrStatus = useIBKRStatus(10000);
  const ibkrActions = useIbkrActions(ibkrStatus);
  const { trades, stats, scanStatus, health, fetchDashboardData } = useDashboardData();
  // One scan-run diagnostics registry for the whole app: the topbar status
  // pills open it, and the Archive header's Scan History button opens the same
  // instance through outlet context.
  const scanHistory = useScanHistory();

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

  const { riskFor, summary: riskSummary, status: riskStatus } = useLiveRisk(trades, Boolean(ibkrStatus?.connected));
  const riskAlerts = useMemo(
    () => deriveTradeAlerts(trades, riskFor),
    [riskFor, trades],
  );

  // "+ New trade" navigates, so it is an exit out of the current route and must
  // ask the same question the top nav asks — it sits inches from the nav tabs on
  // every page, calibration included, and shipped as a silent discard of
  // hand-drawn marks (council review 2026-09-07, A2). Asked only when it really
  // does navigate: from the journal itself it just opens a draft row.
  const startNewTrade = async () => {
    if (activeTab !== 'dashboard') {
      if (!(await confirmLeaveWithDialog())) return;
      navigate('/dashboard');
    }
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
        toast(`Import failed: ${body.detail || res.statusText}`, { tone: 'danger' });
      } else {
        toast(
          `Imported ${body.imported} new fills (${body.skipped} duplicates skipped` +
          `${body.matched_live ? `, ${body.matched_live} matched live fills` : ''}).\n` +
          `Trade logs rebuilt for ${body.trade_logs_rebuilt} symbols.`,
          { tone: 'success' },
        );
        fetchDashboardData();
      }
    } catch (error) {
      toast(`Import error: ${error.message || error}`, { tone: 'danger' });
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
    // Single-owner IBKR status/actions: the shell polls /ibkr/status once for
    // the whole app; routes read these instead of mounting their own poller.
    ibkrStatus,
    ibkrActions,
    onOpenScanRegistry: scanHistory.openHistory,
  };

  return (
    <div className="app-layout">
      <AppTopbar
        healthPill={healthPill}
        scanStatus={scanStatus}
        scanStatusText={scanStatusText}
        ibkrStatus={ibkrStatus}
        ibkrActions={ibkrActions}
        logoUrl={logoUrl}
        onOpenCalculator={() => setCalcModalOpen(true)}
        onOpenScanRegistry={scanHistory.openHistory}
        onNewTrade={startNewTrade}
        csvInputRef={csvInputRef}
        importingCsv={importingCsv}
        onCsvImport={handleCsvImport}
      />

      <main className="main-content">
        <ErrorBoundary>
          <div className="content-scroll">
            <TradeRiskAlerts alerts={riskAlerts} trades={trades} onDetailClick={setDetailTrade} />
            <Outlet context={outletContext} />
          </div>
        </ErrorBoundary>
      </main>

      <FeedbackHost />

      <ErrorBoundary>
        <Suspense fallback={<ModalFallback />}>
          {isCalcModalOpen && <CalculatorModal onClose={() => setCalcModalOpen(false)} />}
          {scanHistory.open && (
            <ScanHistoryModal
              health={health}
              loading={scanHistory.loading}
              notice={scanHistory.notice}
              onClose={scanHistory.closeHistory}
              open={scanHistory.open}
              runs={scanHistory.runs}
            />
          )}
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
