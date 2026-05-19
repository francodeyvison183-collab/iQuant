<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import IosNavBar from '@/components/mobile/ios/IosNavBar.vue'
import IosListGroup from '@/components/mobile/ios/IosListGroup.vue'
import IosListRow from '@/components/mobile/ios/IosListRow.vue'
import IosSegmentedControl from '@/components/mobile/ios/IosSegmentedControl.vue'
import IosComplianceBanner from '@/components/mobile/ios/IosComplianceBanner.vue'
import IosSymbolPickerSheet from '@/components/mobile/ios/IosSymbolPickerSheet.vue'
import MobileLabelChart from '@/views/mobile/MobileLabelChart.vue'
import { useH5RecentSymbols } from '@/composables/useH5RecentSymbols'
import type { SymbolItem } from '@/api/market'
import { extractApiError } from '@/api/errors'
import { KLINE_PERIOD_OPTIONS } from '@/chart/klinePeriod'
import {
  completeBatchItem,
  createLabelBatch,
  createLabelSession,
  getBatchCurrent,
  getBatchSummary,
  getLabelBatch,
  getLabelSession,
  listLabelBatches,
  patchBatchSummary,
  skipBatchItem,
  type LabelBatch,
  type LabelBatchCurrent,
  type LabelBatchListItem,
  type LabelBatchSummary,
  type LabelQueueItem,
  type LabelSession,
} from '@/api/labels'

type LabelScreen =
  | 'home'
  | 'batch-chart'
  | 'batch-done'
  | 'batch-history'
  | 'batch-detail'
  | 'batch-review'
  | 'pick'
  | 'chart'
  | 'list'

const screen = ref<LabelScreen>('home')
const chartMode = ref('buy')
const chartModes = [
  { value: 'buy', label: '买入' },
  { value: 'sell', label: '卖出' },
  { value: 'pan', label: '平移' },
  { value: 'undo', label: '撤销' },
]

const { recent: recentSymbols, remember: rememberSymbol } = useH5RecentSymbols()
const selectedSymbol = ref<SymbolItem | null>(null)
const symbolPickerOpen = ref(false)
const labelSessionId = ref<string | null>(null)
const pairCount = ref(0)
const sessionDetail = ref<LabelSession | null>(null)
const chartBusy = ref(false)
const labelChartRef = ref<InstanceType<typeof MobileLabelChart> | null>(null)
const chartFullscreen = ref(false)

const batchId = ref<string | null>(null)
const batchSnapshot = ref<LabelBatch | null>(null)
const currentItem = ref<LabelQueueItem | null>(null)
const batchActionBusy = ref(false)
const listReturnScreen = ref<LabelScreen>('chart')
const batchSummary = ref<LabelBatchSummary | null>(null)
const summaryLoading = ref(false)
const summarySaving = ref(false)
const selectedCorrections = ref<string[]>([])
const batchHistory = ref<LabelBatchListItem[]>([])
const historyLoading = ref(false)
const reviewItem = ref<LabelQueueItem | null>(null)

const chartPeriod = ref('day')
const marketFilter = ref('')
const periodOptions = KLINE_PERIOD_OPTIONS.map((p) => ({ value: p.value, label: p.label }))
const marketOptions = [
  { value: '', label: '全市场' },
  { value: 'sz', label: '深市' },
  { value: 'sh', label: '沪市' },
]

const symbolRowValue = computed(() => {
  const s = selectedSymbol.value
  if (!s) return '轻点选择'
  return s.name ? `${s.full_code} · ${s.name}` : s.full_code
})

const chartTitleCode = computed(() => {
  if (screen.value === 'batch-chart' && currentItem.value) {
    const n = currentItem.value.symbol_name
    return n ? `${currentItem.value.full_code} · ${n}` : currentItem.value.full_code
  }
  return selectedSymbol.value?.full_code ?? '未选标的'
})

const navTitle = computed(() => {
  if (screen.value === 'home') return 'K 线标注'
  if (screen.value === 'batch-done') return '本轮完成'
  if (screen.value === 'batch-history') return '标注批次'
  if (screen.value === 'batch-detail') return '批次明细'
  if (screen.value === 'batch-review') return chartTitleCode.value
  if (screen.value === 'batch-chart') return chartTitleCode.value
  if (screen.value === 'list') return '逻辑样本'
  return chartTitleCode.value
})

const progressText = computed(() => {
  const p = batchSnapshot.value?.progress
  if (!p?.current_index) return ''
  return `${p.current_index}/${p.total}`
})

const batchDoneStats = computed(() => {
  const p = batchSnapshot.value?.progress
  if (!p) return ''
  return `完成 ${p.completed} · 跳过 ${p.skipped} · 共 ${p.total} 只`
})

watch(chartMode, (m, prev) => {
  if (m !== 'undo') return
  const r = labelChartRef.value?.undoLast()
  chartMode.value = prev && prev !== 'undo' ? prev : 'buy'
  ElMessage.info(r?.message ?? '暂无可撤销内容')
})

const chartModeHint = computed(() => {
  switch (chartMode.value) {
    case 'sell':
      return '点选理想卖出 K 线，完成一笔「若理想执行」的买卖样本'
    case 'pan':
      return '单指拖动图表平移；双指缩放由图表处理'
    case 'undo':
      return ''
    default:
      return '点选理想买入 K 线；随后切到卖出或继续点 K 线完成样本'
  }
})

const pairCountLabel = computed(() => {
  if (pairCount.value < 1) return '尚未记录样本'
  return `已表达 ${pairCount.value} 笔交易逻辑样本`
})

watch(
  () => currentItem.value?.id,
  () => {
    if (screen.value === 'batch-chart') chartMode.value = 'buy'
  },
)

function onSuggestChartMode(mode: string) {
  chartMode.value = mode
}

function resetRoundState() {
  batchSummary.value = null
  selectedCorrections.value = []
  chartMode.value = 'buy'
}

function applyBatchCurrent(data: LabelBatchCurrent) {
  batchSnapshot.value = data.batch
  batchId.value = data.batch.id
  currentItem.value = data.current_item
  if (data.session) {
    labelSessionId.value = data.session.id
    pairCount.value = data.session.pairs?.length ?? 0
    selectedSymbol.value = {
      full_code: data.session.full_code,
      code: data.session.full_code.slice(2),
      market: data.session.full_code.slice(0, 2),
      name: data.current_item?.symbol_name ?? '',
      asset_type: 'stock',
      list_date: null,
    }
  }
}

async function startBatch() {
  chartBusy.value = true
  resetRoundState()
  try {
    const r = await createLabelBatch({
      period: chartPeriod.value,
      market: marketFilter.value || null,
      batch_size: 20,
    })
    batchId.value = r.data.id
    await loadBatchCurrent()
    screen.value = 'batch-chart'
  } catch (err) {
    ElMessage.error(extractApiError(err) || '创建标注批次失败')
  } finally {
    chartBusy.value = false
  }
}

async function loadBatchSummary() {
  if (!batchId.value) return
  summaryLoading.value = true
  try {
    const r = await getBatchSummary(batchId.value)
    batchSummary.value = r.data
    selectedCorrections.value = [...(r.data.user_corrections ?? [])]
  } catch (err) {
    batchSummary.value = null
    ElMessage.error(extractApiError(err) || '加载总结失败')
  } finally {
    summaryLoading.value = false
  }
}

async function saveCorrections() {
  if (!batchId.value || summarySaving.value) return
  summarySaving.value = true
  try {
    const r = await patchBatchSummary(batchId.value, selectedCorrections.value)
    batchSummary.value = r.data
    ElMessage.success('已保存你的修正')
  } catch (err) {
    ElMessage.error(extractApiError(err))
  } finally {
    summarySaving.value = false
  }
}

function toggleCorrection(id: string) {
  const set = new Set(selectedCorrections.value)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  selectedCorrections.value = [...set]
}

async function loadBatchHistory(limit = 8) {
  historyLoading.value = true
  try {
    const r = await listLabelBatches({ limit, offset: 0 })
    batchHistory.value = r.data ?? []
  } catch {
    batchHistory.value = []
  } finally {
    historyLoading.value = false
  }
}

async function openBatchDetail(id: string) {
  chartBusy.value = true
  try {
    const r = await getLabelBatch(id)
    batchId.value = r.data.id
    batchSnapshot.value = r.data
    screen.value = 'batch-detail'
  } catch (err) {
    ElMessage.error(extractApiError(err) || '加载批次失败')
  } finally {
    chartBusy.value = false
  }
}

async function openBatchReview(item: LabelQueueItem) {
  if (!item.session_id || !batchSnapshot.value) return
  reviewItem.value = item
  labelSessionId.value = item.session_id
  chartPeriod.value = batchSnapshot.value.period
  selectedSymbol.value = {
    full_code: item.full_code,
    code: item.full_code.slice(2),
    market: item.full_code.slice(0, 2),
    name: item.symbol_name ?? '',
    asset_type: 'stock',
    list_date: null,
  }
  screen.value = 'batch-review'
}

function itemStatusLabel(status: string) {
  if (status === 'completed') return '已完成'
  if (status === 'skipped') return '已跳过'
  return '待表达'
}

function fmtDate(iso: string) {
  return iso.replace('T', ' ').slice(0, 16)
}

async function loadBatchCurrent() {
  if (!batchId.value) return
  const r = await getBatchCurrent(batchId.value)
  applyBatchCurrent(r.data)
  if (r.data.done) {
    screen.value = 'batch-done'
    void loadBatchSummary()
    return
  }
  if (!r.data.current_item || !r.data.session) {
    ElMessage.warning('批次队列异常，请返回重试')
    return
  }
}

async function skipCurrent() {
  if (!batchId.value || !currentItem.value || batchActionBusy.value) return
  batchActionBusy.value = true
  try {
    const r = await skipBatchItem(batchId.value, currentItem.value.id)
    applyBatchCurrent(r.data)
    if (r.data.done) {
      screen.value = 'batch-done'
      void loadBatchSummary()
      ElMessage.success('本轮表达已完成，可查看节奏摘要')
    } else {
      ElMessage.info('已跳过，换下一只表达')
    }
  } catch (err) {
    ElMessage.error(extractApiError(err))
  } finally {
    batchActionBusy.value = false
  }
}

async function completeCurrent() {
  if (!batchId.value || !currentItem.value || batchActionBusy.value) return
  if (pairCount.value < 1) {
    ElMessage.warning('请至少表达一对理想买卖，或点「跳过本只」')
    return
  }
  batchActionBusy.value = true
  try {
    const r = await completeBatchItem(batchId.value, currentItem.value.id)
    applyBatchCurrent(r.data)
    if (r.data.done) {
      screen.value = 'batch-done'
      void loadBatchSummary()
      ElMessage.success('本轮表达已完成，可查看节奏摘要')
    } else {
      ElMessage.success('样本已保存，换下一只')
    }
  } catch (err) {
    ElMessage.error(extractApiError(err))
  } finally {
    batchActionBusy.value = false
  }
}

async function exitBatch() {
  try {
    await ElMessageBox.confirm('退出后本批进度已保存，可稍后在历史中查看。', '退出本轮？', {
      confirmButtonText: '退出',
      cancelButtonText: '继续标注',
      type: 'warning',
    })
  } catch {
    return
  }
  batchId.value = null
  batchSnapshot.value = null
  currentItem.value = null
  labelSessionId.value = null
  pairCount.value = 0
  screen.value = 'home'
}

function onSymbolPicked(sym: SymbolItem) {
  selectedSymbol.value = sym
  rememberSymbol(sym)
}

function openSymbolPicker() {
  symbolPickerOpen.value = true
}

async function goChartManual() {
  if (!selectedSymbol.value) return
  chartBusy.value = true
  try {
    const r = await createLabelSession({
      full_code: selectedSymbol.value.full_code,
      period: chartPeriod.value,
      title: null,
    })
    labelSessionId.value = r.data.id
    pairCount.value = r.data.pairs?.length ?? 0
    screen.value = 'chart'
  } catch (err) {
    ElMessage.error(extractApiError(err) || '创建标注会话失败')
  } finally {
    chartBusy.value = false
  }
}

function goPick() {
  screen.value = 'pick'
}

function goHome() {
  screen.value = 'home'
  void loadBatchHistory()
}

function goBatchHistory() {
  screen.value = 'batch-history'
  void loadBatchHistory(50)
}

async function goList() {
  if (!labelSessionId.value) return
  listReturnScreen.value =
    screen.value === 'batch-chart' ? 'batch-chart' : screen.value === 'chart' ? 'chart' : 'home'
  screen.value = 'list'
  try {
    const r = await getLabelSession(labelSessionId.value)
    sessionDetail.value = r.data
    pairCount.value = r.data.pairs.length
  } catch {
    sessionDetail.value = null
  }
}

function goBackFromList() {
  screen.value = listReturnScreen.value
}

function onPairsChanged(n: number) {
  pairCount.value = n
}

function fmtBar(t: string) {
  return t.replace('T', ' ').slice(0, 16)
}

function onNavBack() {
  if (screen.value === 'list') {
    goBackFromList()
    return
  }
  if (screen.value === 'batch-chart') {
    void exitBatch()
    return
  }
  if (screen.value === 'batch-done') {
    goHome()
    return
  }
  if (screen.value === 'batch-review') {
    screen.value = 'batch-detail'
    reviewItem.value = null
    return
  }
  if (screen.value === 'batch-detail') {
    screen.value = 'batch-history'
    return
  }
  if (screen.value === 'batch-history') {
    goHome()
    return
  }
  if (screen.value === 'pick' || screen.value === 'chart') {
    goHome()
    labelSessionId.value = null
    pairCount.value = 0
  }
}

onMounted(() => {
  void loadBatchHistory()
})
</script>

<template>
  <div class="lb-page">
    <IosNavBar
      v-show="!chartFullscreen"
      :title="navTitle"
      :show-back="screen !== 'home'"
      @back="onNavBack"
    >
      <template v-if="screen === 'batch-chart' && progressText" #trailing>
        <span class="lb-progress">{{ progressText }}</span>
      </template>
    </IosNavBar>

    <div class="lb-body">
      <template v-if="screen === 'home'">
        <IosComplianceBanner />
        <section class="lb-pipeline" aria-label="策略翻译流程">
          <div class="lb-pipeline__step lb-pipeline__step--active">
            <span class="lb-pipeline__num">1</span>
            <span class="lb-pipeline__text">K 线表达</span>
          </div>
          <span class="lb-pipeline__arrow" aria-hidden="true">→</span>
          <div class="lb-pipeline__step">
            <span class="lb-pipeline__num">2</span>
            <span class="lb-pipeline__text">策略生成</span>
          </div>
          <span class="lb-pipeline__arrow" aria-hidden="true">→</span>
          <div class="lb-pipeline__step lb-pipeline__step--muted">
            <span class="lb-pipeline__num">3</span>
            <span class="lb-pipeline__text">回测验证</span>
          </div>
        </section>
        <IosListGroup
          title="用 K 线表达交易逻辑（推荐）"
          footer="每轮随机 20 只有 K 线的标的；点选理想买卖后，样本将用于生成可回测的策略。"
        >
          <div class="lb-period lb-period--inset">
            <span class="lb-period__label">K 线周期</span>
            <IosSegmentedControl v-model="chartPeriod" :options="periodOptions" />
          </div>
          <div class="lb-period lb-period--inset">
            <span class="lb-period__label">随机范围</span>
            <IosSegmentedControl v-model="marketFilter" :options="marketOptions" />
          </div>
        </IosListGroup>
        <div class="lb-cta-wrap">
          <button type="button" class="lb-cta" :disabled="chartBusy" @click="startBatch">
            {{ chartBusy ? '准备中…' : '开始一轮表达（20 只）' }}
          </button>
        </div>
        <IosListGroup title="单只精细表达（高级）">
          <IosListRow label="标的" :value="symbolRowValue" show-chevron @click="openSymbolPicker" />
        </IosListGroup>
        <div class="lb-cta-wrap lb-cta-wrap--secondary">
          <button
            type="button"
            class="lb-cta lb-cta--secondary"
            :disabled="!selectedSymbol || chartBusy"
            @click="goChartManual"
          >
            单只 K 线标注
          </button>
        </div>
        <IosListGroup
          v-if="batchHistory.length || historyLoading"
          title="历史批次"
          footer="点某批可查看明细与回看 K 线。"
        >
          <p v-if="historyLoading" class="lb-empty">加载中…</p>
          <IosListRow
            v-for="b in batchHistory.slice(0, 5)"
            :key="b.id"
            :label="fmtDate(b.created_at)"
            :value="
              b.profile_draft
                ? `${b.profile_draft.slice(0, 24)}…`
                : `完成 ${b.completed_count} · 跳过 ${b.skipped_count}`
            "
            show-chevron
            @click="openBatchDetail(b.id)"
          />
          <IosListRow
            v-if="batchHistory.length > 5"
            label="查看全部批次"
            show-chevron
            @click="goBatchHistory"
          />
        </IosListGroup>
      </template>

      <template v-else-if="screen === 'batch-chart'">
        <p v-show="!chartFullscreen" class="lb-context">
          在完整历史 K 线上表达：若理想执行，我会在何时买入、何时卖出。
        </p>
        <div class="lb-chart-stage">
          <div v-if="labelSessionId && currentItem" class="lb-chart-scroll">
            <div class="lb-chart-shell">
              <MobileLabelChart
                :key="labelSessionId"
                ref="labelChartRef"
                :session-id="labelSessionId"
                :full-code="currentItem.full_code"
                v-model:period="chartPeriod"
                :interaction-mode="chartMode"
                @pairs-changed="onPairsChanged"
                @suggest-mode="onSuggestChartMode"
                @fullscreen="chartFullscreen = $event"
              />
            </div>
          </div>
        </div>
        <div v-show="!chartFullscreen" class="lb-chart-footer">
          <div class="lb-batch-actions">
            <button
              type="button"
              class="lb-batch-actions__skip"
              :disabled="batchActionBusy"
              @click="skipCurrent"
            >
              跳过本只
            </button>
            <button
              type="button"
              class="lb-batch-actions__done"
              :disabled="batchActionBusy || pairCount < 1"
              @click="completeCurrent"
            >
              保存样本·下一只
            </button>
          </div>
          <div class="lb-tools">
            <IosSegmentedControl v-model="chartMode" :options="chartModes" />
            <p v-if="chartModeHint" class="lb-mode-hint">{{ chartModeHint }}</p>
            <p class="lb-mode-hint lb-mode-hint--count">{{ pairCountLabel }}</p>
          </div>
          <div class="lb-summary">
            <button type="button" class="lb-summary__btn" @click="goList">
              查看本只 {{ pairCount }} 笔样本
              <span class="lb-summary__chev" aria-hidden="true">›</span>
            </button>
          </div>
        </div>
      </template>

      <template v-else-if="screen === 'batch-done'">
        <div class="lb-done">
          <p class="lb-done__title">本轮表达完成</p>
          <p class="lb-done__stats">{{ batchDoneStats }}</p>
          <p class="lb-done__hint lb-done__hint--lead">
            下方为基于本批标注样本的<strong>节奏描述</strong>，用于核对是否贴近你的交易逻辑；最终可回测策略将在「策略生成」环节产出。
          </p>
          <p v-if="summaryLoading" class="lb-done__hint">正在生成模式总结…</p>
          <template v-else-if="batchSummary">
            <p class="lb-done__profile">{{ batchSummary.profile_draft }}</p>
            <ul class="lb-insights">
              <li v-for="(line, i) in batchSummary.insights" :key="i">{{ line }}</li>
            </ul>
            <p class="lb-done__section">若与直觉不符，可多选修正（非投资建议）：</p>
            <label
              v-for="opt in batchSummary.correction_options"
              :key="opt.id"
              class="lb-correction"
            >
              <input
                type="checkbox"
                :checked="selectedCorrections.includes(opt.id)"
                @change="toggleCorrection(opt.id)"
              />
              <span>{{ opt.label }}</span>
            </label>
            <button
              type="button"
              class="lb-cta lb-cta--secondary"
              :disabled="summarySaving"
              @click="saveCorrections"
            >
              {{ summarySaving ? '保存中…' : '保存修正' }}
            </button>
          </template>
          <button type="button" class="lb-cta" :disabled="chartBusy" @click="startBatch">
            开始下一轮（20 只）
          </button>
          <button
            v-if="batchId"
            type="button"
            class="lb-cta lb-cta--secondary"
            @click="openBatchDetail(batchId)"
          >
            查看本批明细
          </button>
          <button type="button" class="lb-cta lb-cta--secondary" @click="goHome">返回</button>
        </div>
      </template>

      <template v-else-if="screen === 'batch-history'">
        <p v-if="historyLoading" class="lb-empty">加载中…</p>
        <IosListGroup v-else title="全部批次">
          <IosListRow
            v-for="b in batchHistory"
            :key="b.id"
            :label="fmtDate(b.created_at)"
            :value="`完成 ${b.completed_count} · ${b.pair_count} 笔`"
            show-chevron
            @click="openBatchDetail(b.id)"
          />
        </IosListGroup>
        <p v-if="!historyLoading && !batchHistory.length" class="lb-empty">暂无历史批次。</p>
      </template>

      <template v-else-if="screen === 'batch-detail'">
        <IosListGroup v-if="batchSnapshot" :title="`共 ${batchSnapshot.items.length} 只`">
          <div
            v-for="item in batchSnapshot.items"
            :key="item.id"
            class="lb-batch-item"
            :class="{ 'lb-batch-item--clickable': item.status === 'completed' && item.session_id }"
            @click="
              item.status === 'completed' && item.session_id ? openBatchReview(item) : undefined
            "
          >
            <span class="lb-batch-item__code">{{ item.full_code }}</span>
            <span class="lb-batch-item__name">{{ item.symbol_name }}</span>
            <span class="lb-batch-item__meta">
              {{ itemStatusLabel(item.status) }}
              <template v-if="item.pair_count"> · {{ item.pair_count }} 笔</template>
            </span>
            <span
              v-if="item.status === 'completed' && item.session_id"
              class="lb-batch-item__chev"
              aria-hidden="true"
              >›</span
            >
          </div>
        </IosListGroup>
      </template>

      <template v-else-if="screen === 'batch-review'">
        <div class="lb-chart-stage">
          <div v-if="labelSessionId && reviewItem" class="lb-chart-scroll">
            <div class="lb-chart-shell">
              <MobileLabelChart
                :key="labelSessionId"
                :session-id="labelSessionId"
                :full-code="reviewItem.full_code"
                v-model:period="chartPeriod"
                readonly
                @fullscreen="chartFullscreen = $event"
              />
            </div>
          </div>
        </div>
        <p v-show="!chartFullscreen" class="lb-review-hint">只读回看：可平移缩放，不可修改标注。</p>
      </template>

      <template v-else-if="screen === 'pick'">
        <IosComplianceBanner />
        <IosListGroup title="标的与区间">
          <IosListRow label="标的" :value="symbolRowValue" show-chevron @click="openSymbolPicker" />
        </IosListGroup>
        <div class="lb-period">
          <span class="lb-period__label">K 线周期</span>
          <IosSegmentedControl v-model="chartPeriod" :options="periodOptions" />
        </div>
        <div class="lb-cta-wrap">
          <button
            type="button"
            class="lb-cta"
            :disabled="!selectedSymbol || chartBusy"
            @click="goChartManual"
          >
            {{ chartBusy ? '创建会话…' : '开始表达' }}
          </button>
        </div>
      </template>

      <template v-else-if="screen === 'chart'">
        <div class="lb-chart-stage">
          <div v-if="labelSessionId && selectedSymbol" class="lb-chart-scroll">
            <div class="lb-chart-shell">
              <MobileLabelChart
                ref="labelChartRef"
                :session-id="labelSessionId"
                :full-code="selectedSymbol.full_code"
                v-model:period="chartPeriod"
                :interaction-mode="chartMode"
                @pairs-changed="onPairsChanged"
                @suggest-mode="onSuggestChartMode"
                @fullscreen="chartFullscreen = $event"
              />
            </div>
          </div>
        </div>
        <div v-show="!chartFullscreen" class="lb-chart-footer">
          <div class="lb-tools">
            <IosSegmentedControl v-model="chartMode" :options="chartModes" />
            <p v-if="chartModeHint" class="lb-mode-hint">{{ chartModeHint }}</p>
            <p class="lb-mode-hint lb-mode-hint--count">{{ pairCountLabel }}</p>
          </div>
          <div class="lb-summary">
            <button type="button" class="lb-summary__btn" @click="goList">
              查看 {{ pairCount }} 笔逻辑样本
              <span class="lb-summary__chev" aria-hidden="true">›</span>
            </button>
          </div>
        </div>
      </template>

      <template v-else>
        <IosListGroup v-if="sessionDetail?.pairs?.length" title="本会话交易逻辑样本">
          <div v-for="(p, idx) in sessionDetail.pairs" :key="p.id" class="lb-trade">
            <div class="lb-trade__row">
              <span class="lb-trade__label">买入</span>
              <span class="lb-trade__val">{{ fmtBar(p.buy_bar_time) }}</span>
            </div>
            <div class="lb-trade__row">
              <span class="lb-trade__label">卖出</span>
              <span class="lb-trade__val">{{ fmtBar(p.sell_bar_time) }}</span>
            </div>
            <div class="lb-trade__ret">区间收益 {{ p.return_pct }}（第 {{ idx + 1 }} 笔）</div>
          </div>
        </IosListGroup>
        <p v-else class="lb-empty">暂无已保存样本。</p>
      </template>
    </div>

    <IosSymbolPickerSheet
      v-model:open="symbolPickerOpen"
      :recent="recentSymbols"
      @pick="onSymbolPicked"
    />
  </div>
</template>

<style scoped>
.lb-page {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: var(--h5-bg-grouped);
}
.lb-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  -webkit-overflow-scrolling: touch;
}
.lb-period {
  padding: 8px 16px 4px;
}
.lb-period--inset {
  padding: 8px 0 4px;
}
.lb-period__label {
  display: block;
  font-size: 13px;
  color: var(--h5-label-secondary);
  margin-bottom: 8px;
}
.lb-cta-wrap {
  padding: 8px 16px 16px;
}
.lb-cta-wrap--secondary {
  padding-top: 0;
  padding-bottom: 24px;
}
.lb-cta {
  width: 100%;
  min-height: 50px;
  border: none;
  border-radius: var(--h5-radius-button);
  background: var(--h5-tint);
  color: #fff;
  font-size: 17px;
  font-weight: 600;
  cursor: pointer;
  touch-action: manipulation;
}
.lb-cta--secondary {
  background: var(--h5-bg-elevated);
  color: var(--h5-tint);
  box-shadow: 0 0.5px 0 var(--h5-separator);
}
.lb-cta:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.lb-cta + .lb-cta {
  margin-top: 10px;
}
.lb-progress {
  font-size: 15px;
  font-weight: 600;
  color: var(--h5-label-secondary);
}
.lb-chart-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.lb-chart-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
}
.lb-chart-shell {
  display: flex;
  flex-direction: column;
  margin: 0 0 8px;
  padding: 0 8px;
}
.lb-chart-footer {
  flex-shrink: 0;
  position: relative;
  z-index: 20;
  background: var(--h5-bg-grouped);
  border-top: 0.5px solid var(--h5-separator);
  padding-top: 4px;
}
.lb-batch-actions {
  display: flex;
  gap: 10px;
  padding: 8px 16px 4px;
}
.lb-batch-actions__skip,
.lb-batch-actions__done {
  flex: 1;
  min-height: 44px;
  border: none;
  border-radius: var(--h5-radius-button);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  touch-action: manipulation;
}
.lb-batch-actions__skip {
  background: var(--h5-bg-elevated);
  color: var(--h5-label-primary);
  box-shadow: 0 0.5px 0 var(--h5-separator);
}
.lb-batch-actions__done {
  background: var(--h5-tint);
  color: #fff;
}
.lb-batch-actions__done:disabled {
  opacity: 0.45;
}
.lb-tools {
  padding: 0 16px 8px;
}
.lb-mode-hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.35;
  color: var(--h5-label-secondary);
  text-align: center;
}
.lb-summary {
  padding: 0 16px 16px;
}
.lb-summary__btn {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 44px;
  padding: 10px 14px;
  border: none;
  border-radius: var(--h5-radius-cell);
  background: var(--h5-bg-elevated);
  font-size: 16px;
  font-weight: 500;
  color: var(--h5-tint);
  cursor: pointer;
  touch-action: manipulation;
  box-shadow: 0 0.5px 0 var(--h5-separator);
}
.lb-summary__chev {
  margin-left: auto;
  font-size: 18px;
  color: var(--h5-label-tertiary);
}
.lb-done {
  padding: 32px 20px 24px;
  text-align: center;
}
.lb-done__title {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
}
.lb-done__stats {
  margin: 0 0 12px;
  font-size: 16px;
  color: var(--h5-tint);
  font-weight: 600;
}
.lb-done__hint {
  margin: 0 0 24px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--h5-label-secondary);
}
.lb-done__hint--lead {
  text-align: left;
}
.lb-done__hint--lead strong {
  font-weight: 600;
}
.lb-done__profile {
  margin: 0 0 12px;
  font-size: 15px;
  line-height: 1.55;
  text-align: left;
  color: var(--h5-label-primary);
}
.lb-done__section {
  margin: 16px 0 8px;
  font-size: 14px;
  text-align: left;
  color: var(--h5-label-secondary);
}
.lb-insights {
  margin: 0 0 16px;
  padding-left: 20px;
  text-align: left;
  font-size: 14px;
  line-height: 1.5;
  color: var(--h5-label-secondary);
}
.lb-correction {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin: 0 0 10px;
  font-size: 14px;
  line-height: 1.4;
  text-align: left;
  cursor: pointer;
}
.lb-correction input {
  margin-top: 3px;
  flex-shrink: 0;
}
.lb-batch-item {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 2px 8px;
  padding: 12px 16px;
  background: var(--h5-bg-elevated);
  border-bottom: 0.5px solid var(--h5-separator);
}
.lb-batch-item--clickable {
  cursor: pointer;
}
.lb-batch-item__code {
  font-weight: 600;
  font-size: 15px;
}
.lb-batch-item__name {
  grid-column: 1;
  font-size: 13px;
  color: var(--h5-label-secondary);
}
.lb-batch-item__meta {
  grid-column: 1;
  font-size: 13px;
  color: var(--h5-tint);
}
.lb-batch-item__chev {
  grid-row: 1 / span 3;
  align-self: center;
  font-size: 20px;
  color: var(--h5-label-tertiary);
}
.lb-review-hint {
  margin: 0;
  padding: 8px 16px 16px;
  font-size: 13px;
  text-align: center;
  color: var(--h5-label-secondary);
}
.lb-trade {
  padding: 12px 16px;
  background: var(--h5-bg-elevated);
}
.lb-trade + .lb-trade {
  border-top: 0.5px solid var(--h5-separator);
}
.lb-trade__row {
  display: flex;
  justify-content: space-between;
  font-size: 15px;
  margin-bottom: 4px;
}
.lb-trade__label {
  color: var(--h5-label-secondary);
}
.lb-trade__ret {
  margin-top: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--h5-tint);
}
.lb-empty {
  margin: 24px 16px;
  font-size: 15px;
  color: var(--h5-label-secondary);
  text-align: center;
}
.lb-pipeline {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 0 16px 12px;
  padding: 10px 8px;
  border-radius: var(--h5-radius-cell);
  background: var(--h5-bg-elevated);
}
.lb-pipeline__step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 72px;
}
.lb-pipeline__step--active .lb-pipeline__num {
  background: var(--h5-tint);
  color: #fff;
}
.lb-pipeline__step--muted {
  opacity: 0.55;
}
.lb-pipeline__num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--h5-fill-tertiary);
  color: var(--h5-label-secondary);
}
.lb-pipeline__text {
  font-size: 11px;
  color: var(--h5-label-secondary);
  text-align: center;
}
.lb-pipeline__arrow {
  font-size: 12px;
  color: var(--h5-label-tertiary);
  flex-shrink: 0;
}
.lb-context {
  margin: 0;
  padding: 8px 16px 4px;
  font-size: 13px;
  line-height: 1.45;
  color: var(--h5-label-secondary);
  text-align: center;
}
.lb-mode-hint--count {
  margin-top: 2px;
  font-weight: 600;
  color: var(--h5-tint);
}
</style>
