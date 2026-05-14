# ADR-0006 时序行情采用 PostgreSQL + TimescaleDB

## 背景

iQuant 需要存储多周期 K 线（日 / 60m / 30m / 15m / 5m）以及指标缓存。10 万用户量级、5000+ 标的、多年历史的数据规模在亿行量级（详见 [CAPACITY_PLANNING.md](../architecture/CAPACITY_PLANNING.md)）。

诉求：

- 高吞吐写入（每日盘后批量增量）。
- 高效时间范围查询（典型查询：某 symbol + 周期 + 时间窗口）。
- 自动分区与冷热压缩，降低运维成本。
- 与业务主库（PostgreSQL）技术栈一致，便于团队复用。
- 易于回放、补数、复权重算等离线操作。

## 决策

时序行情库采用 PostgreSQL 16 + TimescaleDB 扩展，物理实例与业务主库分离。

具体落地：

- 行情表通过 `create_hypertable` 按 `bar_time` 分区，chunk 区间按周期选择（高频周期更短，日线更长）。
- 旧分区开启原生压缩与按 (symbol_id, period) 聚簇。
- 指标缓存表同样使用 hypertable，按 `(symbol_id, period, indicator_code, params_hash, bar_time)` 主键。
- 行情读写仅通过 `packages/market-data` 抽象层，业务代码与具体扩展解耦。

## 影响

- 业务主库不承担时序大表压力，连接池与备份策略独立。
- TimescaleDB 不在所有云厂商托管 RDS 中默认开启，需选择支持该扩展的产品或自建（KingbaseES / 阿里云 PG / 自建 K8s StatefulSet）。
- 升级 PostgreSQL 主版本时需同步评估 TimescaleDB 兼容版本。
- 备份与恢复需覆盖 hypertable 元数据，演练必须验证。
- 团队需要补一份 TimescaleDB 维护手册（压缩策略、连续聚合、保留策略）。

## 备选方案

- **ClickHouse**：列存吞吐强，但与 PG 生态割裂，事务能力弱，增加运维栈复杂度。
- **InfluxDB**：与 PG 模型差异大，团队学习成本高，且 OSS 版本能力受限。
- **MongoDB 时序集合**：与现有 PG 业务模型割裂，且 MVP 阶段引入 NoSQL 无足够收益。
- **Parquet on Object Storage + DuckDB**：适合离线分析，不适合在线即席查询。

综合考虑：与现有 PG 栈兼容、生态成熟、运维曲线友好，选择 PostgreSQL + TimescaleDB。

## 关联文档

- [DATA_STORAGE.md §4](../architecture/DATA_STORAGE.md)
- [CAPACITY_PLANNING.md](../architecture/CAPACITY_PLANNING.md)
- [TECH_STACK.md](../architecture/TECH_STACK.md)
