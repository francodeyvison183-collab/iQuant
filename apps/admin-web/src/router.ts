import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/market/hosts',
    },
    {
      path: '/market/hosts',
      name: 'market-hosts',
      meta: { title: '通达信主站' },
      component: () => import('./views/market/TdxHostsView.vue'),
    },
    {
      path: '/market/data',
      name: 'market-data',
      meta: { title: '行情数据' },
      component: () => import('./views/market/MarketDataView.vue'),
    },

    {
      path: '/market/browser',
      name: 'market-browser',
      meta: { title: '数据查看' },
      component: () => import('./views/market/DataBrowserView.vue'),
    },

  ],
})
