<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getImportTask,
  listImportTasks,
  taskProgressUrl,
  type ImportTask,
} from '@/api/market'

const route = useRoute()
const router = useRouter()
const tasks = ref<ImportTask[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)

const activeTask = ref<ImportTask | null>(null)
let sse: EventSource | null = null

async function refresh() {
  loading.value = true
  try {
    const r = await listImportTasks({
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    })
    tasks.value = r.data
    total.value = r.total || 0
  } finally {
    loading.value = false
  }
}

const progressPercent = computed(() => {
  const t = activeTask.value
  if (!t || !t.total_files) return 0
  return Math.min(100, Math.round((t.done_files / t.total_files) * 100))
})

async function openTask(taskId: string) {
  const r = await getImportTask(taskId)
  activeTask.value = r.data
  router.replace({ query: { task_id: taskId } })
  connectSSE(taskId)
}

function statusTag(s: string) {
  return {
    queued: 'info',
    running: 'warning',
    succeeded: 'success',
    failed: 'danger',
    cancelled: 'info',
  }[s] || 'info'
}

function connectSSE(taskId: string) {
  closeSSE()
  sse = new EventSource(taskProgressUrl(taskId))
  sse.addEventListener('progress', (e) => {
    try {
      const data = JSON.parse((e as MessageEvent).data)
      activeTask.value = { ...(activeTask.value || ({} as ImportTask)), ...data }
    } catch { /* ignore */ }
  })
  sse.addEventListener('done', () => {
    ElMessage.success('任务结束')
    refresh()
    closeSSE()
  })
  sse.addEventListener('error', () => {
    closeSSE()
  })
}

function closeSSE() {
  if (sse) {
    sse.close()
    sse = null
  }
}

onMounted(() => {
  refresh()
  const tid = route.query.task_id as string | undefined
  if (tid) openTask(tid)
})

onUnmounted(closeSSE)

watch([page, pageSize], refresh)
</script>

<template>
  <el-row :gutter="16">
    <el-col :span="14">
      <el-card shadow="never">
        <template #header>
          <div class="header">
            <span>导入任务列表</span>
            <el-button size="small" @click="refresh">刷新</el-button>
          </div>
        </template>
        <el-table v-loading="loading" :data="tasks" stripe>
          <el-table-column prop="task_id" label="任务 ID" min-width="220">
            <template #default="{ row }">
              <el-link type="primary" @click="openTask(row.task_id)">{{ row.task_id.slice(0, 12) }}…</el-link>
            </template>
          </el-table-column>
          <el-table-column prop="task_type" label="类型" width="110" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status) as any">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="进度" min-width="160">
            <template #default="{ row }">
              <span>{{ row.done_files }}/{{ row.total_files }}</span>
              <span style="color:#6b7280; margin-left:8px;">导入 {{ row.imported_bars }} 根</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" min-width="180" />
        </el-table>
        <el-pagination
          class="mt"
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, prev, pager, next, sizes"
        />
      </el-card>
    </el-col>
    <el-col :span="10">
      <el-card shadow="never">
        <template #header>任务详情</template>
        <el-empty v-if="!activeTask" description="点击左侧任务查看实时进度" />
        <div v-else>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="task_id">{{ activeTask.task_id }}</el-descriptions-item>
            <el-descriptions-item label="类型">{{ activeTask.task_type }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusTag(activeTask.status) as any">{{ activeTask.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="开始时间">{{ activeTask.started_at || '-' }}</el-descriptions-item>
            <el-descriptions-item label="结束时间">{{ activeTask.finished_at || '-' }}</el-descriptions-item>
            <el-descriptions-item label="错误">{{ activeTask.error_message || '-' }}</el-descriptions-item>
          </el-descriptions>
          <el-progress
            class="mt"
            :percentage="progressPercent"
            :status="activeTask.status === 'failed' ? 'exception' : (activeTask.status === 'succeeded' ? 'success' : '')"
          />
          <div class="mt small">
            完成 <strong>{{ activeTask.done_files }}</strong> / {{ activeTask.total_files }} 个文件，
            已导入 <strong>{{ activeTask.imported_bars }}</strong> 根 K 线，
            失败 <strong>{{ activeTask.error_count }}</strong>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; }
.mt { margin-top: 12px; }
.small { color: #4b5563; font-size: 13px; }
</style>
