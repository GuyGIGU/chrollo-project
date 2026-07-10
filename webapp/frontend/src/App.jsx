import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from './components/AppShell';
import HomeRoute from './routes/HomeRoute';
import DashboardRoute from './routes/DashboardRoute';
import OptionsRoute from './routes/OptionsRoute';
import PortfolioRoute from './routes/PortfolioRoute';
import ScreenerRoute from './routes/ScreenerRoute';
import ArchiveRoute from './routes/ArchiveRoute';
import CalibrationRoute from './routes/CalibrationRoute';

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
