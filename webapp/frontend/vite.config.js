import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: '/',
  plugins: [react()],
  server: {
    proxy: {
      // Journal attachment images are the ONE thing the page loads from the
      // API as a no-cors subresource (<img src> / a link target), and those
      // carry no Origin header for the same-app guard's dev allowlist to
      // match — only Sec-Fetch-Site, which reads `same-site` across
      // :5173 -> :8000 and is refused. So the API hands out a RELATIVE
      // /attachments/... URL and dev serves it from this origin, exactly as
      // production does. Everything else the app calls is fetch/EventSource
      // through API_BASE, which does send Origin and is allowed as-is.
      '/attachments': 'http://localhost:8000',
    },
  },
})
