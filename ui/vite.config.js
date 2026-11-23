import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat':     { target: 'http://localhost:8000', changeOrigin: true },
      '/reset':    { target: 'http://localhost:8000', changeOrigin: true },
      '/scenario': { target: 'http://localhost:8000', changeOrigin: true },
      '/health':   { target: 'http://localhost:8000', changeOrigin: true },
    }
  },
  build: {
    outDir: '../agent/static',
    emptyOutDir: true,
  }
})
