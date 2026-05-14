<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const activeMenu = computed(() => route.path)

function goto(path: string) {
  router.push(path)
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
          <el-menu-item index="/market/import">历史数据导入</el-menu-item>
          <el-menu-item index="/market/tasks">任务进度</el-menu-item>
          <el-menu-item index="/market/online">在线补数</el-menu-item>
          <el-menu-item index="/market/browser">数据查看</el-menu-item>
        </el-menu-item-group>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="title">{{ (route.meta?.title as string) || 'iQuant' }}</div>
        <div class="right">
          <a class="link" href="/docs" target="_blank">API 文档</a>
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
.menu { border-right: 0; }
.menu :deep(.el-menu-item.is-active) {
  background: rgba(59, 130, 246, 0.25) !important;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}
.title { font-size: 18px; font-weight: 600; color: #111827; }
.link { color: #3b82f6; text-decoration: none; }
.main { background: #f3f4f6; }
</style>
