<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const activeMenu = computed(() => route.path)

function goto(path: string) {
  router.push(path)
}

async function onLogout() {
  await auth.logout()
  router.replace('/login')
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">
        <span class="brand-mark">iQ</span>
        <span class="brand-text">iQuant 后台</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        class="menu"
        @select="goto"
        background-color="transparent"
        text-color="#cfd8dc"
        active-text-color="#ffffff"
      >
        <el-menu-item-group>
          <template #title>行情数据</template>
          <el-menu-item index="/market/hosts">通达信主站</el-menu-item>
          <el-menu-item index="/market/data">数据更新</el-menu-item>
          <el-menu-item index="/market/browser">数据查看</el-menu-item>
        </el-menu-item-group>
        <el-menu-item-group>
          <template #title>产品体验（移动 H5）</template>
          <el-menu-item index="/m">H5版本</el-menu-item>
        </el-menu-item-group>
        <el-menu-item-group>
          <template #title>系统</template>
          <el-menu-item index="/admin/audit-logs">操作日志</el-menu-item>
        </el-menu-item-group>
      </el-menu>
      <div class="aside-footer">
        <a
          class="aside-footer-link"
          href="/docs"
          target="_blank"
          rel="noopener noreferrer"
        >
          API 文档
        </a>
      </div>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="title">{{ (route.meta?.title as string) || 'iQuant' }}</div>
        <div class="right">
          <span v-if="auth.admin" class="user">{{ auth.admin.display_name }}</span>
          <el-button type="primary" link @click="onLogout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout { height: 100vh; }
.aside {
  background: linear-gradient(180deg, #1f2937 0%, #111827 100%);
  color: #cfd8dc;
  display: flex;
  flex-direction: column;
  height: 100%;
}
.brand {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px; height: 32px;
  background: #3b82f6;
  border-radius: 8px;
  font-weight: 700;
}
.brand-text { font-size: 16px; font-weight: 600; }
.menu { border-right: 0; flex: 1; overflow-y: auto; min-height: 0; }
.menu :deep(.el-menu-item.is-active) {
  background: rgba(59, 130, 246, 0.25) !important;
}
.aside-footer {
  flex-shrink: 0;
  padding: 8px 0 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.aside-footer-link {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 20px;
  margin: 0 8px;
  border-radius: 6px;
  color: #cfd8dc;
  text-decoration: none;
  font-size: 14px;
}
.aside-footer-link:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.06);
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}
.title { font-size: 18px; font-weight: 600; color: #111827; }
.right { display: flex; align-items: center; gap: 12px; }
.user { color: #6b7280; font-size: 14px; }
.main { background: #f3f4f6; }
</style>
