# API 设计规范

本规范适用于 `apps/api` 对外暴露的所有 REST 接口。目标读者是后端、小程序端、QA 与文档维护者。

## 1. 总体风格

- **REST + JSON**：资源导向、动词使用 HTTP 方法，路径使用复数名词。
- **HTTPS only**：生产强制 TLS，HTTP 直接 301 到 HTTPS。
- **JSON 编码**：UTF-8，字段使用 `snake_case`，禁止驼峰。
- **时间格式**：所有时间字段 ISO 8601，带时区（`2026-05-13T08:30:00Z`），服务端发出强制 UTC。
- **金额与数量**：必须用字符串或定点数（避免浮点精度问题），整数字段用 `int64`。
- **可空字段**：null 表示"不存在"，缺省/空串不等同于 null，避免歧义。

## 2. 路径与版本

- 基础路径：`/api/v1/...`。
- 大版本切换：`/api/v2/...`，并通过废弃公告 + 双轨期管理。
- 资源层级两层封顶，避免 `/a/b/c/d` 深嵌套。
- 集合用复数：`/strategies`、`/backtests`、`/replays`。
- 子资源用从属：`/strategies/{strategy_id}/versions`。
- 动作类操作用动词后缀但保持名词资源根：`POST /backtests/{id}:cancel`（采用 Google API 风格 ":action"）。

## 3. 鉴权

- 微信小程序通过 `code2session` 换取 openid → 服务端签发 JWT（短 access token + 长 refresh token）。
- 请求头：`Authorization: Bearer <access_token>`。
- 刷新：`POST /api/v1/auth/refresh`，使用 refresh token；access token 不可用作刷新。
- 退出：`POST /api/v1/auth/logout`，服务端吊销该 refresh token；access token 仍有效到过期。
- 鉴权失败：401，含错误码 `AUTH_REQUIRED` / `AUTH_EXPIRED` / `AUTH_INVALID`。
- 权限不足：403，含 `PERMISSION_DENIED`，禁止泄露资源是否存在。

详见 [SECURITY_AND_COMPLIANCE.md](SECURITY_AND_COMPLIANCE.md)。

## 4. 请求规范

- 查询：`GET`，参数走 query string；复杂筛选用 `POST /resource:search` 接受 JSON body。
- 创建：`POST /resource`，返回 201 + Location。
- 全量更新：`PUT /resource/{id}`，幂等。
- 部分更新：`PATCH /resource/{id}`，请求体为 JSON Merge Patch。
- 删除：`DELETE /resource/{id}`，软删除返回 204。
- 批量：`POST /resource:batch-create`，必须返回每项的结果状态。

### 4.1 通用 Header

| Header | 必选 | 说明 |
| --- | --- | --- |
| `Authorization` | 是（除登录类）| Bearer token |
| `X-Request-Id` | 否 | 客户端生成的请求 ID；服务端未收到则补全 |
| `X-Client-Version` | 是 | 小程序版本，便于灰度与统计 |
| `X-Idempotency-Key` | 关键写接口必选 | 幂等保证 |
| `Accept-Language` | 否 | 多语言预留 |

### 4.2 请求体规范

- 所有写接口必须用 Pydantic 模型严格校验。
- 拒绝多余字段（`extra='forbid'`），避免静默丢字段。
- 数组字段必须有显式上限（如 `marks` 单批 ≤ 200）。
- JSONB 字段（如 DSL）必须显式声明 schema 与版本。

## 5. 响应规范

### 5.1 成功响应

```text
HTTP 200 / 201 / 204
Content-Type: application/json; charset=utf-8

{
  "data": { ... },
  "meta": { ... }       // 可选
}
```

- 单资源：`data` 为对象。
- 列表资源：`data` 为数组，`meta` 含分页游标。
- 不在顶层放业务字段，避免后期增加 `data/meta` 包裹时破坏兼容性。

### 5.2 错误响应

```text
HTTP 4xx / 5xx
Content-Type: application/json

{
  "error": {
    "code": "STRATEGY_NOT_FOUND",
    "message": "策略不存在",
    "details": { "strategy_id": "..." },
    "request_id": "..."
  }
}
```

- `code` 全大写下划线，业务唯一。
- `message` 面向终端用户，避免泄露内部实现。
- `details` 仅在非生产或对内接口提供详细上下文；生产对外接口可裁剪。
- 404 与 403 的语义严格区分；对未授权访问已存在资源默认按 404 返回避免枚举。

### 5.3 状态码使用

| 状态码 | 用途 |
| --- | --- |
| 200 | 成功，含响应体 |
| 201 | 创建成功 |
| 202 | 异步任务已接收（含 `task_id`） |
| 204 | 成功且无响应体 |
| 400 | 参数错误、Schema 校验失败 |
| 401 | 未鉴权 / token 失效 |
| 403 | 鉴权通过但无权限 |
| 404 | 资源不存在（或对该用户不可见）|
| 409 | 冲突（幂等键复用、状态机非法跃迁）|
| 422 | 业务规则不通过（比如 DSL 校验失败）|
| 429 | 限流 |
| 500 | 未预期服务端错误（请勿在生产泄露堆栈）|
| 503 | 系统降级 / 维护中 |

## 6. 分页

- 默认 keyset 分页：`?limit=50&cursor=<opaque>`。
- 响应 `meta.next_cursor` 为下一页游标；末页返回 null。
- 严禁 OFFSET 分页用于大表。
- 单页 `limit` 最大 100，默认 20。

## 7. 幂等

写类接口要求：

- 所有创建/触发任务接口必须支持 `X-Idempotency-Key`。
- 服务端使用 `(user_id, endpoint, idempotency_key)` 做唯一约束。
- 重复请求返回上一次成功的结果（包含 200/201 与响应体）。
- 幂等键 TTL ≥ 24 小时。

## 8. 资源命名映射

业务模块到接口的命名映射（节选，完整契约见 `docs/api/openapi.yaml`）：

| 模块 | 资源 | 典型路径 |
| --- | --- | --- |
| 鉴权 | session | `POST /auth/wechat-login`、`POST /auth/refresh`、`POST /auth/logout` |
| 用户 | user | `GET /me`、`PATCH /me/profile` |
| 标的 | symbol | `GET /symbols`、`GET /symbols/{code}` |
| K 线 | bar | `GET /symbols/{code}/bars?period=day&from=...&to=...` |
| 标注会话 | label_session | `POST /labels/sessions`、`POST /labels/sessions/{id}:submit` |
| 标注点 | label_point | `POST /labels/sessions/{id}/marks:batch-create` |
| 策略 | strategy | `POST /strategies/from-labels`、`GET /strategies`、`GET /strategies/{id}` |
| 策略版本 | strategy_version | `GET /strategies/{id}/versions`、`POST /strategies/{id}/versions` |
| 回测 | backtest | `POST /backtests`、`GET /backtests/{id}` |
| 盲测会话 | replay_session | `POST /replays/sessions`、`POST /replays/sessions/{id}:step` |
| 盲测操作 | replay_event | `POST /replays/sessions/{id}/actions` |
| 诊断 | diagnosis | `GET /diagnoses/{id}`、`GET /replays/sessions/{id}/diagnosis` |
| 训练 | training | `POST /trainings`、`GET /trainings/{id}` |
| AI 对话 | ai_conversation | `POST /ai/conversations`、`POST /ai/conversations/{id}/messages` |
| 预警（V0.6） | alert_rule | `POST /alerts/rules`、`GET /alerts/rules` |

## 9. 异步任务接口约定

- 重任务接口 `POST /resource` 返回 202 + `task_id` + 状态查询 URL：

```json
{
  "data": {
    "task_id": "01HV...ULID",
    "status": "queued",
    "status_url": "/api/v1/backtests/01HV...ULID"
  }
}
```

- 客户端通过状态 URL 轮询；状态机 `queued -> running -> succeeded | failed | cancelled`。
- 成功后状态 URL 同时返回结果摘要 + 明细 URL。
- 不建议在 MVP 引入 WebSocket / SSE 通知；轮询足够。

## 10. 限流

- 默认匿名 60 RPM / IP；登录用户 300 RPM / user。
- 重接口（回测提交、AI 对话）按 user + endpoint 单独限：例如 AI 对话 10 RPM / user。
- 限流响应 429，含 `Retry-After` 秒数。
- 限流命中必须记录 metric，便于反查恶意行为或前端 BUG。

## 11. 错误码规范

错误码命名规则：`<DOMAIN>_<REASON>`。示例：

| Code | HTTP | 含义 |
| --- | --- | --- |
| `AUTH_REQUIRED` | 401 | 未携带 token |
| `AUTH_EXPIRED` | 401 | token 已过期 |
| `AUTH_INVALID` | 401 | token 校验失败 |
| `PERMISSION_DENIED` | 403 | 已鉴权但无权限 |
| `RESOURCE_NOT_FOUND` | 404 | 通用兜底 |
| `STRATEGY_DSL_INVALID` | 422 | DSL Schema 校验失败 |
| `BACKTEST_PARAMS_INVALID` | 422 | 回测参数非法 |
| `BACKTEST_QUOTA_EXCEEDED` | 429 | 用户回测次数超限 |
| `REPLAY_SESSION_FINISHED` | 409 | 已结束的盲测无法再操作 |
| `REPLAY_INVALID_STEP` | 409 | 推进越界或重复推进 |
| `AI_PROVIDER_UNAVAILABLE` | 503 | 大模型不可用，已降级 |
| `RATE_LIMITED` | 429 | 触发限流 |
| `INTERNAL_ERROR` | 500 | 未分类异常 |

业务错误码维护在 `packages/domain/src/errors.py`，所有服务复用。

## 12. OpenAPI 与契约管理

- FastAPI 自动生成 OpenAPI；CI 把 `openapi.json` 导出到 `docs/api/openapi.yaml`。
- 小程序端通过 OpenAPI 生成 TypeScript 类型，避免手写。
- 接口变更必须在 PR 中包含 OpenAPI diff，CI 检测破坏性变更（删字段、改类型、删端点）必须有 ADR 或显式版本切换。
- 重要接口提供 `examples`：request、response、error。

## 13. 命名约定速查

| 类型 | 约定 |
| --- | --- |
| URL | 小写、连字符；`/replay-sessions` 而非 `/replaySessions` |
| 资源 ID | 字段名 `<resource>_id`，值 ULID/UUIDv7 |
| 布尔字段 | `is_*` / `has_*` / `can_*` |
| 枚举 | `snake_case` 字符串 |
| 时间 | `*_at` 后缀；区间 `*_from` / `*_to` |
| 分页 | `limit` + `cursor` + `next_cursor` |
| 排序 | `sort=created_at:desc`，禁止任意字段排序，需白名单 |

## 14. 兼容性约束

- 向前兼容（小程序老版本 + 后端新版本）必须成立：新增字段为可选，删除字段需要先标记 deprecated 一个发布窗口。
- 向后兼容（小程序新版本 + 后端老版本）尽量成立：小程序对未知字段应忽略，对缺失字段使用合理默认。
- 服务端发布灰度期间禁止破坏性变更。

## 15. 反例（禁止）

- ❌ 在 GET 接口里做有副作用的操作。
- ❌ 用 200 + `error` 字段表达失败状态。
- ❌ 接口同时返回多种 schema（联合类型未标记 `kind` 字段）。
- ❌ 把内部 DB 错误 / 堆栈直接 JSON 返回。
- ❌ 在路径里塞动词：`/createStrategy`、`/getBacktestById`。
- ❌ 未鉴权接口暴露用户 ID 枚举可能。
- ❌ AI 类接口直接接受"执行交易"指令。
