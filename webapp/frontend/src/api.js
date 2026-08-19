// Single source of truth for the backend URL.
// Production is served by FastAPI, so API calls are same-origin by default.
// The `|| {}` keeps this importable under bare node (the node --test store
// suites) where import.meta.env does not exist; Vite still statically
// replaces import.meta.env at build time.
const env = import.meta.env || {};
export const API_BASE = env.VITE_API_BASE || (env.DEV ? 'http://localhost:8000' : '');
