import { lazy, Suspense, useCallback, useMemo, useRef, useState } from 'react';
import AppContent from './components/AppContent';
import AppSidebar from './components/AppSidebar';
import AppTopbar from './components/AppTopbar';
import ErrorBoundary from './components/ErrorBoundary';
import useDashboardData from './hooks/useDashboardData';
import useIBKRStatus from './hooks/useIBKRStatus';
import useIbkrActions from './hooks/useIbkrActions';
import { API_BASE } from './api';
import logoUrl from './assets/4114b5469d3aaf9d583d8ad081a8d178.jpg';
import { buildHealthPill, buildScanStatusText } from './utils/appFormat';
import { isOptionSymbol } from './utils/tradeUtils';

const CalculatorModal = lazy(() => import('./components/CalculatorModal'));
const TradeDetailDrawer = lazy(() => import('./components/TradeDetailDrawer'));

const ModalFallback = () => null;

function App() {
  const ibkrStatus = useIBKRStatus(10000);
  const ibkrActions = useIbkrActions(ibkrStatus);
  const { trades, stats, scanStatus, health, fetchDashboardData } = useDashboardData();

  const [activeTab, setActiveTab] = useState('screener');
  const [tradeFilter, setTradeFilter] = useState(null);
  const [isCalcModalOpen, setCalcModalOpen] = useState(false);
  const [draftRow, setDraftRow] = useState(null);
  const [detailTrade, setDetailTrade] = useState(null);
  const [importingCsv, setImportingCsv] = useState(false);
  const csvInputRef = useRef(null);

  const sortedTrades = useMemo(() => sortTrades(trades), [trades]);
  const stockTrades = useMemo(
    () => sortedTrades.filter(trade => !isOptionSymbol(trade.ticker)),
    [sortedTrades],
  );
  const optionTrades = useMemo(
    () => sortedTrades.filter(trade => isOptionSymbol(trade.ticker)),
    [sortedTrades],
  );
  const filteredTrades = useMemo(
    () => filterTrades(stockTrades, tradeFilter),
    [stockTrades, tradeFilter],
  );
  const healthPill = useMemo(() => buildHealthPill(health), [health]);
  const scanStatusText = useMemo(() => buildScanStatusText(scanStatus), [scanStatus]);

  const startNewTrade = () => {
    if (activeTab !== 'dashboard') setActiveTab('dashboard');
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
        const failed = Number(body.trade_logs_failed || 0);
        alert(
          `Imported ${body.imported} new fills (${body.skipped} duplicates skipped).\n` +
          `Trade logs rebuilt for ${body.trade_logs_rebuilt} symbols.` +
          (failed ? `\nWarning: ${failed} symbols need attention.` : ''),
        );
        fetchDashboardData();
      }
    } catch (error) {
      alert(`Import error: ${error.message || error}`);
    } finally {
      setImportingCsv(false);
    }
  };

  return (
    <div className="app-layout">
      <AppSidebar
        logoUrl={logoUrl}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onOpenCalculator={() => setCalcModalOpen(true)}
        onNewTrade={startNewTrade}
        csvInputRef={csvInputRef}
        importingCsv={importingCsv}
        onCsvImport={handleCsvImport}
        ibkrStatus={ibkrStatus}
        ibkrActions={ibkrActions}
      />

      <main className="main-content">
        <AppTopbar
          activeTab={activeTab}
          healthPill={healthPill}
          scanStatus={scanStatus}
          scanStatusText={scanStatusText}
          stockTradeCount={stockTrades.length}
          optionTradeCount={optionTrades.length}
        />
        <ErrorBoundary>
          <AppContent
            activeTab={activeTab}
            stats={stats}
            trades={trades}
            tradeFilter={tradeFilter}
            onTradeFilterChange={setTradeFilter}
            filteredTrades={filteredTrades}
            optionTrades={optionTrades}
            draftRow={draftRow}
            setDraftRow={setDraftRow}
            onDetailClick={setDetailTrade}
            onTradeUpdate={fetchDashboardData}
          />
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

function filterTrades(trades, tradeFilter) {
  if (!tradeFilter) return trades;
  return trades.filter(trade => {
    const closed = trade.pnl !== null && trade.pnl !== undefined;
    if (tradeFilter === 'open') return !closed;
    if (tradeFilter === 'wins') return closed && trade.pnl > 0;
    if (tradeFilter === 'losses') return closed && trade.pnl < 0;
    if (tradeFilter === 'wash') return closed && trade.pnl === 0;
    return true;
  });
}

export default App;
