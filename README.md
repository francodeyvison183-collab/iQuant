# iQuant

iQuant 是一个面向普通交易者的 AI 辅助**交易策略验证与盲测训练**产品，目标产品形态是微信小程序。

**核心定位：通过历史盲测回放（交易训练），在隐藏未来走势的条件下记录你的买卖决策，自动识别并评估多次操作的一致性，协助你收敛为可回测、可解释的交易策略，并在规则与参数层面给出可验证的优化建议。**

产品核心不是直接预测涨跌，而是帮助用户：

- 在多轮**盲测训练**中发现自己真实的买卖习惯（行为策略）
- 通过**一致性评估**减少「每次行情换一套心法」
- 将收敛后的规则转化为 **策略 DSL**，用回测与样本外验证检验是否有效
- 在已有行为策略后，用新一轮盲测对比信号，量化**执行偏差**并安排专项训练
- 用 AI **解释**报告与优化建议（不直接给出买卖信号）

> 产品决策见 [ADR-0011 盲测训练归纳行为策略](docs/decisions/ADR-0011-blind-replay-primary-strategy-path.md)。  
> 开卷 K 线标注为**可选对照能力**，非主路径。

## 产品形态

- 用户端：微信小程序（阶段 B）；当前在管理后台 `/m/*` 移动 H5 验证
- 服务端：API + 后台任务
- 核心引擎：策略 DSL、回测、盲测回放、一致性评估、执行偏差诊断和 AI 辅助能力

## 主流程（方案 A）

```text
盲测训练（多轮）→ 一致性评估 → 行为策略 DSL（用户确认）
    → 回测 / 样本外 → 优化建议（参数/规则/训练）
    → 可选：新一轮盲测 vs DSL → 执行偏差诊断
```

## 仓库布局

```text
iQuant/
  apps/
    api/            FastAPI 应用入口
    worker/         Celery worker + Beat
    admin-web/      Vue3 + Element Plus 后台管理界面
    miniprogram/    微信小程序源码（产品文档先行）
  services/
    market-service/       行情服务
    annotation-service/   开卷标注（可选，非主路径）
    # blind-replay-service、strategy-service 等按迭代计划落地
  packages/
    domain/         领域模型（纯 Pydantic）
    market-data/    行情适配层（通达信 TCP + 文件）
  storage/
    migrations/     Alembic 迁移（业务库 + 时序库）
  docs/
    product/        产品文档
    architecture/   技术架构
    decisions/      ADR
```

## 快速开始（开发环境）

见 [AGENTS.md](AGENTS.md) 与 `make.ps1` / `Makefile`。

**Windows PowerShell**：

```powershell
.\make.ps1 env      # 首次：复制 .env.example → .env
.\make.ps1 dev      # 启动开发编排
.\make.ps1 migrate  # 业务库迁移
```

管理后台移动 H5：`http://localhost:5173/m/`（需登录，见 `admin-bootstrap`）。

## 文档索引

| 主题 | 入口 |
| --- | --- |
| MVP 产品方案 | [docs/product/MVP_PRODUCT_PLAN.md](docs/product/MVP_PRODUCT_PLAN.md) |
| 迭代计划 | [docs/product/ITERATION_PLAN.md](docs/product/ITERATION_PLAN.md) |
| 架构总览 | [docs/architecture/README.md](docs/architecture/README.md) |
| 架构决策 | [docs/decisions/README.md](docs/decisions/README.md) |

## 合规提示

本产品为策略验证与训练工具，不构成投资建议。系统不直接向用户输出实时买卖信号或荐股结论。
