import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from './components/AppShell';
import DashboardRoute from './routes/DashboardRoute';
import OptionsRoute from './routes/OptionsRoute';
import PortfolioRoute from './routes/PortfolioRoute';
import ScreenerRoute from './routes/ScreenerRoute';
import ArchiveRoute from './routes/ArchiveRoute';

// The whole app is one AppShell layout route (sidebar + topbar + cross-cutting
// modals) with a child route per former tab. The index and any unknown URL
// redirect to /screener — the historical default landing tab.
function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/screener" replace />} />
        <Route path="screener" element={<ScreenerRoute />} />
        <Route path="dashboard" element={<DashboardRoute />} />
        <Route path="options" element={<OptionsRoute />} />
        <Route path="portfolio" element={<PortfolioRoute />} />
        <Route path="archive" element={<ArchiveRoute />} />
        <Route path="*" element={<Navigate to="/screener" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
