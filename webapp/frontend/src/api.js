// Single source of truth for the backend URL.
// Production is served by FastAPI, so API calls are same-origin by default.
export const API_BASE = import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? 'http://localhost:8000' : '');
