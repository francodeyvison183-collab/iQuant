import type { BarPoint } from '@/api/market'

export interface OhlcDisplay {
  time: string
  open: string
  high: string
  low: string
  close: string
  changePct: number
  changeAbs: number
  volume: string
  isUp: boolean
}

export function fmtBarTime(barTime: string, period: string): string {
  const t = barTime.replace('T', ' ').replace('Z', '')
  if (period === 'day' || period === 'week' || period === 'month') {
    return t.slice(0, 10)
  }
  if (t.length >= 16) {
    return `${t.slice(5, 11)} ${t.slice(11, 16)}`
  }
  return t.slice(0, 16)
}

function fmtNum(n: number, digits = 2): string {
  return Number(n).toFixed(digits)
}

function fmtVolume(v: number): string {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  if (v >= 1e4) return `${(v / 1e4).toFixed(2)}万`
  return String(Math.round(v))
}

/** 指定 K 线索引的行情摘要（十字线 / 默认最新一根）。 */
export function buildOhlcDisplay(bars: BarPoint[], index: number, period: string): OhlcDisplay | null {
  if (index < 0 || index >= bars.length) return null
  const b = bars[index]
  const open = Number(b.open)
  const prev = index > 0 ? Number(bars[index - 1].close) : open
  const close = Number(b.close)
  const changeAbs = close - prev
  const changePct = prev ? (changeAbs / prev) * 100 : 0
  return {
    time: fmtBarTime(b.bar_time, period),
    open: fmtNum(open),
    high: fmtNum(Number(b.high)),
    low: fmtNum(Number(b.low)),
    close: fmtNum(close),
    changePct,
    changeAbs,
    volume: fmtVolume(Number(b.volume)),
    isUp: changeAbs >= 0,
  }
}

export function resolveDisplayIndex(cursorIndex: number | null, barCount: number): number {
  if (barCount <= 0) return -1
  if (cursorIndex != null && cursorIndex >= 0 && cursorIndex < barCount) return cursorIndex
  return barCount - 1
}

/** 从 ECharts updateAxisPointer 事件解析 K 线索引。 */
export function resolvePointerBarIndex(
  ev: unknown,
  barCount: number,
  dateLabels?: string[],
): number | null {
  if (barCount <= 0) return null
  const e = ev as {
    dataIndex?: number
    axesInfo?: { axisDim?: string; axisIndex?: number; value?: number | string }[]
  }
  if (typeof e.dataIndex === 'number' && e.dataIndex >= 0 && e.dataIndex < barCount) {
    return e.dataIndex
  }
  const xInfo = e.axesInfo?.find((a) => a.axisDim === 'x' && a.axisIndex === 0)
  if (xInfo?.value == null) return null
  if (typeof xInfo.value === 'number') {
    const idx = Math.round(xInfo.value)
    return idx >= 0 && idx < barCount ? idx : null
  }
  if (dateLabels?.length) {
    const idx = dateLabels.indexOf(String(xInfo.value))
    return idx >= 0 ? idx : null
  }
  return null
}
