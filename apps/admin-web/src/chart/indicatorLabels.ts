import type { BarPoint } from '@/api/market'
import { bias, boll, cci, dma, dmi, emv, kdj, macd, mtm, obv, psy, roc, rsi, sar, sma, trix, vr, wr } from './indicators'
import type { MainChartKind, SubChart2Kind } from './types'
import { XQ } from './xueqiuTheme'

function fmt(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return Number(v).toFixed(digits)
}

function fmtVolHand(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const hand = v / 100
  if (hand >= 10000) return `${(hand / 10000).toFixed(2)}万手`
  return `${hand.toFixed(0)}手`
}

export interface IndicatorLabelPart {
  text: string
  color?: string
}

export interface ChartIndicatorLabels {
  main: IndicatorLabelPart[]
  volume: IndicatorLabelPart[]
  sub2: IndicatorLabelPart[]
}

/** 主图 / 成交量 / 第二附图左上角指标文案（雪球风格）。 */
export function buildChartIndicatorLabels(params: {
  bars: BarPoint[]
  index: number
  mainKind: MainChartKind
  subChart2: SubChart2Kind
}): ChartIndicatorLabels {
  const { bars, index, mainKind, subChart2 } = params
  if (index < 0 || index >= bars.length) {
    return { main: [], volume: [], sub2: [] }
  }

  const closes = bars.map((b) => Number(b.close))
  const highs = bars.map((b) => Number(b.high))
  const lows = bars.map((b) => Number(b.low))
  const volumes = bars.map((b) => Number(b.volume))

  const main: IndicatorLabelPart[] = []
  if (mainKind === 'ma') {
    const periods = [5, 10, 20, 30, 60]
    periods.forEach((p, i) => {
      const v = sma(closes, p)[index]
      main.push({ text: `MA${p}:${fmt(v)}`, color: XQ.ma[i % XQ.ma.length] })
    })
  } else {
    const b = boll(closes, 20, 2)
    main.push(
      { text: `BOLL上:${fmt(b.upper[index])}`, color: '#FF6B9D' },
      { text: `MID:${fmt(b.mid[index])}`, color: '#E6A23C' },
      { text: `BOLL下:${fmt(b.lower[index])}`, color: '#00D4FF' },
    )
  }

  const volMa5 = sma(volumes, 5)[index]
  const volMa10 = sma(volumes, 10)[index]
  const volume: IndicatorLabelPart[] = [
    { text: `量:${fmtVolHand(volumes[index])}` },
    { text: `MA5:${fmtVolHand(volMa5)}`, color: '#E6A23C' },
    { text: `MA10:${fmtVolHand(volMa10)}`, color: '#00D4FF' },
  ]

  const sub2: IndicatorLabelPart[] = []
  switch (subChart2) {
    case 'macd': {
      const m = macd(closes)
      sub2.push(
        { text: 'MACD(12,26,9)', color: '#666' },
        { text: `DIF:${fmt(m.dif[index])}`, color: '#E6A23C' },
        { text: `DEA:${fmt(m.dea[index])}`, color: '#00D4FF' },
        { text: `MACD:${fmt(m.hist[index])}`, color: (m.hist[index] ?? 0) >= 0 ? XQ.up : XQ.down },
      )
      break
    }
    case 'kdj': {
      const k = kdj(highs, lows, closes)
      sub2.push(
        { text: 'KDJ(9,3,3)', color: '#666' },
        { text: `K:${fmt(k.k[index])}`, color: '#E6A23C' },
        { text: `D:${fmt(k.d[index])}`, color: '#00D4FF' },
        { text: `J:${fmt(k.j[index])}`, color: '#FF6B9D' },
      )
      break
    }
    case 'rsi':
      sub2.push({ text: 'RSI(14)', color: '#666' }, { text: `RSI:${fmt(rsi(closes, 14)[index])}`, color: '#9B7BFF' })
      break
    case 'wr':
      sub2.push({ text: 'WR(14)', color: '#666' }, { text: `WR:${fmt(wr(highs, lows, closes, 14)[index])}`, color: '#9B7BFF' })
      break
    case 'cci':
      sub2.push({ text: 'CCI(20)', color: '#666' }, { text: `CCI:${fmt(cci(highs, lows, closes, 20)[index])}`, color: '#E6A23C' })
      break
    case 'bias':
      sub2.push({ text: 'BIAS(6)', color: '#666' }, { text: `BIAS:${fmt(bias(closes, 6)[index])}`, color: '#00D4FF' })
      break
    case 'obv':
      sub2.push({ text: 'OBV', color: '#666' }, { text: `OBV:${fmt(obv(closes, volumes)[index], 0)}`, color: '#E6A23C' })
      break
    case 'boll': {
      const b = boll(closes, 20, 2)
      sub2.push(
        { text: 'BOLL(20,2)', color: '#666' },
        { text: `上:${fmt(b.upper[index])}`, color: '#FF6B9D' },
        { text: `中:${fmt(b.mid[index])}`, color: '#E6A23C' },
        { text: `下:${fmt(b.lower[index])}`, color: '#00D4FF' },
      )
      break
    }
    case 'dmi': {
      const d = dmi(highs, lows, closes, 14)
      sub2.push(
        { text: 'DMI(14)', color: '#666' },
        { text: `+DI:${fmt(d.pdi[index])}`, color: XQ.up },
        { text: `-DI:${fmt(d.mdi[index])}`, color: XQ.down },
        { text: `ADX:${fmt(d.adx[index])}`, color: '#9B7BFF' },
      )
      break
    }
    case 'dma': {
      const d = dma(closes, 10, 50, 10)
      sub2.push(
        { text: 'DMA', color: '#666' },
        { text: `DDD:${fmt(d.ddd[index])}`, color: '#E6A23C' },
        { text: `AMA:${fmt(d.ama[index])}`, color: '#00D4FF' },
      )
      break
    }
    case 'trix': {
      const t = trix(closes, 12)
      sub2.push(
        { text: 'TRIX(12)', color: '#666' },
        { text: `TRIX:${fmt(t.trix[index])}`, color: '#E6A23C' },
        { text: `MATRIX:${fmt(t.signal[index])}`, color: '#00D4FF' },
      )
      break
    }
    case 'vr':
      sub2.push({ text: 'VR(26)', color: '#666' }, { text: `VR:${fmt(vr(closes, volumes, 26)[index])}`, color: '#9B7BFF' })
      break
    case 'emv':
      sub2.push({ text: 'EMV(14)', color: '#666' }, { text: `EMV:${fmt(emv(highs, lows, volumes, 14)[index])}`, color: '#E6A23C' })
      break
    case 'roc':
      sub2.push({ text: 'ROC(12)', color: '#666' }, { text: `ROC:${fmt(roc(closes, 12)[index])}`, color: '#00D4FF' })
      break
    case 'mtm':
      sub2.push({ text: 'MTM(12)', color: '#666' }, { text: `MTM:${fmt(mtm(closes, 12)[index])}`, color: '#E6A23C' })
      break
    case 'psy':
      sub2.push({ text: 'PSY(12)', color: '#666' }, { text: `PSY:${fmt(psy(closes, 12)[index])}`, color: '#9B7BFF' })
      break
    case 'sar':
      sub2.push({ text: 'SAR', color: '#666' }, { text: `SAR:${fmt(sar(highs, lows)[index])}`, color: XQ.up })
      break
    default:
      break
  }

  return { main, volume, sub2 }
}
