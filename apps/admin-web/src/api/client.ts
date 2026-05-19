import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { extractApiError } from './errors'
import { reportClientError } from '@/logging/clientError'

export interface ApiEnvelope<T = unknown> {
  code: number
  data: T
  message?: string
  total?: number
}

export interface ApiErrorBody {
  error?: { code?: string; message?: string }
  detail?: string
}

export const http: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

let refreshPromise: Promise<string | null> | null = null

function getAuthStore() {
  // 延迟加载避免循环依赖
  return import('@/stores/auth').then((m) => m.useAuthStore())
}

http.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const url = config.url || ''
  if (url.includes('/admin/auth/login') || url.includes('/admin/auth/refresh') || url.includes('/admin/auth/config')) {
    return config
  }
  const store = await getAuthStore()
  if (store.accessToken) {
    config.headers.Authorization = `Bearer ${store.accessToken}`
  }
  return config
})

http.interceptors.response.use(
  (resp) => resp,
  async (err) => {
    const config = err.config as InternalAxiosRequestConfig & { __retryCount?: number; __authRetried?: boolean }
    const status = err?.response?.status
    const body = err?.response?.data as ApiErrorBody | undefined
    const code = body?.error?.code

    if (status === 401 && config && !config.__authRetried && !config.url?.includes('/admin/auth/')) {
      config.__authRetried = true
      const store = await getAuthStore()
      if (store.refreshToken) {
        try {
          if (!refreshPromise) {
            refreshPromise = store
              .refresh()
              .then(() => store.accessToken)
              .finally(() => {
                refreshPromise = null
              })
          }
          const token = await refreshPromise
          if (token) {
            config.headers.Authorization = `Bearer ${token}`
            return http(config)
          }
        } catch {
          await store.logout()
          if (!window.location.pathname.startsWith('/login')) {
            window.location.href = '/login'
          }
          return Promise.reject(err)
        }
      }
    }

    if (status === 503 && config && !config.__retryCount) {
      config.__retryCount = 0
    }
    if (status === 503 && config && (config.__retryCount ?? 0) < 3) {
      config.__retryCount = (config.__retryCount ?? 0) + 1
      const delay = 1000 * 2 ** (config.__retryCount - 1)
      await new Promise((resolve) => setTimeout(resolve, delay))
      return http(config)
    }

    if (status === 401 && code === 'AUTH_REQUIRED') {
      const store = await getAuthStore()
      await store.logout()
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }

    const detail = extractApiError(err)
    const reqUrl = config?.url || ''
    if (!reqUrl.includes('/client-errors')) {
      if (status != null && status >= 500) {
        reportClientError({
          message: `HTTP ${status}: ${detail}`,
          stack: typeof body === 'object' && body != null ? JSON.stringify(body).slice(0, 4000) : '',
          source: 'axios:response',
        })
      } else if (!status && (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error')) {
        reportClientError({
          message: detail || String(err?.message || 'network_error'),
          source: 'axios:network',
        })
      }
    }
    const isLogin = Boolean(config?.url?.includes('/admin/auth/login'))
    // 登录页自行展示错误，避免重复弹窗
    if (!isLogin) {
      ElMessage.error(detail)
    }
    return Promise.reject(err)
  },
)

export async function get<T>(url: string, params?: Record<string, unknown>) {
  const r = await http.get<ApiEnvelope<T>>(url, { params })
  return r.data
}

export async function post<T>(
  url: string,
  body?: unknown,
  headers?: Record<string, string>,
) {
  const r = await http.post<ApiEnvelope<T>>(url, body, { headers })
  return r.data
}

export async function put<T>(
  url: string,
  body?: unknown,
  headers?: Record<string, string>,
) {
  const r = await http.put<ApiEnvelope<T>>(url, body, { headers })
  return r.data
}

export async function patch<T>(url: string, body?: unknown) {
  const r = await http.patch<ApiEnvelope<T>>(url, body)
  return r.data
}

export async function del<T>(url: string, headers?: Record<string, string>) {
  const r = await http.delete<ApiEnvelope<T>>(url, { headers })
  return r.data
}
