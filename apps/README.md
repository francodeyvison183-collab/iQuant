# apps

应用入口层。各子目录均为独立可部署单元，依赖 `services/` 与 `packages/`，反向依赖被禁止。

| 子目录 | 说明 |
| --- | --- |
| `api/` | FastAPI 后端 API |
| `worker/` | Celery worker + Beat |
| `admin-web/` | Vue3 + Element Plus 后台管理界面 |
| `miniprogram/` | 微信小程序用户端（产品文档先行，代码后续接入） |

应用层只做组合和编排，不承载核心交易算法。
