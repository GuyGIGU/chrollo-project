import { NavLink } from 'react-router-dom';
import {
  HomeIcon, PortfolioIcon, JournalIcon, OptionsIcon,
  ScreenerIcon, ArchiveIcon, PlusIcon, UploadIcon, CalcIcon,
} from './NavIcons';

// Compact icon rail: icon + tiny label per item, grouped into sections by a
// faint divider. Reclaims ~130px of width vs the old text list. IBKR mode
// controls moved to the topbar (they belong with the other status indicators);
// the rail is now pure navigation + the three primary actions.
const navSections = [
  {
    label: 'Trade',
    items: [
      { to: '/portfolio', label: 'Portfolio', Icon: PortfolioIcon },
      { to: '/dashboard', label: 'Journal', Icon: JournalIcon },
      { to: '/options', label: 'Options', Icon: OptionsIcon },
    ],
  },
  {
    label: 'Research',
    items: [
      { to: '/screener', label: 'Screener', Icon: ScreenerIcon },
      { to: '/archive', label: 'Archive', Icon: ArchiveIcon },
    ],
  },
];

// eslint-disable-next-line no-unused-vars -- Icon is rendered as a JSX element below; this config lacks react/jsx-uses-vars so it isn't seen as used.
function RailLink({ to, label, Icon, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      title={label}
      className={({ isActive }) => `rail-link ${isActive ? 'active' : ''}`}
    >
      <Icon className="rail-icon" />
      <span className="rail-label">{label}</span>
    </NavLink>
  );
}

function AppSidebar({
  logoUrl,
  onOpenCalculator,
  onNewTrade,
  csvInputRef,
  importingCsv,
  onCsvImport,
}) {
  return (
    <aside className="sidebar">
      <div className="rail-brand" title="Chrollo">
        <img src={logoUrl} alt="Chrollo" />
      </div>

      <nav className="rail-nav">
        <RailLink to="/" end label="Home" Icon={HomeIcon} />
        {navSections.map(section => (
          <div className="rail-section" key={section.label}>
            <div className="rail-section-label">{section.label}</div>
            {section.items.map(item => (
              <RailLink key={item.to} to={item.to} label={item.label} Icon={item.Icon} />
            ))}
          </div>
        ))}
      </nav>

      <div className="rail-actions">
        <button type="button" className="rail-action rail-action-primary" onClick={onNewTrade} title="New Trade">
          <PlusIcon className="rail-icon" />
          <span className="rail-label">Trade</span>
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
          className="rail-action"
          disabled={importingCsv}
          onClick={() => csvInputRef.current?.click()}
          title="Import an IBKR Activity Statement CSV"
          style={{ cursor: importingCsv ? 'wait' : 'pointer', opacity: importingCsv ? 0.6 : 1 }}
        >
          <UploadIcon className="rail-icon" />
          <span className="rail-label">{importingCsv ? '…' : 'Import'}</span>
        </button>
        <button type="button" className="rail-action" onClick={onOpenCalculator} title="Position Calculator">
          <CalcIcon className="rail-icon" />
          <span className="rail-label">Calc</span>
        </button>
      </div>
    </aside>
  );
}

export default AppSidebar;
