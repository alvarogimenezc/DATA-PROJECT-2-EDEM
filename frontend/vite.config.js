import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API_HOST = process.env.VITE_API_HOST || 'localhost'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 3000,
    hmr: { host: 'localhost', port: 3000 },
    watch: { usePolling: true, interval: 300 },
    proxy: {
      '/api/v1': {
        target: `http://${API_HOST}:8080`,
        changeOrigin: true,
      },
      '/ws': {
        target: `ws://${API_HOST}:8080`,
        ws: true,
      },
    },
  },
})
