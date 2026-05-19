import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginView from './views/LoginView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      meta: { public: true, title: '登录' },
      component: LoginView,
    },
    {
      path: '/',
      component: () => import('./layouts/AppLayout.vue'),
      children: [
        { path: '', redirect: '/market/hosts' },
        {
          path: 'market/hosts',
          name: 'market-hosts',
          meta: { title: '通达信主站' },
          component: () => import('./views/market/TdxHostsView.vue'),
        },
        {
          path: 'market/data',
          name: 'market-data',
          meta: { title: '数据更新' },
          component: () => import('./views/market/MarketDataView.vue'),
        },
        {
          path: 'market/browser',
          name: 'market-browser',
          meta: { title: '数据查看' },
          component: () => import('./views/market/DataBrowserView.vue'),
        },
        {
          path: 'm',
          component: () => import('./layouts/MobileIPhoneShellLayout.vue'),
          meta: { title: 'H5版本' },
          children: [
            {
              path: '',
              name: 'm-h5',
              meta: { title: 'H5版本' },
              component: () => import('./views/mobile/MobileH5AppView.vue'),
            },
          ],
        },
        {
          path: 'admin/audit-logs',
          name: 'audit-logs',
          meta: { title: '操作日志' },
          component: () => import('./views/admin/AuditLogsView.vue'),
        },
      ],
    },
  ],
})

async function ensureAdminProfile(): Promise<boolean> {
  const auth = useAuthStore()
  if (auth.admin) return true
  if (!auth.accessToken) return false
  try {
    await auth.fetchMe()
    return Boolean(auth.admin)
  } catch {
    auth.clearSession()
    return false
  }
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public) {
    if (to.path === '/login' && auth.accessToken) {
      void ensureAdminProfile().then((ok) => {
        if (ok) void router.replace('/market/hosts')
      })
    }
    return true
  }

  if (!auth.accessToken) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  const ok = await ensureAdminProfile()
  if (!ok) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  return true
})
