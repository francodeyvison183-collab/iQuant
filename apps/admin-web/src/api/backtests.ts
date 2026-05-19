import { get, post } from './client'

export interface BacktestReport {
  id: string
  summary: Record<string, unknown>
  data_window: Record<string, unknown>
  warnings: string[]
  equity_curve: { bar_time: string; equity: number }[]
  created_at: string
}

export interface BacktestTask {
  id: string
  strategy_version_id: string
  full_code: string
  period: string
  status: string
  error_message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  report: BacktestReport | null
}

export interface BacktestTaskSummary {
  id: string
  strategy_version_id: string
  full_code: string
  period: string
  status: string
  strategy_name: string | null
  total_return: string | null
  created_at: string
  finished_at: string | null
}

function newIdempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, '')
}

export async function createBacktest(payload: {
  strategy_version_id: string
  full_code: string
  period?: string
  initial_cash?: string
}) {
  return post<BacktestTask>('/backtests', payload, {
    'X-Idempotency-Key': newIdempotencyKey(),
  })
}

export async function listBacktests(params?: { limit?: number; offset?: number }) {
  return get<BacktestTaskSummary[]>('/backtests', params as Record<string, unknown> | undefined)
}

export async function getBacktest(taskId: string) {
  return get<BacktestTask>(`/backtests/${taskId}`)
}
