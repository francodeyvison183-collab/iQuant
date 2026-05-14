# packages

领域能力包层。

这里沉淀可复用、高内聚、低耦合的核心能力，例如：

- `domain/`：领域模型。
- `strategy-dsl/`：策略 DSL 解析、校验和版本迁移。
- `indicators/`：技术指标计算。
- `backtest-engine/`：回测引擎。
- `replay-engine/`：盲测回放引擎。
- `diagnosis-engine/`：执行偏差诊断引擎。
- `ai-assistant/`：AI 解释、诊断和训练建议。
- `market-data/`：行情数据适配。

包层不应依赖 `apps/*`。

