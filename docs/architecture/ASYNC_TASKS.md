# 异步任务与消息队列

本文定义 iQuant 后台任务系统的设计：任务分类、队列拓扑、幂等与重试、调度与监控。

## 1. 为什么需要异步

以下场景必须异步：

- 回测：策略 × 区间 × 周期可能耗时几秒到几十秒，Web 进程不能挂起。
- 执行偏差诊断：需要重放策略信号、对齐用户操作、计算指标，耗时较大。
- AI 调用：依赖外部模型，延迟波动大，超时风险高。
- 报告渲染：诊断报告、训练对比图等需要拼装数据并落对象存储。
- 行情拉取：定时增量同步，可能涉及多家供应商。
- 数据清理：过期 AI 对话、临时缓存、孤儿对象存储清理。

API 进程严禁同步执行上述任务。

## 2. 框架与组件

- 任务框架：Celery 5.x
- Broker：Redis（MVP）；只有队列成为明确瓶颈后才迁移 RabbitMQ
- Result backend：Redis（短期态） + PostgreSQL（长期落库）
- 调度器：Celery Beat
- 监控：Flower + Prometheus exporter + 业务自定义 dashboard

选型理由：[ADR-0007](../decisions/ADR-0007-celery-for-async-tasks.md)。

## 3. 队列拓扑

MVP 阶段只保留少量队列，避免运维复杂度过高。按"任务画像"隔离即可，后续按瓶颈再拆细。

| 队列名 | 画像 | Worker 池 | 并发 | 说明 |
| --- | --- | --- | --- | --- |
| `default` | 轻任务 | prefork | 4 ~ 8 | 报告快照、清理、小任务 |
| `cpu` | CPU 中/高 | prefork | 2 ~ 4 | 策略生成、回测、诊断 |
| `io` | I/O 密集 | gevent / asyncio | 20 ~ 50 | AI 调用、行情拉取、对象存储 |

MVP Worker 部署建议：

- 常态 2 个 Worker 容器：1 个偏 `cpu`，1 个偏 `io/default`。
- 高峰扩到 4 个 Worker：2 个 `cpu`，1 个 `io`，1 个 `default`。
- 当某类任务持续挤占队列，再拆为 `backtest`、`diagnosis`、`ai` 等专用队列。

## 4. 任务命名与契约

- 命名：`<service>.<action>`，例如 `backtest.run`、`diagnosis.compute`、`ai.explain_strategy`。
- 入参：必须是可序列化的简单结构（dict / 主键 ID / Pydantic model dump），禁止传 ORM 对象。
- 返回：建议返回 `{"status": "ok", "result_ref": "..."}` 结构，明细落数据库或对象存储后用 ID 引用。
- Schema 演进：任务参数视为 API 契约，破坏性变更走双版本兼容。

## 5. 幂等

所有写入数据库或外部副作用的任务必须幂等。

### 5.1 实现方式

- 业务侧生成 `idempotency_key`（如回测任务 ID、诊断任务 ID）。
- 任务入口先用 `SELECT ... FOR UPDATE SKIP LOCKED` 或 Redis `SETNX` 抢占。
- 若已存在结果直接返回；若处于"运行中"直接放弃当前重试。
- 写结果时使用 `INSERT ... ON CONFLICT DO NOTHING` 或带版本号的 CAS 更新。

### 5.2 幂等粒度

| 任务 | 幂等键 |
| --- | --- |
| 回测 | `backtest_task.id`（即 Celery task_id） |
| 诊断 | `diagnosis_task.id`，由 `replay_session_id` 派生 |
| AI 解释 | `(conversation_id, message_id)` |
| 报告渲染 | `(report_kind, report_id, version)` |
| 行情拉取 | `(symbol_id, period, day)` |

## 6. 重试策略

- 默认：指数退避，初始 5s，最大 5 分钟，最大重试 5 次。
- 不可恢复错误（参数非法、资源不存在、被取消）：禁止重试，标记 `failed`。
- 外部依赖错误（HTTP 5xx、超时）：可重试。
- AI 任务：超时优先降级（返回模板文案）而非无限重试。
- 任务每次重试必须打 metric，便于发现"全靠重试才成功"的隐性故障。

任务示意：

```python
@app.task(
    name="backtest.run",
    bind=True,
    autoretry_for=(TransientError,),
    retry_backoff=5,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_backtest(self, task_id: str) -> dict:
    ...
```

`acks_late=True` 确保 worker 崩溃时任务能被另一 worker 重投。

## 7. 任务可见性与超时

- 单任务硬超时：

  | 队列 | hard timeout | soft timeout |
  | --- | --- | --- |
  | `cpu` | 90s | 60s |
  | `io` | 60s | 45s |
  | `default` | 30s | 20s |

- 超过 soft timeout 抛出 `SoftTimeLimitExceeded`，业务侧做收尾（写失败状态、释放锁）。
- 硬超时强制 kill。

## 8. 优先级与公平性

- 同队列内不依赖 Celery 优先级（Redis broker 支持有限），而是用多队列拆分。
- 用户维度公平：单用户在同队列内并发任务数限制（如回测同时 ≤ 3），防止单用户堵塞队列。
- 任务投递前在 API 层用 Redis 滑动窗口检查用户配额；超限直接返回 429。

## 9. 与数据库的协作

- 任务投递与状态写入必须在同一事务：先写 `backtest_task(status='queued')` 再 `apply_async`；commit 之后再实际入队（使用事务后置 hook 或显式 outbox 模式）。
- 任务执行开始：`UPDATE ... SET status='running', started_at=now()`。
- 任务结束：在单事务内写 `status='succeeded'/'failed'`、报告记录、关键摘要。
- 失败信息：error_code（枚举）+ error_message（截断）+ traceback_object_key（对象存储）。

避免"投递了但 DB 没记录"或"DB 有记录但永远没投递"的双写不一致。

## 10. 重活拆分

回测、诊断等任务允许内部拆为多个阶段。MVP 阶段建议保持单任务即可；当回测窗口达到极限再考虑分块：

- 回测分块：按时间窗口切片并行，使用 `chord` 汇总。
- 诊断分块：按交易对齐组分批，最后汇总。
- 注意：分块会显著增加 broker 压力与状态管理复杂度，不到瓶颈不上。

## 11. 定时任务

由 Celery Beat 调度，统一定义在 `apps/worker/src/schedules.py`。

| 任务 | 频率 | 说明 |
| --- | --- | --- |
| `market.sync_daily` | 每个交易日盘后 30 分钟 | 拉取当日日线、复权因子 |
| `market.sync_intraday` | 按需 | MVP 默认关闭；仅对核心标的和有限周期启用 |
| `housekeeping.expire_ai_messages` | 每天 03:00 | 清理 30 天前的 AI 对话 |
| `housekeeping.compact_market_chunks` | 每周 04:00 | TimescaleDB 旧分区压缩 |
| `report.daily_user_digest` | 每天 21:00 | 推送当日训练总结（可选） |
| `ops.heartbeat_check` | 每分钟 | 健康自检指标 |

Beat 必须有领导选举（单实例或基于 Redis 锁），避免多副本重复触发。

## 12. 优雅停机

- Worker 收到 SIGTERM 后停止接收新任务，最多等待 60s 让在跑任务结束。
- 超过 60s 仍未结束的任务由容器编排系统强杀；任务自身依赖 `acks_late + idempotency` 由下一次重试承接。
- 部署期间任务"重复执行 1 次"必须是无害的。

## 13. 流控与背压

- API 层：用户/IP 维度限流（详见 API_DESIGN.md §10）。
- 任务投递层：每队列设置软上限（Redis pending key 计数）；超限直接返回 429。
- worker 层：worker 内存使用阈值告警，超过阈值停止接新任务。
- MVP 扩容：人工或轻量脚本按队列 pending 增加 Worker 容器。
- 增长期扩容：如果部署到 K8s，再用 HPA 按 broker pending 长度做扩容指标。

## 14. 失败治理

- 失败分类：业务失败（不重试） / 暂时失败（重试） / 致命失败（告警人工介入）。
- 全部失败统一写 `*_task` 表的 `error_code` 字段，必须是受控枚举。
- 每个 error_code 对应一个固定告警 runbook（链接放在告警卡片）。
- 死信处理：超过最大重试仍失败的任务进入死信队列（`*.dead`），由值班人复盘后决定补偿或丢弃。

## 15. 监控

- 任务级 metric：投递数、成功数、失败数、重试数、耗时 P50/P95/P99。
- 队列级 metric：pending、active、reserved。
- 用户级 metric：用户维度任务速率，识别异常用户。
- 业务级 metric：例如回测平均耗时按 strategy_type 维度切片。

具体见 [OBSERVABILITY.md](OBSERVABILITY.md)。

## 16. 与服务层接口

服务层（`services/*-service`）封装"投递任务 + 写库 + 返回 task 句柄"为一个用例：

```python
# services/backtest_service/usecases/run_backtest.py
async def run_backtest(user_id: str, params: BacktestParams) -> BacktestTaskRef:
    idempotency_key = compute_idempotency(user_id, params)

    async with uow.transaction():
        task_row = await tasks.create(user_id, params, idempotency_key)
        # 事务提交 hook 中再发任务
        uow.on_commit(lambda: celery_app.send_task(
            "backtest.run", args=[task_row.id], task_id=task_row.id, queue="cpu"
        ))

    return BacktestTaskRef(id=task_row.id, status="queued")
```

API 路由层只调用上述用例，不直接接触 Celery。

## 17. 反例

- ❌ 在 API 路由里 `celery.send_task` 之后再写 DB（可能丢任务或丢记录）。
- ❌ 在事务内同步等待任务结果。
- ❌ 大模型调用裸跑无超时无重试。
- ❌ 同一队列既跑 CPU 重活又跑 I/O 轻活。
- ❌ 用 Celery 跑"实时"通讯（应改用 WebSocket / SSE 或同步 RPC）。
- ❌ 重试间隔固定 1s 让外部依赖雪崩。
