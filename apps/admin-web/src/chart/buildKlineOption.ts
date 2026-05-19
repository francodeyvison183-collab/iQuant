import type { BarPoint } from '@/api/market'
import type { ECharts, EChartsOption, SeriesOption } from 'echarts'
import { boll, sma } from './indicators'
import { buildCandlestickMarks, type KlineAnnotationMarks } from './klineMarks'
import { fmtBarTime } from './klineOhlc'
import { appendSub2Series } from './subChart2Series'
import type { MainChartKind, MainIndicatorSettings, SubChart2Kind } from './types'
import { XQ_CHART_LAYOUT } from './xueqiuLayout'
import { XQ } from './xueqiuTheme'

export type { KlineAnnotationMarks } from './klineMarks'

export function calcBarMaxWidth(barCount: number, startPct: number, endPct: number): number {
  const visible = Math.max(1, Math.ceil((barCount * (endPct - startPct)) / 100))
  if (visible <= 15) return 14
  if (visible <= 30) return 10
  if (visible <= 60) return 7
  if (visible <= 120) return 5
  return 3
}

export function patchDataZoomInteraction(chart: ECharts, panMode: boolean): void {
  chart.setOption({
    axisPointer: {
      triggerOn: panMode ? 'none' : 'mousemove|click',
    },
    dataZoom: [{ moveOnMouseMove: panMode }],
  })
}

export function patchVolumeBarWidth(
  chart: ECharts,
  barCount: number,
  zoom: { start: number; end: number },
): void {
  const w = calcBarMaxWidth(barCount, zoom.start, zoom.end)
  chart.setOption({
    series: [{ name: '成交量', barMaxWidth: w }],
  })
}

function makeCategoryAxis(dates: string[], gridIndex: number, showLabel: boolean) {
  return {
    type: 'category' as const,
    gridIndex,
    data: dates,
    boundaryGap: false,
    axisLine: { show: gridIndex === 0, lineStyle: { color: XQ.gridLine } },
    axisTick: { show: false },
    axisLabel: {
      show: showLabel,
      fontSize: 10,
      color: XQ.axisLabel,
      margin: 4,
    },
    splitLine: { show: false },
  }
}

function makeYAxis(gridIndex: number, opts?: { splitNumber?: number; showLabel?: boolean }) {
  return {
    scale: true,
    gridIndex,
    position: 'left' as const,
    splitNumber: opts?.splitNumber ?? 3,
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { show: gridIndex === 0, lineStyle: { color: XQ.gridLine } },
    axisLabel: {
      show: opts?.showLabel ?? gridIndex === 0,
      inside: true,
      align: 'left' as const,
      margin: 2,
      fontSize: 10,
      color: XQ.axis,
      formatter: (v: number) => (gridIndex === 0 ? Number(v).toFixed(2) : ''),
    },
  }
}

export function buildKlineChartOption(params: {
  bars: BarPoint[]
  period: string
  mainKind: MainChartKind
  subChart2: SubChart2Kind
  main: MainIndicatorSettings
  marks?: KlineAnnotationMarks
  dataZoomStart?: number
  dataZoomEnd?: number
  panMode?: boolean
}): EChartsOption {
  const { bars, period, mainKind, subChart2, main, marks, panMode = false } = params
  const dates = bars.map((b) => fmtBarTime(b.bar_time, period))
  const closes = bars.map((b) => Number(b.close))
  const highs = bars.map((b) => Number(b.high))
  const lows = bars.map((b) => Number(b.low))
  const opens = bars.map((b) => Number(b.open))
  const volumes = bars.map((b) => Number(b.volume))
  const candles = bars.map((b) => [Number(b.open), Number(b.close), Number(b.low), Number(b.high)])

  const start = params.dataZoomStart ?? 60
  const end = params.dataZoomEnd ?? 100
  const barMaxWidth = calcBarMaxWidth(bars.length, start, end)

  const series: SeriesOption[] = [
    {
      name: 'K线',
      type: 'candlestick',
      data: candles,
      itemStyle: {
        color: XQ.bg,
        color0: XQ.down,
        borderColor: XQ.up,
        borderColor0: XQ.down,
        borderWidth: 1,
      },
    },
  ]

  if (mainKind === 'ma') {
    main.ma.forEach((p, i) => {
      series.push({
        name: `MA${p}`,
        type: 'line',
        data: sma(closes, p),
        smooth: false,
        showSymbol: false,
        lineStyle: { width: 1, color: XQ.ma[i % XQ.ma.length] },
      })
    })
  } else {
    const b = boll(closes, 20, 2)
    series.push(
      {
        name: 'BOLL上',
        type: 'line',
        data: b.upper,
        showSymbol: false,
        lineStyle: { width: 1, color: '#FF6B9D' },
      },
      {
        name: 'BOLL中',
        type: 'line',
        data: b.mid,
        showSymbol: false,
        lineStyle: { width: 1, color: '#E6A23C' },
      },
      {
        name: 'BOLL下',
        type: 'line',
        data: b.lower,
        showSymbol: false,
        lineStyle: { width: 1, color: '#00D4FF' },
      },
    )
  }

  series.push({
    name: '成交量',
    type: 'bar',
    xAxisIndex: 1,
    yAxisIndex: 1,
    data: bars.map((b, i) => ({
      value: b.volume,
      itemStyle: { color: closes[i] >= opens[i] ? XQ.upVol : XQ.downVol },
    })),
    barMaxWidth,
  })

  series.push(
    {
      name: 'VOLMA5',
      type: 'line',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: sma(volumes, 5),
      showSymbol: false,
      lineStyle: { width: 1, color: '#E6A23C' },
    },
    {
      name: 'VOLMA10',
      type: 'line',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: sma(volumes, 10),
      showSymbol: false,
      lineStyle: { width: 1, color: '#00D4FF' },
    },
  )

  appendSub2Series(series, subChart2, highs, lows, closes, volumes)

  if (series[0]?.type === 'candlestick') {
    const candle = series[0] as { markPoint?: object; markLine?: object; markArea?: object }
    Object.assign(candle, buildCandlestickMarks({ bars, period, marks }))
  }

  return {
    backgroundColor: XQ.bg,
    animation: false,
    legend: { show: false },
    tooltip: {
      show: false,
      trigger: 'axis',
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }],
      triggerOn: panMode ? 'none' : 'mousemove|click',
      snap: true,
      type: 'cross',
      lineStyle: { color: XQ.cross, type: 'dashed' },
      label: { show: false },
    },
    grid: [
      {
        left: XQ_CHART_LAYOUT.gridLeft,
        right: XQ_CHART_LAYOUT.gridRight,
        top: XQ_CHART_LAYOUT.mainTop,
        height: XQ_CHART_LAYOUT.mainHeight,
        borderWidth: 0,
      },
      {
        left: XQ_CHART_LAYOUT.gridLeft,
        right: XQ_CHART_LAYOUT.gridRight,
        top: XQ_CHART_LAYOUT.volTop,
        height: XQ_CHART_LAYOUT.volHeight,
        borderWidth: 0,
      },
      {
        left: XQ_CHART_LAYOUT.gridLeft,
        right: XQ_CHART_LAYOUT.gridRight,
        top: XQ_CHART_LAYOUT.ind2Top,
        height: XQ_CHART_LAYOUT.ind2Height,
        borderWidth: 0,
      },
    ],
    xAxis: [
      makeCategoryAxis(dates, 0, false),
      makeCategoryAxis(dates, 1, false),
      makeCategoryAxis(dates, 2, true),
    ],
    yAxis: [makeYAxis(0, { splitNumber: 4 }), makeYAxis(1, { showLabel: false }), makeYAxis(2, { showLabel: false })],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1, 2],
        filterMode: 'none',
        zoomOnMouseWheel: true,
        moveOnMouseMove: panMode,
        moveOnMouseWheel: false,
      },
      {
        type: 'slider',
        xAxisIndex: [0, 1, 2],
        height: XQ_CHART_LAYOUT.sliderHeight,
        bottom: XQ_CHART_LAYOUT.sliderBottom,
        left: XQ_CHART_LAYOUT.gridLeft,
        right: XQ_CHART_LAYOUT.gridRight,
        filterMode: 'none',
        start,
        end,
        borderColor: XQ.sliderBorder,
        fillerColor: XQ.sliderFill,
        handleSize: 0,
        showDetail: false,
        brushSelect: false,
      },
    ],
    series,
  }
}

export function readDataZoomRange(chart: ECharts): { start: number; end: number } | null {
  const opt = chart.getOption() as EChartsOption
  const dzList = (opt.dataZoom ?? []) as { start?: number; end?: number }[]
  const dz = dzList.find((d) => d.start != null && d.end != null)
  if (!dz || dz.start == null || dz.end == null) return null
  return { start: dz.start, end: dz.end }
}

export const DEFAULT_DATA_ZOOM = { start: 60, end: 100 } as const

export function resetDataZoom(chart: ECharts): void {
  chart.dispatchAction({
    type: 'dataZoom',
    start: DEFAULT_DATA_ZOOM.start,
    end: DEFAULT_DATA_ZOOM.end,
  })
}

export function shiftDataZoom(chart: ECharts, delta: { zoom?: number; pan?: number }): void {
  const opt = chart.getOption() as EChartsOption
  const dzList = (opt.dataZoom ?? []) as { start?: number; end?: number }[]
  const dz = dzList.find((d) => d.start != null) ?? dzList[0]
  if (!dz || dz.start == null || dz.end == null) return
  let start = dz.start
  let end = dz.end
  const span = end - start
  if (delta.zoom != null) {
    const center = (start + end) / 2
    const nextSpan = Math.max(8, Math.min(100, span + delta.zoom))
    start = center - nextSpan / 2
    end = center + nextSpan / 2
  }
  if (delta.pan != null) {
    start += delta.pan
    end += delta.pan
  }
  if (start < 0) {
    end -= start
    start = 0
  }
  if (end > 100) {
    start -= end - 100
    end = 100
  }
  start = Math.max(0, start)
  end = Math.min(100, Math.max(start + 5, end))
  chart.dispatchAction({ type: 'dataZoom', start, end })
}
