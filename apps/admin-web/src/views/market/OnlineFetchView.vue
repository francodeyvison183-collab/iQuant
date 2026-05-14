<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createOnlineBatchTask, onlineFetch } from '@/api/market'

const router = useRouter()

const tab = ref<'single' | 'batch'>('single')

// ── 单标的 ────────────────────────────────────────────────────────────────────
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

// ── 批量 ─────────────────────────────────────────────────────────────────────
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
    router.push({ path: '/market/tasks', query: { task_id: r.data.task_id } })
  } finally {
    batchSubmitting.value = false
  }
}
</script>

<template>
  <el-card shadow="never">
    <el-tabs v-model="tab">
      <el-tab-pane label="单标的补数" name="single">
        <el-alert
          title="单标的在线补数"
          type="info"
          :closable="false"
          description="使用通达信在线协议直接拉取最近 N 根 K 线并写入数据库。适合：单标的快速补齐当日或最近若干根。大规模历史导入请用『历史数据导入』或下面的『批量更新』。"
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

      <el-tab-pane label="批量更新" name="batch">
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
              <el-checkbox value="sh">上海 (SH)</el-checkbox>
              <el-checkbox value="sz">深圳 (SZ)</el-checkbox>
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
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<style scoped>
.mt { margin-top: 16px; }
</style>
