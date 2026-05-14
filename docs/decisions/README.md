# 架构决策记录

本目录用于记录重要架构和产品边界决策。

建议使用 ADR（Architecture Decision Record）格式：

- 背景
- 决策
- 影响
- 备选方案

## 已记录决策

- [ADR-0001 使用策略 DSL 作为核心契约](ADR-0001-strategy-dsl.md)
- [ADR-0002 历史标注与盲测回放必须分离](ADR-0002-separate-labeling-and-blind-replay.md)
- [ADR-0003 AI 不直接决定交易信号](ADR-0003-ai-boundary.md)
- [ADR-0004 微信小程序优先](ADR-0004-wechat-miniprogram-first.md)
- [ADR-0005 选择 FastAPI 作为后端 Web 框架](ADR-0005-fastapi-as-web-framework.md)
- [ADR-0006 时序行情采用 PostgreSQL + TimescaleDB](ADR-0006-timescaledb-for-market-data.md)
- [ADR-0007 异步任务采用 Celery](ADR-0007-celery-for-async-tasks.md)
- [ADR-0008 模块化单体起步，按需服务化](ADR-0008-modular-monolith-first.md)
