# 技术栈选型

本文记录 iQuant 服务端的 Python 技术栈选型与版本基线。所有选型遵循三个原则：

- **成熟优先**：选择社区活跃、长期维护、文档完善的方案。
- **异步优先**：I/O 密集型路径优先选择原生 async/await 支持的组件。
- **可替换**：通过包层抽象隔离第三方组件，避免基础设施反向污染业务代码。

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
| 加速 | Numba（按需） | 仅在已识别的热点路径使用，避免无意义引入 |
| 回测核心 | 自研（基于 packages/backtest-engine） | 必须保证无未来函数，详见模块文档 |
| K 线存储格式 | Parquet | 离线分析与冷数据存储用 |

vectorbt、backtrader 等第三方回测框架在 MVP 不引入，避免与策略 DSL 语义不对齐。

## 7. AI 与外部模型

| 项 | 选型 | 说明 |
| --- | --- | --- |
| 大模型供应商 | OpenAI / Anthropic / 阿里通义 / DeepSeek | 通过统一 `ai-assistant` 抽象层，避免业务代码绑定供应商 |
| Prompt 管理 | 仓库内 `packages/ai-assistant/prompts` | 模板版本化、可追溯 |
| 调用编排 | 自研轻量层 + 必要时引入 LangChain 局部能力 | 避免被 LangChain 全栈绑定 |
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

## 12. 不引入的技术（显式排除）

为减少团队负担，以下技术在 MVP 阶段显式不引入：

- Django / Flask：不再选用（用 FastAPI）。
- MongoDB / Cassandra：业务结构强相关，PostgreSQL 已满足。
- Kafka：MVP 流量未到，Redis 即可；RabbitMQ 也需要有明确队列瓶颈后再引入。
- Spark / Flink：批处理体量未到。
- LangChain Agents 全套：依赖过重，仅按需借用局部工具。
- 自研行情爬虫：MVP 用合规数据供应商或本地导入。

引入新技术必须先提 ADR。

## 13. 版本升级策略

- Python 主版本每年评估一次升级窗口。
- 框架次版本（FastAPI、SQLAlchemy、Celery）每季度评估一次。
- 安全补丁随漏洞披露快速跟进。
- 大版本升级必须先在 staging 跑全量集成测试与压测。
