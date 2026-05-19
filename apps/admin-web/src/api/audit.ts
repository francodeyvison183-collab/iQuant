import { get } from './client'

export interface AuditLogRow {
  id: number
  admin_user_id: number | null
  username: string | null
  action: string
  resource_type: string
  resource_id: string
  method: string
  path: string
  status_code: number
  ip: string
  user_agent: string
  request_id: string
  detail: Record<string, unknown>
  created_at: string
}

export const listAuditLogs = (params?: {
  action?: string
  path_contains?: string
  admin_user_id?: number
  days?: number
  limit?: number
  offset?: number
}) => get<AuditLogRow[]>('/admin/audit-logs', params)
