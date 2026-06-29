// Shared lazy-route fallback. Matches the panel that AppContent used to render
// while a tab's chunk loaded. Extracted so every route shares one fallback.
const loadingStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  color: 'var(--text-muted)',
  fontSize: 12,
  padding: 18,
};

const LoadingPanel = () => <div style={loadingStyle}>Loading view...</div>;

export default LoadingPanel;
