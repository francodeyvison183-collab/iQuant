<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { queryBars, type BarPoint } from '@/api/market'
import { extractApiError } from '@/api/errors'
import { getLabelSession, replaceLabelPairs, type LabelPairDraft } from '@/api/labels'
import {
  buildKlineChartOption,
  patchDataZoomInteraction,
  patchVolumeBarWidth,
  readDataZoomRange,
  resetDataZoom,
  shiftDataZoom,
} from '@/chart/buildKlineOption'
import { buildCandlestickMarks } from '@/chart/klineMarks'
import { buildChartIndicatorLabels } from '@/chart/indicatorLabels'
import { buildOhlcDisplay, fmtBarTime, resolveDisplayIndex, resolvePointerBarIndex } from '@/chart/klineOhlc'
import { applyVisibleYAxisScale } from '@/chart/visibleYAxis'
import { KLINE_PERIOD_OPTIONS, defaultBarLimit } from '@/chart/klinePeriod'
import {
  DEFAULT_MAIN_INDICATORS,
  type MainChartKind,
  type SubChart2Kind,
} from '@/chart/types'
import { XQ_CHART_MIN_HEIGHT } from '@/chart/xueqiuLayout'
import { XQ } from '@/chart/xueqiuTheme'
import KlineChartLabelOverlay from '@/components/mobile/KlineChartLabelOverlay.vue'
import KlineChartToolbarFlyout from '@/components/mobile/KlineChartToolbarFlyout.vue'
import KlineOhlcBar from '@/components/mobile/KlineOhlcBar.vue'
import KlineSubIndicatorBar from '@/components/mobile/KlineSubIndicatorBar.vue'

const props = defineProps<{
  sessionId: string
  fullCode: string
  period: string
  interactionMode?: string
  readonly?: boolean
}>()

const emit = defineEmits<{
  'pairs-changed': [count: number]
  'update:period': [value: string]
  fullscreen: [active: boolean]
  'suggest-mode': [mode: string]
}>()

const chartUiMode = computed(() => props.interactionMode ?? 'buy')
const isPanMode = computed(() => chartUiMode.value === 'pan')
const chartPeriod = computed({
  get: () => props.period,
  set: (v: string) => emit('update:period', v),
})

const chartWrapRef = ref<HTMLDivElement | null>(null)
const chartEl = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let resizeObs: ResizeObserver | null = null
let pointerRaf = 0

const bars = ref<BarPoint[]>([])
const pairs = ref<LabelPairDraft[]>([])
const pendingBuy = ref<BarPoint | null>(null)
const loading = ref(false)
const mainKind = ref<MainChartKind>('ma')
const subChart2 = ref<SubChart2Kind>('macd')
const isFullscreen = ref(false)
const dataZoomRange = ref<{ start: number; end: number } | null>(null)
const cursorIndex = ref<number | null>(null)

let saveTimer: ReturnType<typeof setTimeout> | null = null

const dateLabels = computed(() => bars.value.map((b) => fmtBarTime(b.bar_time, props.period)))

const displayIndex = computed(() => resolveDisplayIndex(cursorIndex.value, bars.value.length))

const ohlcDisplay = computed(() => {
  const idx = displayIndex.value
  if (idx < 0) return null
  return buildOhlcDisplay(bars.value, idx, props.period)
})

const indicatorLabels = computed(() =>
  buildChartIndicatorLabels({
    bars: bars.value,
    index: displayIndex.value,
    mainKind: mainKind.value,
    subChart2: subChart2.value,
  }),
)

function chartBuildParams(zoom?: { start: number; end: number } | null) {
  const z = zoom ?? dataZoomRange.value
  return {
    bars: bars.value,
    period: props.period,
    mainKind: mainKind.value,
    subChart2: subChart2.value,
    main: DEFAULT_MAIN_INDICATORS,
    marks: annotationMarks(),
    dataZoomStart: z?.start ?? 60,
    dataZoomEnd: z?.end ?? 100,
    panMode: isPanMode.value,
  }
}

function syncYAxisToVisible() {
  if (!chart || !bars.value.length) return
  applyVisibleYAxisScale(chart, {
    bars: bars.value,
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

function syncInteractionMode() {
  if (!chart) return
  patchDataZoomInteraction(chart, isPanMode.value)
  if (isPanMode.value) cursorIndex.value = null
}

function onAxisPointerUpdate(ev: unknown) {
  if (isPanMode.value) return
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

function parseBarTime(b: BarPoint): Date {
  return new Date(b.bar_time.endsWith('Z') ? b.bar_time : `${b.bar_time}Z`)
}

function barIndex(bar: BarPoint): number {
  return bars.value.findIndex((b) => b.bar_time === bar.bar_time)
}

function fmtSampleReturn(buyClose: string, sellClose: string): string {
  const buy = Number(buyClose)
  const sell = Number(sellClose)
  if (!buy) return ''
  const pct = ((sell - buy) / buy) * 100
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

function scheduleSave() {
  if (props.readonly) return
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    saveTimer = null
    try {
      await replaceLabelPairs(
        props.sessionId,
        pairs.value.map((p) => ({
          buy_bar_time: p.buy_bar_time,
          sell_bar_time: p.sell_bar_time,
          buy_close: p.buy_close,
          sell_close: p.sell_close,
        })),
      )
    } catch {
      /* axios 已弹错 */
    }
  }, 700)
}

function annotationMarks() {
  const pairMarks: { buyIndex: number; sellIndex: number }[] = []
  for (const p of pairs.value) {
    const bi = bars.value.findIndex((b) => b.bar_time === p.buy_bar_time)
    const si = bars.value.findIndex((b) => b.bar_time === p.sell_bar_time)
    if (bi >= 0 && si >= 0) pairMarks.push({ buyIndex: bi, sellIndex: si })
  }
  const pendingBuyIndex = pendingBuy.value ? barIndex(pendingBuy.value) : null
  return { pendingBuyIndex, pairMarks }
}

type RenderMode = 'full' | 'series' | 'marks'

function render(opts?: { resetZoom?: boolean; mode?: RenderMode }) {
  if (!chart || !bars.value.length) return
  const mode = opts?.mode ?? 'full'
  const zoom =
    opts?.resetZoom ? null : (readDataZoomRange(chart) ?? dataZoomRange.value)

  if (mode === 'marks') {
    const overlay = buildCandlestickMarks({
      bars: bars.value,
      period: props.period,
      marks: annotationMarks(),
    })
    chart.setOption(
      {
        series: [
          {
            name: 'K线',
            markPoint: overlay.markPoint ?? { data: [] },
            markArea: overlay.markArea ?? { data: [] },
            markLine: overlay.markLine,
          },
        ],
      },
      { lazyUpdate: true },
    )
    return
  }

  if (mode === 'series') {
    const params = chartBuildParams(zoom)
    const built = buildKlineChartOption(params)
    chart.setOption(
      { series: built.series, xAxis: built.xAxis },
      { replaceMerge: ['series'], lazyUpdate: true },
    )
    if (zoom) dataZoomRange.value = zoom
    syncYAxisToVisible()
    return
  }

  chart.setOption(buildKlineChartOption(chartBuildParams(zoom)), { notMerge: true })
  if (zoom) dataZoomRange.value = zoom
  bindChartEvents()
  syncYAxisToVisible()
  if (opts?.resetZoom) cursorIndex.value = null
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
  cursorIndex.value = null
}

async function toggleFullscreen() {
  const el = chartWrapRef.value
  if (!el) return
  try {
    if (!document.fullscreenElement) {
      const req =
        el.requestFullscreen?.bind(el) ??
        (el as HTMLElement & { webkitRequestFullscreen?: () => Promise<void> }).webkitRequestFullscreen?.bind(el)
      if (req) await req()
      isFullscreen.value = true
    } else {
      await document.exitFullscreen()
      isFullscreen.value = false
    }
    emit('fullscreen', isFullscreen.value)
    await nextTick()
    chart?.resize()
  } catch {
    ElMessage.warning('当前环境不支持全屏')
  }
}

function onFullscreenChange() {
  const active = document.fullscreenElement === chartWrapRef.value
  isFullscreen.value = active
  emit('fullscreen', active)
  chart?.resize()
}

async function loadBars() {
  loading.value = true
  try {
    const [barsEnv, sessionEnv] = await Promise.all([
      queryBars({
        full_code: props.fullCode,
        period: props.period,
        limit: defaultBarLimit(props.period),
      }),
      getLabelSession(props.sessionId),
    ])
    bars.value = barsEnv.data.bars
    if (!bars.value.length) {
      ElMessage.warning('暂无 K 线，请先在「数据更新」导入该标的')
      return
    }
    pairs.value = (sessionEnv.data.pairs ?? []).map((p) => ({
      buy_bar_time: p.buy_bar_time,
      sell_bar_time: p.sell_bar_time,
      buy_close: p.buy_close,
      sell_close: p.sell_close,
    }))
    pendingBuy.value = null
    emit('pairs-changed', pairs.value.length)
    await nextTick()
    if (!chartEl.value) return
    if (!chart) chart = echarts.init(chartEl.value)
    dataZoomRange.value = null
    render({ resetZoom: true, mode: 'full' })
    syncInteractionMode()
    chart.off('click')
    chart.on('click', (p) => {
      if (props.readonly) return
      if (chartUiMode.value === 'pan') return
      if (p.componentType !== 'series' || p.seriesType !== 'candlestick') return
      const idx = typeof p.dataIndex === 'number' ? p.dataIndex : -1
      if (idx < 0 || idx >= bars.value.length) return
      const bar = bars.value[idx]

      if (!pendingBuy.value) {
        if (chartUiMode.value === 'sell') {
          ElMessage.warning('请先点选理想买入位置（可切到「买入」）')
          return
        }
        pendingBuy.value = bar
        emit('suggest-mode', 'sell')
        ElMessage.success('已标记理想买入，请点选理想卖出')
        render({ mode: 'marks' })
        return
      }

      const buy = pendingBuy.value
      if (parseBarTime(bar) <= parseBarTime(buy)) {
        ElMessage.warning('理想卖出须在买入之后')
        return
      }
      pairs.value.push({
        buy_bar_time: buy.bar_time,
        sell_bar_time: bar.bar_time,
        buy_close: buy.close,
        sell_close: bar.close,
      })
      pendingBuy.value = null
      const ret = fmtSampleReturn(buy.close, bar.close)
      emit('pairs-changed', pairs.value.length)
      emit('suggest-mode', 'buy')
      ElMessage.success(
        ret ? `已记录一笔交易逻辑样本（区间 ${ret}）` : '已记录一笔交易逻辑样本',
      )
      scheduleSave()
      render({ mode: 'marks' })
    })
  } catch (err) {
    ElMessage.error(extractApiError(err) || 'K 线加载失败')
  } finally {
    loading.value = false
  }
}

function undoLast(): { changed: boolean; message: string } {
  if (props.readonly) {
    return { changed: false, message: '只读模式不可编辑' }
  }
  if (pendingBuy.value) {
    pendingBuy.value = null
    render({ mode: 'marks' })
    emit('suggest-mode', 'buy')
    return { changed: true, message: '已取消待选卖出点' }
  }
  if (pairs.value.length) {
    pairs.value.pop()
    emit('pairs-changed', pairs.value.length)
    scheduleSave()
    render({ mode: 'marks' })
    emit('suggest-mode', 'buy')
    return { changed: true, message: '已撤销上一笔样本' }
  }
  return { changed: false, message: '暂无可撤销内容' }
}

defineExpose({
  undoLast,
  resetZoom: onResetZoom,
  zoomIn: () => onZoom({ zoom: -6 }),
  zoomOut: () => onZoom({ zoom: 6 }),
  panLeft: () => onZoom({ pan: -6 }),
  panRight: () => onZoom({ pan: 6 }),
  toggleFullscreen,
})

watch(
  () => [props.sessionId, props.fullCode, props.period] as const,
  () => {
    void loadBars()
  },
  { immediate: true },
)

watch([mainKind, subChart2], () => render({ mode: 'series' }))

watch(isPanMode, () => {
  syncInteractionMode()
})

onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  if (chartEl.value) {
    resizeObs = new ResizeObserver(() => chart?.resize())
    resizeObs.observe(chartEl.value)
  }
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  cancelAnimationFrame(pointerRaf)
  if (saveTimer) clearTimeout(saveTimer)
  resizeObs?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div class="mlc" :class="{ 'mlc--fs': isFullscreen }">
    <div class="mlc-period">
      <button
        v-for="p in KLINE_PERIOD_OPTIONS"
        :key="p.value"
        type="button"
        class="mlc-period__tab"
        :class="{ 'mlc-period__tab--on': chartPeriod === p.value }"
        @click="chartPeriod = p.value"
      >
        {{ p.label }}
      </button>
    </div>

    <KlineOhlcBar v-if="bars.length" :ohlc="ohlcDisplay" />

    <div ref="chartWrapRef" class="mlc-chart-wrap">
      <p v-if="!bars.length && !loading" class="mlc-empty">暂无 K 线，请先在「数据更新」导入。</p>
      <div v-loading="loading" ref="chartEl" class="mlc-chart" />
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
  </div>
</template>

<style scoped>
.mlc {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: #fff;
}

.mlc--fs {
  background: #fff;
}

.mlc-chart-wrap {
  position: relative;
  flex: 1;
  min-height: v-bind('`${XQ_CHART_MIN_HEIGHT.wrapPx}px`');
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.mlc-chart-wrap:fullscreen {
  padding: 8px 0 0;
  background: #fff;
}
.mlc-chart-wrap:-webkit-full-screen {
  padding: 8px 0 0;
  background: #fff;
}

.mlc-period {
  display: flex;
  overflow-x: auto;
  flex-shrink: 0;
  border-bottom: 0.5px solid #eee;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.mlc-period::-webkit-scrollbar {
  display: none;
}
.mlc-period__tab {
  flex: 1 0 auto;
  min-width: 44px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  font-size: 14px;
  color: #666;
  touch-action: manipulation;
}
.mlc-period__tab--on {
  color: v-bind('XQ.up');
  font-weight: 600;
  box-shadow: inset 0 -2px 0 v-bind('XQ.up');
}

.mlc-chart {
  flex: 1;
  min-height: v-bind('`${XQ_CHART_MIN_HEIGHT.canvasPx}px`');
  width: 100%;
}

.mlc-empty {
  position: absolute;
  left: 12px;
  top: 8px;
  margin: 0;
  font-size: 12px;
  color: #999;
  z-index: 2;
}
</style>