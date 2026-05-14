import axios from 'axios'
import type { AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'

export interface ApiEnvelope<T = unknown> {
  code: number
  data: T
  message?: string
  total?: number
}

export const http: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

http.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const detail = err?.response?.data?.error?.message
      || err?.response?.data?.detail
      || err?.message
      || '请求失败'
    ElMessage.error(detail)
    return Promise.reject(err)
  },
)

export async function get<T>(url: string, params?: Record<string, unknown>) {
  const r = await http.get<ApiEnvelope<T>>(url, { params })
  return r.data
}

export async function post<T>(url: string, body?: unknown) {
  const r = await http.post<ApiEnvelope<T>>(url, body)
  return r.data
}

export async function del<T>(url: string) {
  const r = await http.delete<ApiEnvelope<T>>(url)
  return r.data
}
