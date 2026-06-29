import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary'

// Note: StrictMode intentionally removed.
// lightweight-charts creates canvas elements that cannot survive
// React StrictMode's mount→unmount→remount cycle in development.
// This was the primary cause of the black screen issue.
//
// Top-level ErrorBoundary so a render-phase throw in the AppShell frame itself
// (sidebar/topbar/risk-alert strip or the dashboard/live-price hooks) shows a
// fallback instead of white-screening — the inner boundaries only cover the
// route content and the modal subtree.
createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </ErrorBoundary>
)
