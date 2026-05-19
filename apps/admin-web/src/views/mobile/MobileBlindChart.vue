<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { extractApiError } from '@/api/errors'
import {
  getBlindSession,
  submitBlindAction,
  type BlindSessionDetail,
} from '@/api/replays'
import type { BlindBarPoint } from '@/api/replays'
import {
  buildKlineChartOption,
  patchDataZoomInteraction,
  patchVolumeBarWidth,
  readDataZoomRange,
  resetDataZoom,
  shiftDataZoom,
} from '@/chart/buildKlineOption'
import { buildChartIndicatorLabels } from '@/chart/indicatorLabels'
import { buildOhlcDisplay, fmtBarTime, resolveDisplayIndex, resolvePointerBarIndex } from '@/chart/klineOhlc'
import { applyVisibleYAxisScale } from '@/chart/visibleYAxis'
import { BLIND_KLINE_PERIOD_OPTIONS } from '@/chart/klinePeriod'
import {
  DEFAULT_MAIN_INDICATORS,
  type MainChartKind,
  type SubChart2Kind,
} from '@/chart/types'
import { XQ_CHART_MIN_HEIGHT } from '@/chart/xueqiuLayout'
import KlineChartLabelOverlay from '@/components/mobile/KlineChartLabelOverlay.vue'
import KlineChartToolbarFlyout from '@/components/mobile/KlineChartToolbarFlyout.vue'
import KlineOhlcBar from '@/components/mobile/KlineOhlcBar.vue'
import KlineSubIndicatorBar from '@/components/mobile/KlineSubIndicatorBar.vue'

const props = defineProps<{
  sessionId: string
  period: string
}>()

const emit = defineEmits<{
  updated: [detail: BlindSessionDetail]
  finished: []
  skip: [payload: { tradeCount: number }]
  'update:period': [value: string]
}>()

const chartPeriod = computed({
  get: () => props.period,
  set: (v: string) => emit('update:period', v),
})

const detail = ref<BlindSessionDetail | null>(null)
const busy = ref(false)
const chartWrapRef = ref<HTMLDivElement | null>(null)
const chartEl = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let resizeObs: ResizeObserver | null = null
let pointerRaf = 0

const mainKind = ref<MainChartKind>('ma')
const subChart2 = ref<SubChart2Kind>('macd')
const dataZoomRange = ref<{ start: number; end: number } | null>(null)
const cursorIndex = ref<number | null>(null)
const isFullscreen = ref(false)

const bars = computed(() => detail.value?.visible_bars ?? [])
const dateLabels = computed(() => bars.value.map((b) => fmtBarTime(b.bar_time, props.period)))

const displayIndex = computed(() => {
  if (!bars.value.length) return -1
  const cursorBar = detail.value?.cursor_bar_time
  const idx = bars.value.findIndex((b) => b.bar_time === cursorBar)
  return resolveDisplayIndex(idx >= 0 ? idx : bars.value.length - 1, bars.value.length)
})

const ohlcDisplay = computed(() => {
  const idx = displayIndex.value
  if (idx < 0) return null
  return buildOhlcDisplay(bars.value as unknown as import('@/api/market').BarPoint[], idx, props.period)
})

const indicatorLabels = computed(() =>
  buildChartIndicatorLabels({
    bars: bars.value as unknown as import('@/api/market').BarPoint[],
    index: displayIndex.value,
    mainKind: mainKind.value,
    subChart2: subChart2.value,
  }),
)

const progressText = computed(() => {
  const d = detail.value
  if (!d) return ''
  return `本轮进度 ${d.round_trade_count}/${d.required_trade_actions}（本只 ${d.trade_action_count}）`
})

const tradeCount = computed(() => detail.value?.trade_action_count ?? 0)
const skipLabel = computed(() => (tradeCount.value > 0 ? '切换下一只' : '跳过本只'))

const statusLine = computed(() => {
  const d = detail.value
  if (!d) return ''
  const pos = Number(d.position_qty) > 0 ? '持仓中' : '空仓'
  return `${pos} · 现金 ${Number(d.cash_balance).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
})

function toMarketBars(list: BlindBarPoint[]) {
  return list.map((b) => ({
    bar_time: b.bar_time,
    open: b.open,
    high: b.high,
    low: b.low,
    close: b.close,
    volume: b.volume,
    amount: b.amount,
  }))
}

function chartBuildParams(zoom?: { start: number; end: number } | null) {
  const z = zoom ?? dataZoomRange.value
  return {
    bars: toMarketBars(bars.value),
    period: props.period,
    mainKind: mainKind.value,
    subChart2: subChart2.value,
    main: DEFAULT_MAIN_INDICATORS,
    marks: { pendingBuyIndex: null, pairMarks: [] },
    dataZoomStart: z?.start ?? 55,
    dataZoomEnd: z?.end ?? 100,
    panMode: false,
  }
}

function syncYAxisToVisible() {
  if (!chart || !bars.value.length) return
  applyVisibleYAxisScale(chart, {
    bars: toMarketBars(bars.value),
    mainKind: mainKind.value,
    main: DEFAULT_MAIN_INDICATORS,
    subChart2: subChart2.value,
    zoom: readDataZoomRange(chart) ?? dataZoomRange.value,
  })
  const z = readDataZoomRange(chart) ?? dataZoomRange.value
  if (z) patchVolumeBarWidth(chart, bars.value.length, z)
}

function syncDataZoomFromChart() {
  if (!chart) return
  const z = readDataZoomRange(chart)
  if (z) dataZoomRange.value = z
  syncYAxisToVisible()
}

function onAxisPointerUpdate(ev: unknown) {
  cancelAnimationFrame(pointerRaf)
  pointerRaf = requestAnimationFrame(() => {
    const idx = resolvePointerBarIndex(ev, bars.value.length, dateLabels.value)
    if (idx != null) cursorIndex.value = idx
  })
}

function bindChartEvents() {
  if (!chart) return
  chart.off('datazoom')
  chart.off('updateAxisPointer')
  chart.off('globalout')
  chart.on('datazoom', syncDataZoomFromChart)
  chart.on('updateAxisPointer', onAxisPointerUpdate)
  chart.on('globalout', () => {
    cursorIndex.value = null
  })
}

function renderChart(opts?: { mode?: 'full' | 'series' }) {
  if (!chart || !bars.value.length) return
  const mode = opts?.mode ?? 'full'
  const zoom = readDataZoomRange(chart) ?? dataZoomRange.value

  if (mode === 'series') {
    const built = buildKlineChartOption(chartBuildParams(zoom))
    chart.setOption({ series: built.series, xAxis: built.xAxis }, { replaceMerge: ['series'], lazyUpdate: true })
    if (zoom) dataZoomRange.value = zoom
    syncYAxisToVisible()
    return
  }

  chart.setOption(buildKlineChartOption(chartBuildParams(zoom)), { notMerge: true })
  if (zoom) dataZoomRange.value = zoom
  bindChartEvents()
  syncYAxisToVisible()
  const idx = displayIndex.value
  if (idx >= 0) {
    chart.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex: idx })
  }
}

function onZoom(delta: { zoom?: number; pan?: number }) {
  if (!chart) return
  shiftDataZoom(chart, delta)
  syncDataZoomFromChart()
}

function onResetZoom() {
  if (!chart) return
  resetDataZoom(chart)
  dataZoomRange.value = null
  syncDataZoomFromChart()
}

async function toggleFullscreen() {
  const el = chartWrapRef.value
  if (!el) return
  try {
    if (!document.fullscreenElement) {
      await el.requestFullscreen()
    } else {
      await document.exitFullscreen()
    }
  } catch {
    /* ignore */
  }
}

function onFullscreenChange() {
  isFullscreen.value = Boolean(document.fullscreenElement)
  chart?.resize()
}

async function reload() {
  try {
    const res = await getBlindSession(props.sessionId, props.period)
    detail.value = res.data
    emit('updated', res.data)
    await nextTick()
    renderChart()
    if (res.data.status === 'finished' || res.data.status === 'abandoned') emit('finished')
  } catch (e) {
    ElMessage.error(extractApiError(e))
  }
}

async function act(user_action: 'buy' | 'sell' | 'hold') {
  if (!detail.value?.can_act || busy.value) return
  busy.value = true
  try {
    const res = await submitBlindAction(props.sessionId, {
      user_action,
      period: props.period,
    })
    detail.value = res.data
    emit('updated', res.data)
    await nextTick()
    renderChart()
    if (res.data.status === 'finished' || res.data.status === 'abandoned') emit('finished')
  } catch (e) {
    ElMessage.error(extractApiError(e))
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  if (chartEl.value) {
    chart = echarts.init(chartEl.value)
    patchDataZoomInteraction(chart, true)
    resizeObs = new ResizeObserver(() => chart?.resize())
    resizeObs.observe(chartEl.value)
  }
  await reload()
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  cancelAnimationFrame(pointerRaf)
  resizeObs?.disconnect()
  chart?.dispose()
  chart = null
})

watch(
  () => props.sessionId,
  () => {
    void reload()
  },
)

watch(
  () => props.period,
  () => {
    void reload()
  },
)

watch([mainKind, subChart2], () => renderChart({ mode: 'series' }))

defineExpose({ reload })
</script>

<template>
  <div class="blind-chart">
    <div class="blind-chart__period">
      <button
        v-for="p in BLIND_KLINE_PERIOD_OPTIONS"
        :key="p.value"
        type="button"
        class="blind-chart__period-tab"
        :class="{ 'blind-chart__period-tab--on': chartPeriod === p.value }"
        @click="chartPeriod = p.value"
      >
        {{ p.label }}
      </button>
    </div>

    <KlineOhlcBar v-if="ohlcDisplay" :ohlc="ohlcDisplay" />
    <p v-if="progressText" class="blind-chart__progress">{{ progressText }}</p>
    <p v-if="statusLine" class="blind-chart__status">{{ statusLine }}</p>

    <div ref="chartWrapRef" class="blind-chart__wrap">
      <div ref="chartEl" class="blind-chart__canvas" :style="{ minHeight: `${XQ_CHART_MIN_HEIGHT}px` }" />
      <KlineChartLabelOverlay v-if="bars.length" :labels="indicatorLabels" />
      <KlineChartToolbarFlyout
        v-if="bars.length"
        :fullscreen="isFullscreen"
        @reset="onResetZoom"
        @zoom-in="onZoom({ zoom: -6 })"
        @zoom-out="onZoom({ zoom: 6 })"
        @pan-left="onZoom({ pan: -6 })"
        @pan-right="onZoom({ pan: 6 })"
        @toggle-fullscreen="toggleFullscreen"
      />
    </div>

    <KlineSubIndicatorBar v-model:main-kind="mainKind" v-model:sub-chart2="subChart2" />

    <div v-if="detail?.can_act" class="blind-chart__actions">
      <button type="button" class="act act--buy" :disabled="busy" @click="act('buy')">买入</button>
      <button type="button" class="act act--hold" :disabled="busy" @click="act('hold')">观望</button>
      <button type="button" class="act act--sell" :disabled="busy" @click="act('sell')">卖出</button>
    </div>
    <p v-else-if="detail" class="blind-chart__hint">
      {{
        detail.status === 'finished'
          ? '本轮已完成'
          : detail.status === 'abandoned'
            ? '本轮已放弃'
            : detail.status === 'switched'
              ? '已切换，请选择下一只'
              : detail.round_trade_count >= detail.required_trade_actions
                ? '本轮次数已满'
                : '该股已至区间末尾，请切换下一只继续本轮'
      }}
    </p>

    <div class="blind-chart__footer">
      <button
        type="button"
        class="blind-chart__skip"
        :disabled="busy"
        @click="emit('skip', { tradeCount })"
      >
        {{ skipLabel }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.blind-chart {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
  background: #fff;
}
.blind-chart__period {
  display: flex;
  overflow-x: auto;
  flex-shrink: 0;
  border-bottom: 0.5px solid #eee;
  -webkit-overflow-scrolling: touch;
}
.blind-chart__period-tab {
  flex: 1 0 auto;
  min-width: 44px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  font-size: 14px;
  color: var(--h5-label-secondary);
}
.blind-chart__period-tab--on {
  color: var(--h5-tint);
  font-weight: 600;
  box-shadow: inset 0 -2px 0 var(--h5-tint);
}
.blind-chart__progress {
  margin: 6px 16px 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--h5-tint);
}
.blind-chart__status {
  margin: 4px 16px 6px;
  font-size: 13px;
  color: var(--h5-label-secondary);
}
.blind-chart__wrap {
  position: relative;
  flex: 1;
  min-height: 280px;
  display: flex;
  flex-direction: column;
}
.blind-chart__canvas {
  flex: 1;
  width: 100%;
  min-height: 280px;
}
.blind-chart__actions {
  display: flex;
  gap: 8px;
  padding: 12px 16px 8px;
}
.act {
  flex: 1;
  padding: 12px 8px;
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
}
.act:disabled {
  opacity: 0.5;
}
.act--buy {
  color: #fff;
  background: #e54d42;
}
.act--hold {
  background: var(--h5-bg-elevated);
  color: var(--h5-label-primary);
}
.act--sell {
  color: #fff;
  background: #26a69a;
}
.blind-chart__hint {
  margin: 12px 16px;
  text-align: center;
  font-size: 14px;
  color: var(--h5-label-secondary);
}
.blind-chart__footer {
  padding: 0 16px calc(12px + var(--h5-content-inset-bottom));
  text-align: center;
}
.blind-chart__skip {
  border: none;
  background: none;
  color: var(--h5-label-secondary);
  font-size: 15px;
  padding: 8px;
}
</style>
