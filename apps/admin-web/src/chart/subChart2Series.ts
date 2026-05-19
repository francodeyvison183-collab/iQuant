import type { SeriesOption } from 'echarts'
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
  trix,
  vr,
  wr,
} from './indicators'
import type { SubChart2Kind } from './types'
import { XQ } from './xueqiuTheme'

const XI = 2
const YI = 2

function line(
  name: string,
  data: (number | null)[],
  color: string,
  markY?: number[],
): SeriesOption {
  return {
    name,
    type: 'line',
    xAxisIndex: XI,
    yAxisIndex: YI,
    data,
    showSymbol: false,
    lineStyle: { width: 1, color },
    ...(markY?.length
      ? {
          markLine: {
            silent: true,
            symbol: 'none',
            data: markY.map((yAxis) => ({ yAxis })),
            lineStyle: { color: XQ.gridLine, type: 'dashed' },
          },
        }
      : {}),
  }
}

export function appendSub2Series(
  series: SeriesOption[],
  kind: SubChart2Kind,
  highs: number[],
  lows: number[],
  closes: number[],
  volumes: number[],
): void {
  switch (kind) {
    case 'macd': {
      const m = macd(closes)
      series.push(
        line('DIF', m.dif, '#E6A23C'),
        line('DEA', m.dea, '#00D4FF'),
        {
          name: 'MACD',
          type: 'bar',
          xAxisIndex: XI,
          yAxisIndex: YI,
          data: m.hist.map((v) => ({
            value: v,
            itemStyle: { color: (v ?? 0) >= 0 ? XQ.up : XQ.down },
          })),
          barMaxWidth: 4,
        },
      )
      break
    }
    case 'kdj': {
      const k = kdj(highs, lows, closes)
      series.push(line('K', k.k, '#E6A23C'), line('D', k.d, '#00D4FF'), line('J', k.j, '#FF6B9D'))
      break
    }
    case 'rsi':
      series.push(line('RSI', rsi(closes, 14), '#9B7BFF', [80, 20]))
      break
    case 'wr':
      series.push(line('WR', wr(highs, lows, closes, 14), '#9B7BFF', [-20, -80]))
      break
    case 'cci':
      series.push(line('CCI', cci(highs, lows, closes, 20), '#E6A23C', [100, -100]))
      break
    case 'bias':
      series.push(line('BIAS', bias(closes, 6), '#00D4FF'))
      break
    case 'obv':
      series.push(line('OBV', obv(closes, volumes), '#E6A23C'))
      break
    case 'boll': {
      const b = boll(closes, 20, 2)
      series.push(
        line('BOLL上', b.upper, '#FF6B9D'),
        line('BOLL中', b.mid, '#E6A23C'),
        line('BOLL下', b.lower, '#00D4FF'),
      )
      break
    }
    case 'dmi': {
      const d = dmi(highs, lows, closes, 14)
      series.push(
        line('+DI', d.pdi, '#F04848'),
        line('-DI', d.mdi, '#1CB54A'),
        line('ADX', d.adx, '#9B7BFF'),
      )
      break
    }
    case 'dma': {
      const d = dma(closes, 10, 50, 10)
      series.push(line('DDD', d.ddd, '#E6A23C'), line('AMA', d.ama, '#00D4FF'))
      break
    }
    case 'trix': {
      const t = trix(closes, 12)
      series.push(line('TRIX', t.trix, '#E6A23C'), line('MATRIX', t.signal, '#00D4FF'))
      break
    }
    case 'vr':
      series.push(line('VR', vr(closes, volumes, 26), '#9B7BFF', [70, 30]))
      break
    case 'emv':
      series.push(line('EMV', emv(highs, lows, volumes, 14), '#E6A23C'))
      break
    case 'roc':
      series.push(line('ROC', roc(closes, 12), '#00D4FF'))
      break
    case 'mtm':
      series.push(line('MTM', mtm(closes, 12), '#E6A23C'))
      break
    case 'psy':
      series.push(line('PSY', psy(closes, 12), '#9B7BFF', [75, 25]))
      break
    case 'sar':
      series.push(line('SAR', sar(highs, lows), '#F04848'))
      break
  }
}
