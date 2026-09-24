import Panel from './Panel';

// Shared lazy-route fallback. Matches the panel that AppContent used to render
// while a tab's chunk loaded. Built on the Panel primitive so the surface stays
// on the design-system ramp.
const LoadingPanel = () => (
  <Panel style={{ color: 'var(--text-muted)', fontSize: 12, padding: 18, borderRadius: 8 }}>
    Loading view...
  </Panel>
);

export default LoadingPanel;
