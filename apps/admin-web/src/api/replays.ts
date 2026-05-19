import { get, patch, post } from './client'

export interface BlindBarPoint {
  bar_time: string
  open: string
  high: string
  low: string
  close: string
  volume: number
  amount: string
}

export interface BlindAction {
  id: string
  bar_time: string
  period: string
  user_action: string
  features_snapshot: Record<string, unknown>
  strategy_signal: string | null
  user_reasons: string[] | null
  confidence: string | null
  created_at: string
}

export interface BlindSession {
  id: string
  display_label: string
  display_name: string | null
  full_code: string
  symbol_name: string | null
  period: string
  range_start: string
  range_end: string
  cursor_bar_time: string
  status: string
  source: string
  cash_balance: string
  position_qty: string
  action_count: number
  trade_action_count: number
  round_trade_count: number
  required_trade_actions: number
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface BlindRoundStock {
  session_id: string
  display_label: string
  display_name: string | null
  full_code: string
  symbol_name: string | null
  status: string
  trade_action_count: number
  created_at: string
}

export interface BlindRound {
  round_id: string
  status: string
  period: string
  range_start: string
  range_end: string
  trade_action_count: number
  required_trade_actions: number
  stock_count: number
  started_at: string
  completed_at: string | null
  stocks: BlindRoundStock[]
}

export interface BlindSessionDetail extends BlindSession {
  view_period: string
  visible_bars: BlindBarPoint[]
  actions: BlindAction[]
  can_act: boolean
}

export interface BlindSessionSummary {
  id: string
  display_label: string
  display_name: string | null
  full_code: string
  symbol_name: string | null
  period: string
  status: string
  action_count: number
  trade_action_count: number
  created_at: string
  completed_at: string | null
}

export interface BlindConsistencyReport {
  id: string
  period: string
  session_count: number
  scores: Record<string, unknown>
  profile_draft: string
  insights: string[]
  correction_options: { id: string; label: string }[]
  user_corrections: string[]
  ready_for_strategy: boolean
  created_at: string
  updated_at: string
}

function newIdempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, '')
}

export async function createBlindSession(payload: {
  period?: string
  months_back?: number
  market?: string
  range_start?: string
  range_end?: string
}) {
  return post<BlindSessionDetail>('/replays/sessions', payload, {
    'X-Idempotency-Key': newIdempotencyKey(),
  })
}

export async function getBlindSession(sessionId: string, period?: string) {
  return get<BlindSessionDetail>(
    `/replays/sessions/${sessionId}`,
    period ? { period } : undefined,
  )
}

export async function listBlindSessions(params?: {
  limit?: number
  offset?: number
  status?: string
}) {
  return get<BlindSessionSummary[]>('/replays/sessions', params as Record<string, unknown> | undefined)
}

export async function listBlindRounds(params?: { limit?: number }) {
  return get<BlindRound[]>('/replays/rounds', params as Record<string, unknown> | undefined)
}

export async function submitBlindAction(
  sessionId: string,
  payload: {
    user_action: 'buy' | 'sell' | 'hold'
    period?: string
    user_reasons?: string[]
    confidence?: string
  },
) {
  return post<BlindSessionDetail>(`/replays/sessions/${sessionId}/actions`, payload)
}

export async function finishBlindSession(sessionId: string) {
  return post<BlindSessionDetail>(
    `/replays/sessions/${sessionId}/finish`,
    {},
    { 'X-Idempotency-Key': newIdempotencyKey() },
  )
}

export async function skipBlindSession(sessionId: string) {
  return post<BlindSessionDetail>(
    `/replays/sessions/${sessionId}/skip`,
    {},
    { 'X-Idempotency-Key': newIdempotencyKey() },
  )
}

export async function evaluateConsistencyReport(params?: { period?: string; regenerate?: boolean }) {
  const q = new URLSearchParams()
  if (params?.period) q.set('period', params.period)
  if (params?.regenerate) q.set('regenerate', 'true')
  const suffix = q.toString() ? `?${q}` : ''
  return post<BlindConsistencyReport>(`/replays/consistency-report${suffix}`, {})
}

export async function getConsistencyReport(period?: string) {
  return get<BlindConsistencyReport>(
    '/replays/consistency-report',
    period ? { period } : undefined,
  )
}

export async function patchConsistencyCorrections(reportId: string, user_corrections: string[]) {
  return patch<BlindConsistencyReport>(`/replays/consistency-report/${reportId}`, {
    user_corrections,
  })
}
