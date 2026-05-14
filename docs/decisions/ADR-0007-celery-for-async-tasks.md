# ADR-0007 异步任务采用 Celery

## 背景

回测、执行偏差诊断、AI 调用、报告渲染、行情拉取等任务耗时较长且不能阻塞 Web 进程。需要一个：

- 与 Python / FastAPI 生态协作良好的任务框架。
- 支持多队列、定时任务、重试、幂等、监控。
- 在 10 万用户量级具备足够稳定性与可运维性。

## 决策

异步任务统一使用 Celery 5.x。

- Broker：Redis（MVP 阶段）；中期视流量切换至 RabbitMQ。
- Result backend：短期态写 Redis；长期任务结果写 PostgreSQL（`*_task` 表）。
- 调度：Celery Beat 单副本 + Redis 选主锁。
- 队列拓扑按任务画像拆分（CPU 重 / I/O 重 / 高优 / 慢清理），详见 [ASYNC_TASKS.md §3](../architecture/ASYNC_TASKS.md)。

## 影响

- 所有重路径业务统一通过 `services/*` 用例 + Celery 任务的方式异步化。
- 任务必须幂等（业务幂等键 + DB 唯一约束）。
- 任务投递与数据库写入需要协调，必须在事务提交后再 enqueue（outbox 模式或事务后置 hook）。
- 监控统一接 Prometheus + Flower；任务级 metric、队列级 metric、重试与失败率都要建看板。
- worker pod 与 broker 资源进入容量与发布纪律范围。

## 备选方案

- **Arq**：基于 async/asyncio，轻量；但生态弱、调度能力与监控生态不如 Celery。
- **Dramatiq**：API 简洁，但社区活跃度与可视化弱于 Celery，长期演进不确定。
- **RQ**：极简，缺少多队列优先级、定时、幂等等关键能力，且无法良好对接 Prometheus。
- **Temporal / Cadence**：能力强、状态机优秀；但运维成本高，团队学习曲线陡，10 万用户量级未到引入门槛。
- **自研 + Redis Streams**：定制能力高，但维护成本高、容易踩坑。

权衡可运维性、生态成熟度与团队熟悉度，选择 Celery。当流量进入更高阶段（如 Temporal 体验明显优于 Celery 时）可再评估迁移。

## 关联文档

- [ASYNC_TASKS.md](../architecture/ASYNC_TASKS.md)
- [TECH_STACK.md](../architecture/TECH_STACK.md)
- [OBSERVABILITY.md](../architecture/OBSERVABILITY.md)
