# 产品模块文档目录

本目录按高内聚、低耦合原则拆分 MVP 产品模块。

每个模块文档应独立说明：模块目标、用户价值、输入与输出、功能范围、依赖关系、核心数据、验收标准。

**产品主路径（方案 A）**：见 [ADR-0011](../../decisions/ADR-0011-blind-replay-primary-strategy-path.md)、[MVP 产品方案](../MVP_PRODUCT_PLAN.md)。

## 模块列表

| # | 模块 | 主路径 |
| --- | --- | --- |
| 04 | [近端历史盲测回放](04-blind-replay.md) | ✅ 核心 |
| 02 | [行为策略生成](02-ideal-strategy-generation.md) | ✅ |
| 03 | [回测验证](03-backtest-validation.md) | ✅ |
| 05 | [执行偏差诊断](05-execution-gap-diagnosis.md) | ✅（DSL 建立后） |
| 06 | [盲测训练](06-training.md) | ✅ |
| 07 | [AI 策略助手](07-ai-assistant.md) | ✅ |
| 01 | [历史 K 线标注](01-historical-labeling.md) | 辅助 |
| 08 | [策略库与预警准备](08-strategy-library-alerting-prep.md) | 支撑 |
| 09 | [数据与样本资产](09-data-and-sample-assets.md) | 支撑 |
| 10 | [微信小程序端体验](10-wechat-miniprogram-experience.md) | 端 IA |

## 模块边界原则

- **盲测回放**记录闭卷决策，是行为策略与一致性的唯一主输入。
- **行为策略生成**只消费 blind 样本（及用户确认），不默认消费开卷标注。
- **历史标注**仅作对照；数据与 blind 分源（ADR-0002）。
- **执行偏差诊断**：无 DSL 时输出一致性报告；有 DSL 时对齐信号与操作。
- **AI** 只解释与建议，不直接生成交易信号（ADR-0003）。
- **策略 DSL** 是模块间共享契约（ADR-0001）。
