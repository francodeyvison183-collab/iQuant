import { del, get, http, post } from './client'

export interface TdxHost {
  id?: number
  is_builtin?: boolean
  ip: string
  port: number
  name: string
  status: 'untested' | 'ok' | 'fail'
  speed_ms: number
  last_tested: string | null
  fail_since: string | null
}

export interface ImportTask {
  task_id: string
  task_type: 'incremental' | 'full' | 'online_fetch' | 'online_batch'
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  params: Record<string, unknown>
  total_files: number
  done_files: number
  imported_bars: number
  error_count: number
  error_message: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string | null
}

export interface ScanPreview {
  data_dir: string
  total_files: number
  by_period: Record<string, number>
  by_market: Record<string, Record<string, number>>
  changed_files: number
  unchanged_files: number
}

export interface SymbolItem {
  full_code: string
  code: string
  market: string
  name: string
  asset_type: string
  list_date: string | null
}

export interface BarPoint {
  bar_time: string
  open: string
  high: string
  low: string
  close: string
  volume: number
  amount: string
}

export interface BarQueryResult {
  full_code: string
  period: string
  bars: BarPoint[]
}

export interface SymbolCoverage {
  full_code: string
  period: string
  first_bar_time: string | null
  last_bar_time: string | null
  bar_count: number
}

// ── 主站 ─────────────────────────────────────────────────────────────────────
export const listHosts = () => get<TdxHost[]>('/admin/market/hosts')
export const addHost = (payload: { ip: string; port: number; name?: string }) =>
  post<TdxHost>('/admin/market/hosts', payload)
export const removeHostById = (id: number) => del<null>(`/admin/market/hosts/${id}`)
export const testAllHosts = () => post<TdxHost[]>('/admin/market/hosts/test')

export interface HostsImportResult {
  parsed: number
  kept: number
  added: number
  total: number
  hosts: TdxHost[]
}

export async function importHostsCfg(
  file: File,
  opts: { only_quote_ports?: boolean; run_test?: boolean } = {},
): Promise<HostsImportResult> {
  const fd = new FormData()
  fd.append('file', file)
  const r = await http.post('/admin/market/hosts/import-cfg', fd, {
    params: {
      only_quote_ports: opts.only_quote_ports ?? true,
      run_test: opts.run_test ?? true,
    },
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return r.data.data as HostsImportResult
}

// ── 扫描 / 导入 ──────────────────────────────────────────────────────────────
export const scanPreview = (vipdoc_dir?: string, markets?: string[]) =>
  post<ScanPreview>('/admin/market/scan/preview', { vipdoc_dir, markets })

export async function uploadVipdoc(uploadId: string, files: File[], paths: string[]) {
  const fd = new FormData()
  fd.append('upload_id', uploadId)
  fd.append('file_paths', JSON.stringify(paths))
  for (const f of files) {
    fd.append('files', f)
  }
  const r = await http.post<{ data: { vipdoc_dir: string } }>('/admin/market/upload-vipdoc', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return r.data
}

export const createImportTask = (payload: {
  task_type: 'incremental' | 'full'
  vipdoc_dir?: string
  markets?: string[]
}) => post<{ task_id: string; status: string }>('/admin/market/import-tasks', payload)

export const listImportTasks = (params?: {
  status?: string
  limit?: number
  offset?: number
}) => get<ImportTask[]>('/admin/market/import-tasks', params)

export const getImportTask = (taskId: string) =>
  get<ImportTask>(`/admin/market/import-tasks/${taskId}`)

export const taskProgressUrl = (taskId: string) =>
  `/api/v1/admin/market/import-tasks/${taskId}/progress`

export const retryImportTask = (taskId: string) =>
  post<{ message: string }>(`/admin/market/import-tasks/${taskId}/retry`)

// ── 在线补数 ─────────────────────────────────────────────────────────────────
export const onlineFetch = (payload: {
  full_code: string
  period: string
  max_count?: number
}) => post<{ inserted: number }>('/admin/market/online/fetch', payload)

export const createOnlineBatchTask = (payload: {
  markets?: string[]
  codes?: string[]
  periods: string[]
  start_date: string
  end_date?: string | null
}) => post<{ task_id: string; status: string }>('/admin/market/online/batch', payload)

// ── 数据查看 ─────────────────────────────────────────────────────────────────
export const listSymbols = (params?: {
  market?: string
  keyword?: string
  limit?: number
  offset?: number
}) => get<SymbolItem[]>('/admin/market/symbols', params)

export const queryBars = (params: {
  full_code: string
  period: string
  start?: string
  end?: string
  limit?: number
}) => get<BarQueryResult>('/admin/market/bars', params)

export const getCoverage = (params: { full_code: string; period: string }) =>
  get<SymbolCoverage>('/admin/market/coverage', params)
