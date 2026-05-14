# iQuant 后台管理界面

基于 Vue 3 + Vite + TypeScript + Element Plus。

## 功能模块

| 模块 | 路径 | 说明 |
| --- | --- | --- |
| 通达信主站 | `/market/hosts` | 添加/删除/测速 TDX 行情主站 |
| 历史数据导入 | `/market/import` | 预览 vipdoc 扫描结果，提交增量/全量导入任务 |
| 任务进度 | `/market/tasks` | 列出导入任务，SSE 实时进度 |
| 在线补数 | `/market/online` | 通过 TDX 在线协议直接拉取最近 K 线 |
| 数据查看 | `/market/browser` | 浏览标的列表与 K 线（含 ECharts 图表） |

## 开发

容器内由 docker-compose.dev.yml 中的 `admin-web` 服务启动，源码通过卷挂载实现热更新。

本机直接调试：

```bash
cd apps/admin-web
pnpm install
pnpm dev
```

默认监听 `http://localhost:5173`，``/api`` 通过 vite 代理转发到后端。
