# ADR-0009 回测引擎自研边界与第三方库复用

> **总原则（2026-03 修订）**：项目级默认**优先成熟第三方库**，重造轮子是愚蠢的。本 ADR 只划定「因 iQuant 产品契约必须保留的自研薄层」，**不是**鼓励在指标、协议、通用算法上重复实现。许可证与 SaaS 合规按个案评估，见 [`SECURITY_AND_COMPLIANCE.md`](../architecture/SECURITY_AND_COMPLIANCE.md)。

## 背景

iQuant 的回测能力被三个产品模块**共同消费**，且必须共享同一份信号生成结果：

| 模块 | 文档 | 对信号生成的要求 |
| --- | --- | --- |
| 回测验证 | [03-backtest-validation](../product/modules/03-backtest-validation.md) | 全历史批量执行，越快越好 |
| 盲测回放 | [04-blind-replay](../product/modules/04-blind-replay.md) | **逐根 K 线推进**，用户只能看见到当前 bar 的数据 |
| 执行偏差诊断 | [05-execution-gap-diagnosis](../product/modules/05-execution-gap-diagnosis.md) | 用户在某根 bar 做了 X，DSL 在那根 bar 的"应做"必须 bit-for-bit 可重放 |

三者的唯一契约是 [ADR-0001](ADR-0001-strategy-dsl.md) 定义的策略 DSL；产品默认成交规则（信号在收盘后生成、次根开盘价成交、不允许未来函数）也是合规底线，不是"可选优化"。

主流量化回测框架（vectorbt、backtrader、backtesting.py、zipline-reloaded）解决的是"已有 entries/exits 信号 → 计算交易与指标"这层问题，并不消费 DSL，也不暴露逐 bar 的求值轨迹。如果用其中任一框架直接覆盖回测路径，盲测和诊断模块仍需自建一套与之严格等价的信号生成器，会得到**两个必须永远一致的引擎**——这是个永久维护陷阱。

但另一方面，回测里"标准化指标计算（Sharpe / Sortino / Calmar / 最大回撤 / 胜率 / 盈亏比 / 资金曲线）"这部分是经过 10 年以上社区验证的轮子，没有 iQuant 特异性，**重新发明纯属浪费**。

因此需要一份决策明确**因产品契约必须自研的边界**与**应当复用的第三方能力**，避免"回测核心自研"被字面误读为"所有相关代码都自己写"，也避免在标准化指标与协议上重造轮子。

## 决策

### 1. 因产品契约保留的自研层（`packages/backtest-engine`、`packages/strategy-dsl`）

> 下列能力**暂无**能直接替代且满足盲测/诊断契约的单一成熟框架；若未来出现，应通过新 ADR 评估替换，而非永久自研。

- **DSL 求值器**：从 DSL 节点 → 每根 bar 的 predicate 评估结果 → 信号事件。必须保留可序列化的求值轨迹（供盲测回放和诊断模块复用）。
- **成交撮合**：A 股专属规则——T+1、涨跌停判断（成交价被限板时回退或拒绝）、停牌跳过、复权处理；MVP 默认次根开盘价成交、手续费 0.05% / 滑点 0.05%（见 [03-backtest-validation §4](../product/modules/03-backtest-validation.md#4-默认回测规则)）。
- **"无未来函数"不变式检查**：DSL 求值在 bar `t` 只允许访问 `≤ t` 的数据，由引擎在编译期或运行期断言；测试用 hypothesis 做属性测试。
- **与盲测/诊断模块共享的求值入口**：盲测每推进一根 bar 调用同一求值器，诊断模块比对"实际操作 vs 理论信号"也走同一求值器。

### 2. 应当优先使用的第三方库（持续扩展）

| 能力 | 选用库 | License | 说明 |
| --- | --- | --- | --- |
| 资金曲线 / 最大回撤 / Sharpe / Sortino / Calmar 等收益风险指标 | **empyrical-reloaded** | Apache-2.0 | Quantopian empyrical 的活跃分支，纯函数式 API，易包装 |
| 报告级指标补充（胜率、盈亏比、最大连续亏损分布等） | **quantstats**（可选，按需引入） | MIT | 注意只用其 `stats` 模块，绘图模块依赖重 |
| 技术指标 | TA-Lib + pandas-ta | 已在 [TECH_STACK §6](../architecture/TECH_STACK.md#6-数据科学与策略计算) 选定 | — |
| 参数扫描调度 | Celery + 自研 fan-out | — | 通过任务拆分实现，不引入 vectorbt 的向量化参数搜索 |
| 数据帧操作 | NumPy / Pandas / Polars | 已选定 | — |

封装要求（非「少引库」）：

- 第三方库在 `packages/*` 内按模块封装，对外暴露 iQuant 自有 schema（`BacktestReport`、`BacktestSummary` 等），避免第三方类型穿透 `services/` / `apps/`。
- 许可证：涉及 AGPL/GPL 等 copyleft 时，在 PR 中说明部署形态与合规结论；无统一「禁止名单」，以 [`SECURITY_AND_COMPLIANCE.md`](../architecture/SECURITY_AND_COMPLIANCE.md) 为准。

### 3. 当前未采用为「回测主引擎」的框架（架构原因，非排斥第三方）

| 框架 | 当前未作为主引擎的原因 |
| --- | --- |
| **vectorbt** / **backtesting.py** | 典型用法为 signal-in / metric-out，难以作为盲测/诊断的唯一 DSL 求值源；另需评估 AGPL 与 SaaS 部署合规 |
| **vectorbt PRO** | 商业授权与供应商锁定 |
| **backtrader** | 维护停滞、大规模扫描性能一般；若仅作局部参考可个案引入 |
| **zipline-reloaded** | 偏美股日历与撮合模型，A 股全量适配成本高 |

**说明**：上表表示「不适合整体替代 evaluator+execution」，不禁止在子模块中复用其中**可拆出的成熟组件**（例如指标、日历工具），也不禁止未来通过 ADR 更换主引擎。

### 4. 包结构约束

```text
packages/
  strategy-dsl/        # DSL 数据结构 + 校验
  backtest-engine/     # ↓
    src/iquant_backtest_engine/
      evaluator/       # DSL → 信号事件（自研，盲测/诊断复用）
      execution/       # 成交撮合（T+1、涨跌停、停牌、复权）
      invariants/      # 无未来函数检查
      metrics/         # 收益风险指标（薄包装 empyrical-reloaded）
      report/          # 输出 BacktestReport / BacktestSummary
```

`metrics/` 是**唯一**允许 import empyrical / quantstats 的子包；其它子包禁止 import 上述库。

## 影响

- `packages/backtest-engine` 与 `packages/replay-engine`、`packages/diagnosis-engine` 共用同一份 `evaluator/`（通过依赖 `packages/backtest-engine.evaluator` 子模块或将 evaluator 抽到独立 `packages/dsl-evaluator`，由具体实现决定）。
- 新增运行时依赖：`empyrical-reloaded`（必须）、`quantstats`（可选）。两者均在 `packages/backtest-engine/pyproject.toml` 声明，不进入 workspace 根。
- License 合规：依赖变更时在 PR 中标注许可证；必要时用 `pip-licenses` 等工具辅助审查，**不以许可证类型一刀切拒绝**（copyleft 需结合部署形态评估）。
- 文档同步：`TECH_STACK.md §6`、`PROJECT_STRUCTURE.md §5.4` 表述需要按本 ADR 更新。
- 对开发者：实现"参数敏感性验证"（[03-backtest-validation §5](../product/modules/03-backtest-validation.md)）时使用 Celery fan-out + 单回测复用，而不是寄望于框架级向量化扫描；如未来性能成为瓶颈，再考虑在 evaluator 内部用 Numba JIT 关键路径。

## 备选方案

- **整体使用 vectorbt（OSS 或 PRO）**：放弃 DSL 求值轨迹的共享，盲测和诊断单独再写一套引擎。被否：维护两套等价引擎的成本远高于复用收益；vectorbt OSS 的 AGPL 协议对商业 SaaS 是真实合规风险。
- **整体使用 backtrader**：项目维护停滞，事件驱动模型在参数扫描下性能差；放弃。
- **整体使用 zipline-reloaded + A 股 calendar 改写**：理论上可行，但 calendar / commission model / slippage model 都需要大改，工作量与自研 evaluator 接近，且仍要解决"逐 bar 求值轨迹"的暴露问题；放弃。
- **完全不引入任何第三方指标库**：除了 evaluator + execution，连 Sharpe / 最大回撤都自己算。被否：这些指标算法是标准化、已被充分验证的，自实现等于增加 bug 面，也没有竞争优势。

## 关联文档

- [ADR-0001 使用策略 DSL 作为核心契约](ADR-0001-strategy-dsl.md)
- [ADR-0002 历史标注与盲测回放必须分离](ADR-0002-separate-labeling-and-blind-replay.md)
- [TECH_STACK.md §6 数据科学与策略计算](../architecture/TECH_STACK.md)
- [PROJECT_STRUCTURE.md §5.4 packages/backtest-engine](../architecture/PROJECT_STRUCTURE.md)
- [03-backtest-validation](../product/modules/03-backtest-validation.md)
- [04-blind-replay](../product/modules/04-blind-replay.md)
- [05-execution-gap-diagnosis](../product/modules/05-execution-gap-diagnosis.md)
