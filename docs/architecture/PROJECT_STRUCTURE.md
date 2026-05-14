# 项目目录结构规划

## 1. 设计目标

项目目录按高内聚、低耦合原则规划。

核心思路：

- 产品文档、架构文档和代码实现分层管理。
- 业务能力按模块拆分，每个模块有清晰边界。
- 策略 DSL 作为各模块之间的核心契约。
- AI 能力作为辅助层，不侵入策略计算和回测核心。
- 行情数据、指标计算、回测、盲测和诊断互相通过接口协作，避免直接耦合。
- 用户端优先面向微信小程序，服务端和核心算法保持平台无关。

## 2. 推荐目录结构

```text
iQuant/
  README.md

  docs/
    product/
      MVP_PRODUCT_PLAN.md
      modules/
        README.md
        01-historical-labeling.md
        02-ideal-strategy-generation.md
        03-backtest-validation.md
        04-blind-replay.md
        05-execution-gap-diagnosis.md
        06-training.md
        07-ai-assistant.md
        08-strategy-library-alerting-prep.md
        09-data-and-sample-assets.md
    architecture/
      PROJECT_STRUCTURE.md
    api/
      openapi.yaml
    decisions/
      ADR-0001-strategy-dsl.md

  apps/
    miniprogram/
      src/
        pages/
        features/
        components/
        shared/
      tests/
    api/
      src/
        routes/
        middlewares/
        bootstrap/
      tests/
    worker/
      src/
      tests/

  packages/
    domain/
      src/
        market/
        strategy/
        backtest/
        replay/
        diagnosis/
      tests/
    strategy-dsl/
      src/
      tests/
    indicators/
      src/
      tests/
    backtest-engine/
      src/
      tests/
    replay-engine/
      src/
      tests/
    diagnosis-engine/
      src/
      tests/
    ai-assistant/
      src/
      prompts/
      tests/
    market-data/
      src/
      adapters/
      tests/

  services/
    strategy-service/
    backtest-service/
    replay-service/
    diagnosis-service/
    ai-service/

  storage/
    migrations/
    seeds/

  scripts/
    dev/
    data/
    qa/

  tests/
    integration/
    e2e/
    fixtures/
```

## 3. 文档层

### 3.1 docs/product

存放产品方案。

- `MVP_PRODUCT_PLAN.md`：总体产品方案，全局视角。
- `modules/`：每个独立产品模块一份文档。

### 3.2 docs/architecture

存放架构规划。

- 项目目录结构。
- 模块边界。
- 核心契约。
- 数据流。

### 3.3 docs/api

存放 API 契约，例如 OpenAPI。

MVP 初期可以先留空，等接口设计稳定后补充。

### 3.4 docs/decisions

存放架构决策记录 ADR。

建议优先记录：

- 为什么策略必须使用 DSL。
- 为什么历史标注和盲测回放不能混合。
- 为什么 AI 不直接生成交易信号。

## 4. 应用层

### 4.1 apps/miniprogram

微信小程序用户端。

建议按业务 feature 拆分：

```text
features/
  historical-labeling/
  strategy-generation/
  backtest/
  blind-replay/
  execution-diagnosis/
  training/
  strategy-library/
  ai-assistant/
```

职责：

- 微信登录与授权。
- K 线展示、触控标注和盲测交互。
- 策略、回测、诊断和训练报告展示。
- AI 助手对话入口。
- 微信订阅消息授权。

不负责：

- 策略生成算法。
- 回测计算。
- 执行偏差诊断计算。
- AI 推理编排。

### 4.2 apps/api

后端 API 入口。

职责：

- 用户请求鉴权。
- 聚合领域服务。
- 对外提供 REST / RPC API。
- 不承载复杂业务算法。

### 4.3 apps/worker

后台任务。

职责：

- 批量指标计算。
- 大回测任务。
- 后续预警扫描。
- 报告生成。

## 5. 包层

包层承载高内聚领域能力，尽量不依赖应用层。

### 5.1 packages/domain

领域模型。

包括：

- MarketBar。
- StrategyDSL。
- BacktestReport。
- BlindReplaySession。
- ExecutionDiagnosisReport。

原则：

- 只放稳定业务概念。
- 不放具体数据库实现。
- 不放 UI 逻辑。

### 5.2 packages/strategy-dsl

策略 DSL 的解析、校验和执行前检查。

职责：

- DSL schema。
- DSL validator。
- DSL version migration。
- DSL explain metadata。

### 5.3 packages/indicators

技术指标计算。

职责：

- MA。
- MACD。
- RSI。
- ATR。
- 成交量比率。
- 突破和回踩特征。

### 5.4 packages/backtest-engine

回测引擎。自研/复用边界见 [ADR-0009](../decisions/ADR-0009-backtest-engine-boundary.md)。

子包：

- `evaluator/`：DSL → 逐 bar 求值结果 → 信号事件。自研，盲测与诊断模块复用同一求值器。
- `execution/`：成交撮合（A 股 T+1、涨跌停、停牌、复权、滑点、手续费）。自研。
- `invariants/`：无未来函数检查与属性测试支持。自研。
- `metrics/`：收益风险指标（Sharpe / Sortino / 最大回撤 / Calmar / 胜率 / 盈亏比 / 资金曲线等）。**唯一允许 import empyrical-reloaded / quantstats 的子包**。
- `report/`：输出 `BacktestReport` / `BacktestSummary` 等 iQuant 自有 schema，对外屏蔽第三方库类型。

职责：

- 执行策略 DSL。
- 生成理论交易。
- 计算资金曲线和指标。
- 保证无未来函数。

显式不引入的第三方回测框架：vectorbt（AGPL）、backtrader（GPL/停滞）、backtesting.py（AGPL）、zipline-reloaded（A 股适配工作量大）。

### 5.5 packages/replay-engine

盲测回放引擎。

职责：

- 控制可见 K 线窗口。
- 推进行情。
- 处理模拟成交。
- 记录用户操作。

### 5.6 packages/diagnosis-engine

执行偏差诊断引擎。

职责：

- 对齐策略信号和用户操作。
- 计算偏差指标。
- 计算收益损耗。
- 生成纪律评分。

### 5.7 packages/ai-assistant

AI 辅助能力。

职责：

- Prompt 模板。
- 结构化输入输出 schema。
- 策略解释。
- 回测解读。
- 偏差报告解释。

AI 包不能直接调用交易信号执行逻辑，只能消费结构化报告。

### 5.8 packages/market-data

行情数据适配层。

职责：

- 读取本地 CSV。
- 接入第三方行情源。
- 数据清洗。
- 数据版本管理。

## 6. 服务层

如果后端采用模块化服务，建议服务按能力拆分：

| 服务 | 职责 |
| --- | --- |
| strategy-service | 策略生成、策略保存、版本管理 |
| backtest-service | 回测任务和报告 |
| replay-service | 盲测会话和用户操作 |
| diagnosis-service | 执行偏差诊断 |
| ai-service | AI 解释、总结、训练建议 |

MVP 阶段可以先做单体后端，但代码边界仍应按上述服务职责组织。

## 7. 模块依赖方向

推荐依赖方向：

```text
apps/*
  -> services/*
    -> packages/*
      -> packages/domain
```

禁止依赖方向：

```text
packages/domain -> apps/*
packages/backtest-engine -> apps/miniprogram
packages/diagnosis-engine -> ai-assistant
```

AI 可以读取诊断报告，但诊断引擎不能依赖 AI。

## 8. 产品模块到代码模块映射

| 产品模块 | 主要代码位置 |
| --- | --- |
| 历史 K 线标注 | apps/miniprogram/features/historical-labeling, services/strategy-service |
| 理想策略生成 | packages/strategy-dsl, packages/indicators, services/strategy-service |
| 回测验证 | packages/backtest-engine, services/backtest-service |
| 盲测回放 | packages/replay-engine, services/replay-service |
| 执行偏差诊断 | packages/diagnosis-engine, services/diagnosis-service |
| 盲测训练 | services/diagnosis-service, apps/miniprogram/features/training |
| AI 策略助手 | packages/ai-assistant, services/ai-service |
| 策略库与预警准备 | services/strategy-service, apps/miniprogram/features/strategy-library |
| 数据与样本资产 | packages/domain, packages/market-data, storage/migrations |
| 微信小程序端体验 | apps/miniprogram |

## 9. 高内聚低耦合约束

### 9.1 高内聚

每个模块只处理自己的核心问题：

- 标注模块只处理理想样本表达。
- 策略生成模块只生成理想策略。
- 回测模块只验证策略盈利能力。
- 盲测模块只记录用户真实操作。
- 诊断模块只计算执行偏差。
- AI 模块只解释和建议。

### 9.2 低耦合

模块通过稳定契约协作：

- 策略 DSL。
- K 线数据模型。
- 盲测操作记录。
- 回测报告。
- 执行诊断报告。

模块之间不直接读取彼此内部状态。

### 9.3 可替换

未来可以替换：

- 前端图表库。
- 微信小程序图表实现。
- 行情数据源。
- AI 模型供应商。
- 回测引擎实现。
- 策略模板库。

只要核心数据契约不变，其他模块不应被大面积影响。
