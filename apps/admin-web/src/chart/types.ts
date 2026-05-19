/** 主图叠加指标（雪球指标栏 MA / BOLL）。 */
export type MainChartKind = 'ma' | 'boll'

export const MAIN_CHART_OPTIONS: { value: MainChartKind; label: string }[] = [
  { value: 'ma', label: 'MA' },
  { value: 'boll', label: 'BOLL' },
]

/** 第二附图指标（第一附图固定为成交量）。顺序参考雪球指标栏。 */
export type SubChart2Kind =
  | 'macd'
  | 'kdj'
  | 'rsi'
  | 'boll'
  | 'wr'
  | 'bias'
  | 'cci'
  | 'dmi'
  | 'dma'
  | 'trix'
  | 'obv'
  | 'vr'
  | 'emv'
  | 'roc'
  | 'mtm'
  | 'psy'
  | 'sar'

export const SUB_CHART2_OPTIONS: { value: SubChart2Kind; label: string }[] = [
  { value: 'macd', label: 'MACD' },
  { value: 'kdj', label: 'KDJ' },
  { value: 'rsi', label: 'RSI' },
  { value: 'boll', label: 'BOLL' },
  { value: 'wr', label: 'WR' },
  { value: 'bias', label: 'BIAS' },
  { value: 'cci', label: 'CCI' },
  { value: 'dmi', label: 'DMI' },
  { value: 'dma', label: 'DMA' },
  { value: 'trix', label: 'TRIX' },
  { value: 'obv', label: 'OBV' },
  { value: 'vr', label: 'VR' },
  { value: 'emv', label: 'EMV' },
  { value: 'roc', label: 'ROC' },
  { value: 'mtm', label: 'MTM' },
  { value: 'psy', label: 'PSY' },
  { value: 'sar', label: 'SAR' },
]

/** 主图均线：雪球默认展示 MA5/10/20/30 */
export interface MainIndicatorSettings {
  ma: number[]
}

export const DEFAULT_MAIN_INDICATORS: MainIndicatorSettings = {
  ma: [5, 10, 20, 30, 60],
}
