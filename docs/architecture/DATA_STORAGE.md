# 数据存储与数据模型设计

本文定义 iQuant 的数据存储分层、核心表设计、时序行情方案与数据生命周期。

## 1. 存储分层

| 层 | 选型 | 承载 |
| --- | --- | --- |
| 业务主库 | PostgreSQL 16 | 用户、策略、回测元数据、盲测会话、诊断报告、AI 对话 |
| 时序行情 | PostgreSQL 分区表；可启用 TimescaleDB 扩展 | K 线、指标缓存、行情衍生时序 |
| 缓存 | Redis 7 | 热点读、会话推进游标、限流、分布式锁、轻量任务结果 |
| 对象存储 | S3 兼容（OSS / MinIO） | 回测明细 JSON、诊断报告快照、AI 长上下文、Parquet 冷数据 |
| 文件 | 仓库内 `storage/migrations`、`storage/seeds` | Alembic 迁移与种子数据 |

MVP 阶段优先使用单 PostgreSQL 实例承载业务数据和行情数据，通过 schema、分区表、索引和连接池隔离降低复杂度。只有当行情数据量、慢查询或连接池争用明确影响业务路径时，才将行情库物理拆分。

拆分触发条件：

- 行情表数据量 > 200GB。
- 行情查询导致业务库 CPU 持续 > 60%。
- 行情查询慢查询占比连续 3 天 > 20%。
- 行情导入任务影响业务写入延迟。

## 2. 命名与建模规范

- 表名小写下划线、单数（`user`、`strategy`、`backtest_report`）。冲突关键字必须加 `_v2`，禁止改名。
- 主键：业务实体使用 `ULID` 或 `UUIDv7`（时间有序），便于分页与冷热分离。无业务语义的关联表可用自增 `bigint`。
- 时间：所有时间字段使用 `timestamptz`，写入端统一 UTC，展示端在小程序侧本地化。
- 软删除：默认 `deleted_at timestamptz null`；不允许物理删除业务表数据，除非合规要求。
- 审计：所有写入主体表均带 `created_at` / `updated_at` / `created_by` / `updated_by`。
- 枚举：用 `varchar(32)` + 应用层枚举校验，避免 PG 原生 enum 改动成本。
- JSON：策略 DSL、报告明细等结构允许使用 `jsonb`，必须配合 Pydantic 模型与 GIN 索引。

## 3. 核心实体（业务主库）

### 3.1 用户与账户

```text
user
  id (ulid, pk)
  openid (varchar, unique, idx)        微信 openid
  unionid (varchar, nullable, idx)
  nickname (varchar)
  avatar_url (text)
  status (varchar)                     active / disabled / banned
  risk_acknowledged_at (timestamptz)
  created_at / updated_at / deleted_at
```

```text
user_profile
  user_id (fk -> user.id, pk)
  experience_level (varchar)           beginner / intermediate / advanced
  preferred_markets (jsonb)            A 股 / 港股 / ...
  preferred_periods (jsonb)            ['day','30m']
  updated_at
```

```text
auth_session
  id (ulid, pk)
  user_id (fk)
  refresh_token_hash (varchar)
  device_info (jsonb)
  expires_at (timestamptz, idx)
  revoked_at (timestamptz)
  created_at
```

会话上下文走 Redis，`auth_session` 仅作 refresh token 与设备审计。

### 3.2 标的与行情元数据

```text
symbol
  id (ulid, pk)
  code (varchar, unique idx)           '600519.SH'
  market (varchar)                     SH / SZ / HK / US
  name (varchar)
  asset_type (varchar)                 stock / etf / index
  list_date (date)
  delist_date (date, nullable)
  metadata (jsonb)                     行业、板块、停牌段等
  created_at / updated_at
```

K 线本体放 TimescaleDB，详见 §4。

### 3.3 盲测与样本（主路径 · 方案 A）

产品主路径见 [ADR-0011](../decisions/ADR-0011-blind-replay-primary-strategy-path.md)。规划表（实现随迭代 1 落地）：

```text
blind_session
  id, user_id, full_code, period, range_start, range_end
  status, strategy_id (nullable，对照 DSL 阶段使用)
  visible_cursor, created_at / updated_at

blind_action
  id, session_id, bar_time, user_action (buy/sell/hold)
  features_snapshot (jsonb), strategy_signal (nullable)
  user_reason, confidence

consistency_report
  user_id, period, scores_json, insights_json, created_at

strategy / strategy_version   # 见 §3.4
```

### 3.4 开卷标注（辅助 · 已实现）

`label_*` 表用于对照/补录，**不得**作为生成主策略的默认输入。见 [01 历史 K 线标注](../product/modules/01-historical-labeling.md)。

```text
label_session
  id (uuid, pk)
  admin_user_id (int, fk, nullable)    迭代 1 管理员；预留 user_id
  full_code (varchar)
  period (varchar)
  title (varchar, nullable)
  idempotency_key (varchar, nullable)
  created_at / updated_at
```

```text
label_pair
  id (uuid, pk)
  session_id (fk, idx)
  sort_order (int)
  buy_bar_time / sell_bar_time (timestamptz)
  buy_close / sell_close (numeric)
  return_pct (numeric)
```

```text
label_batch
  id (uuid, pk)
  admin_user_id (int)
  period, market_filter, batch_size
  status (varchar)                     active / completed
  completed_at (timestamptz, nullable)
```

```text
label_queue_item
  id (uuid, pk)
  batch_id (fk)
  sort_order, full_code, symbol_name
  status (varchar)                     pending / completed / skipped
  session_id (fk, nullable)
  skip_reason (varchar, nullable)
```

```text
label_batch_summary
  batch_id (uuid, pk, fk)
  stats_json, profile_draft (text)
  insights_json, correction_options_json, user_corrections_json
```

盲测域与标注域**分表、分 API**（[ADR-0002](../decisions/ADR-0002-separate-labeling-and-blind-replay.md)）。行为策略 DSL 由 **blind** 样本归纳，不由 `label_pair` 默认驱动。

### 3.5 策略 DSL 与版本

```text
strategy
  id (ulid, pk)
  user_id (fk, idx)
  name (varchar)
  symbol_id (fk)
  period (varchar)
  status (varchar)                     draft / active / archived
  current_version_id (fk -> strategy_version.id, nullable)
  created_at / updated_at / deleted_at
```

```text
strategy_version
  id (ulid, pk)
  strategy_id (fk, idx)
  version_no (integer)                 自增版本号
  dsl_schema_version (varchar)         DSL schema 版本
  dsl_payload (jsonb)                  完整 DSL
  derived_from_blind_profile_id (fk, nullable)   # 一致性/归纳批次；label 仅辅助对照
  ai_revision_of (fk, nullable)        若来自 AI 修改建议
  hash (varchar, idx)                  规范化 DSL 的内容哈希，用于幂等
  created_at
  unique(strategy_id, version_no)
```

`strategy_version` 不可变；任何修改创建新版本。`strategy.current_version_id` 指向当前激活版本。

### 3.6 回测任务与报告

```text
backtest_task
  id (ulid, pk)                        与 Celery task_id 同源
  user_id (fk, idx)
  strategy_version_id (fk, idx)
  params (jsonb)                       回测区间、滑点、手续费、初始资金
  status (varchar)                     queued / running / succeeded / failed / cancelled
  idempotency_key (varchar, unique idx) 业务幂等键
  enqueued_at / started_at / finished_at
  error_code (varchar, nullable)
  created_at
```

```text
backtest_report
  id (ulid, pk)
  task_id (fk, unique idx)
  strategy_version_id (fk, idx)
  summary (jsonb)                      收益、回撤、胜率、Sharpe 等关键指标
  detail_object_key (text)             对象存储路径，明细 JSON 太大不入库
  data_window (jsonb)                  样本内/样本外窗口
  warnings (jsonb)                     过拟合、数据质量、参数敏感性提示
  created_at
```

`backtest_report.detail_object_key` 指向 OSS 上的明细 JSON（交易流水、每日资金曲线等）。

### 3.7 盲测会话与操作（实现命名）

> 与 §3.3 规划对应；表名实现阶段可用 `replay_*` 或 `blind_*`，须统一 `source=blind_replay`。

```text
replay_session
  id (ulid, pk)
  user_id (fk, idx)
  strategy_version_id (fk, idx)
  symbol_id (fk)
  period (varchar)
  range_start (timestamptz)
  range_end (timestamptz)
  cursor_time (timestamptz)            当前已暴露的最后一根 K 线时间
  status (varchar)                     active / paused / finished / abandoned
  visibility_seed (varchar)            随机种子，避免可预测剧透
  source (varchar)                     blind_replay                          -- 与标注严格区分
  created_at / updated_at
```

```text
replay_event
  id (ulid, pk)
  session_id (fk, idx)
  occurred_at (timestamptz)            服务器收到时间
  visible_until (timestamptz)          当时可见 K 线截止
  kind (varchar)                       step / buy / sell / hold / abort
  payload (jsonb)                      价格、数量、备注
  visible_snapshot_hash (varchar)      可见 K 线哈希，便于复核
  created_at
```

写入只追加；任何"撤销"必须新增反向事件而不是物理删除。

### 3.8 执行诊断报告

```text
diagnosis_task
  id (ulid, pk)
  replay_session_id (fk, idx)
  status (varchar)
  enqueued_at / finished_at
  error_code (varchar, nullable)
```

```text
diagnosis_report
  id (ulid, pk)
  task_id (fk, unique idx)
  replay_session_id (fk, unique idx)
  strategy_version_id (fk, idx)
  signal_execution_rate (numeric)
  off_signal_entry_rate (numeric)
  early_exit_rate (numeric)
  stoploss_compliance_rate (numeric)
  discipline_score (numeric)
  loss_attribution (jsonb)
  recommendations (jsonb)
  detail_object_key (text)
  created_at
```

### 3.9 训练任务与进度

```text
training_plan
  id (ulid, pk)
  user_id (fk, idx)
  source_diagnosis_id (fk, nullable)
  focus (jsonb)                        重点偏差类型与目标
  status (varchar)                     active / paused / done
  created_at / updated_at
```

```text
training_session
  id (ulid, pk)
  plan_id (fk, idx)
  replay_session_id (fk, nullable)     训练通常关联一次盲测
  outcome (jsonb)                      与上次对比的关键指标变化
  created_at
```

### 3.10 AI 对话与上下文

```text
ai_conversation
  id (ulid, pk)
  user_id (fk, idx)
  topic (varchar)                      strategy_explain / backtest_review / diagnosis_review / chat
  context_refs (jsonb)                 引用的 strategy_version_id、backtest_report_id 等
  status (varchar)
  created_at / updated_at
```

```text
ai_message
  id (ulid, pk)
  conversation_id (fk, idx)
  role (varchar)                       user / assistant / system / tool
  content (text)
  structured_output (jsonb, nullable)  AI 必须结构化返回的部分
  prompt_version (varchar)
  model_name (varchar)
  tokens_in / tokens_out (int)
  moderation_result (jsonb)
  created_at
```

### 3.11 预警准备（V0.6 起）

```text
alert_rule
  id (ulid, pk)
  user_id (fk, idx)
  strategy_version_id (fk)
  symbol_id (fk)
  channel (varchar)                    wechat_subscribe / inapp
  status (varchar)
  created_at / updated_at
```

```text
alert_event
  id (ulid, pk)
  rule_id (fk, idx)
  triggered_at (timestamptz, idx)
  signal_payload (jsonb)
  delivery_status (varchar)
  created_at
```

## 4. 时序行情

MVP 行情数据默认与业务库同实例，通过独立 schema 和分区表管理；可在同实例启用 TimescaleDB 扩展。当触发拆分条件后，再迁移到独立 TimescaleDB 实例。

### 4.1 表设计

```text
market_bar
  symbol_id (fk)
  period (varchar)                     day / 60m / 30m / 15m / 5m
  bar_time (timestamptz)
  open / high / low / close (numeric)
  volume (numeric)
  amount (numeric)
  adj_factor (numeric)                 复权因子
  source (varchar)                     数据源标识
  ingested_at (timestamptz)
  primary key (symbol_id, period, bar_time)
```

- 如果启用 TimescaleDB，通过 `create_hypertable` 按 `bar_time` 分区。
- 如果暂不启用 TimescaleDB，使用 PostgreSQL 原生 range partition，按月或季度分区。
- MVP 不做全市场高频分钟线，只保留核心标的和有限周期，避免早期数据膨胀。
- 旧分区开启压缩或迁移到对象存储 Parquet。
- 复合主键保证幂等导入。

### 4.2 指标缓存

```text
indicator_cache
  symbol_id
  period
  indicator_code (varchar)             MA20 / MACD / ATR / ...
  params_hash (varchar)
  bar_time
  value (jsonb)                        允许多列指标
  computed_at (timestamptz)
  primary key (symbol_id, period, indicator_code, params_hash, bar_time)
```

仅缓存计算昂贵或被频繁请求的指标。轻量指标即用即算。

### 4.3 行情写入路径

- 拉取：定时任务从供应商或本地 Parquet 增量写入。
- 校验：写入前比对前后值连续性、异常 spike，发现异常进入 `market_bar_anomaly` 表人工复核。
- 复权：仅在 `adj_factor` 变更时回算，避免每次查询都做复权。

## 5. 对象存储路径约定

```text
oss://iquant-prod/
  backtest/
    {user_id}/{report_id}/detail.json
    {user_id}/{report_id}/equity_curve.parquet
  diagnosis/
    {user_id}/{report_id}/detail.json
  ai/
    {user_id}/{conversation_id}/context-{seq}.json
  market/
    parquet/{period}/{symbol_id}/{yyyy}.parquet
  ops/
    audit-logs/{yyyy}/{mm}/{dd}.jsonl
```

约束：

- 路径含 `user_id`，便于按用户清理。
- 业务读取时通过预签名 URL，禁止直接公开桶。
- 大文件不入主库；主库只存对象 key。

## 6. 索引与查询模式

### 6.1 通用约束

- 任何 user 维度查询：必须能命中 `(user_id, created_at desc)` 或 `(user_id, status)` 索引。
- 任何"列表分页"接口：必须用 keyset 分页（基于 `id` 或 `created_at`），禁止 `OFFSET N`。
- 任何 `jsonb` 上的过滤：必须有 GIN 索引或局部表达式索引；无索引的 `jsonb` 过滤禁止上线。
- 高频写表（标注、盲测事件、AI 消息）：避免次要索引过多，必要时只保留主键 + 时间序索引。

### 6.2 典型索引清单

```text
user:                  (openid), (unionid)
strategy:              (user_id, status, updated_at desc)
strategy_version:      (strategy_id, version_no desc), (hash)
backtest_task:         (user_id, status, enqueued_at desc), (idempotency_key)
backtest_report:       (strategy_version_id, created_at desc)
replay_session:        (user_id, status, updated_at desc), (strategy_version_id)
replay_event:          (session_id, occurred_at)
diagnosis_report:      (replay_session_id), (strategy_version_id, created_at desc)
ai_conversation:       (user_id, updated_at desc)
ai_message:            (conversation_id, created_at)
market_bar:            主键 (symbol_id, period, bar_time)
indicator_cache:       主键，及 (symbol_id, period, indicator_code, bar_time desc)
```

## 7. 事务与一致性

- 写入主体表必须用单一事务包住相关附属表（如 `replay_session` + `replay_event` 在同一事务）。
- 长事务禁止跨网络 I/O（HTTP 调用、大模型调用必须在事务外）。
- 分布式一致性：跨服务的写不能要求强一致，使用任务队列 + 幂等键 + 事件最终一致。
- 任务幂等：所有 Celery 任务接收 `idempotency_key`，重复入队必须不产生重复结果。

## 8. 数据迁移

- Alembic 管理所有 DDL。
- 一次迁移只做一件事；不允许"改表 + 改数据 + 改约束"同迁移。
- 在线 DDL 必须可向后兼容：先加列（nullable）→ 灰度写入 → 回填 → 切换读取 → 删旧列。
- 大表索引创建走 `CONCURRENTLY`，并在维护窗口执行。
- 任何破坏性迁移必须有回滚脚本。

## 9. 数据生命周期与归档

| 数据 | 保留策略 |
| --- | --- |
| K 线 | 永久；超过 1 年自动压缩，超过 5 年迁移到对象存储 Parquet |
| 标注/策略 | 永久；用户主动删除走软删除 |
| 回测元数据 | 永久；明细 JSON 默认 90 天，"收藏"延长到 2 年 |
| 盲测会话与事件 | 永久；为用户成长曲线核心数据 |
| 诊断报告 | 永久；明细同回测策略 |
| AI 对话 | 默认 30 天，用户主动归档可延长；审核日志 180 天 |
| 操作日志 | 90 天热存，180 天冷存 |

所有清理由 Celery Beat 定时任务执行，必须有 dry-run 模式。

## 10. 备份与恢复

- 业务主库：每天全量备份 + 增量 WAL；备份保留 30 天。
- 时序库：每天全量备份；旧分区由压缩 + 对象存储归档兜底。
- 对象存储：开启版本控制 + 跨区域复制（生产）。
- 演练：每季度演练全量恢复，记录 RTO/RPO 实测值。

恢复目标：

- RTO（恢复时间）：业务主库 ≤ 1 小时。
- RPO（最大数据丢失）：业务主库 ≤ 5 分钟，时序库 ≤ 24 小时。

## 11. 多租户与隔离

- MVP 单租户（C 端）：所有数据按 `user_id` 维度隔离，禁止跨用户查询。
- 行级隔离：所有用户数据查询入口必须在 `services/*` 层强制注入 `user_id` 条件。
- 后续 B 端（培训机构）扩展：预留 `tenant_id`，应用层启用行级安全策略。

## 12. 数据契约与外部交互

- 行情供应商：通过 `packages/market-data/adapters/*` 抽象，业务代码不依赖具体协议。
- 微信开放平台：通过 `services/auth-service`（或单体内同名模块）封装 openid/unionid 换取与刷新。
- AI 供应商：通过 `packages/ai-assistant` 抽象，业务侧只看到 Prompt 输入与结构化输出。
- 内部模块：通过领域模型（DSL、报告、事件），不通过对方数据库表。
