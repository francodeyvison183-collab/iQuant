# 技术架构文档

本目录沉淀 iQuant 的技术架构、技术选型与工程规范。当前目标是 MVP 稳定支撑 1 万注册用户，并保留向 10 万用户平滑扩容的路径。

## 1. 阅读顺序

新成员建议按以下顺序阅读：

1. [项目目录结构规划](PROJECT_STRUCTURE.md)：理解代码组织。
2. [技术规划优化审查](TECHNICAL_OPTIMIZATION_REVIEW.md)：理解为什么 MVP 先按 1 万用户、简单高性能设计。
3. [技术栈选型](TECH_STACK.md)：理解我们用什么、为什么。
4. [系统架构总览](SYSTEM_ARCHITECTURE.md)：理解模块、依赖、数据流。
5. [容量规划与性能目标](CAPACITY_PLANNING.md)：理解 1 万用户 MVP 的容量假设和扩容路径。
6. [数据存储设计](DATA_STORAGE.md)：理解数据库选型、数据生命周期和拆分触发条件。
7. [API 设计规范](API_DESIGN.md)：理解接口风格、版本、错误约定。
8. [异步任务与消息队列](ASYNC_TASKS.md)：理解回测、诊断、AI 等重活如何编排。
9. [缓存策略](CACHING.md)：理解 Redis 用法、缓存失效、热点保护。
10. [安全与合规](SECURITY_AND_COMPLIANCE.md)：理解鉴权、风控、合规边界。
11. [可观测性](OBSERVABILITY.md)：理解日志、指标、追踪、告警。
12. [部署与基础设施](DEPLOYMENT.md)：理解环境、CI/CD、部署和扩容。
13. [Python 工程目录规范](PYTHON_PROJECT_LAYOUT.md)：理解仓库内 Python 代码摆放规则。

## 2. 文档分工

| 文档 | 关注点 | 目标读者 |
| --- | --- | --- |
| `PROJECT_STRUCTURE.md` | 仓库整体目录、模块边界 | 全员 |
| `TECHNICAL_OPTIMIZATION_REVIEW.md` | MVP 技术规划审查与优化结论 | 全员 |
| `TECH_STACK.md` | 框架、组件、版本约束 | 全员 |
| `SYSTEM_ARCHITECTURE.md` | 模块、调用关系、数据流 | 后端、架构师 |
| `CAPACITY_PLANNING.md` | 用户量、QPS、资源预算 | 后端、SRE、产品 |
| `DATA_STORAGE.md` | 表设计、时序数据、冷热分离 | 后端、DBA |
| `API_DESIGN.md` | REST 风格、错误码、版本 | 后端、前端、小程序 |
| `ASYNC_TASKS.md` | 任务编排、幂等、重试 | 后端 |
| `CACHING.md` | 缓存模型、失效、击穿/穿透 | 后端 |
| `SECURITY_AND_COMPLIANCE.md` | 鉴权、风控、内容审核 | 后端、合规 |
| `OBSERVABILITY.md` | 日志、指标、追踪、告警 | 后端、SRE |
| `DEPLOYMENT.md` | 环境、容器、CI/CD、发布 | 后端、SRE |
| `PYTHON_PROJECT_LAYOUT.md` | Python 包/模块/依赖管理 | 后端 |

## 3. 设计总原则

- **业务正确性优先于性能**：策略、回测、诊断的语义正确性不可妥协，性能在此前提下优化。
- **核心计算下沉到包层**：`packages/*` 不依赖 Web 框架与基础设施，方便测试、迁移和水平扩展。
- **服务无状态**：API 进程不持有任何用户会话状态，所有持久与共享状态收敛到 PostgreSQL / Redis / 对象存储。
- **重任务异步化**：回测、特征提取、AI 调用、报告渲染等耗时操作走任务队列，HTTP 端只返回任务句柄。
- **数据契约优先于实现**：模块通过 DSL、报告、操作记录等稳定 schema 协作，而不是相互直读对方的表。
- **可观测性内建**：每条业务链路都要可追踪、可计量、可复现，否则就算"还没上线"。
- **小步迭代、单体起步**：MVP 阶段采用模块化单体，先支撑 1 万注册用户；按依赖方向预留服务化和横向扩容路径。
- **不提前复杂化**：Kubernetes、独立 TimescaleDB、RabbitMQ、只读副本、分库分表都必须由真实容量瓶颈触发。
- **优先选择成熟生态**：Python 后端优先 FastAPI + SQLAlchemy 2.x + Celery + PostgreSQL + Redis，避免堆砌冷门组件。

## 4. 关联文档

- 产品方案：[MVP 总体产品方案](../product/MVP_PRODUCT_PLAN.md)
- 产品模块：[产品模块文档目录](../product/modules/README.md)
- 架构决策：[架构决策记录](../decisions/README.md)
- 接口契约：[API 文档](../api/README.md)
