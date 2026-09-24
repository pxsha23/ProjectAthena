import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    // Forward API calls (and the progress WebSocket) to the FastAPI server in ../server,
    // so the browser sees one origin and the httpOnly auth cookies just work.
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true, ws: true },
    },
  },
  build: {
    // Monaco (and its language workers) is large by nature. It is only loaded
    // by the lazily imported workspace route, never on the landing/dashboard pages.
    chunkSizeWarningLimit: 7500,
  },
})
