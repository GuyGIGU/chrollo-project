import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from './components/AppShell';
import HomeRoute from '../features/home/HomeRoute';
import DashboardRoute from '../features/journal/DashboardRoute';
import OptionsRoute from '../features/options/OptionsRoute';
import PortfolioRoute from '../features/portfolio/PortfolioRoute';
import ScreenerRoute from '../features/screener/ScreenerRoute';
import WatchlistRoute from '../features/watchlist/WatchlistRoute';
import ArchiveRoute from '../features/archive/ArchiveRoute';
import CalibrationRoute from '../features/calibration/CalibrationRoute';

// The whole app is one AppShell layout route (sidebar + topbar + cross-cutting
// modals) with a child route per surface. The index is the Home command-center;
// any unknown URL falls back to it.
function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomeRoute />} />
        <Route path="home" element={<HomeRoute />} />
        <Route path="screener" element={<ScreenerRoute />} />
        <Route path="watchlist" element={<WatchlistRoute />} />
        <Route path="dashboard" element={<DashboardRoute />} />
        <Route path="options" element={<OptionsRoute />} />
        <Route path="portfolio" element={<PortfolioRoute />} />
        <Route path="archive" element={<ArchiveRoute />} />
        <Route path="calibration" element={<CalibrationRoute />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
