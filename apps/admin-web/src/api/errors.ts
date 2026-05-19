import type { AxiosError } from 'axios'
import type { ApiErrorBody } from './client'

/** 从 axios 错误中提取用户可读文案。 */
export function extractApiError(err: unknown): string {
  if (!err || typeof err !== 'object') {
    return '请求失败'
  }
  const ax = err as AxiosError<ApiErrorBody>
  const body = ax.response?.data
  if (body?.error?.message) {
    return body.error.message
  }
  if (typeof body?.detail === 'string') {
    return body.detail
  }
  if (ax.code === 'ECONNABORTED') {
    return '请求超时，请确认 API 服务已启动（docker compose up）'
  }
  if (!ax.response) {
    return '无法连接服务器，请检查网络或 API 代理配置'
  }
  const status = ax.response?.status
  if (status === 503) {
    return body?.error?.message || '服务暂不可用，请稍后重试（检查 Redis / API 容器）'
  }
  if (status != null && status >= 500) {
    return body?.error?.message || '服务内部错误，请稍后重试或查看 logs/iquant-api-errors.log'
  }
  if (ax.message?.includes('status code 500')) {
    return body?.error?.message || '服务内部错误，请确认 API 容器已就绪后重试'
  }
  return ax.message || '请求失败'
}
