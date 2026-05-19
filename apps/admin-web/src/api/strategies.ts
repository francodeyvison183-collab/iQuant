import { get, post } from './client'

export interface StrategyVersion {
  id: string
  version_no: number
  status: string
  dsl: Record<string, unknown>
  rules_summary: string[]
  rank_score: string
  is_selected: boolean
  created_at: string
  confirmed_at: string | null
}

export interface BehaviorStrategy {
  id: string
  name: string
  status: string
  source: string
  period: string
  consistency_report_id: string | null
  created_at: string
  updated_at: string
  versions: StrategyVersion[]
}

export interface StrategySummary {
  id: string
  name: string
  status: string
  period: string
  version_count: number
  confirmed_version_id: string | null
  created_at: string
}

function newIdempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, '')
}

export async function generateStrategies(payload: {
  period?: string
  consistency_report_id?: string
}) {
  return post<BehaviorStrategy>('/strategies/generate', payload, {
    'X-Idempotency-Key': newIdempotencyKey(),
  })
}

export async function listStrategies(params?: { limit?: number; offset?: number }) {
  return get<StrategySummary[]>('/strategies', params as Record<string, unknown> | undefined)
}

export async function getStrategy(strategyId: string) {
  return get<BehaviorStrategy>(`/strategies/${strategyId}`)
}

export async function confirmStrategyVersion(strategyId: string, versionId: string) {
  return post<BehaviorStrategy>(
    `/strategies/${strategyId}/confirm`,
    { version_id: versionId },
    { 'X-Idempotency-Key': newIdempotencyKey() },
  )
}
