import { existsSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

function resolveApiProxyTarget(mode: string): string {
  const env = loadEnv(mode, process.cwd(), '')
  // process.env 优先：Docker Compose 注入的 VITE_API_PROXY 不会进 loadEnv 返回值
  const fromProcess = process.env.VITE_API_PROXY || process.env.VITE_API_BASE
  if (fromProcess) return fromProcess
  const fromFile = env.VITE_API_PROXY || env.VITE_API_BASE
  if (fromFile) return fromFile
  if (existsSync('/.dockerenv')) return 'http://api:8000'
  return 'http://127.0.0.1:8001'
}

export default defineConfig(({ mode }) => {
  const apiTarget = resolveApiProxyTarget(mode)
  return {
    plugins: [
      vue(),
      AutoImport({ resolvers: [ElementPlusResolver()] }),
      Components({ resolvers: [ElementPlusResolver()] }),
    ],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        '/healthz': { target: apiTarget, changeOrigin: true },
        '/readyz': { target: apiTarget, changeOrigin: true },
        // FastAPI Swagger（与 /api 同级，须单独代理）
        '/docs': { target: apiTarget, changeOrigin: true },
        '/openapi.json': { target: apiTarget, changeOrigin: true },
      },
      watch: {
        // Docker for Windows / Mac 需要 polling
        usePolling: true,
        interval: 500,
      },
    },
  }
})
