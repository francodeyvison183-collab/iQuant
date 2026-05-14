# ADR-0005 选择 FastAPI 作为后端 Web 框架

## 背景

iQuant 服务端需要在 10 万注册用户量级提供 REST API，并满足：

- 高 I/O 并发（K 线读取、行情代理、AI 调用）。
- 强类型契约，便于小程序端类型生成。
- 良好 OpenAPI 支持，便于接口治理。
- 与 Python 生态、Pydantic v2、SQLAlchemy 2.x 异步栈协作顺畅。

## 决策

后端 Web 框架统一采用 FastAPI（基于 Starlette / anyio），生产用 Gunicorn + UvicornWorker 多进程部署。

## 影响

- 所有 HTTP 路由必须用 FastAPI Router 组织，统一 OpenAPI 自动生成。
- 入出参强制使用 Pydantic v2 模型；禁止裸 dict。
- 异步路径：FastAPI + asyncpg + redis-py async + httpx，全链路 async。
- CPU 密集计算不在 Web 进程内同步执行，必须走 Celery worker。
- 接口契约纳入版本管理：CI 导出 `docs/api/openapi.yaml`，破坏性变更在 PR 检出。

## 备选方案

- **Django + DRF**：模板/Admin 强，但同步默认、异步生态相对弱，与时序数据场景吻合度一般。
- **Flask**：上下文模式不利于显式依赖注入，类型与 OpenAPI 支持需要大量第三方拼装。
- **Sanic / Litestar**：异步可用，但社区与文档不如 FastAPI 稳定。
- **gRPC 优先**：与微信小程序端协议不匹配，且会显著增加端侧成本。

综合社区成熟度、团队熟悉度与生态契合度，选择 FastAPI 作为唯一 Web 框架。

## 关联文档

- [TECH_STACK.md](../architecture/TECH_STACK.md)
- [API_DESIGN.md](../architecture/API_DESIGN.md)
- [PYTHON_PROJECT_LAYOUT.md](../architecture/PYTHON_PROJECT_LAYOUT.md)
