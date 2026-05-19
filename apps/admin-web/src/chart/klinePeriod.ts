/** 与后端 KlinePeriod 一致；顺序参考雪球周期 Tab。 */
export const KLINE_PERIOD_OPTIONS = [
  { value: '5m', label: '5分' },
  { value: '30m', label: '30分' },
  { value: 'day', label: '日K' },
  { value: 'week', label: '周K' },
  { value: 'month', label: '月K' },
] as const

/** 盲测训练可选周期（不含月K） */
export const BLIND_KLINE_PERIOD_OPTIONS = KLINE_PERIOD_OPTIONS.filter((p) =>
  (['5m', '30m', 'day', 'week'] as const).includes(p.value as '5m' | '30m' | 'day' | 'week'),
)

export type KlinePeriodValue = (typeof KLINE_PERIOD_OPTIONS)[number]['value']

export function periodLabel(period: string): string {
  return KLINE_PERIOD_OPTIONS.find((p) => p.value === period)?.label ?? period
}

export function defaultBarLimit(period: string): number {
  if (period === 'month' || period === 'week') return 300
  if (period === 'day') return 500
  return 800
}
