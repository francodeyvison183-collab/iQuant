# services

业务服务层。

MVP 可以先采用单体后端，但服务职责应按模块边界组织：

- `strategy-service/`：策略生成、策略保存、版本管理。
- `backtest-service/`：回测任务和报告。
- `replay-service/`：盲测会话和用户操作。
- `diagnosis-service/`：执行偏差诊断。
- `ai-service/`：AI 解释、总结和训练建议。

服务层负责应用用例编排，核心算法放在 `packages/*`。

