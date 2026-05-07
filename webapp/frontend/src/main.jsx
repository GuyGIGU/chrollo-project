import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Note: StrictMode intentionally removed.
// lightweight-charts creates canvas elements that cannot survive
// React StrictMode's mount→unmount→remount cycle in development.
// This was the primary cause of the black screen issue.
createRoot(document.getElementById('root')).render(<App />)
