import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import App from './App.vue'
import { reportClientError } from './logging/clientError'
import { router } from './router'

async function bootstrap() {
  const app = createApp(App)
  app.config.errorHandler = (err, _instance, info) => {
    const e = err instanceof Error ? err : new Error(String(err))
    reportClientError({
      message: e.message,
      stack: e.stack ?? '',
      source: `vue:errorHandler:${info}`,
    })
  }
  window.addEventListener('unhandledrejection', (ev) => {
    const r = ev.reason
    const msg = r instanceof Error ? r.message : String(r)
    const stack = r instanceof Error ? (r.stack ?? '') : ''
    reportClientError({
      message: msg,
      stack,
      source: 'window:unhandledrejection',
    })
  })

  app.use(createPinia())
  app.use(router)
  app.use(ElementPlus, { locale: zhCn })
  await router.isReady()
  app.mount('#app')
}

bootstrap().catch((err) => {
  const root = document.getElementById('app')
  const msg = err instanceof Error ? err.message : String(err)
  if (root) {
    root.innerHTML = `<p style="padding:24px;font-family:sans-serif;color:#b91c1c">应用启动失败：${msg}</p>`
  }
  reportClientError({
    message: msg,
    stack: err instanceof Error ? (err.stack ?? '') : '',
    source: 'bootstrap',
  })
})
