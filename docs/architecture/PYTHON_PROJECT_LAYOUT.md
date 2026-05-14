# Python 工程目录规范

本文与 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) 配套，专门定义 Python 代码层面的目录、包、命名与依赖管理规则。目标是让 `apps/`、`services/`、`packages/` 三层在 Python 层面真正落地，并保持高内聚低耦合。

## 1. 仓库整体形态：单仓多包（monorepo）

仓库采用 monorepo，包含多个 Python 包：

- `apps/api`：FastAPI 应用。
- `apps/worker`：Celery 应用。
- `services/*-service`：服务层应用代码（用例编排）。MVP 单体阶段，全部以 Python 包形式存在并被 `apps/*` 引用。
- `packages/*`：领域包，可独立测试，不依赖 `apps/*`。

工作区使用 `uv` 的 workspace 能力或 `pip install -e` 的 path 依赖统一管理本地依赖。

### 1.1 顶层文件

```text
iQuant/
  pyproject.toml             # workspace 根，声明 workspace 成员
  uv.lock                    # 锁定依赖（提交到仓库）
  Makefile                   # 常用命令封装
  .python-version            # 3.12.x
  .pre-commit-config.yaml
  .ruff.toml
  mypy.ini
  pytest.ini
  .dockerignore
  .gitignore
  README.md
  AGENTS.md                  # 可选，开发协作规范
```

### 1.2 workspace 声明示例

`pyproject.toml`：

```toml
[tool.uv.workspace]
members = [
  "apps/api",
  "apps/worker",
  "services/*",
  "packages/*",
]

[tool.uv.sources]
iquant-domain          = { workspace = true }
iquant-strategy-dsl    = { workspace = true }
iquant-indicators      = { workspace = true }
iquant-backtest-engine = { workspace = true }
iquant-replay-engine   = { workspace = true }
iquant-diagnosis-engine= { workspace = true }
iquant-ai-assistant    = { workspace = true }
iquant-market-data     = { workspace = true }
```

每个成员包都有自己的 `pyproject.toml`。

## 2. 每个包的标准结构

```text
packages/strategy-dsl/
  pyproject.toml
  README.md
  src/
    iquant_strategy_dsl/
      __init__.py
      schema.py
      validator.py
      version.py
      explain.py
  tests/
    test_schema.py
    test_validator.py
```

约定：

- 使用 `src/` 布局，避免本地 import 污染测试。
- 顶层 Python 包名 `iquant_<...>`，下划线分隔（PEP 8）。仓库目录名 `strategy-dsl` 使用连字符（生态习惯）。
- 测试与代码同级、不在 `src/` 内。
- 每个包暴露明确公共 API（`__init__.py` 显式 re-export），其它视为内部实现。

## 3. apps 与 services 内部结构

### 3.1 `apps/api`

```text
apps/api/
  pyproject.toml
  src/iquant_api/
    __init__.py
    main.py                # FastAPI app 实例
    bootstrap/
      __init__.py
      settings.py          # Pydantic Settings
      di.py                # 依赖注入容器
      logging_config.py
      telemetry.py         # OpenTelemetry 注入
    middlewares/
      auth.py
      request_id.py
      rate_limit.py
      error_handler.py
    routes/
      v1/
        __init__.py
        auth.py
        users.py
        symbols.py
        labels.py
        strategies.py
        backtests.py
        replays.py
        diagnoses.py
        trainings.py
        ai.py
        alerts.py
    schemas/               # FastAPI 入出参（Pydantic）
      auth.py
      strategy.py
      ...
    openapi/
      tags.py
      examples.py
  tests/
    routes/
      ...
```

约束：

- `routes/` 只做参数校验、调用 service 用例、组装响应。
- `routes/` 不引入 SQLAlchemy；不直接调用 packages（统一走 service）。
- `schemas/` 与 service 入参分开：API schema 描述协议，service 入参描述用例。

### 3.2 `apps/worker`

```text
apps/worker/
  pyproject.toml
  src/iquant_worker/
    __init__.py
    celery_app.py
    schedules.py
    tasks/
      backtest.py
      diagnosis.py
      ai.py
      report.py
      market.py
      housekeeping.py
    bootstrap/
      settings.py
      logging_config.py
      telemetry.py
  tests/
    tasks/
      ...
```

约束：

- `tasks/*` 文件即 Celery 任务集合，文件内任务命名严格遵循 `<service>.<action>`。
- 任务内部立即委托给 service 用例；不要在任务里写业务逻辑。

### 3.3 `services/<name>-service`

```text
services/backtest-service/
  pyproject.toml
  src/iquant_backtest_service/
    __init__.py
    usecases/
      run_backtest.py
      get_backtest.py
      list_backtests.py
    repositories/
      backtest_task_repo.py
      backtest_report_repo.py
    models/                 # SQLAlchemy ORM 模型（专属本服务）
      backtest_task.py
      backtest_report.py
    schemas/                # service 层入参/出参（不暴露给外部）
      params.py
      results.py
    events/
      published.py
      handlers.py
    errors.py               # 服务内业务异常
    config.py
  tests/
    usecases/
      ...
```

约束：

- 一个 service 只能写自己负责的表。跨服务通过对方 service 函数调用（单体）或后续 RPC。
- `usecases/` 函数即业务用例，函数签名清晰，返回值是 Pydantic 模型，避免 ORM 对象越界。
- `repositories/` 包装数据库访问，便于单测 mock。
- service 包不依赖 `apps/*`，依赖 `packages/*` 与 `packages/domain`。

### 3.4 `packages/domain`

```text
packages/domain/
  src/iquant_domain/
    __init__.py
    market.py              # MarketBar、SymbolMeta
    strategy.py            # StrategyDSL、StrategyVersion
    backtest.py            # BacktestReport、BacktestSummary
    replay.py              # ReplaySession、ReplayEvent
    diagnosis.py           # ExecutionDiagnosisReport
    errors.py              # 跨模块错误码
    typing.py              # 公共类型别名
```

约束：

- 仅纯 Pydantic / dataclass 模型，无 I/O。
- 无 SQLAlchemy 依赖。
- 是其他所有包的"上游"，不能反向依赖任何业务包。

## 4. 命名规范

- 包名（PyPI 包）：`iquant-<dash-name>`；Python 包名：`iquant_<snake_name>`。
- 模块名：小写下划线。
- 类名：UpperCamelCase。
- 函数与变量：snake_case。
- 常量：UPPER_SNAKE_CASE，定义在模块顶部。
- 私有：单下划线前缀，限本模块使用；双下划线不要乱用。
- 文件长度：建议 ≤ 400 行；超过考虑拆分。

## 5. 依赖管理

### 5.1 依赖分层

- 应用依赖只放在 `apps/*` 与 `services/*`。
- `packages/*` 依赖必须最小化：除非真的需要，不引入大型框架。
- 共用基础依赖（pydantic、structlog 等）由 workspace 根 lock 文件统一锁定。

### 5.2 第三方依赖入选标准

- 是否社区主流（>1k stars、活跃维护）。
- 是否纯 Python 或常用平台均有 wheel。
- 许可证是否允许商用（MIT / Apache-2.0 / BSD 优先；GPL/AGPL 需评估）。
- 是否会扩散到 `packages/domain`（如会则慎用）。

引入新依赖必须在 PR 描述里说明原因并标注是否替代已有依赖。

### 5.3 禁止

- `pip install` 临时依赖不写入 `pyproject.toml`。
- 引入仅在小众场景能用、长尾维护的"魔法库"。
- 同一职能引入多个等价库（如同时用 requests + httpx）。

## 6. 类型与静态检查

- 全部源码强制类型注解（mypy strict）。
- 禁止 `Any` 泛滥；如必须，加 `# type: ignore[<code>]` 并附注释说明。
- API schema、service 入出参、领域模型一律 Pydantic v2 模型，避免裸 dict。
- 跨模块的"公共类型"集中放 `packages/domain/typing.py`。

## 7. 异步与同步

- I/O 路径：默认 async；FastAPI + SQLAlchemy 2.x + asyncpg + redis-py async。
- CPU 路径：保持同步（NumPy/Pandas 自然同步）；通过 Celery 进程分离避免阻塞 event loop。
- 禁止在 async 函数里直接调用 blocking 长任务；必要时 `run_in_executor` 或外抛到 worker。

## 8. 异常与错误码

- 包 `packages/domain/errors.py` 定义所有业务错误码 enum。
- 每层定义自己的异常类，继承公共 base（`IquantError`）。
- API 层有统一异常处理器，将业务异常映射为标准化 HTTP 响应（API_DESIGN §11）。
- 不允许"裸 `except`" 或 `except Exception` 后吞掉异常。

## 9. 日志与可观测

- 各模块通过 `structlog.get_logger(__name__)` 获取 logger。
- 关键路径打 INFO 日志（"started/finished/decision"）；错误打 ERROR + 上下文。
- OpenTelemetry：API、SQLAlchemy、Celery、httpx、Redis 全部启用 instrumentation。
- 业务指标：通过 `packages/common/metrics`（建议新增）封装 Prometheus 计数器与直方图，避免散落定义。

## 10. 测试结构

- 单元测试与代码同包；命名 `tests/test_xxx.py`。
- 集成测试在仓库顶层 `tests/integration/`，按服务/链路组织。
- 端到端测试在 `tests/e2e/`。
- Fixtures：`tests/fixtures/` 存 K 线样例、标注样例、DSL 样例；不允许业务测试直接读真实供应商。
- 测试命名：`test_<被测函数>_<场景>_<期望>`。
- 测试覆盖率目标：`packages/*` ≥ 85%，`services/*` ≥ 70%，`apps/*` ≥ 50%（端到端为主）。

## 11. 代码风格

- ruff 作为唯一 lint + format 工具（替代 flake8 + black + isort）。
- 行宽 100。
- 字符串：双引号优先。
- import 顺序：标准库 → 第三方 → 本地工作区 → 当前包。
- docstring：公共 API 必须有，描述用途 + 参数 + 返回 + 异常；私有可省略。

## 12. 模块边界强制

使用 `import-linter`（或同类工具）在 CI 强制依赖方向：

```ini
[importlinter:contract:layers]
name = layers
type = layers
layers =
  iquant_api | iquant_worker
  iquant_*_service
  iquant_backtest_engine | iquant_replay_engine | iquant_diagnosis_engine | iquant_strategy_dsl | iquant_indicators | iquant_market_data | iquant_ai_assistant
  iquant_domain
```

加上"特定包不允许互相 import"的细则：

- `iquant_diagnosis_engine` 不可 import `iquant_ai_assistant`。
- `iquant_*_service` 之间不能直接 import。

## 13. 模板片段

### 13.1 service 用例典型骨架

```python
# services/backtest-service/src/iquant_backtest_service/usecases/run_backtest.py
from __future__ import annotations

import structlog
from iquant_domain.strategy import StrategyVersionId
from iquant_domain.backtest import BacktestParams, BacktestTaskRef

from ..repositories.backtest_task_repo import BacktestTaskRepo
from ..errors import BacktestParamsInvalid

logger = structlog.get_logger(__name__)


async def run_backtest(
    *,
    user_id: str,
    strategy_version_id: StrategyVersionId,
    params: BacktestParams,
    task_repo: BacktestTaskRepo,
    publish_task,
) -> BacktestTaskRef:
    params.validate()
    idempotency_key = params.idempotency_key(user_id, strategy_version_id)

    task = await task_repo.upsert_pending(
        user_id=user_id,
        strategy_version_id=strategy_version_id,
        params=params,
        idempotency_key=idempotency_key,
    )

    publish_task("backtest.run", task_id=task.id, queue="backtest")
    logger.info("backtest_enqueued", task_id=task.id)
    return BacktestTaskRef(id=task.id, status=task.status)
```

### 13.2 FastAPI route 典型骨架

```python
# apps/api/src/iquant_api/routes/v1/backtests.py
from fastapi import APIRouter, Depends, status
from iquant_backtest_service.usecases.run_backtest import run_backtest as run_backtest_uc

from ...schemas.backtest import RunBacktestRequest, RunBacktestResponse
from ...bootstrap.di import get_current_user, get_backtest_deps

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("", response_model=RunBacktestResponse, status_code=status.HTTP_202_ACCEPTED)
async def post_backtest(
    body: RunBacktestRequest,
    user=Depends(get_current_user),
    deps=Depends(get_backtest_deps),
) -> RunBacktestResponse:
    ref = await run_backtest_uc(
        user_id=user.id,
        strategy_version_id=body.strategy_version_id,
        params=body.params,
        task_repo=deps.task_repo,
        publish_task=deps.publish_task,
    )
    return RunBacktestResponse.from_domain(ref)
```

### 13.3 Celery 任务典型骨架

```python
# apps/worker/src/iquant_worker/tasks/backtest.py
import structlog
from iquant_backtest_service.usecases.execute_backtest import execute_backtest

from ..celery_app import app
from ..bootstrap.di import get_container

logger = structlog.get_logger(__name__)


@app.task(
    name="backtest.run",
    bind=True,
    autoretry_for=(TimeoutError,),
    retry_backoff=5,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def run_backtest(self, task_id: str) -> dict:
    container = get_container()
    return execute_backtest(task_id=task_id, deps=container.backtest_deps).model_dump()
```

## 14. 反例

- ❌ 在 FastAPI route 里直接 `select(...)` 查数据库。
- ❌ 把 SQLAlchemy ORM 对象传到 `packages/*`。
- ❌ 在 `packages/domain` 中 `import requests` 或任何 I/O 客户端。
- ❌ 多个 service 共用同一组 ORM 模型并互相写表。
- ❌ Celery 任务文件里写 200+ 行业务逻辑。
- ❌ 单测 mock 整个 service 然后只测 mock 本身。
- ❌ 任意 service 直接 import `apps/api` 或 `apps/worker`。
