# 技术栈选型

本文记录 iQuant 服务端的 Python 技术栈选型与版本基线。所有选型遵循四个原则：

- **成熟优先**：选择社区活跃、长期维护、文档完善的方案。
- **能用库就别造轮子**：有成熟稳定的第三方依赖能**简洁、优雅**地解决问题时，**大胆引入**；重复实现协议、指标、编解码等通用能力是浪费且易出错（行情在线层已采用 `pytdx`，见 [`market-data.md`](modules/market-data.md)）。
- **异步优先**：I/O 密集型路径优先选择原生 async/await 支持的组件。
- **可替换**：通过包层抽象隔离第三方组件，避免基础设施反向污染业务代码；引入/替换库走 ADR 或 PR 说明即可，不设额外审批门槛（见 [`PYTHON_PROJECT_LAYOUT.md` §5](PYTHON_PROJECT_LAYOUT.md#5-依赖管理)）。

## 1. 运行时

| 项 | 选型 | 版本基线 | 说明 |
| --- | --- | --- | --- |
| 语言 | Python | 3.12.x | 性能与类型表达均显著优于 3.10，3.11 起 GIL 性能有重要改进 |
| 解释器 | CPython | 官方发行版 | MVP 不引入 PyPy / Cython 编译 |
| 包管理 | uv | 最新稳定版 | 速度远快于 pip / poetry，原生支持 lockfile 与多环境 |
| 虚拟环境 | uv venv | - | 与 uv 一体化 |
| 依赖锁定 | `uv.lock` | - | 必须提交到仓库 |
| 工程工具 | ruff + mypy + pytest | 最新稳定版 | 统一 lint / 格式化 / 类型 / 测试 |

CPython 3.12 之前的版本不在维护范围内。

## 2. Web 框架与 API 层

| 项 | 选型 | 说明 |
| --- | --- | --- |
| Web 框架 | FastAPI | 基于 Starlette/anyio，原生 async，自带 OpenAPI |
| ASGI Server | Uvicorn（开发） / Gunicorn + UvicornWorker（生产） | 多进程 + 单进程多协程 |
| 数据校验 | Pydantic v2 | 与 FastAPI 一体化，性能比 v1 提升数倍 |
| OpenAPI | FastAPI 自带 + 导出 `docs/api/openapi.yaml` | 接口契约纳入版本管理 |
| HTTP 客户端 | httpx | 同步与异步统一 API，比 requests 更适合服务间调用 |
| WebSocket | FastAPI WebSocket | 仅用于真正需要的场景（暂无强需求） |
| GraphQL | 暂不引入 | REST 已能满足 |

FastAPI 选型理由记录于 [ADR-0005](../decisions/ADR-0005-fastapi-as-web-framework.md)。

## 3. 数据存储

| 用途 | 选型 | 说明 |
| --- | --- | --- |
| 主数据库 | PostgreSQL 16 | 用户、策略、回测报告、盲测会话、诊断报告等业务数据 |
| 时序行情 | PostgreSQL 分区表；可启用 TimescaleDB 扩展 | MVP 可与主库同实例；数据量或查询压力触发后再拆独立行情库 |
| 缓存 | Redis 7 | 热点缓存、限流、轻量任务队列、分布式锁 |
| 消息队列 | Redis（MVP） → RabbitMQ（明确瓶颈后） | 任务分发与解耦；不要提前引入 |
| 对象存储 | S3 兼容（MinIO / 阿里云 OSS） | 报告快照、K 线 parquet、AI 上下文存档 |
| 全文检索 | 暂不引入 | 后续策略搜索需要再评估 OpenSearch |

时序数据选型理由记录于 [ADR-0006](../decisions/ADR-0006-timescaledb-for-market-data.md)。MVP 先保持单 PostgreSQL 运维面，TimescaleDB 可以作为扩展启用，不默认物理拆库。

## 4. 持久层与数据访问

| 项 | 选型 | 说明 |
| --- | --- | --- |
| ORM | SQLAlchemy 2.x（async） | 业界事实标准，支持类型注解风格 |
| 迁移工具 | Alembic | 与 SQLAlchemy 一体化 |
| 连接池 | asyncpg + SQLAlchemy 连接池 | 异步驱动，性能优秀 |
| Redis 客户端 | redis-py（async 模式） | 官方维护，5.x 起异步支持完善 |
| 对象存储客户端 | aioboto3 / aiobotocore | 异步 S3 兼容客户端 |

禁止在业务代码中混用原生 SQL 拼接和 ORM；如确需原生 SQL，必须使用 `sqlalchemy.text` + 参数绑定。

## 5. 异步任务与调度

| 项 | 选型 | 说明 |
| --- | --- | --- |
| 任务框架 | Celery 5.x | 生态成熟、Worker 弹性、可视化工具丰富 |
| Broker | Redis（MVP） → RabbitMQ（队列成为瓶颈后） | 与缓存共用 Redis 实例时需做命名空间隔离 |
| Result Backend | PostgreSQL + Redis | 短期态走 Redis，长期结果落 PostgreSQL |
| 定时调度 | Celery Beat | 拉取行情、清理过期会话、生成日报 |
| 监控 | Flower + 自研 dashboard | Flower 用于排查、自研 dashboard 接入业务指标 |

任务框架选型理由记录于 [ADR-0007](../decisions/ADR-0007-celery-for-async-tasks.md)。

## 6. 数据科学与策略计算

| 用途 | 选型 | 说明 |
| --- | --- | --- |
| 数据结构 | NumPy + Pandas | 通用计算基线 |
| 高性能数据帧 | Polars | 大批量行情扫描、特征提取场景使用 |
| 技术指标 | TA-Lib + pandas-ta | TA-Lib 优先（C 实现），pandas-ta 兜底纯 Python 指标 |
| 加速 | Numba（按需） | 热点路径可用；成熟方案优先 |
| DSL 求值 + 成交撮合 | `packages/backtest-engine`（`evaluator/`、`execution/`、`invariants/`） | **产品特异性**：须与盲测/诊断共享逐 bar 求值轨迹，不宜用「仅 signal-in → metric-out」的通用回测框架整体替代 |
| 收益风险指标 | empyrical-reloaded（必选）+ quantstats（可选） | 标准指标不手写；在 `metrics/` 内封装，对外只暴露 iQuant schema |
| 在线行情协议 | pytdx | 不自研 TDX TCP 编解码 |
| K 线存储格式 | Parquet | 离线分析与冷数据存储用 |

回测「哪些必须自建、哪些应用库」见 [ADR-0009](../decisions/ADR-0009-backtest-engine-boundary.md)。**当前未把 vectorbt / backtrader 等作为回测主引擎**，主因是架构契约（逐 bar DSL 轨迹），不是「排斥第三方」；若未来有库能同时满足契约与合规，可通过 ADR 替换。

## 7. AI 与外部模型

| 项 | 选型 | 说明 |
| --- | --- | --- |
| 大模型供应商 | OpenAI / Anthropic / 阿里通义 / DeepSeek | 通过统一 `ai-assistant` 抽象层，避免业务代码绑定供应商 |
| Prompt 管理 | 仓库内 `packages/ai-assistant/prompts` | 模板版本化、可追溯 |
| 调用编排 | 轻量自研 + 按需引入 LangChain 等成熟编排库 | 以解决问题为准，避免为「不依赖」而手写全套编排 |
| 结构化输出 | Pydantic v2 + JSON Schema 强约束 | AI 必须返回结构化结果，否则视为失败 |
| 内容审核 | 微信小程序内容安全 API + 自研敏感词 | 用户输入与 AI 输出双向审核 |

AI 模型不直接生成交易信号，约束见 [ADR-0003](../decisions/ADR-0003-ai-boundary.md)。

## 8. 可观测性

| 项 | 选型 | 说明 |
| --- | --- | --- |
| 日志 | structlog + JSON 输出 | 结构化日志，便于 Loki / ELK 索引 |
| 指标 | Prometheus + prometheus_client | Pull 模式，业务与系统指标分桶 |
| 追踪 | OpenTelemetry SDK + Tempo / Jaeger | FastAPI、SQLAlchemy、Celery、httpx 全链路注入 |
| 日志聚合 | Loki + Grafana | 与指标共用 Grafana 看板 |
| 告警 | Alertmanager + 飞书/钉钉 Webhook | 分级、抑制、值班路由 |
| 错误聚合 | Sentry（自托管或 SaaS） | 异常去重、版本聚合、用户上下文 |

详见 [OBSERVABILITY.md](OBSERVABILITY.md)。

## 9. 基础设施

| 项 | 选型 | 说明 |
| --- | --- | --- |
| 容器 | Docker | 所有服务统一容器化 |
| 编排 | docker compose（开发） / 轻量容器服务或 VM（MVP 生产） / Kubernetes（增长期） | MVP 不默认上 K8s，避免过早增加运维复杂度 |
| 反向代理 | Nginx / 云厂商 SLB | TLS 终结、限流、WAF 前置 |
| 配置管理 | 环境变量 + Pydantic Settings | 不允许把配置写死在代码里 |
| 机密管理 | 云厂商 Secret Manager / KMS；Vault（中期） | 严禁明文进仓库 |
| CI/CD | GitHub Actions / GitLab CI | 镜像构建、测试、扫描、部署一体化 |
| 镜像仓库 | 云厂商 ACR | 与 K8s 同地域 |

详见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 10. 测试与质量

| 项 | 选型 | 说明 |
| --- | --- | --- |
| 单元测试 | pytest + pytest-asyncio | 覆盖率以 packages/* 为主战场 |
| 属性测试 | hypothesis | 用于 DSL、指标、回测核心边界 |
| 集成测试 | pytest + testcontainers（PostgreSQL/Redis） | 真实容器跑端到端用例 |
| 负载测试 | locust | 关键 API 与回测任务必须有压测脚本 |
| 静态检查 | ruff（lint + format）+ mypy（strict） | CI 强制通过 |
| 安全扫描 | pip-audit + trivy | 依赖与镜像同时扫描 |

## 11. 微信小程序与端外能力

| 项 | 选型 | 说明 |
| --- | --- | --- |
| 微信登录 | 微信小程序 code2session | 服务端换取 openid / unionid |
| 订阅消息 | 微信订阅消息接口 | 后续真实预警使用 |
| 推送 | 服务端 → 微信订阅消息 | MVP 不引入第三方推送 |
| 客服与反馈 | 小程序客服 + 内置反馈表单 | MVP 阶段足够 |

## 12. MVP 阶段暂未选用的技术（可随需求变更）

以下为**当前**取舍，不是永久禁令；有更合适的成熟方案时，通过 ADR 或 PR 说明即可引入。

| 技术 | 当前未选原因 |
| --- | --- |
| Django / Flask | 已统一 FastAPI |
| MongoDB / Cassandra | 关系型 + TimescaleDB 已覆盖 |
| Kafka | 流量未到，Redis/Celery 足够 |
| Spark / Flink | 批处理体量未到 |
| 自研行情 TCP 协议 | 已用 **pytdx** |
| 自研行情爬虫 | MVP 用本地 vipdoc + 在线补数 |

**不因「少依赖」而拒绝成熟库**；仅当引入后明显损害可维护性、或与架构契约冲突时再记录排除理由。

## 13. 版本升级策略

- Python 主版本每年评估一次升级窗口。
- 框架次版本（FastAPI、SQLAlchemy、Celery）每季度评估一次。
- 安全补丁随漏洞披露快速跟进。
- 大版本升级必须先在 staging 跑全量集成测试与压测。
