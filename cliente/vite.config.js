import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El navegador usa el mismo origen; FastAPI conserva su configuración original.
const proxy = {
  '/api': {
    target: 'http://127.0.0.1:8000',
    rewrite: (path) => path.replace(/^\/api/, ''),
    proxyTimeout: 0,
    timeout: 0,
  },
}

export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy },
})
