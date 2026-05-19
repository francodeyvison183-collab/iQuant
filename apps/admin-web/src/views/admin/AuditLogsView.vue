<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listAuditLogs, type AuditLogRow } from '@/api/audit'

const loading = ref(false)
const rows = ref<AuditLogRow[]>([])
const total = ref(0)
const action = ref('')
const pathContains = ref('')
const days = ref(30)
const page = ref(1)
const pageSize = ref(50)

async function load() {
  loading.value = true
  try {
    const resp = await listAuditLogs({
      action: action.value || undefined,
      path_contains: pathContains.value || undefined,
      days: days.value,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    })
    rows.value = resp.data || []
    total.value = resp.total ?? rows.value.length
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  load()
}

onMounted(load)
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div class="head">
        <span>操作日志</span>
        <el-button type="primary" link @click="load">刷新</el-button>
      </div>
    </template>
    <el-form :inline="true" class="filters" @submit.prevent="onSearch">
      <el-form-item label="动作">
        <el-input v-model="action" placeholder="如 auth.login" clearable />
      </el-form-item>
      <el-form-item label="路径包含">
        <el-input v-model="pathContains" placeholder="/admin/market" clearable />
      </el-form-item>
      <el-form-item label="天数">
        <el-input-number v-model="days" :min="1" :max="90" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="onSearch">查询</el-button>
      </el-form-item>
    </el-form>
    <el-table v-loading="loading" :data="rows" stripe border size="small">
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column prop="username" label="用户" width="100" />
      <el-table-column prop="action" label="动作" width="160" />
      <el-table-column prop="method" label="方法" width="72" />
      <el-table-column prop="path" label="路径" min-width="200" show-overflow-tooltip />
      <el-table-column prop="status_code" label="状态" width="72" />
      <el-table-column prop="ip" label="IP" width="120" />
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
        @size-change="onSearch"
      />
    </div>
  </el-card>
</template>

<style scoped>
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.filters {
  margin-bottom: 12px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
