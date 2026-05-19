# 09 数据与样本资产模块

版本：V0.2（方案 A）

## 1. 模块定位

管理行情、**盲测操作**、行为策略 DSL、回测报告、一致性/诊断报告及（辅助）开卷标注样本。

## 2. 用户价值

- 样本与策略可追溯、可版本化。
- `blind_replay` 与 `historical_labeling` 严格分源。
- 支撑回测、一致性评估与执行诊断。

## 3. 核心数据类型

| 数据类型 | 说明 |
| --- | --- |
| MarketBar | K 线 |
| BlindReplaySession | 盲测会话（主路径） |
| BlindReplayAction | 盲测操作 + features_snapshot |
| ConsistencyReport | 跨轮一致性（可 JSON 落库） |
| StrategyDSL | 行为策略（用户确认后） |
| BacktestReport | 回测报告 |
| OptimizationSuggestion | 优化建议记录（关联 DSL 版本与回测 id） |
| ExecutionDiagnosisReport | 执行偏差（DSL vs blind） |
| TrainingTask | 专项训练 |
| HistoricalLabelTrade | 开卷标注（辅助，`label_*`） |

## 4. 关键原则

### 4.1 来源必须明确

```text
blind_replay:           主路径 — 行为策略归纳、一致性评估
historical_labeling:    辅助 — 对照/补录，禁止生成主策略
```

### 4.2 策略版本不可覆盖

DSL 参数变更 → 新版本 + 新回测。

### 4.3 报告可追溯

回测/诊断/一致性报告均关联：用户、策略版本（如有）、数据区间、规则版本。

## 5. 验收标准

- [ ] 所有样本 `source` 可审计。
- [ ] blind 不会被误标为 labeling；label 不会进入默认 `generate_from_blind` 路径。
