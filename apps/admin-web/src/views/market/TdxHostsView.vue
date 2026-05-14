<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { addHost, listHosts, removeHostById, testAllHosts, type TdxHost } from '@/api/market'

const hosts = ref<TdxHost[]>([])
const loading = ref(false)
const testing = ref(false)

const dialogVisible = ref(false)
const form = ref({ ip: '', port: 7709, name: '' })

async function refresh() {
  loading.value = true
  try {
    const r = await listHosts()
    hosts.value = r.data
  } finally {
    loading.value = false
  }
}

async function onTest() {
  testing.value = true
  try {
    const r = await testAllHosts()
    hosts.value = r.data
    ElMessage.success(`测速完成：可用 ${r.data.filter((h) => h.status === 'ok').length}/${r.data.length}`)
  } finally {
    testing.value = false
  }
}

async function onAdd() {
  if (!form.value.ip || !form.value.port) {
    ElMessage.warning('请填写 IP 和端口')
    return
  }
  await addHost({ ip: form.value.ip, port: form.value.port, name: form.value.name })
  ElMessage.success('已添加')
  dialogVisible.value = false
  form.value = { ip: '', port: 7709, name: '' }
  await refresh()
}

async function onRemove(row: TdxHost & { id?: number }) {
  await ElMessageBox.confirm(`确定删除 ${row.ip}:${row.port} 吗？`, '提示', { type: 'warning' })
  if (!row.id) {
    ElMessage.warning('内置主站不可删除')
    return
  }
  await removeHostById(row.id)
  ElMessage.success('已删除')
  await refresh()
}

function statusTagType(s: string) {
  return s === 'ok' ? 'success' : s === 'fail' ? 'danger' : 'info'
}

onMounted(refresh)
</script>

<template>
  <el-card shadow="never">
    <div class="toolbar">
      <div>
        <el-button :loading="testing" type="primary" @click="onTest">一键测速</el-button>
        <el-button @click="dialogVisible = true">添加主站</el-button>
        <el-button @click="refresh">刷新</el-button>
      </div>
      <div class="hint">7709/7708 为真实行情端口；7727 为扩展市场端口，不提供 K 线</div>
    </div>

    <el-table v-loading="loading" :data="hosts" stripe class="mt">
      <el-table-column prop="name" label="名称" min-width="160">
        <template #default="{ row }">
          <span>{{ row.name }}</span>
          <el-tag v-if="row.is_builtin" size="small" type="info" class="ml">内置</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="ip" label="IP" width="160" />
      <el-table-column prop="port" label="端口" width="90" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="延迟(ms)" width="120">
        <template #default="{ row }">
          {{ row.speed_ms >= 9999 ? '-' : row.speed_ms }}
        </template>
      </el-table-column>
      <el-table-column prop="last_tested" label="最近测速" min-width="180" />
      <el-table-column prop="fail_since" label="持续失败起" min-width="180" />
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="danger" :disabled="row.is_builtin" @click="onRemove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="dialogVisible" title="添加 TDX 主站" width="420">
    <el-form :model="form" label-width="80">
      <el-form-item label="IP">
        <el-input v-model="form.ip" placeholder="如 119.147.212.81" />
      </el-form-item>
      <el-form-item label="端口">
        <el-input-number v-model="form.port" :min="1" :max="65535" />
      </el-form-item>
      <el-form-item label="名称">
        <el-input v-model="form.name" placeholder="可选" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="onAdd">添加</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.toolbar { display: flex; align-items: center; justify-content: space-between; }
.hint { color: #6b7280; font-size: 12px; }
.mt { margin-top: 16px; }
.ml { margin-left: 8px; }
</style>
