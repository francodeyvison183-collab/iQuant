/**
 * 雪球移动端 K 线区高度比例（主图 : 成交量 : 副图 ≈ 4 : 1 : 1）。
 * 百分比相对 ECharts 容器，底部留给时间轴与滑块。
 */
export const XQ_CHART_LAYOUT = {
  /** 为内侧 Y 轴刻度与左上角指标文案留空 */
  gridLeft: 10,
  gridRight: 4,
  /** 主图 */
  mainTop: 2,
  mainHeight: '56%',
  /** 成交量附图 */
  volTop: '59%',
  volHeight: '14%',
  /** 第二附图（MACD 等） */
  ind2Top: '74%',
  ind2Height: '14%',
  /** 底部滑块 */
  sliderHeight: 16,
  sliderBottom: 0,
} as const

/** ECharts 区域最小高度（相对早期 300/260 提升 50%）。 */
export const XQ_CHART_MIN_HEIGHT = {
  wrapPx: 450,
  canvasPx: 390,
} as const
