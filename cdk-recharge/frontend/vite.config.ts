import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { localPreviewApi } from './local-preview'

export default defineConfig(({ mode }) => ({
  plugins: [vue(), ...(mode === 'visual-preview' ? [{
    name: 'isolated-local-preview',
    configureServer(server: import('vite').ViteDevServer) {
      server.middlewares.use(localPreviewApi)
    },
  }] : [])],
  server: {
    port: 5173,
    proxy: mode === 'visual-preview' ? undefined : {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
}))
