# 可观测性

本文定义 iQuant 服务端的日志、指标、追踪、告警与排障路径。目标是：

- 任何线上问题在 5 分钟内能定位到模块。
- 任何业务异常（任务失败、AI 降级、用户越权尝试）都可量化、可告警。
- 任何用户反馈都能在系统里复现链路。

## 1. 三大支柱

| 支柱 | 选型 | 主要用途 |
| --- | --- | --- |
| 日志（Logs） | structlog（结构化 JSON）+ Loki + Grafana | 详细上下文、错误堆栈、审计 |
| 指标（Metrics） | Prometheus + Grafana | 速率、延迟、错误率、资源使用 |
| 追踪（Traces） | OpenTelemetry SDK + Tempo / Jaeger | 单请求跨服务链路 |

补充：

- Sentry：错误聚合、版本追踪、用户上下文。
- Flower：Celery 任务实时视图（仅运维侧）。

## 2. 日志规范

### 2.1 格式

- 一律 JSON 单行，字段固定：

```json
{
  "ts": "2026-05-13T09:00:00.123Z",
  "level": "INFO",
  "logger": "services.backtest.usecases",
  "msg": "backtest started",
  "service": "api",
  "version": "1.4.2",
  "request_id": "01HV...",
  "trace_id": "...",
  "span_id": "...",
  "user_id_hashed": "ab12...",
  "context": { "task_id": "...", "strategy_version_id": "..." }
}
```

- `user_id` 不直接打印，使用 `user_id_hashed = sha256(user_id)[:16]`。
- `request_id` 中间件强制注入；缺失时生成 ULID。
- `trace_id` / `span_id` 由 OpenTelemetry 注入。

### 2.2 日志级别

| 级别 | 用途 |
| --- | --- |
| DEBUG | 开发期细节，生产关闭 |
| INFO | 主流程、入口、出口、关键状态变化 |
| WARNING | 可恢复异常、降级、重试 |
| ERROR | 未捕获异常、业务必失败、外部依赖失败 |
| CRITICAL | 服务不可用、数据可能损坏 |

约束：

- 单接口正常路径产生的 INFO 日志条数 ≤ 5。
- 禁止在循环里打日志（必要时做采样）。
- ERROR 必须附 traceback；WARNING 不必。

### 2.3 上下文绑定

使用 `structlog.contextvars` 绑定请求级上下文，自动透传到所有日志：

```python
async def auth_middleware(request, call_next):
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request.headers.get("x-request-id", new_ulid()),
        path=request.url.path,
        method=request.method,
    )
    response = await call_next(request)
    return response
```

### 2.4 采集与查询

- stdout 直输 JSON → 容器日志驱动 → Loki。
- Loki 索引仅基于 label（service、env、level），全文搜索用 query。
- 保留：热存 14 天，冷存 90 天。

## 3. 指标规范

### 3.1 指标命名

- 命名空间：`iquant_<domain>_<measure>_<unit>`。
- 单位后缀：`_seconds` / `_bytes` / `_total`。
- 例：`iquant_api_request_duration_seconds`、`iquant_celery_task_duration_seconds`、`iquant_backtest_runs_total`。

### 3.2 标签

- 标签维度尽量低（< 10 万 series/metric）。
- 不允许把 user_id、strategy_id、task_id 作为标签（基数爆炸）。
- 推荐标签：`service`、`env`、`endpoint`、`method`、`status_class`（2xx/4xx/5xx）、`task_name`、`queue`、`outcome`。

### 3.3 核心指标清单

#### API

```text
iquant_api_request_duration_seconds_bucket{endpoint, method, status_class}
iquant_api_request_total{endpoint, method, status_class}
iquant_api_inflight_requests{endpoint}
iquant_api_request_size_bytes
iquant_api_response_size_bytes
```

#### Celery

```text
iquant_celery_task_duration_seconds_bucket{task_name, queue, outcome}
iquant_celery_task_total{task_name, queue, outcome}
iquant_celery_task_retries_total{task_name}
iquant_celery_queue_pending{queue}
iquant_celery_worker_concurrency{queue}
```

#### 业务

```text
iquant_strategy_generation_total{outcome}
iquant_backtest_runs_total{outcome}
iquant_backtest_duration_seconds_bucket
iquant_diagnosis_runs_total{outcome}
iquant_ai_calls_total{provider, outcome}
iquant_ai_tokens_in_total / iquant_ai_tokens_out_total{provider, model}
iquant_replay_sessions_started_total
iquant_replay_events_total{kind}
iquant_moderation_flags_total{source, severity}
```

#### 基础设施

```text
iquant_db_pool_in_use{pool}
iquant_db_query_duration_seconds_bucket{op}
iquant_redis_command_duration_seconds_bucket{cmd}
iquant_cache_hits_total{prefix}
iquant_cache_misses_total{prefix}
```

### 3.4 采集

- FastAPI：自定义中间件填充 Prometheus 指标。
- SQLAlchemy：事件监听器统计查询。
- Celery：Prometheus exporter + 自定义 signal hook。
- httpx：拦截器统计外部依赖。
- Redis 客户端：连接池与命令计时。
- 主机/容器：node_exporter、cAdvisor / kube-state-metrics。

## 4. 追踪规范

### 4.1 覆盖范围

OpenTelemetry SDK 自动注入：

- FastAPI 入口（每个 request 一个 root span）。
- SQLAlchemy 查询、Redis 命令、httpx 调用作为子 span。
- Celery 任务作为新 root span，trace_id 通过任务 headers 透传。
- AI 调用、对象存储调用作为子 span（手动 instrument）。

### 4.2 字段

- `trace_id` / `span_id` 自动。
- 推荐属性：`iquant.user_id_hashed`、`iquant.task_name`、`iquant.strategy_id`（仅 trace，不进 metric label）。
- 错误：`status=error`，附 `exception.type / message / stacktrace`。

### 4.3 采样

- 默认 10% 头采样。
- 错误请求 100% 采样。
- 慢请求（> 1s）100% 采样。
- 关键业务路径（回测、诊断）100% 采样。

## 5. 错误聚合（Sentry）

- 所有未捕获异常自动上报。
- 标签：`env`、`service`、`version`、`user_id_hashed`。
- PII 过滤：禁止上报原始 token、openid、明文请求体。
- 关联：Sentry 事件挂上 `trace_id`，可一键跳到 Tempo/Jaeger。

## 6. 告警

### 6.1 分级

| 级别 | 响应 | 渠道 |
| --- | --- | --- |
| P0 | 立即响应（< 10 分钟） | 电话 + 短信 + 飞书 oncall |
| P1 | 30 分钟内响应 | 短信 + 飞书 oncall |
| P2 | 1 小时内响应 | 飞书 oncall |
| P3 | 工作日处理 | 飞书 channel |

### 6.2 告警清单（节选）

| 告警 | 条件 | 级别 |
| --- | --- | --- |
| API 错误率高 | 5 分钟 5xx > 2% | P1 |
| API P95 延迟高 | 5 分钟 P95 > 1s | P2 |
| Celery 队列堆积 | pending > 1000 持续 5 分钟 | P1 |
| Celery 任务失败率高 | 10 分钟失败率 > 5% | P1 |
| 回测任务长尾 | P95 > 60s | P2 |
| DB 连接池打满 | in_use / total > 90% 持续 5 分钟 | P1 |
| DB 主库不可用 | 健康检查失败 | P0 |
| Redis 内存使用高 | > 80% | P2 |
| Redis 不可用 | 健康检查失败 | P0 |
| 外部依赖（行情）失败 | 错误率 > 10% | P1 |
| AI 供应商失败 | 错误率 > 20% | P2（降级模板，不阻塞业务） |
| 大量鉴权失败 | 5 分钟 401 > 1000 | P2（可能撞库） |
| 越权尝试 | 1 分钟 403 > 50 / IP | P2 |
| 用户回测配额异常 | 1 分钟某 user 提交 > 50 | P3 |
| 内容审核违规暴涨 | 10 分钟 flagged > 100 | P2 |

### 6.3 抑制与去重

- 同一告警 30 分钟内只通知 1 次。
- 上游故障（DB 主库不可用）期间，子告警（API 错误率高）自动抑制。
- 每个告警必须关联 Runbook 链接，否则禁止上线。

## 7. SLO 与错误预算

| SLI | SLO | 错误预算（30 天） |
| --- | --- | --- |
| API 可用性（2xx + 3xx 占比） | 99.5% | 0.5% ≈ 3.6 小时 |
| API P95 延迟 ≤ 500ms | 95% 时间满足 | - |
| 回测任务成功率 | 99% | 1% |
| AI 调用成功率（含降级） | 99% | 1% |

错误预算耗尽：

- 暂停非紧急发布。
- 召集稳定性专题复盘。
- 列入下一阶段改进项。

## 8. 健康检查

- `/healthz`：进程存活（不访问外部依赖）。
- `/readyz`：依赖（DB、Redis）连通 + 关键迁移已应用。
- K8s liveness 探针：`/healthz`。
- K8s readiness 探针：`/readyz`。
- Worker：使用 Celery `ping` + 进程探针双重检测。

## 9. 业务大盘

Grafana 至少维护以下 dashboard：

- 总览：可用性、QPS、延迟、错误率、活跃用户。
- API 详情：按 endpoint 拆分。
- Celery 详情：按 queue / task_name 拆分。
- DB / Redis / 缓存：连接池、慢查询、命中率。
- 业务关键漏斗：标注完成率、策略生成转化率、回测完成率、盲测完成率、训练完成率。
- AI 大盘：调用量、token 消耗、降级率、违规率。
- 风险大盘：鉴权失败、越权、限流、内容审核。

dashboard 与告警共用 PromQL，避免"看一套用一套"。

## 10. 排障路径示例

### 10.1 用户反馈"回测一直转圈"

1. 用 `request_id` 或 `user_id_hashed` 在 Loki 检索最近的请求日志。
2. 找到 `task_id`，在 Sentry / Tempo 查任务 trace。
3. 查看 `iquant_celery_queue_pending{queue="backtest"}`：是否堆积。
4. 查看任务 outcome：是否失败、失败原因。
5. 根据 error_code 跳转对应 Runbook。

### 10.2 用户反馈"AI 回复变成模板了"

1. 在 Sentry / Loki 检索该用户最近的 AI 调用。
2. 查看 `iquant_ai_calls_total{provider, outcome="fallback"}`。
3. 判断是供应商抖动还是审核命中。
4. 如供应商问题：观察故障切换是否生效；不生效则手动切换。

### 10.3 大盘指标突然异常

1. 看时间点对应的发布事件（Grafana 中标注 release annotation）。
2. 关联日志暴涨的 logger、Sentry 新错误聚类。
3. 必要时回滚版本，事后复盘。

## 11. 数据保留

| 数据 | 热存 | 冷存 |
| --- | --- | --- |
| 日志 | 14 天 | 90 天 |
| 指标 | 15 天高分辨率 + 1 年降采样 | - |
| 追踪 | 7 天 | - |
| Sentry 事件 | 30 天 | - |
| 审计日志 | 180 天 | 3 年 |

## 12. 反例

- ❌ 把日志当指标用（`grep` 出 QPS）。
- ❌ 把指标当审计用（缺乏明细可追溯性）。
- ❌ 把 user_id 作为 Prometheus 标签。
- ❌ 把原始用户输入写到日志或 Sentry 上下文。
- ❌ 告警全配置 P0，每个告警都是噪声。
- ❌ 没有 Runbook 的告警上线。
- ❌ 测试与生产共享同一 Sentry 项目导致信号污染。
