import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/market/hosts',
    },
    {
      path: '/market',
      meta: { title: '行情数据' },
      children: [
        {
          path: 'hosts',
          name: 'market-hosts',
          meta: { title: '通达信主站' },
          component: () => import('./views/market/TdxHostsView.vue'),
        },
        {
          path: 'import',
          name: 'market-import',
          meta: { title: '历史数据导入' },
          component: () => import('./views/market/ImportView.vue'),
        },
        {
          path: 'tasks',
          name: 'market-tasks',
          meta: { title: '任务进度' },
          component: () => import('./views/market/TasksView.vue'),
        },
        {
          path: 'browser',
          name: 'market-browser',
          meta: { title: '数据查看' },
          component: () => import('./views/market/DataBrowserView.vue'),
        },
        {
          path: 'online',
          name: 'market-online',
          meta: { title: '在线补数' },
          component: () => import('./views/market/OnlineFetchView.vue'),
        },
      ],
    },
  ],
})
