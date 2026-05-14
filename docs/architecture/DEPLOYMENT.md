# 部署与基础设施

本文定义 iQuant 的环境模型、MVP 生产部署、发布流程和扩容路径。

当前原则：

> MVP 先用简单、可靠、可观测的部署形态支撑 1 万注册用户；Kubernetes、复杂多副本数据库和独立消息中间件在明确瓶颈出现后再引入。

## 1. 环境模型

| 环境 | 用途 | 数据 | 访问 |
| --- | --- | --- | --- |
| local | 开发者本机 | docker compose + 种子数据 | 本机 |
| ci | CI 构建测试 | 临时容器（testcontainers） | 内部 |
| dev | 集成联调 | 仿真数据 | 内部 IP 白名单 |
| staging | 预发布 | 生产脱敏样本 | 内部 IP 白名单 + 微信小程序体验版 |
| prod | 生产 | 真实数据 | 公网 + WAF |

环境差异通过环境变量控制；代码和镜像在所有环境保持一致。

## 2. MVP 生产部署形态

### 2.1 推荐拓扑

```text
微信小程序
  -> 云 SLB / WAF / HTTPS
  -> API 容器 × 2
  -> Worker 容器 × 2~4
  -> Beat 容器 × 1
  -> 托管 PostgreSQL
  -> 托管 Redis
  -> 对象存储
```

### 2.2 部署载体

MVP 可选以下任一简单形态：

| 形态 | 适用场景 | 说明 |
| --- | --- | --- |
| 单台云主机 + docker compose | 内测 / 早期验证 | 成本最低，但可用性一般 |
| 两台云主机 + SLB + docker compose | MVP 正式上线 | API/Worker 可水平扩容，复杂度低 |
| 云厂商轻量容器服务 | 团队希望少管机器 | 比 K8s 简单，支持容器扩缩 |

不默认使用 Kubernetes。进入增长期且有明确 HPA、服务拆分或多团队发布需求时再评估。

## 3. 容器化

所有后端应用统一容器化：

| 镜像 | 入口 | 说明 |
| --- | --- | --- |
| `iquant-api` | `gunicorn -k uvicorn.workers.UvicornWorker apps.api.main:app` | FastAPI API 服务 |
| `iquant-worker` | `celery -A apps.worker.celery_app worker` | 异步任务 Worker |
| `iquant-beat` | `celery -A apps.worker.celery_app beat` | 定时任务，单实例 |
| `iquant-migrator` | `alembic upgrade head` | 一次性迁移任务 |

镜像要求：

- 基础镜像：`python:3.12-slim-bookworm`。
- 多阶段构建，运行镜像尽量小。
- non-root 运行。
- 镜像标签使用 `<service>:<git_sha>`，禁止 `latest`。
- `uv.lock` 必须进入构建，CI 使用 frozen install。

## 4. MVP 资源建议

| 组件 | 建议规格 | 数量 | 说明 |
| --- | --- | --- | --- |
| API | 1 ~ 2 vCPU / 1 ~ 2 GB | 2 | 无状态，横向扩容 |
| Worker | 2 vCPU / 4 GB | 2 起 | CPU / IO 队列可分开跑 |
| Beat | 0.5 vCPU / 512 MB | 1 | 单实例 + 锁 |
| PostgreSQL | 2 ~ 4 vCPU / 8 ~ 16 GB / SSD 200 GB | 1 | 托管 RDS |
| Redis | 1 ~ 2 GB | 1 | 托管 Redis，后续可主从 |
| 对象存储 | 按量 | 1 | 报告、快照、明细 |

## 5. 数据基础设施

### 5.1 PostgreSQL

- MVP 使用托管 PostgreSQL 单主。
- 业务数据和行情数据可同实例，不同 schema / 分区管理。
- 开启自动备份和 WAL 归档。
- 不在 MVP 默认启用只读副本。

只读副本触发条件：

- 主库 CPU > 60% 持续 3 天。
- 读查询导致写入延迟明显增加。
- 报告查询或行情查询无法通过缓存和索引优化解决。

### 5.2 Redis

- MVP 使用单实例或云厂商标准版。
- 承担缓存、限流、短期状态、Celery broker。
- Redis 不是持久真理源，所有关键状态必须可从 PostgreSQL 重建。

主从或分离触发条件：

- Redis 内存 > 70%。
- Redis 连接数接近实例上限。
- Celery broker 与业务缓存互相影响。

### 5.3 对象存储

用于：

- 回测明细。
- 诊断报告明细。
- 大型快照。
- 后续行情冷数据 Parquet。

## 6. 构建与发布

### 6.1 CI 流水线

```text
push / pr
  -> lint (ruff)
  -> type-check (mypy)
  -> unit-test (pytest)
  -> integration-test (pytest + testcontainers)
  -> security-scan (pip-audit / trivy)
  -> build-image
  -> push-image
  -> deploy staging / prod
```

### 6.2 发布规则

- main 分支必须通过 CI。
- staging 自动部署 main。
- prod 需要人工审批。
- 发布前确认数据库迁移向后兼容。
- 发布后观察核心指标至少 30 分钟。

### 6.3 数据库迁移

- Alembic 统一管理 DDL。
- 迁移先于应用发布。
- 大表索引用 `CONCURRENTLY`。
- 破坏性迁移必须两步发布：先兼容写入，再删除旧字段。

## 7. 灰度与回滚

MVP 简化灰度：

- API 新版本先部署 1 个实例。
- 健康检查通过后替换剩余实例。
- 任务 Worker 先停旧实例接新任务，再启动新实例。
- 出现异常时回滚镜像标签。

回滚要求：

- 最近 5 个生产镜像可回滚。
- 数据库迁移默认向后兼容，避免依赖 downgrade。
- Worker 任务必须幂等，允许重复执行一次。

## 8. 安全与接入

- 所有外部流量走 HTTPS。
- 云厂商 WAF / SLB 前置。
- API 层做用户、IP、接口维度限流。
- Secret 使用云厂商 Secret Manager / KMS 或部署平台密钥能力。
- 禁止把密钥写入 Git、镜像或 ConfigMap 明文。

## 9. 监控与告警

MVP 必须有：

- API 延迟 P50/P95/P99。
- API 错误率。
- PostgreSQL CPU、连接数、慢查询。
- Redis 内存、连接数、错误率。
- Worker 队列 pending、任务成功率、任务耗时。
- AI 调用成功率、降级率、成本。
- 核心业务漏斗：标注完成率、策略生成率、回测完成率、盲测完成率。

## 10. 备份与恢复

- PostgreSQL：每日全量备份 + WAL，保留 30 天。
- 对象存储：开启版本控制。
- Redis：不作为关键数据唯一来源，不要求强 RPO。
- 每季度至少演练一次 PostgreSQL 恢复。

MVP 目标：

- RTO：≤ 2 小时。
- RPO：≤ 15 分钟。

进入付费规模后再提升到：

- RTO：≤ 1 小时。
- RPO：≤ 5 分钟。

## 11. 扩容路径

| 阶段 | 部署形态 | 主要动作 |
| --- | --- | --- |
| Stage 0 内测 | 单机 docker compose + 托管 PG/Redis | 验证业务正确性 |
| Stage 1 MVP | SLB + API×2 + Worker×2~4 + 托管 PG/Redis | 支撑 1 万注册用户 |
| Stage 2 增长 | API/Worker 横向扩容 + Redis 主从 | 支撑 3 万注册用户 |
| Stage 3 放量 | 可选 K8s + 独立行情库 + PG 只读副本 | 支撑 10 万注册用户 |
| Stage 4 成熟 | 按瓶颈服务化 + 独立队列中间件 | 支撑更大规模 |

Kubernetes 触发条件：

- Worker 扩缩容频繁，人工调整成本明显。
- 多服务发布节奏不同，单体部署影响效率。
- DAU > 5,000 且 API/Worker 资源曲线差异明显。
- 需要跨可用区自动调度和 HPA。

## 12. 成本预算

| 阶段 | 月成本目标 |
| --- | --- |
| 内测 | < ¥2,000 |
| MVP 1 万注册用户 | ¥3,000 ~ ¥8,000 |
| 增长期 | ¥8,000 ~ ¥20,000 |
| 10 万注册用户 | 根据 AI 使用量和行情数据规模单独评估 |

AI 是最大可变成本之一，必须配额、缓存和降级。

## 13. 反例

- ❌ MVP 一开始就上 Kubernetes，但没有专职运维或明确 HPA 需求。
- ❌ 一开始就拆业务库和行情库，导致迁移、备份、连接池复杂度上升。
- ❌ API 和 Worker 跑在同一个进程里，导致回测拖慢接口。
- ❌ 用 Redis 作为唯一数据源。
- ❌ 数据库迁移不可回滚且不兼容旧代码。
- ❌ 没有监控就上线异步任务。

