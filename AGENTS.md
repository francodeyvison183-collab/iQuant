# AGENTS.md

本文档面向所有协作开发 iQuant 项目的 AI 编码代理（Cursor、Claude Code、Codex CLI、GitHub Copilot Agent 等）。**进入仓库的第一件事是阅读本文档**；它规定了你在本仓库内必须遵守的项目约束、工作流和质量门槛。

如果与某条具体任务指令冲突，先以本文档为基础与用户澄清，再行动。

---

## 1. 项目速览

- 项目：**iQuant** —— 面向普通交易者的 AI 辅助交易策略验证与盲测训练产品；**核心定位**：历史盲测训练 → 一致性评估 → 行为策略 DSL → 回测与优化建议（见 [README](README.md)、[ADR-0011](docs/decisions/ADR-0011-blind-replay-primary-strategy-path.md)）。开卷 K 线标注为可选对照，非主路径。
- 用户端：微信小程序；服务端：Python 后端（FastAPI + Celery）。
- MVP 容量目标：稳定支撑 1 万注册用户，并保留向 10 万用户平滑扩容的路径。
- 架构风格：**模块化单体（modular monolith）**，按 `apps/ → services/ → packages/` 严格单向依赖。
- AI 定位：辅助决策、解释偏差、生成训练材料；**不直接生成交易信号**（见 [ADR-0003](docs/decisions/ADR-0003-ai-boundary.md)）。

如要做超出本文档范围的修改，请先阅读：
[`docs/architecture/README.md`](docs/architecture/README.md) →
[`PROJECT_STRUCTURE.md`](docs/architecture/PROJECT_STRUCTURE.md) →
[`PYTHON_PROJECT_LAYOUT.md`](docs/architecture/PYTHON_PROJECT_LAYOUT.md) →
[`API_DESIGN.md`](docs/architecture/API_DESIGN.md)。

---

## 2. 仓库结构（必须遵守）

```text
iQuant/
  apps/
    api/            # FastAPI 应用入口（src/iquant_api/）
    worker/         # Celery worker + Beat（src/iquant_worker/）
    admin-web/      # Vue3 + Element Plus 后台管理界面
    miniprogram/    # 微信小程序源码
  services/
    <name>-service/ # 业务用例 + 仓储 + ORM（src/iquant_<name>_service/）
  packages/
    domain/         # 纯 Pydantic 领域模型（src/iquant_domain/）
    market-data/    # 行情适配层（src/iquant_market_data/）
    <other>/        # 其他纯算法 / 协议包
  storage/
    migrations/     # Alembic（业务库 + 时序库两个 section）
    local/          # 本地开发数据，不入库
  docs/             # 产品、架构、决策、模块文档
  tests/            # 跨层集成测试（包内单测放在各包 tests/）
  docker-compose.yml          # 生产
  docker-compose.dev.yml      # 开发（热更新）
  Dockerfile / Dockerfile.dev
  Makefile / make.ps1         # Linux/Mac / Windows 命令封装
  pyproject.toml              # uv workspace 根
```

### 2.1 依赖方向（**禁止反向 / 跨层穿透**）

```
apps/*     ──▶  services/*  ──▶  packages/*  ──▶  packages/domain
              （单向）            （单向）            （顶层叶子）
```

具体规则：

- `apps/*` 可以依赖 `services/*` 和 `packages/*`。
- `services/*` 可以依赖 `packages/*` 与 `packages/domain`，**不能依赖 `apps/*`**。
- `packages/*` 之间只允许依赖 `packages/domain`；其余横向依赖必须先在 PR 里说明并审阅。
- `packages/domain` 是所有包的上游，**禁止依赖任何其他业务包**。
- `apps/api` 的 `routes/` 一律 **不直接** 引入 SQLAlchemy 或 `packages/*`，必须经过 service 用例。

如需新增模块或调整依赖方向，先在 `docs/decisions/` 写 ADR。

---

## 3. 技术栈与版本

| 维度 | 选型 |
| --- | --- |
| 运行时 | Python **3.12**（不要在代码里出现 3.13 only 语法），Node **20**（admin-web） |
| 包管理 | `uv` workspace；`pnpm` 用于前端 |
| Web | FastAPI 0.115+ / Pydantic v2 / SQLAlchemy 2.x（async） |
| 异步任务 | Celery 5.4+，broker 用 Redis；任务队列：`market`、`default` |
| 数据库 | PostgreSQL 16（业务库） + TimescaleDB 2.17（时序行情库） |
| 缓存/总线 | Redis 7 |
| 前端 | Vue 3.5 + Vite 5 + Element Plus 2.8 + ECharts 5 |
| 部署 | Docker Compose（MVP），后续按需上 K8s |

**第三方依赖：有成熟库就用，重造轮子是愚蠢的。** 有利于稳定、简单、高效、易维护即可引入，写入对应 `pyproject.toml` 并更新 lock；详见 [`PYTHON_PROJECT_LAYOUT.md` §5](docs/architecture/PYTHON_PROJECT_LAYOUT.md)。PR 中一句话说明用途即可。

**与 HQScanner 的关系**：二者为**独立项目**，禁止共享 Python 包、子模块依赖或双向 import；可参考其业务/协议做法，但所有代码与依赖必须落在本仓库内。

---

## 4. 开发工作流

### 4.0 容器内开发、测试与调试（**强制**）

- **所有**与本仓库相关的**开发、测试、调试**（编写代码后的运行、单测、集成测、API/Worker/前端 dev server、lint/typecheck 等）必须在 **Docker Compose** 编排的容器内进行；默认编排见 [`docker-compose.dev.yml`](docker-compose.dev.yml)（如 `api`、`worker`、`admin-web` 服务及其启动命令中的 `uv sync` / `pnpm install` / 热重载进程）。
- **禁止**在宿主机为承担上述工作流而**安装**本项目的运行时与工具链依赖（例如在本机创建用于跑本仓库的 Python venv、全局/用户级安装 `uv`/`pnpm` 后仅在本机执行 `pytest` / `ruff` / `mypy` / `vite dev` 等以替代容器）。依赖仍只通过仓库内的 `pyproject.toml`、`apps/*/pyproject.toml`、`package.json` 等声明；**锁文件与安装产物以容器内为准**。
- 智能体或脚本需用终端执行上述命令时：应使用 `docker compose -f docker-compose.dev.yml exec <service> …`，或仓库提供的 **`make.ps1` / `Makefile`** 中已封装为面向 Compose 的目标；不得假设宿主机已具备与容器一致的 Python/Node 版本与依赖树。
- 宿主机仅用于不替代容器环境的工作（如编辑文件、`git`、浏览文档）。若用户指令要求仅在宿主机执行与本条冲突的操作，须先与用户确认并说明偏离团队约定的风险。

### 4.1 启动开发环境

**Windows PowerShell**：

```powershell
.\make.ps1 env          # 首次：复制 .env.example → .env，按需填 IQUANT_TDX_VIPDOC_HOST_DIR
.\make.ps1 dev          # 前台启动全部服务
.\make.ps1 migrate      # 业务库迁移
.\make.ps1 migrate-ts   # 时序库迁移
```

**Linux / Mac**：用同名 `make` 命令。

### 4.2 热更新约定（**禁止破坏**）

- 后端：`uvicorn --reload` 监听 `apps/api/src`、`services/`、`packages/`。
- Worker：`watchfiles` 包装 `celery worker`，源码变化重启 worker；任务由 `task_acks_late` 自动重派。
- 前端：`vite dev` HMR，`usePolling: true`。

任何"必须重启容器才能生效"的修改都属于回归。如果你的改动绕开了卷挂载或破坏了 reload-dir 列表，必须显式在 PR 里说明并修复。

### 4.3 数据库迁移

- 业务库：`storage/migrations/versions/` + `alembic.ini` 默认 section。
- 时序库：`storage/migrations/versions_ts/` + `-n timescale`。
- 严禁直接改既有 migration 文件（已被部署过）；新增表/字段写新的 revision。
- 新增 ORM 模型必须同时：
  1. 在 `services/<name>-service/src/.../models/` 添加 ORM 类；
  2. 注册到 `models/__init__.py`；
  3. 写对应 Alembic 迁移（`make.ps1 revision -m "..."`）；
  4. 如属时序数据，挂到 TimescaleDB hypertable 并设压缩策略。

---

## 5. 代码规范（最低底线）

- **类型注解强制**：mypy strict 通过。禁止 `Any` 泛滥；必须用时加 `# type: ignore[<code>]` 并写明原因。
- **Pydantic v2**：所有跨模块边界（API schema、service 入参、domain 模型）一律 Pydantic 模型，禁止裸 dict / ORM 越界。
- **价格使用 `Decimal`**，时间使用 `datetime`（带时区 / UTC）。禁止 `float` 价格累加。
- **错误模型**：业务异常继承 `iquant_domain.errors.IquantError`；API 层有统一 handler 翻译为 `{"error": {"code": ..., "message": ...}}`。
- **日志**：`structlog.get_logger(__name__)`；关键路径打 `started/finished/decision`，错误打 ERROR + 上下文（trace_id、task_id）。**禁止用日志当业务通信**。**需持久化排障的错误与异常落盘**见 **§5.3**。
- **配置**：全部走 `pydantic-settings` + 环境变量；不要把配置写死，不要 `os.environ[...]` 散落。
- **ruff** 是唯一 lint+format 工具；行宽 100；双引号优先。
- **文件 ≤ 400 行**作为软上限；超过先拆模块。

### 5.1 注释规范

- **公共 API**（函数 / 类 / 模块）写 docstring：用途 + 参数 + 返回 + 异常。
- **禁止流水账注释**：不要写"# 导入模块"、"# 定义函数"、"# 增量计数器"这种解释代码字面意思的注释。
- 注释只解释 **为什么**（业务约束、协议怪癖、性能取舍），不解释 **是什么**。
- 修改代码不要保留"# 这里改了 ..."、"# 旧代码 ..." 的考古注释。

### 5.2 异步 / 同步

- I/O 路径默认 `async`（FastAPI + asyncpg + redis async）。
- CPU 重活（向量化回测、指标计算、文件解析）保持同步，通过 Celery 进程隔离。
- 禁止在 `async` 函数里直接调用 blocking 长任务；必要时 `run_in_executor` 或外抛到 Celery。

### 5.3 异常与错误落盘（前端 / 后端 / 定时任务）

- **后端（API 与各 service）**：对**需排障的异常**（未捕获异常、任务失败、依赖故障等）必须记录完整上下文（含栈、`trace_id` / `request_id`、路由等），并**写入**项目约定的 **ERROR 级滚动日志文件**（默认 `logs/iquant-api-errors.log`，环境变量 `IQUANT_API_ERROR_LOG_PATH`）。**预期内的业务校验失败**（如 `ValidationError` 返回 400）以 API 响应体为准，不要求写入 error 日志以免噪声；若需留痕走审计表或访问日志。
- **定时任务（Celery Worker / Beat）**：任务入口与 Beat 触发的逻辑在失败分支须 `logger.exception`（或等价），并依赖 Worker/Beat 进程挂载的 **ERROR 文件**（默认 `logs/iquant-worker-errors.log`，`IQUANT_WORKER_ERROR_LOG_PATH`）。新增任务必须覆盖异常路径，不得静默吞掉栈信息。
- **前端（admin-web 等）**：浏览器沙盒**不能**直接写宿主机文件；须通过 **`POST /api/v1/client-errors`** 将 Vue 运行时错误、`unhandledrejection`、关键 HTTP 失败等**上报**，由 API **追加写入 JSONL**（默认 `logs/iquant-admin-web-errors.log`，`IQUANT_CLIENT_ERROR_LOG_PATH`）。上报体禁止包含 token、密码、完整 Cookie。
- 上述路径位于 `logs/`（仓库 `.gitignore`）；生产 Compose 将 `logs_data` 挂到容器内 `/workspace/logs`。

---

## 6. 模块协作契约

### 6.1 模块通过 schema 协作，禁止互读对方的表

- 跨服务调用 **必须** 通过 service 用例函数（单体阶段）或后续 RPC，不能直接 SELECT 对方的表。
- 同一张表只允许一个服务写；其他服务只读，且最好通过 repository 提供的方法。

### 6.2 行情数据

- 任何模块需要 K 线 → 走 `services/market-service` 或 `packages/market-data`。
- 写入：批量 `ON CONFLICT DO NOTHING`，主键 `(full_code, period, bar_time)` 保证幂等。
- 在线 TDX 协议是同步 TCP，必须经过 `TdxConnectionPool.run_sync`，禁止在 event loop 中直接 `socket.recv`。

### 6.3 AI 边界

- AI 模块只消费 **结构化报告**（回测、诊断、盲测），输出建议性内容。
- **禁止** 让 LLM 直接产出买卖信号、价格预测、仓位决策。
- 用户输入到 LLM 前必须做内容审核 + PII 脱敏。

### 6.4 异步任务

- 任务命名：`<service>.<action>`，如 `market.import_local`、`market.test_hosts`。
- 任务函数立刻委托给 service 用例，**不要在 task 里写业务逻辑**。
- 所有任务必须可重入（依赖 `task_id` / `idempotency_key`），失败默认按指数退避重试。
- 长任务必须设 `soft_time_limit` < `time_limit`，并把进度通过 `progress_bus` 发到 Redis pub/sub。
- **新增 / 修改 Celery 任务**：失败与未预期异常须在任务内 `logger.exception`（或等价），并确保 Worker/Beat 进程挂载的 **ERROR 日志文件**能收录栈信息（见 **§5.3**）；不得静默吞异常。

---

## 7. 测试要求

- 执行与调试测试（`pytest`、覆盖率等）须在 **§4.0** 规定的容器环境内进行，不得以宿主机临时虚拟环境替代。
- 与前后端、任务相关的**可复现失败**应能通过 **§5.3** 约定的错误日志文件或 JSONL 在容器内定位；新增能力时检查是否已接入落盘或上报。
- 包内单测：`packages/<name>/tests/`、`services/<name>-service/tests/`。
- 跨层集成 / 端到端：`tests/integration/`、`tests/e2e/`。
- 命名：`test_<被测函数>_<场景>_<期望>.py` / `def test_*()`。
- 覆盖率门槛：`packages/* ≥ 85%`、`services/* ≥ 70%`、`apps/* ≥ 50%`。
- 不允许业务测试直接读真实数据源；用 `tests/fixtures/` 下样例。
- 修改 / 新增公共函数 → **必须** 同步新增或更新单测。

---

## 8. 任务执行规则（给智能体）

### 8.1 开工前

1. **先读规范，再写代码**。本文档 + `docs/architecture/README.md` + 与任务相关的模块文档（如 `docs/architecture/modules/market-data.md`）。
2. 探索仓库以确认现有约定；**不要从零臆造命名 / 目录**。
3. 多步骤任务（≥ 3 步）开始前先列 TODO 清单，过程中持续维护。
4. **开发、测试、调试命令**一律按 **§4.0** 在 Docker 容器内执行；不在宿主机为本仓库安装运行时与依赖以替代容器。

### 8.2 落地时

1. **优先编辑已有文件，禁止无谓新建**。新建文件必须有结构上的理由（新模块、新用例、新组件）。
2. **不要主动创建文档文件**（README、CHANGELOG、docs/*.md），除非用户明确要求或本文档要求。
3. 修改 ≥ 3 个文件后，在**容器内**跑一次 `ruff check`（及必要的 `mypy`），或使用 IDE ReadLints；若 IDE 与容器结论不一致，**以容器内结果为准**。自己引入的 lint 错误必须自己修。
4. 涉及数据库结构 → 必须配套 Alembic 迁移。
5. 涉及新依赖 → 改对应 `pyproject.toml` 而不是 `pip install` 后忘掉。
6. 涉及 API 变更 → 同步更新 `apps/admin-web/src/api/*.ts`（如有 UI 消费）。

### 8.3 完工后

1. 用一两句话告诉用户：**改了什么、为什么、怎么验证**。
2. 任何"绕过约束"的妥协必须显式说明（例如"暂时未加 Redis 分布式锁，后续 follow-up"）。
3. **不要**：自作主张 `git commit` / `git push`；除非用户明确要求。

### 8.4 中文与编码

- 沟通和注释优先使用中文，但代码标识符（变量、函数、类名）一律英文。
- 提交到仓库的 `.ps1` / `.bat` 脚本必须是 **UTF-8 BOM**；`.sh` / `.py` / `.md` 用 **UTF-8 无 BOM**。
- 控制台输出包含中文时，PowerShell 脚本要在脚本开头设置 `[Console]::OutputEncoding`，避免 Windows 5.1 乱码。

---

## 9. 安全与合规红线

- 严禁把真实密钥 / token / 用户数据写入仓库；`.env` 已在 `.gitignore`，不要 commit。
- 用户敏感字段（手机号、身份证、地址）：日志中必须脱敏；落库必须加密或散列。
- 用户输入文本（标注理由、策略备注）发到 LLM 前必须通过内容审核 API。
- 所有写操作（创建、更新、删除）必须支持 **`X-Idempotency-Key`**；不要发明新风格。
- 风险提示与免责声明属于硬性合规：相关模块的 UI / API 文案不要擅自精简。

---

## 10. 提交 / PR 自查清单

完成任务后，确认满足：

- [ ] 类型注解齐全，**在容器内** `ruff check` 与 `mypy` 在改动文件上通过（见 §4.0）。
- [ ] 修改 / 新增的公共函数有单测；现有测试无回归。
- [ ] 涉及表结构 → 已写 Alembic 迁移；迁移可向下回滚。
- [ ] 涉及配置 → `.env.example` 已同步新键。
- [ ] 涉及前端 API 调用 → `apps/admin-web/src/api/*.ts` 已更新。
- [ ] 涉及新依赖 → `pyproject.toml` + lock 已更新；PR 中已简要说明用途（若有）。
- [ ] 未引入"重启容器才能生效"的回归。
- [ ] 前后端与 Celery 相关错误已按 **§5.3** 可落盘（API/Worker ERROR 文件或前端经 `/api/v1/client-errors` 写入 JSONL）。
- [ ] 未在代码里留无用注释 / 调试 print / TODO 而无追踪 issue。
- [ ] 提交信息（如用户要求提交）符合现仓库风格（祈使句，中文 OK）。

---

## 11. 参考文档索引

| 主题 | 入口 |
| --- | --- |
| 架构总览 | [`docs/architecture/README.md`](docs/architecture/README.md) |
| 目录约束 | [`docs/architecture/PROJECT_STRUCTURE.md`](docs/architecture/PROJECT_STRUCTURE.md) |
| Python 工程规范 | [`docs/architecture/PYTHON_PROJECT_LAYOUT.md`](docs/architecture/PYTHON_PROJECT_LAYOUT.md) |
| API 设计 | [`docs/architecture/API_DESIGN.md`](docs/architecture/API_DESIGN.md) |
| 异步任务 | [`docs/architecture/ASYNC_TASKS.md`](docs/architecture/ASYNC_TASKS.md) |
| 数据存储 | [`docs/architecture/DATA_STORAGE.md`](docs/architecture/DATA_STORAGE.md) |
| 缓存策略 | [`docs/architecture/CACHING.md`](docs/architecture/CACHING.md) |
| 安全合规 | [`docs/architecture/SECURITY_AND_COMPLIANCE.md`](docs/architecture/SECURITY_AND_COMPLIANCE.md) |
| 可观测性 | [`docs/architecture/OBSERVABILITY.md`](docs/architecture/OBSERVABILITY.md) |
| 部署 | [`docs/architecture/DEPLOYMENT.md`](docs/architecture/DEPLOYMENT.md) |
| 行情模块 | [`docs/architecture/modules/market-data.md`](docs/architecture/modules/market-data.md) |
| 架构决策 | [`docs/decisions/README.md`](docs/decisions/README.md) |

---

> 本文档是活的规范。在工作中发现规则缺失或与现实冲突，应在 PR 中提议修订，而不是默默绕开。
