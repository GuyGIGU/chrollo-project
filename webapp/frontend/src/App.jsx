import React, { useState, useEffect, useMemo } from 'react';
import DashboardStats from './components/DashboardStats';
import TradeTable from './components/TradeTable';
import PositionCalculator from './components/PositionCalculator';
import ScreenerGrid from './components/ScreenerGrid';
import ErrorBoundary from './components/ErrorBoundary';
import PortfolioTab from './components/PortfolioTab';
import AnalyticsPanel from './components/AnalyticsPanel';
import ArchiveTab from './components/ArchiveTab';
import TradeDetailDrawer from './components/TradeDetailDrawer';
import useIBKRStatus from './hooks/useIBKRStatus';
import useIBKRAccountSummary from './hooks/useIBKRAccountSummary';
import { API_BASE } from './api';
import logoUrl from './assets/4114b5469d3aaf9d583d8ad081a8d178.jpg';

const fmtScanTime = (value) => {
  if (!value) return 'none';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return 'unknown';
  return dt.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const scanStatusColor = (status) => {
  if (status === 'ok') return 'var(--success)';
  if (status === 'running') return 'var(--accent-blue)';
  if (status === 'failed' || status === 'stale_data') return 'var(--danger)';
  return 'var(--text-muted)';
};

const navSections = [
  {
    label: 'Trading',
    items: [
      { key: 'portfolio', label: 'Portfolio' },
      { key: 'dashboard', label: 'Dashboard' },
      { key: 'options', label: 'Options' },
    ],
  },
  {
    label: 'Research',
    items: [
      { key: 'screener', label: 'Screener Grid' },
      { key: 'archive', label: 'Setup Archive' },
    ],
  },
];

const fmtMoney = (v) => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

// IBKR option symbols look like "AAPL 03JUN26 200 C" — space + DDMMMYY date + strike + C/P.
// Bare tickers ("AAPL") are stocks. This is the same format that comes through CSV import
// and live IBKR fills, so it works for both.
const OPTION_SYMBOL_RE = /^[A-Z.]+\s+\d{1,2}[A-Z]{3}\d{2}\s+[\d.]+\s+[CP]$/;
export const isOptionSymbol = (sym) => !!sym && OPTION_SYMBOL_RE.test(String(sym).trim());

// Direction in the DB is "L"/"S" for IBKR-imported trades and "LONG"/"SHORT" for manual.
// Falls back to inferring from the stop position relative to entry: stop below entry → LONG,
// stop above entry → SHORT. Returns 'LONG' as last resort.
export const inferDirection = (t) => {
  const d = String(t?.direction || '').toUpperCase();
  if (d === 'L' || d === 'LONG') return 'LONG';
  if (d === 'S' || d === 'SHORT') return 'SHORT';
  const entry = Number(t?.entry_price);
  const stop = Number(t?.stop_loss);
  if (Number.isFinite(entry) && Number.isFinite(stop) && stop !== 0) {
    return stop < entry ? 'LONG' : 'SHORT';
  }
  return 'LONG';
};

function App() {
  const ibkrStatus = useIBKRStatus(10000);
  const isLive = ibkrStatus?.mode === 'live';
  const isGateway = ibkrStatus?.client === 'gateway';
  const isConnected = !!ibkrStatus?.connected;
  const acct = useIBKRAccountSummary(isConnected);

  const [activeTab, setActiveTab] = useState('dashboard');
  const [scanStatus, setScanStatus] = useState(null);
  const [health, setHealth] = useState(null);

  const [trades, setTrades] = useState([]);
  const [stats, setStats] = useState(null);

  const [isCalcModalOpen, setCalcModalOpen] = useState(false);
  const [draftRow, setDraftRow] = useState(null);
  const [detailTrade, setDetailTrade] = useState(null);

  const todayIso = () => new Date().toISOString().split('T')[0];
  const startNewTrade = () => {
    if (activeTab !== 'dashboard') setActiveTab('dashboard');
    setDraftRow({
      opening_date: todayIso(),
      direction: 'LONG',
      ticker: '',
      entry_price: '',
      stop_loss: '',
      quantity: '',
    });
  };
  const [switchingMode, setSwitchingMode] = useState(false);
  const [switchingClient, setSwitchingClient] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);

  const reconnectIbkr = async () => {
    if (reconnecting) return;
    // Live mode is gated behind a deliberate human confirmation: the always-on
    // service is broker-free, so connecting hands your single IBKR API session
    // to Chrollo until you disconnect. Paper mode needs no confirmation.
    let confirm = false;
    if (isLive) {
      const livePort = isGateway ? 4001 : 7496;
      const livePeer = isGateway ? 'IB Gateway' : 'TWS';
      const ok = window.confirm(
        `Connect Chrollo to your LIVE real-money IBKR account on port ${livePort}?\n\n` +
        `This hands your single IBKR API session to Chrollo until you disconnect — ` +
        `make sure ${livePeer} is logged into the live account and TradingView isn't using it.`,
      );
      if (!ok) return;
      confirm = true;
    }
    setReconnecting(true);
    try {
      const res = await fetch(`${API_BASE}/ibkr/reconnect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm }),
      });
      if (!res.ok) {
        const body = await res.text();
        alert(`Reconnect failed: ${body}`);
      }
    } catch (err) {
      alert(`Reconnect error: ${err.message || err}`);
    } finally {
      setReconnecting(false);
    }
  };

  const disconnectIbkr = async () => {
    if (reconnecting) return;
    setReconnecting(true);
    try {
      const res = await fetch(`${API_BASE}/ibkr/disconnect`, { method: 'POST' });
      if (!res.ok) {
        const body = await res.text();
        alert(`Disconnect failed: ${body}`);
      }
    } catch (err) {
      alert(`Disconnect error: ${err.message || err}`);
    } finally {
      setReconnecting(false);
    }
  };

  // null = no filter; 'wins' | 'losses' | 'open' | 'wash'
  const [tradeFilter, setTradeFilter] = useState(null);

  const csvInputRef = React.useRef(null);
  const [importingCsv, setImportingCsv] = useState(false);

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
          `Imported ${body.imported} new fills (${body.skipped} duplicates skipped).\n` +
          `Trade logs rebuilt for ${body.trade_logs_rebuilt} symbols.`
        );
        fetchDashboardData();
      }
    } catch (err) {
      alert(`Import error: ${err.message || err}`);
    } finally {
      setImportingCsv(false);
    }
  };

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

  // Master sort: newest opening_date first, ties broken by id desc so a same-day
  // re-import keeps a stable order. Applied once here; downstream filters preserve it.
  const sortedTrades = useMemo(() => {
    return [...trades].sort((a, b) => {
      const da = a.opening_date || '';
      const db = b.opening_date || '';
      if (da !== db) return da < db ? 1 : -1;
      return (b.id || 0) - (a.id || 0);
    });
  }, [trades]);

  const stockTrades = useMemo(
    () => sortedTrades.filter(t => !isOptionSymbol(t.ticker)),
    [sortedTrades],
  );
  const optionTrades = useMemo(
    () => sortedTrades.filter(t => isOptionSymbol(t.ticker)),
    [sortedTrades],
  );

  const filteredTrades = useMemo(() => {
    if (!tradeFilter) return stockTrades;
    return stockTrades.filter(t => {
      const closed = t.pnl !== null && t.pnl !== undefined;
      if (tradeFilter === 'open') return !closed;
      if (tradeFilter === 'wins') return closed && t.pnl > 0;
      if (tradeFilter === 'losses') return closed && t.pnl < 0;
      if (tradeFilter === 'wash') return closed && t.pnl === 0;
      return true;
    });
  }, [stockTrades, tradeFilter]);

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

  const fetchScanStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/scan-status/latest`);
      if (res.ok) {
        setScanStatus(await res.json());
      }
    } catch (error) {
      console.error("Error fetching scan status:", error);
    }
  };

  const fetchHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        setHealth(await res.json());
      }
    } catch (error) {
      console.error("Error fetching health:", error);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    fetchScanStatus();
    fetchHealth();
    const scanStatusTimer = window.setInterval(fetchScanStatus, 60000);
    const healthTimer = window.setInterval(fetchHealth, 60000);
    return () => {
      window.clearInterval(scanStatusTimer);
      window.clearInterval(healthTimer);
    };
  }, []);

  // Health pill: green when all checks pass, amber when degraded, with a tooltip
  // naming the failing check(s). IBKR is informational and never degrades.
  const healthPill = useMemo(() => {
    if (!health) return null;
    const checks = health.checks || {};
    const failing = Object.entries(checks)
      .filter(([k, v]) => k !== 'ibkr' && v && v.ok === false)
      .map(([k, v]) => `${k}${v.detail ? `: ${v.detail}` : ''}`);
    const degraded = health.status !== 'ok';
    return {
      color: degraded ? 'var(--danger)' : 'var(--success)',
      label: degraded ? 'Degraded' : 'Healthy',
      title: failing.length ? `Degraded — ${failing.join('; ')}` : 'All systems OK',
    };
  }, [health]);

  const scanStatusText = useMemo(() => {
    if (!scanStatus || scanStatus.status === 'never') return 'Last scan: none';
    const when = fmtScanTime(scanStatus.finished_at || scanStatus.started_at);
    const count = Number.isFinite(Number(scanStatus.n_setups)) ? Number(scanStatus.n_setups) : 0;
    const label = scanStatus.status === 'stale_data' ? 'stale' : scanStatus.status;
    return `Last scan: ${when} | ${count} setups | ${label}`;
  }, [scanStatus]);

  return (
    <div className="app-layout">
      {/* SIDEBAR */}
      <aside className="sidebar">
        <div className="brand" style={{gap: '12px', fontSize: '1.4rem', letterSpacing: '2px', textTransform: 'uppercase', marginBottom: '0.8rem'}}>
          <img src={logoUrl} alt="Chrollo" style={{ width: 32, height: 32, borderRadius: 6, objectFit: 'cover' }} />
          <span className="brand-text">Chrollo</span>
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
              <div style={{fontSize: '10px', color: 'var(--accent-blue)', marginBottom: '6px'}}>Buying Power: ${fmtMoney(acct.values?.BuyingPower)}</div>
              <button
                type="button"
                onClick={disconnectIbkr}
                disabled={reconnecting}
                title="Release the IBKR API session so you can use it in TWS / TradingView."
                style={{
                  fontSize: '10px', fontWeight: 600, letterSpacing: '0.5px',
                  padding: '3px 10px', borderRadius: 'var(--radius-pill, 999px)',
                  background: 'transparent', color: 'var(--text-muted)',
                  border: '1px solid var(--border-color)',
                  cursor: reconnecting ? 'wait' : 'pointer',
                  opacity: reconnecting ? 0.6 : 1,
                  fontFamily: 'inherit',
                }}
              >
                Disconnect
              </button>
            </>
          ) : ibkrStatus?.session_competition ? (
            <>
              <div style={{color: 'var(--danger)', fontSize: '11px', marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: 6}}>
                <span style={{width: 6, height: 6, borderRadius: '50%', background: 'var(--danger)'}} />
                Session Conflict
              </div>
              <div style={{fontSize: '1.2rem', fontWeight: '700', color: '#fff', opacity: 0.7}}>${fmtMoney(acct.values?.NetLiquidation)}</div>
              <div style={{fontSize: '10px', color: 'var(--danger)', marginBottom: '6px'}}>Paused — TradingView/TWS has the session</div>
              <button
                type="button"
                onClick={reconnectIbkr}
                disabled={reconnecting}
                title="Force a fresh connection. Will bump whatever else is logged into IBKR with this username."
                style={{
                  fontSize: '10px', fontWeight: 600, letterSpacing: '0.5px',
                  padding: '3px 10px', borderRadius: 'var(--radius-pill, 999px)',
                  background: 'rgba(229,72,77,0.15)', color: 'var(--danger)',
                  border: '1px solid var(--danger)',
                  cursor: reconnecting ? 'wait' : 'pointer',
                  opacity: reconnecting ? 0.6 : 1,
                  fontFamily: 'inherit',
                }}
              >
                {reconnecting ? 'Reconnecting…' : 'Reconnect'}
              </button>
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
              <div style={{fontSize: '1.2rem', fontWeight: '700', color: '#fff'}}>${Number.isFinite(Number(stats?.total_pnl)) ? Number(stats.total_pnl).toFixed(2) : "0.00"}</div>
              <div style={{fontSize: '10px', color: 'var(--text-muted)', marginBottom: '6px'}}>IBKR disconnected</div>
              <button
                type="button"
                onClick={reconnectIbkr}
                disabled={reconnecting}
                title={isLive
                  ? 'Connect Chrollo to your live IBKR account for portfolio snapshots (read-only). You will confirm first.'
                  : 'Connect Chrollo to your paper IBKR account.'}
                style={{
                  fontSize: '10px', fontWeight: 600, letterSpacing: '0.5px',
                  padding: '3px 10px', borderRadius: 'var(--radius-pill, 999px)',
                  background: 'rgba(109,138,199,0.15)', color: 'var(--accent-blue)',
                  border: '1px solid var(--accent-blue)',
                  cursor: reconnecting ? 'wait' : 'pointer',
                  opacity: reconnecting ? 0.6 : 1,
                  fontFamily: 'inherit',
                }}
              >
                {reconnecting ? 'Connecting…' : '↻ Connect IBKR'}
              </button>
            </>
          )}
        </div>

        <nav className="nav-menu">
          {navSections.map(section => (
            <div className="nav-section" key={section.label}>
              <div className="nav-section-label">{section.label}</div>
              {section.items.map(item => (
                <button
                  type="button"
                  key={item.key}
                  className={`nav-link ${activeTab === item.key ? 'active' : ''}`}
                  onClick={() => setActiveTab(item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ))}
          <div className="nav-section">
            <div className="nav-section-label">Tools</div>
            <button type="button" className="nav-link" onClick={() => setCalcModalOpen(true)}>Calculator</button>
          </div>
        </nav>

        <div className="action-buttons">
          <button className="btn-action btn-trade" onClick={startNewTrade}><span>+</span> New Trade</button>
          <input
            ref={csvInputRef}
            type="file"
            accept=".csv,text/csv"
            style={{ display: 'none' }}
            onChange={handleCsvImport}
          />
          <button
            type="button"
            className="btn-action"
            disabled={importingCsv}
            onClick={() => csvInputRef.current?.click()}
            title="Upload an IBKR Activity Statement CSV (Performance & Reports → Activity → CSV) to bulk-import historical fills"
            style={{
              marginTop: '8px',
              background: 'transparent',
              border: '1px solid var(--border-color)',
              color: 'var(--text-muted)',
              fontSize: '11px',
              cursor: importingCsv ? 'wait' : 'pointer',
              opacity: importingCsv ? 0.6 : 1,
            }}
          >
            {importingCsv ? 'Importing…' : '⇪ Import IBKR CSV'}
          </button>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <main className="main-content">
        <header className="topbar" style={{justifyContent: 'space-between'}}>
          <div style={{color: 'var(--text-muted)', fontSize: '14px', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '1px'}}>
            {activeTab === 'dashboard' ? 'Trading Journal Analytics'
              : activeTab === 'options' ? 'Options Trades'
              : activeTab === 'portfolio' ? 'Live IBKR Portfolio'
              : activeTab === 'archive' ? 'Setup Archive & Calibration'
              : 'Wyckoff Screener Scans'}
          </div>
          <div style={{display: 'flex', gap: '1rem', alignItems: 'center', justifyContent: 'flex-end', flexWrap: 'wrap'}}>
             {healthPill && (
               <span
                 title={healthPill.title}
                 style={{
                   display: 'inline-flex', alignItems: 'center', gap: '5px',
                   fontSize: '12px', fontWeight: 600, whiteSpace: 'nowrap',
                   color: healthPill.color, cursor: 'default',
                 }}
               >
                 <span style={{ width: 7, height: 7, borderRadius: '50%', background: healthPill.color }} />
                 {healthPill.label}
               </span>
             )}
             <span
               title={scanStatus?.error || ''}
               style={{
                 color: scanStatusColor(scanStatus?.status),
                 fontSize: '12px',
                 fontWeight: 600,
                 whiteSpace: 'nowrap',
               }}
             >
               {scanStatusText}
             </span>
             {activeTab === 'dashboard' && <span style={{color: 'var(--text-muted)'}}>{stockTrades.length} stock trades loaded.</span>}
             {activeTab === 'options' && <span style={{color: 'var(--text-muted)'}}>{optionTrades.length} option trades loaded.</span>}
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
                draftRow={draftRow}
                setDraftRow={setDraftRow}
                onDetailClick={(trade) => setDetailTrade(trade)}
                onTradeUpdate={fetchDashboardData}
              />
              <ErrorBoundary>
                <AnalyticsPanel />
              </ErrorBoundary>
            </>
          )}
          {activeTab === 'options' && (
            <ErrorBoundary>
              <TradeTable
                trades={optionTrades}
                draftRow={null}
                setDraftRow={() => {}}
                onDetailClick={(trade) => setDetailTrade(trade)}
                onTradeUpdate={fetchDashboardData}
              />
            </ErrorBoundary>
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
