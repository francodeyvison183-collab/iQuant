import type { BarPoint } from '@/api/market'
import type { ECharts } from 'echarts'
import {
  bias,
  boll,
  cci,
  dma,
  dmi,
  emv,
  kdj,
  macd,
  mtm,
  obv,
  psy,
  roc,
  rsi,
  sar,
  sma,
  trix,
  vr,
  wr,
} from './indicators'
import type { EChartsOption } from 'echarts'
import type { MainChartKind, MainIndicatorSettings, SubChart2Kind } from './types'

const PAD = 0.04

function visibleIndexRange(count: number, startPct: number, endPct: number): { from: number; to: number } {
  if (count <= 0) return { from: 0, to: 0 }
  const from = Math.max(0, Math.floor((startPct / 100) * count))
  const to = Math.min(count - 1, Math.max(from, Math.ceil((endPct / 100) * count) - 1))
  return { from, to }
}

function withPadding(min: number, max: number, ratio = PAD): { min: number; max: number } {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 }
  if (min === max) {
    const d = Math.max(Math.abs(min) * 0.02, 0.01)
    return { min: min - d, max: max + d }
  }
  const pad = (max - min) * ratio
  return { min: min - pad, max: max + pad }
}

function rangeOfValues(values: (number | null)[], from: number, to: number): { min: number; max: number } | null {
  let min = Infinity
  let max = -Infinity
  for (let i = from; i <= to; i++) {
    const v = values[i]
    if (v == null || !Number.isFinite(v)) continue
    min = Math.min(min, v)
    max = Math.max(max, v)
  }
  if (min === Infinity) return null
  return withPadding(min, max)
}

function mergeRanges(a: { min: number; max: number } | null, b: { min: number; max: number } | null) {
  if (!a) return b
  if (!b) return a
  return withPadding(Math.min(a.min, b.min), Math.max(a.max, b.max))
}

function mergeMany(ranges: ({ min: number; max: number } | null)[]) {
  return ranges.reduce((acc, r) => mergeRanges(acc, r), null)
}

function readDataZoomRange(chart: ECharts): { start: number; end: number } | null {
  const opt = chart.getOption() as EChartsOption
  const dzList = (opt.dataZoom ?? []) as { start?: number; end?: number }[]
  const dz = dzList.find((d) => d.start != null && d.end != null)
  if (!dz || dz.start == null || dz.end == null) return null
  return { start: dz.start, end: dz.end }
}

function mainYRange(
  bars: BarPoint[],
  from: number,
  to: number,
  mainKind: MainChartKind,
  maPeriods: number[],
) {
  let min = Infinity
  let max = -Infinity
  const closes = bars.map((b) => Number(b.close))
  for (let i = from; i <= to; i++) {
    min = Math.min(min, Number(bars[i].low))
    max = Math.max(max, Number(bars[i].high))
  }
  if (mainKind === 'boll') {
    const b = boll(closes, 20, 2)
    for (let i = from; i <= to; i++) {
      for (const arr of [b.upper, b.mid, b.lower]) {
        const v = arr[i]
        if (v == null || !Number.isFinite(v)) continue
        min = Math.min(min, v)
        max = Math.max(max, v)
      }
    }
  } else {
    for (const p of maPeriods) {
      const ma = sma(closes, p)
      for (let i = from; i <= to; i++) {
        const v = ma[i]
        if (v == null || !Number.isFinite(v)) continue
        min = Math.min(min, v)
        max = Math.max(max, v)
      }
    }
  }
  if (min === Infinity) return null
  return withPadding(min, max)
}

function volumeYRange(bars: BarPoint[], from: number, to: number) {
  const volumes = bars.map((b) => Number(b.volume))
  let max = 0
  for (let i = from; i <= to; i++) {
    max = Math.max(max, volumes[i])
  }
  for (const p of [5, 10]) {
    const ma = sma(volumes, p)
    for (let i = from; i <= to; i++) {
      const v = ma[i]
      if (v != null && Number.isFinite(v)) max = Math.max(max, v)
    }
  }
  if (max <= 0) return { min: 0, max: 1 }
  return { min: 0, max: max * 1.08 }
}

function sub2YRange(
  kind: SubChart2Kind,
  highs: number[],
  lows: number[],
  closes: number[],
  volumes: number[],
  from: number,
  to: number,
): { min: number; max: number } | null {
  switch (kind) {
    case 'macd': {
      const m = macd(closes)
      return mergeMany([
        rangeOfValues(m.dif, from, to),
        rangeOfValues(m.dea, from, to),
        rangeOfValues(m.hist, from, to),
      ])
    }
    case 'kdj': {
      const k = kdj(highs, lows, closes)
      return mergeMany([rangeOfValues(k.k, from, to), rangeOfValues(k.d, from, to), rangeOfValues(k.j, from, to)])
    }
    case 'rsi':
      return rangeOfValues(rsi(closes, 14), from, to)
    case 'wr':
      return rangeOfValues(wr(highs, lows, closes, 14), from, to)
    case 'cci':
      return rangeOfValues(cci(highs, lows, closes, 20), from, to)
    case 'bias':
      return rangeOfValues(bias(closes, 6), from, to)
    case 'obv':
      return rangeOfValues(obv(closes, volumes), from, to)
    case 'boll': {
      const b = boll(closes, 20, 2)
      return mergeMany([
        rangeOfValues(b.upper, from, to),
        rangeOfValues(b.mid, from, to),
        rangeOfValues(b.lower, from, to),
      ])
    }
    case 'dmi': {
      const d = dmi(highs, lows, closes, 14)
      return mergeMany([
        rangeOfValues(d.pdi, from, to),
        rangeOfValues(d.mdi, from, to),
        rangeOfValues(d.adx, from, to),
      ])
    }
    case 'dma': {
      const d = dma(closes, 10, 50, 10)
      return mergeMany([rangeOfValues(d.ddd, from, to), rangeOfValues(d.ama, from, to)])
    }
    case 'trix': {
      const t = trix(closes, 12)
      return mergeMany([rangeOfValues(t.trix, from, to), rangeOfValues(t.signal, from, to)])
    }
    case 'vr':
      return rangeOfValues(vr(closes, volumes, 26), from, to)
    case 'emv':
      return rangeOfValues(emv(highs, lows, volumes, 14), from, to)
    case 'roc':
      return rangeOfValues(roc(closes, 12), from, to)
    case 'mtm':
      return rangeOfValues(mtm(closes, 12), from, to)
    case 'psy':
      return rangeOfValues(psy(closes, 12), from, to)
    case 'sar':
      return rangeOfValues(sar(highs, lows), from, to)
    default:
      return null
  }
}

/** 按当前 dataZoom 可见区间收紧 Y 轴，使 K 线/附图纵向铺满。 */
export function applyVisibleYAxisScale(
  chart: ECharts,
  params: {
    bars: BarPoint[]
    mainKind: MainChartKind
    main: MainIndicatorSettings
    subChart2: SubChart2Kind
    zoom?: { start: number; end: number } | null
  },
): void {
  const n = params.bars.length
  if (!n) return

  const z = params.zoom ?? readDataZoomRange(chart) ?? { start: 60, end: 100 }
  const { from, to } = visibleIndexRange(n, z.start, z.end)

  const highs = params.bars.map((b) => Number(b.high))
  const lows = params.bars.map((b) => Number(b.low))
  const closes = params.bars.map((b) => Number(b.close))
  const volumes = params.bars.map((b) => Number(b.volume))

  const main = mainYRange(params.bars, from, to, params.mainKind, params.main.ma)
  const vol = volumeYRange(params.bars, from, to)
  const sub = sub2YRange(params.subChart2, highs, lows, closes, volumes, from, to)

  chart.setOption({
    yAxis: [
      main
        ? { min: main.min, max: main.max, scale: false, position: 'left' as const }
        : { scale: true, position: 'left' as const },
      vol
        ? { min: vol.min, max: vol.max, scale: false, position: 'left' as const }
        : { scale: true, position: 'left' as const },
      sub
        ? { min: sub.min, max: sub.max, scale: false, position: 'left' as const }
        : { scale: true, position: 'left' as const },
    ],
  })
}
