import Panel from './Panel';
import Skeleton from './Skeleton';

// Shared lazy-route fallback: the panel AppContent used to render while a tab's
// chunk loaded, now holding the shared skeleton rather than a "Loading view..."
// line. Built on the Panel primitive so the surface stays on the design-system ramp.
const LoadingPanel = () => (
  <Panel style={{ padding: 18, borderRadius: 8 }}>
    <Skeleton rows={4} label="Loading view" />
  </Panel>
);

export default LoadingPanel;
