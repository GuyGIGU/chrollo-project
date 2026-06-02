function ScreenerWatchlistPanel({ watchlist, screenerData, isScanning, onToggleWatchlist }) {
  if (isScanning || watchlist.size === 0) return null;

  return (
    <div style={panelStyle}>
      <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', marginRight: '6px' }}>
        Manage ({watchlist.size}):
      </span>
      {Array.from(watchlist).sort().map(ticker => (
        <WatchlistItem
          key={ticker}
          ticker={ticker}
          hasSetup={!!screenerData?.chart_data?.[ticker]}
          onToggleWatchlist={onToggleWatchlist}
        />
      ))}
    </div>
  );
}

function WatchlistItem({ ticker, hasSetup, onToggleWatchlist }) {
  return (
    <span
      title={hasSetup ? '' : 'No matching setup in the latest scan'}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 4px 4px 10px',
        borderRadius: '14px',
        border: '1px solid var(--border-color)',
        background: hasSetup ? 'transparent' : 'rgba(255,255,255,0.04)',
        color: hasSetup ? 'var(--text-main)' : 'var(--text-muted)',
        fontSize: '12px',
        fontStyle: hasSetup ? 'normal' : 'italic',
      }}
    >
      {ticker}
      {!hasSetup && <span style={{ fontSize: '10px', opacity: 0.7 }}>(no setup)</span>}
      <button
        onClick={() => onToggleWatchlist(ticker)}
        title="Remove from watchlist"
        style={{
          border: 'none',
          background: 'transparent',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          fontSize: '14px',
          lineHeight: 1,
          padding: '0 6px',
          borderRadius: '10px',
        }}
      >
        x
      </button>
    </span>
  );
}

const panelStyle = {
  padding: '10px 16px',
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: '8px',
  display: 'flex',
  gap: '8px',
  alignItems: 'center',
  flexWrap: 'wrap',
};

export default ScreenerWatchlistPanel;
