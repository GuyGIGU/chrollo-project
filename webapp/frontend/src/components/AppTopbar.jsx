import { Fragment } from 'react';
import { NavLink } from 'react-router-dom';
import { scanStatusColor } from '../utils/appFormat';
import IbkrModeControls from './IbkrModeControls';
import AppearanceControl from './AppearanceControl';
import {
  HomeIcon, PortfolioIcon, JournalIcon, OptionsIcon, ScreenerIcon,
  WatchlistIcon, ArchiveIcon, CalibrationIcon, PlusIcon, UploadIcon, CalcIcon,
} from './NavIcons';

// The one global bar: brand + horizontal nav on the left, live status + IBKR +
// primary actions on the right. This replaces the old vertical icon rail — on a
// wide monitor the flattened nav hands the full width back to the card wall.
// Nav groups (Home / trade / research) are told apart by a hairline seam, not
// the stacked section labels the vertical rail used. Actions collapse to
// icon-only (label lives in the tooltip) so the whole bar stays on one row.
const NAV_GROUPS = [
  [{ to: '/', end: true, label: 'Home', Icon: HomeIcon }],
  [
    { to: '/portfolio', label: 'Portfolio', Icon: PortfolioIcon },
    { to: '/dashboard', label: 'Journal', Icon: JournalIcon },
    { to: '/options', label: 'Options', Icon: OptionsIcon },
  ],
  [
    { to: '/screener', label: 'Screener', Icon: ScreenerIcon },
    { to: '/watchlist', label: 'Watchlist', Icon: WatchlistIcon },
    { to: '/archive', label: 'Archive', Icon: ArchiveIcon },
    { to: '/calibration', label: 'Calibration', Icon: CalibrationIcon },
  ],
];

function NavTab({ to, end, label, Icon }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => `topnav-link ${isActive ? 'active' : ''}`}
    >
      <Icon className="topnav-icon" />
      <span>{label}</span>
    </NavLink>
  );
}

function AppTopbar({
  healthPill,
  scanStatus,
  scanStatusText,
  ibkrStatus,
  ibkrActions,
  logoUrl,
  onOpenCalculator,
  onNewTrade,
  csvInputRef,
  importingCsv,
  onCsvImport,
}) {
  return (
    <header className="app-topnav">
      <div className="topnav-brand" title="Chrollo">
        <img src={logoUrl} alt="Chrollo" />
      </div>

      <nav className="topnav-nav" aria-label="Primary">
        {NAV_GROUPS.map((group, index) => (
          <Fragment key={index}>
            {index > 0 && <span className="topnav-seam" aria-hidden="true" />}
            {group.map(item => <NavTab key={item.to} {...item} />)}
          </Fragment>
        ))}
      </nav>

      <div className="topnav-right">
        {healthPill && (
          <span title={healthPill.title} className="topnav-status" style={{ color: healthPill.color }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: healthPill.color }} />
            {healthPill.label}
          </span>
        )}
        <span
          title={scanStatus?.error || ''}
          className="topnav-status"
          style={{ color: scanStatusColor(scanStatus?.status) }}
        >
          {scanStatusText}
        </span>

        {ibkrActions && (
          <IbkrModeControls
            ibkrStatus={ibkrStatus}
            isConnected={ibkrActions.isConnected}
            isLive={ibkrActions.isLive}
            isGateway={ibkrActions.isGateway}
            reconnecting={ibkrActions.reconnecting}
            switchingClient={ibkrActions.switchingClient}
            switchingMode={ibkrActions.switchingMode}
            onToggleClient={ibkrActions.toggleIbkrClient}
            onToggleMode={ibkrActions.toggleIbkrMode}
            onReconnect={ibkrActions.reconnectIbkr}
            onDisconnect={ibkrActions.disconnectIbkr}
          />
        )}

        <div className="topnav-actions">
          <button
            type="button"
            className="topnav-action topnav-action-primary"
            onClick={onNewTrade}
            title="New trade"
            aria-label="New trade"
          >
            <PlusIcon className="topnav-icon" />
          </button>
          <input
            ref={csvInputRef}
            type="file"
            accept=".csv,text/csv"
            style={{ display: 'none' }}
            onChange={onCsvImport}
          />
          <button
            type="button"
            className="topnav-action"
            disabled={importingCsv}
            onClick={() => csvInputRef.current?.click()}
            title="Import an IBKR Activity Statement CSV"
            aria-label="Import CSV"
            style={{ cursor: importingCsv ? 'wait' : 'pointer', opacity: importingCsv ? 0.6 : 1 }}
          >
            <UploadIcon className="topnav-icon" />
          </button>
          <button
            type="button"
            className="topnav-action"
            onClick={onOpenCalculator}
            title="Position calculator"
            aria-label="Position calculator"
          >
            <CalcIcon className="topnav-icon" />
          </button>
          <AppearanceControl />
        </div>
      </div>
    </header>
  );
}

export default AppTopbar;
