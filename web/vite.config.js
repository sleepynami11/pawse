import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Served by FastAPI at /app (pawse/app.py) after `npm run build`; in dev, /api goes to uvicorn on :8765.
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  server: {
    port: 5173,
    // Keep the browser's Host so it matches Origin; the backend rejects cross-origin POSTs.
    proxy: { '/api': { target: process.env.PAWSE_API || 'http://127.0.0.1:8765', changeOrigin: false } },
  },
});
