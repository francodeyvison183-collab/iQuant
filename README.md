# iQuant

iQuant 是一个面向普通交易者的 AI 辅助交易策略验证与盲测训练产品，目标产品形态是微信小程序。

产品核心不是直接预测涨跌，而是帮助用户：

- 通过历史 K 线标注建立"理想策略"
- 用回测验证理想策略是否具备盈利能力
- 通过近端历史盲测回放识别真实交易与理想策略之间的执行差距
- 用 AI 解释、偏差诊断和专项训练帮助用户缩小差距

## 产品形态

- 用户端：微信小程序
- 服务端：API + 后台任务
- 核心引擎：策略 DSL、回测、盲测回放、执行偏差诊断和 AI 辅助能力

## 仓库布局

```text
iQuant/
  apps/
    api/            FastAPI 应用入口
    worker/         Celery worker + Beat
    admin-web/      Vue3 + Element Plus 后台管理界面
    miniprogram/    微信小程序源码（产品文档先行）
  services/
    market-service/ 行情服务用例 + 仓储 + ORM
  packages/
    domain/         领域模型（纯 Pydantic）
    market-data/    行情适配层（通达信 TCP + 文件）
  storage/
    migrations/     Alembic 迁移（业务库 + 时序库）
    local/          本地开发数据（不入库）
  docs/
    product/        产品文档
    architecture/   技术架构与模块文档
    decisions/      架构决策记录（ADR）
  docker-compose.yml          生产
  docker-compose.dev.yml      开发（热更新）
  Dockerfile / Dockerfile.dev
  Makefile                    Linux / Mac 命令封装
  make.ps1                    Windows PowerShell 命令封装
  pyproject.toml              uv workspace 根
```

## 快速开始（开发环境）

仅需 Docker Desktop。

**Windows PowerShell**

```powershell
# 1. 拷贝环境变量样例
.\make.ps1 env
# 编辑 .env，按需填写 IQUANT_TDX_VIPDOC_HOST_DIR 指向本机通达信 vipdoc 目录

# 2. 启动全部服务（PostgreSQL + TimescaleDB + Redis + API + Worker + admin-web）
.\make.ps1 dev

# 3. 后台首次启动会自动执行 Alembic 迁移；如需手动触发：
.\make.ps1 migrate
# 时序库迁移：
.\make.ps1 migrate-ts
```

**Linux / Mac (bash)**

```bash
make env
make dev
make migrate
```

启动后入口：

| 服务 | 地址 |
| --- | --- |
| 后台管理 UI | <http://localhost:5173> |
| API 文档 | <http://localhost:8000/docs> |
| 健康检查 | <http://localhost:8000/readyz> |

### 热更新行为

- **后端**：`uvicorn --reload` 监听 `apps/api/src`、`services/`、`packages/`，源码改动毫秒级生效。
- **Worker**：`watchfiles` 包装 `celery worker`，源码变化触发 worker 重启（含进行中的任务由 `acks_late` 重试承接）。
- **前端**：`vite dev` 默认 HMR，浏览器自动刷新。
- 镜像内只装依赖，源码完全通过卷挂载进容器，开发期无需 `docker compose build`。

## 行情基础数据模块

第一个落地的能力是行情基础数据模块，详细设计：[行情数据模块文档](docs/architecture/modules/market-data.md)。

后台管理界面功能：

| 路径 | 功能 |
| --- | --- |
| `/market/hosts` | 通达信主站列表、添加/删除、一键测速 |
| `/market/import` | vipdoc 扫描预览，提交增量/全量导入任务 |
| `/market/tasks` | 任务列表 + SSE 实时进度 |
| `/market/online` | 单标的在线 TDX 协议补数 |
| `/market/browser` | 浏览标的与 K 线（ECharts） |

## 文档入口

### 协作规范（人 + AI 编码代理）

- [AGENTS.md](AGENTS.md) —— 智能体开发协作手册（Cursor / Claude Code / Codex CLI 等进入仓库的第一份必读文档）

### 产品

- [MVP 总体产品方案](docs/product/MVP_PRODUCT_PLAN.md)
- [产品模块文档目录](docs/product/modules/README.md)

### 技术架构（面向 10 万用户、Python 后端）

- [技术文档总览](docs/architecture/README.md)
- [项目目录结构规划](docs/architecture/PROJECT_STRUCTURE.md)
- [技术栈选型](docs/architecture/TECH_STACK.md)
- [系统架构总览](docs/architecture/SYSTEM_ARCHITECTURE.md)
- [容量规划与性能目标](docs/architecture/CAPACITY_PLANNING.md)
- [数据存储与数据模型设计](docs/architecture/DATA_STORAGE.md)
- [API 设计规范](docs/architecture/API_DESIGN.md)
- [异步任务与消息队列](docs/architecture/ASYNC_TASKS.md)
- [缓存策略](docs/architecture/CACHING.md)
- [安全与合规](docs/architecture/SECURITY_AND_COMPLIANCE.md)
- [可观测性](docs/architecture/OBSERVABILITY.md)
- [部署与基础设施](docs/architecture/DEPLOYMENT.md)
- [Python 工程目录规范](docs/architecture/PYTHON_PROJECT_LAYOUT.md)

### 模块

- [行情基础数据模块](docs/architecture/modules/market-data.md)

### 决策

- [架构决策记录](docs/decisions/README.md)
