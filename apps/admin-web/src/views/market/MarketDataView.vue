<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createImportTask, scanPreview, type ScanPreview, createOnlineBatchTask, onlineFetch, uploadVipdoc, listImportTasks, retryImportTask } from '@/api/market'

const router = useRouter()
const tab = ref<'local' | 'single' | 'batch' | 'history'>('local')

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
const liveTaskId = ref('')
const liveProgress = ref({
  total_files: 0,
  done_files: 0,
  imported_bars: 0,
  status: '',
  task_type: '',
  error_count: 0,
  error_message: ''
})
const liveStocks = ref<{ full_code: string, period: string, inserted: number }[]>([])
let es: EventSource | null = null

function connectSSE(taskId: string) {
  if (es) es.close()
  liveTaskId.value = taskId
  liveProgress.value = { 
    total_files: 0, 
    done_files: 0, 
    imported_bars: 0, 
    status: 'running',
    task_type: '',
    error_count: 0,
    error_message: ''
  }
  liveStocks.value = []
  
  const baseUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  es = new EventSource(`${baseUrl}/admin/market/import-tasks/${taskId}/progress`)
  
  es.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data)
    liveProgress.value = { ...liveProgress.value, ...data }
    
    if (data.recent_imported) {
      liveStocks.value.unshift(...data.recent_imported)
      if (liveStocks.value.length > 200) {
        liveStocks.value.length = 200
      }
    }
  })
  es.addEventListener('done', (e) => {
    try {
      const data = JSON.parse(e.data)
      liveProgress.value = { ...liveProgress.value, ...data, status: data.status || 'succeeded' }
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
    es?.close()
    refreshHistory()
  })
  es.addEventListener('error', (e) => {
    try {
      const data = JSON.parse(e.data)
      liveProgress.value = { ...liveProgress.value, ...data, status: 'failed' }
      ElMessage.error(data.message || data.error_message || '任务失败')
    } catch {
      liveProgress.value.status = 'failed'
      ElMessage.error('任务出错或连接断开')
    }
    es?.close()
    refreshHistory()
  })
}

onUnmounted(() => {
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

// ── 在线单标的 ────────────────────────────────────────────────────────────────────
const singleForm = ref({ full_code: 'sh600519', period: 'day', max_count: 800 })
const singleSubmitting = ref(false)
const singleLastInserted = ref<number | null>(null)

async function onSingleFetch() {
  singleSubmitting.value = true
  try {
    const r = await onlineFetch(singleForm.value)
    singleLastInserted.value = r.data.inserted
    ElMessage.success(`已写入 ${r.data.inserted} 根`)
  } finally {
    singleSubmitting.value = false
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

      <el-tab-pane label="在线单标的补数" name="single">
        <el-alert
          title="单标的在线补数"
          type="info"
          :closable="false"
          description="使用通达信在线协议直接拉取最近 N 根 K 线并写入数据库。适合：单标的快速补齐当日或最近若干根。大规模历史导入请用『本地数据导入』或后面的『在线批量更新』。"
          show-icon
        />

        <el-form class="mt" inline>
          <el-form-item label="完整代码">
            <el-input v-model="singleForm.full_code" placeholder="如 sh600519" style="width: 200px" />
          </el-form-item>
          <el-form-item label="周期">
            <el-select v-model="singleForm.period" style="width: 140px">
              <el-option label="1 分钟" value="1m" />
              <el-option label="5 分钟" value="5m" />
              <el-option label="15 分钟" value="15m" />
              <el-option label="30 分钟" value="30m" />
              <el-option label="60 分钟" value="60m" />
              <el-option label="日线" value="day" />
              <el-option label="周线" value="week" />
              <el-option label="月线" value="month" />
            </el-select>
          </el-form-item>
          <el-form-item label="最多条数">
            <el-input-number v-model="singleForm.max_count" :min="1" :max="8000" :step="100" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="singleSubmitting" @click="onSingleFetch">拉取并入库</el-button>
          </el-form-item>
        </el-form>

        <el-alert
          v-if="singleLastInserted !== null"
          class="mt"
          :title="`本次写入 ${singleLastInserted} 根 K 线（已存在的会自动跳过）`"
          type="success"
          :closable="false"
        />
      </el-tab-pane>

      <el-tab-pane label="在线批量更新" name="batch">
        <el-alert
          title="按市场 / 周期 / 日期范围批量更新"
          type="warning"
          :closable="false"
          description="选择市场和周期，TDX 协议会按代码×周期逐对在线拉取并补全 [起止日期] 范围内的 K 线。所有任务会进入『任务列表』，可在 SSE 进度页查看实时进度。注意：单次任务量大时会被 TDX 主站限速，请按需切片。"
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
