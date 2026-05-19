# ADR-0010：管理后台鉴权 MVP（单超级管理员）

## 状态

已接受（2026-05-15）

## 背景

管理后台将面向公网部署，需防止未授权访问行情导入、在线拉数等高危操作。MVP 仅服务单一运营团队，不要求多角色 RBAC。

## 决策

1. **独立 `identity-service`**：管理员账号、Refresh Token、审计日志落在业务 PostgreSQL；通过 service 用例对外暴露，API 层不直连 ORM。
2. **双 Token**：短期 HS256 Access JWT（含 `jti` 可吊销）+ 长期 Refresh Token（仅存哈希）。
3. **密码**：Argon2 哈希；bootstrap 仅允许在 `admin_user` 为空时执行一次。
4. **公网防护**：Cloudflare Turnstile（可配置跳过开发）、登录 IP 限流与失败锁定、管理 API 全局限流、安全响应头；生产收敛 OpenAPI 与 CORS 白名单。
5. **SSE**：`EventSource` 无法携带 `Authorization`，进度流使用 Redis 一次性 ticket（`GET .../progress?ticket=`）。
6. **审计**：写操作经中间件落 `admin_audit_log`；登录失败由登录用例单独记录。

## 后果

- 所有 `/api/v1/admin/market/*`（除 ticket 校验的 SSE）需 Bearer Token。
- 前端需登录页、Token 刷新与进度 ticket 申请流程。
- 生产必须配置 `IQUANT_ADMIN_JWT_SECRET`、Turnstile、CORS；执行 `make.ps1 admin-bootstrap` 创建首个账号。

## 后续

- 多管理员 / RBAC、2FA、会话设备管理可在身份表扩展，不阻塞当前 MVP。
