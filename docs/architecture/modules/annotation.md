# 历史 K 线标注（annotation-service）— 辅助能力

> **非主路径**。产品主流程见 [ADR-0011](../../decisions/ADR-0011-blind-replay-primary-strategy-path.md)、[04 盲测回放](../../product/modules/04-blind-replay.md)。

产品定义：[01 历史 K 线标注](../../product/modules/01-historical-labeling.md)（辅助）。

## 边界

| 层 | 位置 | 职责 |
| --- | --- | --- |
| 用例 + ORM | `services/annotation-service` | 开卷 `label_*` 样本 |
| HTTP | `apps/api/routes/v1/labels.py` | `/api/v1/labels/*` |
| 行情 | `market-service` | 只读 `query_bars` |

**禁止**：`strategy-service` 默认从 `label_*` 生成主策略 DSL（见 ADR-0011）。

## 数据表

`label_session`、`label_pair`、`label_batch`、`label_queue_item`、`label_batch_summary`。

## 维护说明

已实现批次标注与轮次总结；H5 入口应标为「高级 / 对照」。新功能优先投入 `blind-replay-service`。
