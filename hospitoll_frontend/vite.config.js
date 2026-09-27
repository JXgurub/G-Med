import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/xlsx')) return 'vendor-xlsx'
          if (id.includes('node_modules/react-router')) return 'vendor-router'
          if (id.includes('node_modules/react')) return 'vendor-react'
        }
      }
    }
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    allowedHosts: ['.ngrok-free.app', '.ngrok-free.dev'],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
