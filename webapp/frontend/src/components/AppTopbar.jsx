import { scanStatusColor, tabTitle } from '../utils/appFormat';

function AppTopbar({
  activeTab,
  healthPill,
  scanStatus,
  scanStatusText,
  stockTradeCount,
  optionTradeCount,
}) {
  return (
    <header className="topbar" style={{ justifyContent: 'space-between' }}>
      <div style={{
        color: 'var(--text-muted)',
        fontSize: '14px',
        fontWeight: '500',
        textTransform: 'uppercase',
        letterSpacing: '1px',
      }}>
        {tabTitle(activeTab)}
      </div>
      <div style={{
        display: 'flex',
        gap: '1rem',
        alignItems: 'center',
        justifyContent: 'flex-end',
        flexWrap: 'wrap',
      }}>
        {healthPill && (
          <span
            title={healthPill.title}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '12px',
              fontWeight: 600,
              whiteSpace: 'nowrap',
              color: healthPill.color,
              cursor: 'default',
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
        {activeTab === 'dashboard' && <span style={{ color: 'var(--text-muted)' }}>{stockTradeCount} stock trades loaded.</span>}
        {activeTab === 'options' && <span style={{ color: 'var(--text-muted)' }}>{optionTradeCount} option trades loaded.</span>}
      </div>
    </header>
  );
}

export default AppTopbar;
