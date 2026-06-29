import { NavLink } from 'react-router-dom';
import IbkrModeControls from './IbkrModeControls';

const navSections = [
  {
    label: 'Trading',
    items: [
      { to: '/portfolio', label: 'Portfolio' },
      { to: '/dashboard', label: 'Dashboard' },
      { to: '/options', label: 'Options' },
    ],
  },
  {
    label: 'Research',
    items: [
      { to: '/screener', label: 'Screener Grid' },
      { to: '/archive', label: 'Setup Archive' },
    ],
  },
];

function AppSidebar({
  logoUrl,
  onOpenCalculator,
  onNewTrade,
  csvInputRef,
  importingCsv,
  onCsvImport,
  ibkrStatus,
  ibkrActions,
}) {
  return (
    <aside className="sidebar">
      <div className="brand" style={{
        gap: '12px',
        fontSize: '1.4rem',
        letterSpacing: '2px',
        textTransform: 'uppercase',
        marginBottom: '0.8rem',
      }}>
        <img src={logoUrl} alt="Chrollo" style={{ width: 32, height: 32, borderRadius: 6, objectFit: 'cover' }} />
        <span className="brand-text">Chrollo</span>
      </div>

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

      <nav className="nav-menu">
        {navSections.map(section => (
          <div className="nav-section" key={section.label}>
            <div className="nav-section-label">{section.label}</div>
            {section.items.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
        <div className="nav-section">
          <div className="nav-section-label">Tools</div>
          <button type="button" className="nav-link" onClick={onOpenCalculator}>Calculator</button>
        </div>
      </nav>

      <div className="action-buttons">
        <button className="btn-action btn-trade" onClick={onNewTrade}><span>+</span> New Trade</button>
        <input
          ref={csvInputRef}
          type="file"
          accept=".csv,text/csv"
          style={{ display: 'none' }}
          onChange={onCsvImport}
        />
        <button
          type="button"
          className="btn-action"
          disabled={importingCsv}
          onClick={() => csvInputRef.current?.click()}
          title="Upload an IBKR Activity Statement CSV to bulk-import historical fills"
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
          {importingCsv ? 'Importing...' : 'Import IBKR CSV'}
        </button>
      </div>
    </aside>
  );
}

export default AppSidebar;
