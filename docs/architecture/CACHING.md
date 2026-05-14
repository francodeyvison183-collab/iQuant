# 缓存策略

本文定义 iQuant 服务端的缓存使用规范：用途、键设计、失效、保护策略。所有缓存默认走 Redis，必要时辅以进程内 LRU 与 CDN。

## 1. 缓存目的

按目的分类，每类有不同的设计偏好：

| 类别 | 目的 | 典型场景 |
| --- | --- | --- |
| 读加速 | 降低数据库压力与响应时间 | K 线读取、策略详情、用户资料 |
| 状态共享 | 跨进程共享会话/游标状态 | 盲测推进游标、AI 对话最近 N 轮 |
| 限流与配额 | 滑动窗口/令牌桶 | API 限流、用户回测配额 |
| 任务协调 | 分布式锁、幂等校验 | Celery 任务幂等、定时任务领导选举 |
| 防穿透/防击穿 | 保护底层存储 | 空值缓存、热点重建锁 |

## 2. 缓存层级

```text
client(小程序) → CDN → Nginx 静态缓存 → 进程内 LRU → Redis → DB
```

- CDN：仅缓存可公开静态资源、行情 Parquet 快照、版本化报告快照。
- Nginx：极少使用，作为短期防雪崩缓冲（5 ~ 30 秒）。
- 进程内 LRU：缓存稳定且高频读的小对象（Symbol 元数据、DSL schema 版本），TTL 短（≤ 60 秒）以避免发布不一致。
- Redis：业务主缓存层，承担绝大多数缓存职责。

## 3. 键设计规范

- 命名空间前缀强制：`{env}:{service}:{purpose}:{...}`。
- 例：`prod:backtest:summary:{strategy_version_id}`。
- 不使用空格、不可控字符；变长部分必须可哈希。
- 用户维度的键必须含 `user_id`，便于按用户失效与隔离。
- 涉及版本的资源键必须带版本号或内容哈希，避免发布污染老缓存。

### 3.1 常用键模板

| 用途 | 键 | 值 | TTL |
| --- | --- | --- | --- |
| 用户资料 | `prod:user:profile:{user_id}` | JSON | 10 分钟 |
| openid → user_id 映射 | `prod:user:openid:{openid}` | user_id | 1 天 |
| Symbol 元数据 | `prod:symbol:meta:{code}` | JSON | 1 小时 |
| K 线（窗口） | `prod:bar:{period}:{symbol_id}:{from_ts}:{to_ts}:{adj_v}` | bytes | 1 小时 |
| 指标缓存 | `prod:ind:{indicator}:{params_hash}:{symbol_id}:{period}:{to_ts}` | JSON | 1 小时 |
| 策略版本 | `prod:strategy:ver:{version_id}` | JSON | 1 天 |
| 回测摘要 | `prod:backtest:sum:{report_id}` | JSON | 7 天 |
| 盲测可见游标 | `prod:replay:cursor:{session_id}` | timestamp | 2 小时（活跃续期） |
| 盲测会话锁 | `prod:replay:lock:{session_id}` | owner | 5 秒 |
| AI 最近上下文 | `prod:ai:ctx:{conversation_id}` | JSON 数组 | 1 小时 |
| 限流：用户 API | `prod:rl:user:{user_id}:{endpoint}` | 计数 | 60 秒滚动 |
| 限流：用户配额 | `prod:quota:backtest:{user_id}:{yyyymmdd}` | 计数 | 24 小时 |
| 幂等键 | `prod:idem:{endpoint}:{key}` | result_ref | 24 小时 |
| 分布式锁 | `prod:lock:{resource}` | owner | 业务定 |
| Beat 领导锁 | `prod:beat:leader` | owner | 30 秒 |

`adj_v` 是复权因子版本号；复权因子刷新时整体 K 线键失效。

## 4. 失效策略

### 4.1 TTL 是默认

- 任何缓存键必须有显式 TTL，禁止使用 `EXPIRE -1`。
- TTL 长度：可重算的纯读缓存 ≤ 1 小时，跨用户共享元数据可到 1 天，业务报告类（写后基本不变）可到 7 天。

### 4.2 主动失效

- 写入数据后必须主动 `DEL` 相关键，TTL 兜底但不依赖。
- 多键失效：使用受控的"失效函数"集中维护键名规则，避免散落字符串拼接。
- 集合失效：避免使用 `KEYS pattern` 扫描（生产严禁）；改用维护版本号或显式索引集合。

例如策略版本更新时：

```python
async def invalidate_strategy_version(version_id: str):
    keys = [
        f"prod:strategy:ver:{version_id}",
        f"prod:strategy:current:{version_id}",
    ]
    await redis.delete(*keys)
```

### 4.3 版本前缀

对集体失效成本高的资源使用版本号：

- 应用启动时读取 `prod:meta:cache_ver:symbol`，作为 Symbol 元数据键的前缀。
- 行情元数据大变更时只需 `INCR` 版本号，旧键自然 TTL 过期。

## 5. 缓存模式

| 模式 | 适用 | 说明 |
| --- | --- | --- |
| Cache-Aside（旁路缓存） | 默认 | 业务先查缓存，未命中查 DB，回写缓存 |
| Write-Through | 极少 | 仅在频繁写但读取也频繁的明确热点上使用 |
| Write-Behind | 禁用 | MVP 不引入，复杂度过高 |
| Read-Through | 通过装饰器 | 在 service 层用统一的"缓存装饰器"封装 cache-aside |

封装示例：

```python
@cached(
    key=lambda r: f"prod:backtest:sum:{r}",
    ttl=timedelta(days=7),
    null_ttl=timedelta(seconds=30),
)
async def get_backtest_summary(report_id: str) -> BacktestSummary:
    return await repo.get_summary(report_id)
```

## 6. 防护：穿透 / 击穿 / 雪崩

### 6.1 缓存穿透

- 对"查不到"的结果也短期缓存（空值缓存 30 秒，键标记为 `__null__`）。
- 对查询参数做合法性校验，避免恶意构造未知 ID 透传到 DB。
- 用户输入触发的查询经过 ID 白名单或归属校验后才查缓存。

### 6.2 缓存击穿（热点 Key 失效瞬间高并发）

- 重建加锁：通过 Redis `SET NX EX 5` 拿构建锁，未拿到的请求等待短时再读缓存。
- 热点资源（明星策略、行情近端）显式预热与续期，避免 TTL 同时到期。

### 6.3 缓存雪崩（大量键同时过期）

- 所有 TTL 加 ±10% 抖动（jitter），避免集体过期。
- 关键基础数据双层缓存：进程内 LRU + Redis；Redis 抖动时进程内兜底。
- 应用启动时禁止"上来就清缓存"，按需懒加载。

## 7. 一致性约束

- 缓存与 DB 一致性优先采用"先写库再删缓存"。
- 失败补偿：删除缓存失败必须重试（最多 3 次）；最终失败入异步重试队列。
- 不允许"先删缓存再写库"：极端竞态下可能写回旧值。
- 涉及强一致性的金额/订单类操作（MVP 没有），缓存仅作只读快照。

## 8. 限流与配额

- 单接口限流：滑动窗口（Redis `ZADD` + `ZREMRANGEBYSCORE` 或 token bucket）。
- 用户配额：日维度 `INCR` + `EXPIRE` 实现。
- 全局配额：Lua 脚本保证原子。
- 限流命中：返回 429 + `Retry-After`，并打 metric `rl.hit.{endpoint}`。

## 9. 分布式锁

- Redis 单实例锁：`SET NX EX <ttl>` + 唯一 owner token，释放时校验 token。
- 长事务锁：禁止跨网络 I/O 拿着锁；锁持有时间 ≤ 5 秒。
- 跨实例临界区少而精；优先用数据库唯一约束实现幂等。
- Beat 领导选举：用 Redis 锁 + 心跳续期，租约 30 秒。

不引入 Redlock（多实例 Redis）：MVP 单 Redis 主从足够，避免实现复杂性。

## 10. 进程内缓存

- 仅缓存"稳定不变 + 高频读 + 小体积"的数据。
- TTL ≤ 60 秒，且在 worker 启动时不预热（避免 cold start 暴涨）。
- 内存上限：每进程 ≤ 200 MB，超限按 LRU 淘汰。
- 内存敏感模块（worker）必须能通过开关一键禁用进程内缓存。

候选缓存项：

- DSL schema 解析器实例。
- Symbol 元数据（小集合）。
- 指标计算器实例。

## 11. CDN 与浏览器缓存

- 静态资源（图片、字体）走 CDN，文件名带 hash 永久缓存。
- 公开 K 线快照（教学用样本）以 Parquet 形式放对象存储 + CDN，`Cache-Control: public, max-age=3600`。
- 私有报告快照禁止走 CDN，必须经过鉴权与签名 URL。

## 12. 缓存监控

| 指标 | 说明 |
| --- | --- |
| `cache.hit` / `cache.miss` | 按 key prefix 切片 |
| `cache.set` | 缓存写入速率 |
| `cache.evict` | Redis 内存压力指标 |
| `cache.fill_latency` | 未命中后回填耗时 |
| `cache.null_ratio` | 空值缓存比例，过高提示参数合法性问题 |
| `redis.memory_used` / `redis.keys` | 容量与键数 |

缓存命中率目标：

- 用户资料、Symbol、K 线：> 90%
- 策略 / 回测摘要：> 80%
- AI 上下文：> 60%（强相关用户行为）

## 13. 容量与运维

- Redis 实例内存 MVP 从 1 ~ 2 GB 起步；监控告警阈值 70% 内存。
- 当 Redis 内存或连接数接近上限时，优先扩容内存；再考虑主从；最后才分离 broker 与 cache。
- 单 key 大小 ≤ 256 KB；超过必须改用对象存储 + 引用。
- 单 hash/list/set 元素数 ≤ 10000；超过必须分桶。
- 大对象切片：例如 K 线窗口按 1 小时切分键，禁止单键巨大 array。
- 禁止 Redis 当持久存储；任何掉电数据丢失必须可由数据库重建。

## 14. 反例

- ❌ `KEYS *` 在生产环境扫描。
- ❌ 缓存 ORM session / 大对象 / 闭包。
- ❌ "查询失败默默返回空"导致前端误以为无数据。
- ❌ 多语言序列化混用（pickle + json + msgpack 共用一个键）。
- ❌ 跨用户共享键且不含 user_id（典型越权风险）。
- ❌ 使用 Redis 作为唯一真理源（持久化 + 业务唯一约束必须落 PG）。
