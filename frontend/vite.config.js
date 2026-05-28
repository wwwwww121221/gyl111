import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const allowedHosts = (env.VITE_ALLOWED_HOSTS || '')
    .split(',')
    .map((host) => host.trim())
    .filter(Boolean)
  const proxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'
  const hmr = String(env.VITE_DISABLE_HMR || '').toLowerCase() === 'true' ? false : undefined

  return {
    plugins: [vue()],
    server: {
      host: '0.0.0.0',
      allowedHosts,
      hmr,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true
        },
        '/static': {
          target: proxyTarget,
          changeOrigin: true
        },
        '/wechat': {
          target: proxyTarget,
          changeOrigin: true
        }
      }
    }
  }
})
