import type { BarPoint } from '@/api/market'
import { fmtBarTime } from './klineOhlc'
import { XQ } from './xueqiuTheme'
export interface KlineAnnotationMarks {
  pendingBuyIndex: number | null
  pairMarks: { buyIndex: number; sellIndex: number }[]
}

export interface CandlestickMarkOverlay {
  markPoint?: object
  markLine?: object
  markArea?: object
}

/** 标注买卖点、买卖区间与最新价线。 */
export function buildCandlestickMarks(params: {
  bars: BarPoint[]
  period: string
  marks?: KlineAnnotationMarks
}): CandlestickMarkOverlay {
  const { bars, period, marks } = params
  const dates = bars.map((b) => fmtBarTime(b.bar_time, period))
  const closes = bars.map((b) => Number(b.close))
  const lastIdx = bars.length - 1
  const lastClose = lastIdx >= 0 ? closes[lastIdx] : 0
  const prevClose = lastIdx > 0 ? closes[lastIdx - 1] : lastClose
  const lastUp = lastClose >= prevClose

  const out: CandlestickMarkOverlay = {}

  const markPointData: {
    coord: [string, number]
    name: string
    itemStyle: { color: string }
    label?: { formatter: string; color: string }
  }[] = []

  if (marks?.pendingBuyIndex != null && marks.pendingBuyIndex >= 0) {
    const b = bars[marks.pendingBuyIndex]
    markPointData.push({
      coord: [dates[marks.pendingBuyIndex], Number(b.low)],
      name: '买',
      itemStyle: { color: '#2563EB' },
      label: { formatter: '买', color: '#fff' },
    })
  }

  const markAreaData: [{ xAxis: string }, { xAxis: string }][] = []

  for (const pm of marks?.pairMarks ?? []) {
    const buy = bars[pm.buyIndex]
    const sell = bars[pm.sellIndex]
    if (buy) {
      markPointData.push({
        coord: [dates[pm.buyIndex], Number(buy.low)],
        name: '买',
        itemStyle: { color: '#2563EB' },
        label: { formatter: '买', color: '#fff' },
      })
    }
    if (sell) {
      markPointData.push({
        coord: [dates[pm.sellIndex], Number(sell.high)],
        name: '卖',
        itemStyle: { color: '#F97316' },
        label: { formatter: '卖', color: '#fff' },
      })
    }
    if (buy && sell && pm.buyIndex < pm.sellIndex) {
      markAreaData.push([{ xAxis: dates[pm.buyIndex] }, { xAxis: dates[pm.sellIndex] }])
    }
  }

  if (markPointData.length) {
    out.markPoint = {
      symbol: 'circle',
      symbolSize: 10,
      label: { fontSize: 9, fontWeight: 'bold' },
      data: markPointData,
    }
  }

  if (markAreaData.length) {
    out.markArea = {
      silent: true,
      itemStyle: { color: 'rgba(37, 99, 235, 0.1)', borderWidth: 0 },
      data: markAreaData,
    }
  }

  if (lastIdx >= 0) {
    out.markLine = {
      symbol: 'none',
      silent: true,
      animation: false,
      data: [
        {
          yAxis: lastClose,
          lineStyle: {
            color: lastUp ? XQ.up : XQ.down,
            type: 'dashed',
            width: 1,
          },
          label: {
            show: true,
            position: 'end',
            formatter: lastClose.toFixed(2),
            color: '#fff',
            backgroundColor: lastUp ? XQ.up : XQ.down,
            padding: [2, 4],
            fontSize: 10,
            borderRadius: 2,
          },
        },
      ],
    }
  }

  return out
}
