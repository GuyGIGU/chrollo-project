// Single source of truth for the backend URL.
// Override in production by setting VITE_API_BASE (e.g. in .env.production).
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
