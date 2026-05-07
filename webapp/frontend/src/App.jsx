import React, { useState, useEffect, useMemo } from 'react';
import DashboardStats from './components/DashboardStats';
import TradeTable from './components/TradeTable';
import LogTradeForm from './components/LogTradeForm';
import PositionCalculator from './components/PositionCalculator';
import ScreenerGrid from './components/ScreenerGrid';
import ErrorBoundary from './components/ErrorBoundary';
import EditTradeModal from './components/EditTradeModal';
import PortfolioTab from './components/PortfolioTab';
import AnalyticsPanel from './components/AnalyticsPanel';
import ArchiveTab from './components/ArchiveTab';
import TradeDetailDrawer from './components/TradeDetailDrawer';
import useIBKRStatus from './hooks/useIBKRStatus';
import useIBKRAccountSummary from './hooks/useIBKRAccountSummary';
import { API_BASE } from './api';
import logoUrl from './assets/4114b5469d3aaf9d583d8ad081a8d178.jpg';

const fmtMoney = (v) => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

function App() {
  const ibkrStatus = useIBKRStatus(10000);
  const isLive = ibkrStatus?.mode === 'live';
  const isGateway = ibkrStatus?.client === 'gateway';
  const isConnected = !!ibkrStatus?.connected;
  const acct = useIBKRAccountSummary(isConnected);

  const [activeTab, setActiveTab] = useState('dashboard');

  const [trades, setTrades] = useState([]);
  const [stats, setStats] = useState(null);

  const [isTradeModalOpen, setTradeModalOpen] = useState(false);
  const [isCalcModalOpen, setCalcModalOpen] = useState(false);
  const [editingTrade, setEditingTrade] = useState(null);
  const [detailTrade, setDetailTrade] = useState(null);
  const [switchingMode, setSwitchingMode] = useState(false);
  const [switchingClient, setSwitchingClient] = useState(false);

  // null = no filter; 'wins' | 'losses' | 'open' | 'wash'
  const [tradeFilter, setTradeFilter] = useState(null);

  const toggleIbkrMode = async () => {
    if (switchingMode) return;
    const next = isLive ? 'paper' : 'live';
    if (next === 'live') {
      const livePort = isGateway ? 4001 : 7496;
      const livePeer = isGateway ? 'IB Gateway' : 'TWS';
      const ok = window.confirm(
        'Switch to LIVE trading mode?\n\n' +
        `This connects to your real-money IBKR account on port ${livePort}. ` +
        `Make sure ${livePeer} is logged into the live account.`,
      );
      if (!ok) return;
    }
    setSwitchingMode(true);
    try {
      const res = await fetch(`${API_BASE}/ibkr/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: next, confirm: true }),
      });
      if (!res.ok) {
        const body = await res.text();
        alert(`Mode switch failed: ${body}`);
      }
    } catch (err) {
      alert(`Mode switch error: ${err.message || err}`);
    } finally {
      setSwitchingMode(false);
    }
  };

  const toggleIbkrClient = async () => {
    if (switchingClient) return;
    const next = isGateway ? 'tws' : 'gateway';
    setSwitchingClient(true);
    try {
      const res = await fetch(`${API_BASE}/ibkr/client`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client: next }),
      });
      if (!res.ok) {
        const body = await res.text();
        alert(`Client switch failed: ${body}`);
      }
    } catch (err) {
      alert(`Client switch error: ${err.message || err}`);
    } finally {
      setSwitchingClient(false);
    }
  };

  const filteredTrades = useMemo(() => {
    if (!tradeFilter) return trades;
    return trades.filter(t => {
      const closed = t.pnl !== null && t.pnl !== undefined;
      if (tradeFilter === 'open') return !closed;
      if (tradeFilter === 'wins') return closed && t.pnl > 0;
      if (tradeFilter === 'losses') return closed && t.pnl < 0;
      if (tradeFilter === 'wash') return closed && t.pnl === 0;
      return true;
    });
  }, [trades, tradeFilter]);

  const fetchDashboardData = async () => {
    try {
      const tradesRes = await fetch(`${API_BASE}/trades/`);
      if (tradesRes.ok) {
        const tradesData = await tradesRes.json();
        setTrades(tradesData);
      }
      
      const statsRes = await fetch(`${API_BASE}/journal-stats/`);
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleTradeSaved = () => {
    setTradeModalOpen(false);
    fetchDashboardData();
  };

  const handleTradeEdited = () => {
    setEditingTrade(null);
    fetchDashboardData();
  };

  return (
    <div className="app-layout">
      {/* SIDEBAR */}
      <aside className="sidebar">
        <div className="brand" style={{gap: '12px', fontSize: '1.4rem', letterSpacing: '2px', textTransform: 'uppercase', marginBottom: '0.8rem'}}>
          <img src={logoUrl} alt="Chrollo" style={{ width: 32, height: 32, borderRadius: 6, objectFit: 'cover' }} />
          Chrollo
        </div>

        <div style={{ padding: '0 1.5rem', marginBottom: '1.5rem', display: 'flex', gap: '8px' }}>
          <button
            type="button"
            onClick={toggleIbkrClient}
            disabled={switchingClient}
            title={
              switchingClient ? 'Switching…' :
              isGateway ? `Click to switch to TWS (${isLive ? 7496 : 7497})`
                        : `Click to switch to IB Gateway (${isLive ? 4001 : 4002})`
            }
            style={{
              fontSize: '9px',
              fontWeight: 700,
              letterSpacing: '1px',
              padding: '3px 8px',
              borderRadius: 'var(--radius-pill, 999px)',
              background: 'rgba(255,255,255,0.08)',
              color: 'var(--text-muted)',
              border: '1px solid var(--border-color)',
              cursor: switchingClient ? 'wait' : 'pointer',
              opacity: switchingClient ? 0.6 : 1,
              fontFamily: 'inherit',
            }}
          >
            {switchingClient ? '…' : (isGateway ? 'GATEWAY' : 'TWS')}
          </button>
          <button
            type="button"
            onClick={toggleIbkrMode}
            disabled={switchingMode}
            title={
              switchingMode ? 'Switching…' :
              isLive ? `Click to switch to PAPER (port ${isGateway ? 4002 : 7497})`
                     : `Click to switch to LIVE — real money (port ${isGateway ? 4001 : 7496})`
            }
            style={{
              fontSize: '9px',
              fontWeight: 700,
              letterSpacing: '1px',
              padding: '3px 8px',
              borderRadius: 'var(--radius-pill, 999px)',
              background: isLive ? 'var(--danger)' : 'rgba(255,255,255,0.08)',
              color: isLive ? '#fff' : 'var(--text-muted)',
              border: isLive ? '1px solid var(--danger)' : '1px solid var(--border-color)',
              boxShadow: isLive ? '0 0 10px rgba(229,72,77,0.5)' : 'none',
              cursor: switchingMode ? 'wait' : 'pointer',
              opacity: switchingMode ? 0.6 : 1,
              fontFamily: 'inherit',
            }}
          >
            {switchingMode ? '…' : (isLive ? 'LIVE' : 'PAPER')}
          </button>
        </div>

        <div className="account-info">
          {isConnected ? (
            <>
              <div style={{color: 'var(--text-muted)', fontSize: '11px', marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: 6}}>
                <span style={{width: 6, height: 6, borderRadius: '50%', background: 'var(--success)'}} />
                Net Liquidation
              </div>
              <div style={{fontSize: '1.2rem', fontWeight: '700', color: '#fff'}}>${fmtMoney(acct.values?.NetLiquidation)}</div>
              <div style={{fontSize: '10px', color: 'var(--text-muted)'}}>Cash: ${fmtMoney(acct.values?.TotalCashValue)}</div>
              <div style={{fontSize: '10px', color: 'var(--accent-blue)'}}>Buying Power: ${fmtMoney(acct.values?.BuyingPower)}</div>
            </>
          ) : ibkrStatus?.session_competition ? (
            <>
              <div style={{color: 'var(--danger)', fontSize: '11px', marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: 6}}>
                <span style={{width: 6, height: 6, borderRadius: '50%', background: 'var(--danger)'}} />
                Session Conflict
              </div>
              <div style={{fontSize: '1.2rem', fontWeight: '700', color: '#fff', opacity: 0.7}}>${fmtMoney(acct.values?.NetLiquidation)}</div>
              <div style={{fontSize: '10px', color: 'var(--danger)'}}>Another platform has the session</div>
            </>
          ) : ibkrStatus?.daily_restart ? (
            <>
              <div style={{color: 'var(--accent-blue)', fontSize: '11px', marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: 6}}>
                <span style={{width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-blue)', animation: 'pulse-subtle 2s ease-in-out infinite'}} />
                Daily Restart
              </div>
              <div style={{fontSize: '1.2rem', fontWeight: '700', color: '#fff'}}>${fmtMoney(acct.values?.NetLiquidation)}</div>
              <div style={{fontSize: '10px', color: 'var(--accent-blue)'}}>Gateway restarting — data will resume</div>
            </>
          ) : ibkrStatus?.stale && acct.values?.NetLiquidation ? (
            <>
              <div style={{color: 'var(--accent-yellow, #ca9f3c)', fontSize: '11px', marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: 6}}>
                <span style={{width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-yellow, #ca9f3c)'}} />
                Reconnecting…
              </div>
              <div style={{fontSize: '1.2rem', fontWeight: '700', color: '#fff', opacity: 0.8}}>${fmtMoney(acct.values?.NetLiquidation)}</div>
              <div style={{fontSize: '10px', color: 'var(--accent-yellow, #ca9f3c)'}}>Last known · reconnecting…</div>
            </>
          ) : (
            <>
              <div style={{color: 'var(--text-muted)', fontSize: '11px', marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: 6}}>
                <span style={{width: 6, height: 6, borderRadius: '50%', background: 'var(--text-muted)'}} />
                Journal P&L
              </div>
              <div style={{fontSize: '1.2rem', fontWeight: '700', color: '#fff'}}>${stats ? stats.total_pnl.toFixed(2) : "0.00"}</div>
              <div style={{fontSize: '10px', color: 'var(--text-muted)'}}>IBKR disconnected</div>
            </>
          )}
        </div>

        <nav className="nav-menu">
          <div className={`nav-link ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}>Dashboard</div>
          <div className={`nav-link ${activeTab === 'portfolio' ? 'active' : ''}`} onClick={() => setActiveTab('portfolio')}>Portfolio</div>
          <div className={`nav-link ${activeTab === 'screener' ? 'active' : ''}`} onClick={() => setActiveTab('screener')}>Screener Grid</div>
          <div className={`nav-link ${activeTab === 'archive' ? 'active' : ''}`} onClick={() => setActiveTab('archive')}>Setup Archive</div>
          <div className="nav-link" onClick={() => setCalcModalOpen(true)}>Calculator</div>
        </nav>

        <div className="action-buttons">
          <button className="btn-action btn-trade" onClick={() => setTradeModalOpen(true)}><span>+</span> New Trade</button>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <main className="main-content">
        <header className="topbar" style={{justifyContent: 'space-between'}}>
          <div style={{color: 'var(--text-muted)', fontSize: '14px', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '1px'}}>
            {activeTab === 'dashboard' ? 'Trading Journal Analytics'
              : activeTab === 'portfolio' ? 'Live IBKR Portfolio'
              : activeTab === 'archive' ? 'Setup Archive & Calibration'
              : 'Wyckoff Screener Scans'}
          </div>
          <div style={{display: 'flex', gap: '1rem', alignItems: 'center'}}>
             {activeTab === 'dashboard' && <span style={{color: 'var(--text-muted)'}}>{trades.length} trades loaded.</span>}
             <span style={{cursor: 'pointer'}}>🔔</span>
             <span style={{background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-pink))', borderRadius: '50%', width:'24px', height:'24px', cursor: 'pointer', boxShadow: '0 2px 4px rgba(0,0,0,0.2)'}}></span>
          </div>
        </header>

        <div className="content-scroll">
          {activeTab === 'dashboard' && (
            <>
              <DashboardStats
                stats={stats}
                trades={trades}
                activeFilter={tradeFilter}
                onFilterChange={setTradeFilter}
              />
              <TradeTable
                trades={filteredTrades}
                onEditClick={(trade) => setEditingTrade(trade)}
                onDetailClick={(trade) => setDetailTrade(trade)}
              />
              <ErrorBoundary>
                <AnalyticsPanel />
              </ErrorBoundary>
            </>
          )}
          {activeTab === 'portfolio' && (
            <ErrorBoundary>
              <PortfolioTab key="portfolio" />
            </ErrorBoundary>
          )}
          {activeTab === 'screener' && (
            <ErrorBoundary>
              <ScreenerGrid key="screener" />
            </ErrorBoundary>
          )}
          {activeTab === 'archive' && (
            <ErrorBoundary>
              <ArchiveTab key="archive" />
            </ErrorBoundary>
          )}
        </div>
      </main>

      {/* MODALS */}
      {isTradeModalOpen && (
        <div className="modal-overlay" onClick={() => setTradeModalOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 style={{fontSize: '1.2rem', margin: 0}}>Log New Trade</h2>
              <button className="modal-close" onClick={() => setTradeModalOpen(false)}>×</button>
            </div>
            <LogTradeForm onSave={handleTradeSaved} />
          </div>
        </div>
      )}

      {isCalcModalOpen && (
        <div className="modal-overlay" onClick={() => setCalcModalOpen(false)}>
          <div className="modal-content" style={{maxWidth: '600px'}} onClick={e => e.stopPropagation()}>
             <div className="modal-header">
              <h2 style={{fontSize: '1.2rem', margin: 0}}>Position Size Utility</h2>
              <button className="modal-close" onClick={() => setCalcModalOpen(false)}>×</button>
            </div>
            <PositionCalculator />
          </div>
        </div>
      )}

      {editingTrade && (
        <EditTradeModal
          trade={editingTrade}
          onClose={() => setEditingTrade(null)}
          onSave={handleTradeEdited}
        />
      )}

      {detailTrade && (
        <TradeDetailDrawer
          trade={detailTrade}
          onClose={() => setDetailTrade(null)}
        />
      )}
    </div>
  );
}

export default App;
