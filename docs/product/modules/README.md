# 产品模块文档目录

本目录按高内聚、低耦合原则拆分 MVP 产品模块。

每个模块文档应独立说明：

- 模块目标
- 用户价值
- 输入与输出
- 功能范围
- 与其他模块的依赖关系
- 核心数据
- 指标与验收标准

## 模块列表

1. [历史 K 线标注](01-historical-labeling.md)
2. [理想策略生成](02-ideal-strategy-generation.md)
3. [回测验证](03-backtest-validation.md)
4. [近端历史盲测回放](04-blind-replay.md)
5. [执行偏差诊断](05-execution-gap-diagnosis.md)
6. [盲测训练](06-training.md)
7. [AI 策略助手](07-ai-assistant.md)
8. [策略库与预警准备](08-strategy-library-alerting-prep.md)
9. [数据与样本资产](09-data-and-sample-assets.md)
10. [微信小程序端体验](10-wechat-miniprogram-experience.md)

## 模块边界原则

- 历史标注模块只负责表达理想买卖点，不判断用户执行能力。
- 理想策略生成模块只基于历史标注生成策略，不混入盲测交易行为。
- 盲测回放模块只负责记录用户在隐藏未来走势下的实际操作。
- 执行偏差诊断模块负责对齐理想策略信号与盲测操作。
- AI 策略助手只解释、诊断和建议，不直接生成最终交易信号。
- 微信小程序端只做交互呈现和轻量状态管理，不承载策略、回测、诊断和 AI 核心计算。
- 策略 DSL 是模块间共享的核心契约。
