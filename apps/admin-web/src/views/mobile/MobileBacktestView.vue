<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import IosNavBar from '@/components/mobile/ios/IosNavBar.vue'
import IosListGroup from '@/components/mobile/ios/IosListGroup.vue'
import IosListRow from '@/components/mobile/ios/IosListRow.vue'
import IosComplianceBanner from '@/components/mobile/ios/IosComplianceBanner.vue'
import { extractApiError } from '@/api/errors'
import {
  createBacktest,
  getBacktest,
  listBacktests,
  type BacktestTask,
  type BacktestTaskSummary,
} from '@/api/backtests'
import { listStrategies, type StrategySummary } from '@/api/strategies'

type BtScreen = 'list' | 'create' | 'detail'

const screen = ref<BtScreen>('list')
const jobs = ref<BacktestTaskSummary[]>([])
const loading = ref(false)
const detail = ref<BacktestTask | null>(null)
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)
const chartEl = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const confirmedStrategies = ref<StrategySummary[]>([])
const createVersionId = ref('')
const createFullCode = ref('sz300750')
const createBusy = ref(false)

const statusLabel: Record<string, string> = {
  queued: '排队中',
  running: '进行中',
  succeeded: '已完成',
  failed: '失败',
}

function tone(status: string) {
  if (status === 'succeeded') return 'done'
  if (status === 'failed') return 'fail'
  return 'run'
}

async function loadList() {
  loading.value = true
  try {
    const res = await listBacktests({ limit: 30 })
    jobs.value = res.data ?? []
  } catch (e) {
    ElMessage.error(extractApiError(e))
  } finally {
    loading.value = false
  }
}

async function loadConfirmedStrategies() {
  try {
    const res = await listStrategies({ limit: 50 })
    confirmedStrategies.value = (res.data ?? []).filter((s) => s.status === 'confirmed')
    if (confirmedStrategies.value.length && !createVersionId.value) {
      const s = confirmedStrategies.value[0]
      createVersionId.value = s.confirmed_version_id ?? ''
    }
  } catch {
    confirmedStrategies.value = []
  }
}

async function openDetail(id: string) {
  try {
    const res = await getBacktest(id)
    detail.value = res.data
    screen.value = 'detail'
    startPollIfNeeded()
    await renderChart()
  } catch (e) {
    ElMessage.error(extractApiError(e))
  }
}

function startPollIfNeeded() {
  stopPoll()
  if (!detail.value || !['queued', 'running'].includes(detail.value.status)) return
  pollTimer.value = setInterval(async () => {
    if (!detail.value) return
    try {
      const res = await getBacktest(detail.value.id)
      detail.value = res.data
      if (!['queued', 'running'].includes(res.data.status)) {
        stopPoll()
        await loadList()
        await renderChart()
      }
    } catch {
      /* ignore poll errors */
    }
  }, 2000)
}

function stopPoll() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

async function renderChart() {
  const curve = detail.value?.report?.equity_curve
  if (!chartEl.value || !curve?.length) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption({
    grid: { left: 8, right: 8, top: 12, bottom: 24 },
    xAxis: { type: 'category', data: curve.map((p) => p.bar_time.slice(0, 10)), show: false },
    yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: '#eee' } } },
    series: [
      {
        type: 'line',
        data: curve.map((p) => p.equity),
        showSymbol: false,
        lineStyle: { width: 1.5, color: '#e54d42' },
        areaStyle: { color: 'rgba(229,77,66,0.08)' },
      },
    ],
  })
}

const detailSummary = computed(() => detail.value?.report?.summary ?? {})

async function submitCreate() {
  if (!createVersionId.value || !createFullCode.value.trim()) {
    ElMessage.warning('请选择已确认策略并填写标的代码')
    return
  }
  createBusy.value = true
  try {
    const res = await createBacktest({
      strategy_version_id: createVersionId.value,
      full_code: createFullCode.value.trim(),
    })
    ElMessage.success('回测任务已提交')
    screen.value = 'detail'
    detail.value = res.data
    startPollIfNeeded()
    await loadList()
  } catch (e) {
    ElMessage.error(extractApiError(e))
  } finally {
    createBusy.value = false
  }
}

function goList() {
  stopPoll()
  screen.value = 'list'
  detail.value = null
}

function goCreate() {
  loadConfirmedStrategies()
  screen.value = 'create'
}

watch(
  () => detail.value?.report?.equity_curve,
  () => {
    renderChart()
  },
)

onMounted(loadList)
onUnmounted(stopPoll)
</script>

<template>
  <div class="bt-page">
    <IosNavBar
      :title="screen === 'list' ? '回测' : screen === 'create' ? '新建回测' : '回测详情'"
      :show-back="screen !== 'list'"
      @back="goList"
    />

    <div class="bt-body">
      <template v-if="screen === 'list'">
        <IosComplianceBanner />
        <section class="bt-cta">
          <button type="button" class="bt-cta__btn" @click="goCreate">新建回测</button>
        </section>
        <div v-if="loading" class="bt-loading">加载中…</div>
        <IosListGroup v-else title="任务">
          <button
            v-for="j in jobs"
            :key="j.id"
            type="button"
            class="bt-cell"
            @click="openDetail(j.id)"
          >
            <div class="bt-cell__text">
              <span class="bt-cell__title">{{ j.strategy_name ?? j.full_code }}</span>
              <span class="bt-cell__sub">{{ j.full_code }} · {{ j.period }}</span>
            </div>
            <span class="bt-pill" :class="`bt-pill--${tone(j.status)}`">
              {{ statusLabel[j.status] ?? j.status }}
            </span>
            <span class="bt-cell__chev" aria-hidden="true">›</span>
          </button>
          <p v-if="!jobs.length" class="bt-empty">暂无回测，请先确认行为策略 DSL</p>
        </IosListGroup>
      </template>

      <template v-else-if="screen === 'create'">
        <IosListGroup title="已确认策略">
          <select v-model="createVersionId" class="bt-select">
            <option value="" disabled>选择策略版本</option>
            <option
              v-for="s in confirmedStrategies"
              :key="s.id"
              :value="s.confirmed_version_id ?? ''"
            >
              {{ s.name }} ({{ s.period }})
            </option>
          </select>
        </IosListGroup>
        <IosListGroup title="标的">
          <input v-model="createFullCode" class="bt-input" placeholder="如 sz300750" />
        </IosListGroup>
        <section class="bt-cta">
          <button type="button" class="bt-cta__btn" :disabled="createBusy" @click="submitCreate">
            {{ createBusy ? '提交中…' : '提交回测' }}
          </button>
        </section>
        <p v-if="!confirmedStrategies.length" class="bt-hint">
          请先在「训练 / 工作台」确认行为策略 DSL。
        </p>
      </template>

      <template v-else-if="detail">
        <section v-if="detail.status !== 'succeeded'" class="bt-status-banner">
          {{ statusLabel[detail.status] ?? detail.status }}
          <span v-if="detail.error_message"> — {{ detail.error_message }}</span>
        </section>
        <template v-if="detail.report">
          <section class="bt-hero">
            <p class="bt-hero__label">累计收益</p>
            <p class="bt-hero__value">{{ detailSummary.total_return ?? '—' }}</p>
            <div class="bt-hero__grid">
              <div>
                <span class="bt-metric__k">最大回撤</span>
                <span class="bt-metric__v">{{ detailSummary.max_drawdown ?? '—' }}</span>
              </div>
              <div>
                <span class="bt-metric__k">胜率</span>
                <span class="bt-metric__v">{{ detailSummary.win_rate ?? '—' }}</span>
              </div>
              <div>
                <span class="bt-metric__k">交易次数</span>
                <span class="bt-metric__v">{{ detailSummary.trade_count ?? '—' }}</span>
              </div>
            </div>
          </section>
          <div ref="chartEl" class="bt-chart" />
          <IosListGroup title="样本划分">
            <div class="bt-stat">
              <span class="bt-stat__k">样本内</span>
              <span class="bt-stat__v">{{ detailSummary.in_sample_return ?? '—' }}</span>
            </div>
            <div class="bt-stat">
              <span class="bt-stat__k">样本外</span>
              <span class="bt-stat__v">{{ detailSummary.out_sample_return ?? '—' }}</span>
            </div>
          </IosListGroup>
          <IosListGroup v-if="detail.report.warnings.length" title="提示">
            <p v-for="(w, i) in detail.report.warnings" :key="i" class="bt-warn">{{ w }}</p>
          </IosListGroup>
        </template>
        <footer class="bt-risk">
          <p>
            历史回测不代表未来表现；费用、滑点模型为 MVP 简化。详见产品文档与合规提示。
          </p>
        </footer>
      </template>
    </div>
  </div>
</template>

<style scoped>
.bt-page {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: var(--h5-bg-grouped);
}
.bt-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-bottom: 16px;
}
.bt-cta {
  margin: 12px 16px;
}
.bt-cta__btn {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  background: var(--h5-tint);
}
.bt-loading,
.bt-empty,
.bt-hint {
  padding: 16px;
  text-align: center;
  font-size: 14px;
  color: var(--h5-label-secondary);
}
.bt-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 12px 16px;
  border: none;
  background: var(--h5-bg-elevated);
  text-align: left;
}
.bt-cell__text {
  flex: 1;
  min-width: 0;
}
.bt-cell__title {
  font-size: 17px;
  font-weight: 500;
}
.bt-cell__sub {
  font-size: 13px;
  color: var(--h5-label-secondary);
}
.bt-pill {
  padding: 4px 10px;
  border-radius: 100px;
  font-size: 12px;
  font-weight: 600;
}
.bt-pill--done {
  background: rgba(52, 199, 89, 0.15);
  color: #248a3d;
}
.bt-pill--run {
  background: rgba(0, 122, 255, 0.12);
  color: var(--h5-tint);
}
.bt-pill--fail {
  background: rgba(255, 59, 48, 0.12);
  color: #c62828;
}
.bt-cell__chev {
  font-size: 20px;
  color: var(--h5-label-tertiary);
}
.bt-select,
.bt-input {
  width: 100%;
  margin: 0;
  padding: 12px 16px;
  border: none;
  font-size: 17px;
  background: var(--h5-bg-elevated);
}
.bt-status-banner {
  margin: 12px 16px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(0, 122, 255, 0.1);
  font-size: 14px;
}
.bt-hero {
  margin: 12px 16px;
  padding: 20px;
  border-radius: var(--h5-radius-cell);
  background: var(--h5-bg-elevated);
}
.bt-hero__label {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--h5-label-secondary);
}
.bt-hero__value {
  margin: 0 0 16px;
  font-size: 40px;
  font-weight: 700;
}
.bt-hero__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.bt-metric__k {
  display: block;
  font-size: 11px;
  color: var(--h5-label-secondary);
}
.bt-metric__v {
  font-size: 17px;
  font-weight: 600;
}
.bt-chart {
  margin: 0 16px 16px;
  height: 180px;
  border-radius: var(--h5-radius-cell);
  background: var(--h5-bg-elevated);
}
.bt-stat {
  display: flex;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--h5-bg-elevated);
}
.bt-stat + .bt-stat {
  border-top: 0.5px solid var(--h5-separator);
}
.bt-warn {
  margin: 0;
  padding: 10px 16px;
  font-size: 13px;
  color: var(--h5-label-secondary);
}
.bt-risk {
  margin: 8px 16px;
  padding: 12px;
  border-radius: var(--h5-radius-cell);
  background: rgba(142, 142, 147, 0.12);
}
.bt-risk p {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--h5-label-secondary);
}
</style>
