/** 将管理端运行时错误上报 API，由服务端写入 JSONL 错误日志。 */

const MAX_BODY = 50_000

export function reportClientError(payload: {
  message: string
  stack?: string
  source?: string
}): void {
  const body = {
    message: payload.message.slice(0, 8000),
    stack: (payload.stack ?? '').slice(0, 48_000),
    source: (payload.source ?? '').slice(0, 512),
  }
  const json = JSON.stringify(body)
  if (json.length > MAX_BODY) {
    return
  }
  void fetch('/api/v1/client-errors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: json,
  }).catch(() => {})
}
