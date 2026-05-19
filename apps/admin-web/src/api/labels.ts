import { del, get, patch, post, put } from './client'

export interface LabelPair {
  id: string
  sort_order: number
  buy_bar_time: string
  sell_bar_time: string
  buy_close: string
  sell_close: string
  return_pct: string
}

export interface LabelSession {
  id: string
  full_code: string
  period: string
  title: string | null
  created_at: string
  updated_at: string
  pairs: LabelPair[]
}

export interface LabelSessionSummary {
  id: string
  full_code: string
  period: string
  title: string | null
  created_at: string
  pair_count: number
}

export interface LabelPairDraft {
  buy_bar_time: string
  sell_bar_time: string
  buy_close: string
  sell_close: string
}

function newIdempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, '')
}

export async function createLabelSession(payload: {
  full_code: string
  period?: string
  title?: string | null
}) {
  return post<LabelSession>('/labels/sessions', payload, {
    'X-Idempotency-Key': newIdempotencyKey(),
  })
}

export async function listLabelSessions(params?: { limit?: number; offset?: number }) {
  return get<LabelSessionSummary[]>('/labels/sessions', params as Record<string, unknown> | undefined)
}

export async function getLabelSession(sessionId: string) {
  return get<LabelSession>(`/labels/sessions/${sessionId}`)
}

export async function replaceLabelPairs(sessionId: string, pairs: LabelPairDraft[]) {
  return put<LabelSession>(
    `/labels/sessions/${sessionId}/pairs`,
    { pairs },
    { 'X-Idempotency-Key': newIdempotencyKey() },
  )
}

export async function deleteLabelSession(sessionId: string) {
  return del<null>(`/labels/sessions/${sessionId}`, {
    'X-Idempotency-Key': newIdempotencyKey(),
  })
}

export interface LabelBatchProgress {
  total: number
  completed: number
  skipped: number
  pending: number
  current_index: number | null
}

export interface LabelQueueItem {
  id: string
  sort_order: number
  full_code: string
  symbol_name: string
  status: string
  skip_reason: string | null
  session_id: string | null
  pair_count: number
}

export interface LabelBatch {
  id: string
  period: string
  market_filter: string | null
  batch_size: number
  status: string
  created_at: string
  completed_at: string | null
  progress: LabelBatchProgress
  items: LabelQueueItem[]
}

export interface LabelBatchCurrent {
  batch: LabelBatch
  current_item: LabelQueueItem | null
  session: LabelSession | null
  done: boolean
}

export async function createLabelBatch(payload: {
  period?: string
  market?: string | null
  batch_size?: number
}) {
  return post<LabelBatch>('/labels/batches', payload, {
    'X-Idempotency-Key': newIdempotencyKey(),
  })
}

export async function getLabelBatch(batchId: string) {
  return get<LabelBatch>(`/labels/batches/${batchId}`)
}

export async function getBatchCurrent(batchId: string) {
  return get<LabelBatchCurrent>(`/labels/batches/${batchId}/current`)
}

export async function skipBatchItem(
  batchId: string,
  itemId: string,
  skipReason?: string | null,
) {
  return post<LabelBatchCurrent>(
    `/labels/batches/${batchId}/items/${itemId}/skip`,
    { skip_reason: skipReason ?? null },
    { 'X-Idempotency-Key': newIdempotencyKey() },
  )
}

export async function completeBatchItem(batchId: string, itemId: string) {
  return post<LabelBatchCurrent>(
    `/labels/batches/${batchId}/items/${itemId}/complete`,
    {},
    { 'X-Idempotency-Key': newIdempotencyKey() },
  )
}

export interface LabelBatchSummary {
  batch_id: string
  stats: Record<string, unknown>
  profile_draft: string
  insights: string[]
  correction_options: { id: string; label: string }[]
  user_corrections: string[]
  outlier_pairs: {
    pair_id: string
    session_id: string
    full_code: string
    return_pct: string
    hold_days: string
  }[]
  created_at: string
  updated_at: string
}

export interface LabelBatchListItem {
  id: string
  period: string
  market_filter: string | null
  batch_size: number
  status: string
  created_at: string
  completed_at: string | null
  completed_count: number
  skipped_count: number
  pair_count: number
  profile_draft: string | null
}

export async function listLabelBatches(params?: { limit?: number; offset?: number }) {
  return get<LabelBatchListItem[]>('/labels/batches', params as Record<string, unknown> | undefined)
}

export async function getBatchSummary(batchId: string) {
  return get<LabelBatchSummary>(`/labels/batches/${batchId}/summary`)
}

export async function patchBatchSummary(batchId: string, userCorrections: string[]) {
  return patch<LabelBatchSummary>(`/labels/batches/${batchId}/summary`, {
    user_corrections: userCorrections,
  })
}
