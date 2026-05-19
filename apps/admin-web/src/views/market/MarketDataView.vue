<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  createImportTask,
  scanPreview,
  type ScanPreview,
  createOnlineBatchTask,
  uploadVipdoc,
  listImportTasks,
  retryImportTask,
  createProgressTicket,
  taskProgressUrl,
} from '@/api/market'

const router = useRouter()
const tab = ref<'local' | 'batch' | 'history'>('local')

const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const uploadProgress = ref('')

function triggerFileSelect() {
  fileInput.value?.click()
}

async function onFilesSelected(event: Event) {
  const target = event.target as HTMLInputElement
  if (!target.files?.length) return
  
  const files = Array.from(target.files).filter(f => f.name.endsWith('.day') || f.name.endsWith('.lc5'))
  if (!files.length) {
    ElMessage.warning('选中的目录下没有找到 .day 或 .lc5 结尾的行情数据文件')
    return
  }

  uploading.value = true
  uploadProgress.value = `0 / ${files.length}`
  const uploadId = Date.now().toString()
  const chunkSize = 100
  let uploadedCount = 0
  let finalVipdocDir = ''

  try {
    for (let i = 0; i < files.length; i += chunkSize) {
      const chunk = files.slice(i, i + chunkSize)
      const paths = chunk.map(f => {
        const parts = f.webkitRelativePath.split('/')
        const idx = parts.findIndex(p => ['sh', 'sz', 'bj'].includes(p.toLowerCase()))
        if (idx >= 0) return parts.slice(idx).join('/')
        
        // 如果用户选中的不是标准的 vipdoc 目录结构，而是平铺的文件，则基于文件名重构标准目录结构
        const name = f.name.toLowerCase()
        let market = 'sh'
        if (name.startsWith('sz')) market = 'sz'
        else if (name.startsWith('bj')) market = 'bj'
        
        let subdir = 'lday'
        if (name.endsWith('.lc5')) subdir = 'fzline'
        else if (name.endsWith('.lc1')) subdir = 'minline'
        
        return `${market}/${subdir}/${f.name}`
      })
      const res = await uploadVipdoc(uploadId, chunk, paths)
      finalVipdocDir = res.data.vipdoc_dir
      uploadedCount += chunk.length
      uploadProgress.value = `${uploadedCount} / ${files.length}`
    }
    
    vipdocDir.value = finalVipdocDir
    await onPreview()
    if (preview.value?.total_files) {
      await onSubmitImport()
    }
  } catch (e: any) {
    ElMessage.error('上传失败：' + (e.message || '未知错误'))
  } finally {
    uploading.value = false
    uploadProgress.value = ''
    if (target) target.value = ''
  }
}


// ── 本地导入 ────────────────────────────────────────────────────────────────────
const vipdocDir = ref('')
const preview = ref<ScanPreview | null>(null)
const loadingPreview = ref(false)
const submittingImport = ref(false)
const taskType = ref<'incremental' | 'full'>('incremental')
const localMarkets = ref<string[]>([])

async function onPreview() {
  loadingPreview.value = true
  try {
    const mkts = localMarkets.value.length ? localMarkets.value : undefined
    const r = await scanPreview(vipdocDir.value || undefined, mkts)
    preview.value = r.data
    if (!preview.value.total_files) {
      ElMessage.warning('未扫描到任何文件，请检查路径或映射')
    }
  } finally {
    loadingPreview.value = false
  }
}

// ── SSE 进度管理 ──────────────────────────────────────────────────────────────
type LiveProgress = {
  total_files: number
  done_files: number
  imported_bars: number
  status: string
  task_type: string
  error_count: number
  error_message: string
  code_count?: number
  elapsed_seconds?: number
  eta_seconds?: number | null
  speed_per_minute?: number
  concurrency_cap?: number
  concurrency_active?: number
  concurrency_max?: number
  pool_cooldown_remain_seconds?: number
  batch_cooldown_remain_seconds?: number
}

const liveTaskId = ref('')
const liveProgress = ref<LiveProgress>({
  total_files: 0,
  done_files: 0,
  imported_bars: 0,
  status: '',
  task_type: '',
  error_count: 0,
  error_message: '',
})
const liveStocks = ref<{ full_code: string, period: string, inserted: number }[]>([])
let es: EventSource | null = null

const progressTickMs = ref(0)
let progressTickTimer: ReturnType<typeof setInterval> | null = null
let lastProgressAt = 0

function isOnlineBatchProgress() {
  return liveProgress.value.task_type === 'online_batch'
}

function formatDuration(sec: number | null | undefined): string {
  if (sec == null || sec < 0 || Number.isNaN(sec)) return '-'
  const s = Math.floor(sec)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const r = s % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
  return `${m}:${String(r).padStart(2, '0')}`
}

function displayElapsed(): string {
  const base = liveProgress.value.elapsed_seconds ?? 0
  const extra =
    ['running', 'queued', ''].includes(liveProgress.value.status)
      ? progressTickMs.value / 1000
      : 0
  return formatDuration(base + extra)
}

function displayEta(): string {
  const eta = liveProgress.value.eta_seconds
  if (eta == null) {
    return liveProgress.value.done_files > 0 ? '计算中…' : '-'
  }
  if (['running', 'queued', ''].includes(liveProgress.value.status) && progressTickMs.value > 0) {
    const rate =
      liveProgress.value.done_files > 0 && (liveProgress.value.elapsed_seconds ?? 0) > 0
        ? liveProgress.value.done_files / (liveProgress.value.elapsed_seconds ?? 1)
        : 0
    if (rate > 0) {
      const remain = Math.max(0, liveProgress.value.total_files - liveProgress.value.done_files)
      return formatDuration(remain / rate)
    }
  }
  return formatDuration(eta)
}

function concurrencyLabel(): string {
  const cap = liveProgress.value.concurrency_cap
  const active = liveProgress.value.concurrency_active
  const max = liveProgress.value.concurrency_max
  if (cap == null && max == null) return '-'
  const a = active ?? 0
  const c = cap ?? '-'
  const m = max ?? '-'
  return `${a} / ${c}（上限 ${m}）`
}

function onProgressPayload(data: Record<string, unknown>) {
  liveProgress.value = { ...liveProgress.value, ...data } as LiveProgress
  if (typeof data.elapsed_seconds === 'number') {
    lastProgressAt = Date.now()
    progressTickMs.value = 0
  }
  if (['running', 'queued', ''].includes(String(data.status ?? liveProgress.value.status))) {
    startProgressTick()
  }
  if (data.recent_imported && Array.isArray(data.recent_imported)) {
    liveStocks.value.unshift(...(data.recent_imported as typeof liveStocks.value))
    if (liveStocks.value.length > 200) {
      liveStocks.value.length = 200
    }
  }
}

function startProgressTick() {
  if (progressTickTimer) return
  progressTickTimer = setInterval(() => {
    if (lastProgressAt > 0) {
      progressTickMs.value = Date.now() - lastProgressAt
    }
  }, 1000)
}

function stopProgressTick() {
  if (progressTickTimer) {
    clearInterval(progressTickTimer)
    progressTickTimer = null
  }
  progressTickMs.value = 0
  lastProgressAt = 0
}

async function connectSSE(taskId: string) {
  if (es) es.close()
  stopProgressTick()
  liveTaskId.value = taskId
  liveProgress.value = {
    total_files: 0,
    done_files: 0,
    imported_bars: 0,
    status: 'running',
    task_type: '',
    error_count: 0,
    error_message: '',
  }
  liveStocks.value = []

  let ticketResp
  try {
    ticketResp = await createProgressTicket(taskId)
  } catch {
    ElMessage.error('无法获取进度订阅凭证')
    return
  }
  const ticket = ticketResp.data?.ticket
  if (!ticket) {
    ElMessage.error('进度 ticket 无效')
    return
  }

  es = new EventSource(taskProgressUrl(taskId, ticket))

  es.addEventListener('progress', (e) => {
    onProgressPayload(JSON.parse(e.data))
  })
  es.addEventListener('done', (e) => {
    try {
      const data = JSON.parse(e.data)
      onProgressPayload(data)
      liveProgress.value.status = data.status || 'succeeded'
      const bars = data.imported_bars ?? liveProgress.value.imported_bars
      if (bars > 0) {
        ElMessage.success(`任务完成，共入库 ${bars} 根 K 线`)
      } else {
        ElMessage.warning(data.message || '任务结束但未写入 K 线')
      }
    } catch {
      liveProgress.value.status = 'succeeded'
      ElMessage.success('任务执行完成')
    }
    stopProgressTick()
    es?.close()
    refreshHistory()
  })
  es.addEventListener('error', (e: Event) => {
    try {
      const raw = (e as MessageEvent).data
      if (typeof raw !== 'string' || !raw) {
        throw new Error('no message data')
      }
      const data = JSON.parse(raw)
      onProgressPayload(data)
      liveProgress.value.status = 'failed'
      ElMessage.error(data.message || data.error_message || '任务失败')
    } catch {
      liveProgress.value.status = 'failed'
      ElMessage.error('任务出错或连接断开')
    }
    stopProgressTick()
    es?.close()
    refreshHistory()
  })
  startProgressTick()
}

onUnmounted(() => {
  stopProgressTick()
  if (es) es.close()
})

// ── 任务历史 ──────────────────────────────────────────────────────────────────
const tasks = ref<any[]>([])
const totalTasks = ref(0)
const loadingHistory = ref(false)
const historyPage = ref(1)
const historyPageSize = ref(10)

async function refreshHistory() {
  loadingHistory.value = true
  try {
    const r = await listImportTasks({
      limit: historyPageSize.value,
      offset: (historyPage.value - 1) * historyPageSize.value,
    })
    tasks.value = r.data
    totalTasks.value = r.total || 0
  } finally {
    loadingHistory.value = false
  }
}

function viewTaskProgress(taskId: string) {
  tab.value = 'history' // 或者保持当前 tab，但这里我们提供一个统一查看的地方
  connectSSE(taskId)
}

async function handleRetry(taskId: string) {
  try {
    await retryImportTask(taskId)
    ElMessage.success('任务已重新启动')
    refreshHistory()
    viewTaskProgress(taskId) // 自动跳转并连接 SSE
  } catch (e: any) {
    ElMessage.error('重试失败：' + (e.message || '未知错误'))
  }
}

const TASK_TYPE_LABEL: Record<string, string> = {
  incremental: '增量导入',
  full: '全量导入',
  online_fetch: '在线补数',
  online_batch: '批量在线更新',
}
function taskTypeLabel(t: string) {
  return TASK_TYPE_LABEL[t] || t
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

onMounted(() => {
  refreshHistory()
})

async function onSubmitImport() {
  submittingImport.value = true
  try {
    const mkts = localMarkets.value.length ? localMarkets.value : undefined
    const r = await createImportTask({
      task_type: taskType.value,
      vipdoc_dir: vipdocDir.value || undefined,
      markets: mkts,
    })
    ElMessage.success(`导入任务已创建并开始执行: ${r.data.task_id}`)
    connectSSE(r.data.task_id)
  } finally {
    submittingImport.value = false
  }
}

// ── 在线批量 ─────────────────────────────────────────────────────────────────────
const today = new Date().toISOString().slice(0, 10)
const defaultStart = new Date(Date.now() - 365 * 24 * 3600 * 1000).toISOString().slice(0, 10)

const batchForm = ref<{
  markets: string[]
  periods: string[]
  codesRaw: string
  range: [string, string]
}>({
  markets: ['sh', 'sz'],
  periods: ['day'],
  codesRaw: '',
  range: [defaultStart, today],
})
const batchSubmitting = ref(false)

async function onBatchSubmit() {
  if (!batchForm.value.periods.length) {
    ElMessage.warning('至少选择一个周期')
    return
  }
  const codes = batchForm.value.codesRaw
    .split(/[\s,]+/)
    .map((c) => c.trim())
    .filter(Boolean)
  if (!codes.length && !batchForm.value.markets.length) {
    ElMessage.warning('请选择市场或填写具体代码')
    return
  }
  if (!batchForm.value.range?.length) {
    ElMessage.warning('请选择日期范围')
    return
  }
  batchSubmitting.value = true
  try {
    const r = await createOnlineBatchTask({
      markets: codes.length ? undefined : batchForm.value.markets,
      codes: codes.length ? codes : undefined,
      periods: batchForm.value.periods,
      start_date: batchForm.value.range[0],
      end_date: batchForm.value.range[1],
    })
    ElMessage.success(`已创建批量更新任务：${r.data.task_id.slice(0, 8)}…`)
    connectSSE(r.data.task_id)
  } finally {
    batchSubmitting.value = false
  }
}
</script>

<template>
  <el-card shadow="never">
    <el-tabs v-model="tab">
      <el-tab-pane label="本地数据导入" name="local">
        <el-alert
          title="本地 VIPDOC 历史数据导入"
          type="info"
          :closable="false"
          description="将本地通达信 VIPDOC 目录下的日线、5分钟线数据导入数据库。支持全量或增量导入。"
          show-icon
        />
        <el-form inline class="mt">
          <el-form-item label="市场筛选">
            <el-checkbox-group v-model="localMarkets">
              <el-checkbox value="sh">上海主板</el-checkbox>
              <el-checkbox value="sz">深圳主板/中小板</el-checkbox>
              <el-checkbox value="cyb">创业板 (300/301)</el-checkbox>
              <el-checkbox value="kcb">科创板 (688)</el-checkbox>
              <el-checkbox value="bj">北交所</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </el-form>
        <el-form inline class="mt">
          <el-form-item>
            <el-button type="default" :loading="uploading" @click="triggerFileSelect">
              {{ uploading ? `上传中 (${uploadProgress})` : '选择本地目录并扫描' }}
            </el-button>
            <input type="file" ref="fileInput" webkitdirectory directory multiple style="display: none" @change="onFilesSelected" />
          </el-form-item>
          <el-form-item label="任务类型">
            <el-radio-group v-model="taskType">
              <el-radio-button value="incremental">增量更新</el-radio-button>
              <el-radio-button value="full">全量重导</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-form>

        <el-divider />

        <el-empty v-if="!preview" description="点击「扫描预览」开始" />

        <div v-else>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="数据目录">{{ preview.data_dir }}</el-descriptions-item>
            <el-descriptions-item label="文件总数">{{ preview.total_files }}</el-descriptions-item>
            <el-descriptions-item label="变更文件（需导入）">
              <el-tag type="warning">{{ preview.changed_files }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="未变文件">
              <el-tag type="info">{{ preview.unchanged_files }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>

          <div v-if="liveTaskId && liveProgress.task_type !== 'online_batch'" class="mt">
            <el-card shadow="never">
              <template #header>
                实时导入进度
                <el-tag :type="statusTag(liveProgress.status) as any" size="small" style="margin-left: 8px;">
                  {{ liveProgress.status }}
                </el-tag>
              </template>
              <el-descriptions :column="3" border size="small">
                <el-descriptions-item label="任务 ID">{{ liveTaskId }}</el-descriptions-item>
                <el-descriptions-item label="标的数量">{{ liveProgress.code_count || '-' }}</el-descriptions-item>
                <el-descriptions-item label="文件进度">{{ liveProgress.done_files }} / {{ liveProgress.total_files }}</el-descriptions-item>
                <el-descriptions-item label="入库 K 线数">{{ liveProgress.imported_bars }}</el-descriptions-item>
              </el-descriptions>
              
              <el-progress 
                class="mt" 
                :percentage="liveProgress.total_files ? Math.round(liveProgress.done_files / liveProgress.total_files * 100) : 0"
                :status="liveProgress.status === 'failed' ? 'exception' : (liveProgress.status === 'succeeded' ? 'success' : '')"
              />

              <el-table :data="liveStocks" size="small" class="mt" max-height="300" border>
                <el-table-column prop="full_code" label="股票代码" width="120" />
                <el-table-column prop="period" label="周期" width="100" />
                <el-table-column prop="inserted" label="新增入库数" align="right" />
              </el-table>
            </el-card>
          </div>

          <el-row :gutter="16" class="mt" v-else>
            <el-col :span="12">
              <el-card shadow="never">
                <template #header>按周期</template>
                <el-table :data="periodRows(preview)" size="small">
                  <el-table-column prop="period" label="周期" />
                  <el-table-column prop="count" label="文件数" align="right" />
                </el-table>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never">
                <template #header>按市场</template>
                <el-table :data="marketRows(preview)" size="small">
                  <el-table-column prop="market" label="市场" />
                  <el-table-column prop="day" label=".day" align="right" />
                  <el-table-column prop="m5" label=".lc5" align="right" />
                </el-table>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <el-tab-pane label="在线批量更新" name="batch">
        <el-alert
          title="按市场 / 周期 / 日期范围批量更新"
          type="warning"
          :closable="false"
          description="选择市场和周期，TDX 协议会按代码×周期逐对在线拉取并补全 [起止日期] 范围内的 K 线。可在「任务记录」查看实时进度。单次任务量大时会被 TDX 主站限速，请按需切片；单只标的可在下方填写具体代码。"
          show-icon
        />

        <el-form class="mt" label-position="top">
          <el-form-item label="市场（codes 为空时按此从 symbol 表枚举）">
            <el-checkbox-group v-model="batchForm.markets">
              <el-checkbox value="sh">上海主板</el-checkbox>
              <el-checkbox value="sz">深圳主板/中小板</el-checkbox>
              <el-checkbox value="cyb">创业板 (300/301)</el-checkbox>
              <el-checkbox value="kcb">科创板 (688)</el-checkbox>
              <el-checkbox value="bj">北交所 (BJ)</el-checkbox>
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="周期（可多选）">
            <el-checkbox-group v-model="batchForm.periods">
              <el-checkbox value="5m">5 分钟</el-checkbox>
              <el-checkbox value="30m">30 分钟</el-checkbox>
              <el-checkbox value="day">日线</el-checkbox>
              <el-checkbox value="week">周线</el-checkbox>
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="日期范围">
            <el-date-picker
              v-model="batchForm.range"
              type="daterange"
              value-format="YYYY-MM-DD"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
          </el-form-item>

          <el-form-item label="指定代码（可选，每行或逗号分隔；填写后忽略上面的市场选择）">
            <el-input
              v-model="batchForm.codesRaw"
              type="textarea"
              :rows="3"
              placeholder="例如：sh600519, sz000001&#10;sh688981"
            />
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="batchSubmitting" @click="onBatchSubmit">
              提交批量更新任务
            </el-button>
          </el-form-item>
        </el-form>

        <div v-if="liveTaskId && liveProgress.task_type === 'online_batch'" class="mt">
          <el-card shadow="never">
            <template #header>
              在线批量更新进度
              <el-tag :type="statusTag(liveProgress.status) as any" size="small" style="margin-left: 8px;">
                {{ liveProgress.status }}
              </el-tag>
            </template>
            <el-descriptions :column="3" border size="small">
              <el-descriptions-item label="任务 ID">{{ liveTaskId }}</el-descriptions-item>
              <el-descriptions-item label="标的数量">{{ liveProgress.code_count || '-' }}</el-descriptions-item>
              <el-descriptions-item label="进度 (代码×周期)">{{ liveProgress.done_files }} / {{ liveProgress.total_files }}</el-descriptions-item>
              <el-descriptions-item label="入库 K 线数">{{ liveProgress.imported_bars }}</el-descriptions-item>
              <el-descriptions-item label="已耗时">{{ displayElapsed() }}</el-descriptions-item>
              <el-descriptions-item label="预计剩余">{{ displayEta() }}</el-descriptions-item>
              <el-descriptions-item label="处理速度">
                {{ liveProgress.speed_per_minute != null ? `${liveProgress.speed_per_minute} 对/分钟` : '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="并发">{{ concurrencyLabel() }}</el-descriptions-item>
              <el-descriptions-item label="失败数">{{ liveProgress.error_count }}</el-descriptions-item>
              <el-descriptions-item
                v-if="liveProgress.batch_cooldown_remain_seconds"
                label="批次熔断冷却"
              >
                {{ formatDuration(liveProgress.batch_cooldown_remain_seconds) }}
              </el-descriptions-item>
              <el-descriptions-item
                v-if="liveProgress.pool_cooldown_remain_seconds"
                label="池全局冷却"
              >
                {{ formatDuration(liveProgress.pool_cooldown_remain_seconds) }}
              </el-descriptions-item>
            </el-descriptions>
            
            <el-progress 
              class="mt" 
              :percentage="liveProgress.total_files ? Math.round(liveProgress.done_files / liveProgress.total_files * 100) : 0"
              :status="liveProgress.status === 'failed' ? 'exception' : (liveProgress.status === 'succeeded' ? 'success' : '')"
            />

            <el-table :data="liveStocks" size="small" class="mt" max-height="300" border>
              <el-table-column prop="full_code" label="代码" width="120" />
              <el-table-column prop="period" label="周期" width="100" />
              <el-table-column prop="inserted" label="新增入库" align="right" />
            </el-table>
          </el-card>
        </div>
      </el-tab-pane>
      <el-tab-pane label="任务记录" name="history">
        <el-row :gutter="16">
          <el-col :span="liveTaskId ? 14 : 24">
            <el-table v-loading="loadingHistory" :data="tasks" stripe size="small" border>
              <el-table-column prop="task_id" label="任务 ID" min-width="180">
                <template #default="{ row }">
                  <el-link type="primary" @click="connectSSE(row.task_id)">{{ row.task_id.slice(0, 8) }}...</el-link>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="120">
                <template #default="{ row }">{{ taskTypeLabel(row.task_type) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="statusTag(row.status) as any" size="small">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="进度" width="120">
                <template #default="{ row }">{{ row.done_files }} / {{ row.total_files }}</template>
              </el-table-column>
              <el-table-column prop="imported_bars" label="入库数" align="right" width="100" />
              <el-table-column prop="created_at" label="创建时间" min-width="160" />
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button link type="primary" @click="viewTaskProgress(row.task_id)">查看</el-button>
                  <el-button link type="warning" v-if="row.status === 'failed' || row.status === 'cancelled'" @click="handleRetry(row.task_id)">重试</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-pagination
              class="mt"
              v-model:current-page="historyPage"
              v-model:page-size="historyPageSize"
              :total="totalTasks"
              :page-sizes="[10, 20, 50]"
              layout="total, prev, pager, next, sizes"
              @current-change="refreshHistory"
              @size-change="refreshHistory"
            />
          </el-col>
          <el-col :span="10" v-if="liveTaskId">
            <el-card shadow="never">
              <template #header>
                任务实时进度
                <el-tag :type="statusTag(liveProgress.status) as any" size="small" style="margin-left: 8px">
                  {{ liveProgress.status }}
                </el-tag>
              </template>
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="任务 ID">{{ liveTaskId }}</el-descriptions-item>
                <el-descriptions-item label="类型">{{ taskTypeLabel(liveProgress.task_type) }}</el-descriptions-item>
                <el-descriptions-item label="进度">{{ liveProgress.done_files }} / {{ liveProgress.total_files }}</el-descriptions-item>
                <el-descriptions-item label="入库数">{{ liveProgress.imported_bars }}</el-descriptions-item>
                <template v-if="isOnlineBatchProgress()">
                  <el-descriptions-item label="已耗时">{{ displayElapsed() }}</el-descriptions-item>
                  <el-descriptions-item label="预计剩余">{{ displayEta() }}</el-descriptions-item>
                  <el-descriptions-item label="速度">
                    {{ liveProgress.speed_per_minute != null ? `${liveProgress.speed_per_minute} 对/分钟` : '-' }}
                  </el-descriptions-item>
                  <el-descriptions-item label="并发">{{ concurrencyLabel() }}</el-descriptions-item>
                  <el-descriptions-item
                    v-if="liveProgress.batch_cooldown_remain_seconds || liveProgress.pool_cooldown_remain_seconds"
                    label="冷却"
                  >
                    <span v-if="liveProgress.batch_cooldown_remain_seconds">
                      批次 {{ formatDuration(liveProgress.batch_cooldown_remain_seconds) }}
                    </span>
                    <span v-if="liveProgress.pool_cooldown_remain_seconds">
                      {{ liveProgress.batch_cooldown_remain_seconds ? '；' : '' }}池
                      {{ formatDuration(liveProgress.pool_cooldown_remain_seconds) }}
                    </span>
                  </el-descriptions-item>
                </template>
                <el-descriptions-item v-if="liveProgress.error_message" label="错误">{{ liveProgress.error_message }}</el-descriptions-item>
              </el-descriptions>
              
              <el-progress 
                class="mt" 
                :percentage="liveProgress.total_files ? Math.round(liveProgress.done_files / liveProgress.total_files * 100) : 0"
                :status="liveProgress.status === 'failed' ? 'exception' : (liveProgress.status === 'succeeded' ? 'success' : '')"
              />

              <el-table :data="liveStocks" size="small" class="mt" max-height="300" border>
                <el-table-column prop="full_code" label="代码" width="100" />
                <el-table-column prop="period" label="周期" width="70" />
                <el-table-column prop="inserted" label="入库数" align="right" />
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script lang="ts">
function periodRows(p: ScanPreview) {
  return Object.entries(p.by_period).map(([period, count]) => ({ period, count }))
}
function marketRows(p: ScanPreview) {
  return Object.entries(p.by_market).map(([market, d]) => ({
    market,
    day: d.day || 0,
    m5: d['5m'] || d['lc5'] || 0,
  }))
}
export { periodRows, marketRows }
</script>

<style scoped>
.mt { margin-top: 16px; }
</style>
