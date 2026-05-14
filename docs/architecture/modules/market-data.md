# 行情基础数据模块

行情基础数据模块是策略生成、回测、盲测、诊断的共同上游。本文记录其设计、目录、关键流程与运维方法。

## 1. 目标

- 作为 iQuant 唯一权威的 K 线来源，被策略 / 回测 / 盲测 / 诊断模块共同消费。
- 提供两条互补的数据通道：
  - **本地文件批量导入**：从通达信安装目录的 ``vipdoc`` 读取 ``.day`` / ``.lc5`` 文件，导入速度快、不消耗在线限额。
  - **在线协议补数**：通过通达信行情 TCP 协议拉取最新若干根 K 线，用于盘后增量、单点补缺。
- 提供后台管理界面：主站维护、扫描预览、增量/全量导入、任务进度、在线补数、数据查看。
- 与项目技术规划一致：FastAPI + Celery + PostgreSQL + TimescaleDB + Redis + Docker 热更新。

## 2. 模块边界

| 层 | 位置 | 职责 |
| --- | --- | --- |
| 领域模型 | `packages/domain` | `Symbol`、`MarketBar`、`MarketBarBatch`、`KlinePeriod`、`Market` |
| 协议与适配器 | `packages/market-data` | TDX TCP 客户端、主站管理、连接池、本地文件扫描/解析、`MarketDataSource` 抽象 |
| 业务用例 | `services/market-service` | ORM、仓储、用例（扫描、导入、查询、在线拉取、主站维护）、进度总线 |
| 应用入口 | `apps/api` | REST 路由（`/api/v1/admin/market/*`）、SSE 进度流 |
| 异步执行 | `apps/worker` | Celery 任务：`market.import_local`、`market.test_hosts` |
| 前端 | `apps/admin-web` | Vue3 + Element Plus 后台 5 个面板 |
| 数据 | `storage/migrations` | Alembic 业务库 + TimescaleDB 时序库迁移 |

依赖方向严格：``apps/* → services/* → packages/*``，禁止反向。

## 3. 数据通道

### 3.1 本地文件批量导入

```
vipdoc/{market}/{lday | fzline | minline}/{market}{code}.{day | lc5 | lc1}
        ↓        ↓
扫描器 scan_tdx_files → 状态对比 scan_changed_files
        ↓
parse_day_file / parse_lc5_file（生成 MarketBar 流）
        ↓
MarketBarRepo.bulk_upsert(PG + TimescaleDB)
        ↓
ImportStateRepo.upsert（按文件记录 size/mtime/已导入记录数）
```

- 全量：忽略状态，重导所有文件（``ON CONFLICT DO NOTHING`` 自然去重）。
- 增量：与 ``market_import_state`` 表比对 size+mtime；变更文件的 ``record_offset`` 跳到上次已导入条数继续追加。

### 3.2 在线 TDX 协议

```
TdxConnectionPool → TdxClient（带握手与差分解码） → MarketBarBatch → bulk_upsert
        ↑
TdxHostManager（连接池按主站轮询，分散压力）
```

- 单次请求最多约 800 根，分页累计可拿数千根历史。
- 协议错误/超时由连接池捕获，自动重连并切换主站重试。
- 在线源不替代本地导入，定位为「单标的、最近 N 根」的补数路径。

## 4. 数据流与表

### 4.1 业务主库（PostgreSQL）

| 表 | 用途 |
| --- | --- |
| `symbol` | 标的基础信息（市场、代码、名称、上市/退市日） |
| `tdx_host` | 主站列表与最近测速结果，含内置主站标记 |
| `market_import_task` | 导入任务元数据与进度 |
| `market_import_state` | 单文件最近一次导入位置（增量续传） |

### 4.2 时序行情库（TimescaleDB）

| 表 | 用途 |
| --- | --- |
| `market_bar` | K 线主表，hypertable，按 `bar_time` 7 天一个 chunk，30 天后自动压缩 |

主键 ``(full_code, period, bar_time)`` 同时充当幂等键，保证重复导入不会生成脏数据。

## 5. 关键约束

- **价格使用 Decimal**：避免浮点累计误差影响策略与回测语义。
- **时间统一 UTC**：写入侧若收到 naive datetime 自动按 UTC 标记。
- **增量幂等**：所有写入路径都走 ``ON CONFLICT DO NOTHING``，可任意重试。
- **CPU 任务异步化**：API 路由只投递任务、查询状态，本身不解析文件。
- **配置走环境变量**：vipdoc 目录、连接串、Redis、Celery broker 全由环境变量注入。
- **强类型边界**：模块间一律通过 ``packages/domain`` 中的 Pydantic 模型传递数据。

## 6. 后台 API 速查

所有响应统一为 ``{"code": 0, "data": ..., "message": ...}``，便于前端模板复用。

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/v1/admin/market/hosts` | GET | 列出主站 |
| `/api/v1/admin/market/hosts` | POST | 添加主站 |
| `/api/v1/admin/market/hosts/{id}` | DELETE | 删除主站（内置主站不可删） |
| `/api/v1/admin/market/hosts/test` | POST | 一键测速 |
| `/api/v1/admin/market/scan/preview` | POST | 扫描 vipdoc 预览 |
| `/api/v1/admin/market/import-tasks` | POST | 创建导入任务（增量/全量） |
| `/api/v1/admin/market/import-tasks` | GET | 任务列表 |
| `/api/v1/admin/market/import-tasks/{id}` | GET | 任务详情 |
| `/api/v1/admin/market/import-tasks/{id}/progress` | GET (SSE) | 实时进度（Server-Sent Events） |
| `/api/v1/admin/market/online/fetch` | POST | 单标的在线拉取并入库 |
| `/api/v1/admin/market/symbols` | GET | 标的分页列表（按市场/关键字） |
| `/api/v1/admin/market/bars` | GET | 查询 K 线 |
| `/api/v1/admin/market/coverage` | GET | 查询某标的某周期的数据覆盖范围 |

## 7. 后台 UI 模块

| 路径 | 功能 |
| --- | --- |
| `/market/hosts` | 通达信主站：内置 + 自定义 + 一键测速 |
| `/market/import` | 扫描预览 + 增量/全量导入入口 |
| `/market/tasks` | 任务列表 + 选中任务后通过 SSE 实时刷新 |
| `/market/online` | 在线 TDX 单标的补数 |
| `/market/browser` | 标的浏览 + K 线 ECharts + 数据覆盖范围 |

## 8. Docker 与开发体验

- **生产**：`docker compose up -d`，使用 `Dockerfile` 多阶段构建，固化代码与依赖。
- **开发**：`docker compose -f docker-compose.dev.yml up`：
  - 源码通过 `.:/workspace` 挂载，``uvicorn --reload`` 监听 ``apps/api/src``、``services``、``packages``。
  - Celery worker 由 ``watchfiles`` 包裹，源码变更后自动重启。
  - 前端 ``admin-web`` 使用 ``vite dev`` 热更新，``/api`` 反向代理到 ``api`` 容器。
- **vipdoc 目录挂载**：由 ``IQUANT_TDX_VIPDOC_HOST_DIR`` 指向宿主机通达信安装目录，只读挂入容器。

## 9. 常见运维操作

| 场景 | 操作 |
| --- | --- |
| 首次启动 | `make env && make dev` |
| 跑迁移 | `make migrate`；时序库手动 `alembic -c storage/migrations/alembic.ini -n timescale upgrade head` |
| 创建迁移 | `make revision m="msg"` |
| 看 worker 日志 | `make dev-logs s=worker` |
| 进 API 容器 | `make dev-shell s=api` |
| 触发增量同步 | 后台 UI `/market/import`，或 ``celery -A iquant_worker.celery_app call market.import_local`` |

## 10. 待办（后续迭代）

- 完善 `MarketDataSource.list_symbols`：基于 TDX `GetSecurityList` 协议解析所有标的元数据。
- 加入 1m / 15m / 30m / 60m 等本地文件类型解析（pytdx 已有先例，按需扩展）。
- 引入 ``Symbol.name`` 维护任务（从行情或新浪/东方财富批量回填名称）。
- 增加复权因子表与回算流水。
- 接入 OpenTelemetry / Prometheus 指标（任务速率、解析耗时、文件大小分布）。
- 为高频读路径增加 Redis 缓存（详见 `CACHING.md`）。
