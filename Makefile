# ==============================================================================
# iQuant 常用命令
# ==============================================================================
.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE_DEV := docker compose -f docker-compose.dev.yml
COMPOSE     := docker compose -f docker-compose.yml

help:
	@echo "iQuant 常用命令："
	@echo "  make env              # 复制 .env.example 为 .env（如不存在）"
	@echo "  make dev              # 启动开发环境（带热更新）"
	@echo "  make dev-bg           # 后台启动开发环境"
	@echo "  make dev-down         # 停止开发环境"
	@echo "  make dev-logs s=api   # 实时查看某个服务日志"
	@echo "  make dev-shell s=api  # 进入某个服务的容器"
	@echo "  make migrate          # 在 api 容器内执行 Alembic 升级到 head"
	@echo "  make revision m=msg   # 生成新 Alembic 迁移文件"
	@echo "  make lint             # ruff + mypy"
	@echo "  make test             # pytest"
	@echo "  make build            # 构建生产镜像"
	@echo "  make prod             # 启动生产 compose"

env:
	@if [ ! -f .env ]; then cp .env.example .env && echo "已生成 .env，请按需修改"; else echo ".env 已存在，跳过"; fi

dev:
	$(COMPOSE_DEV) up

dev-bg:
	$(COMPOSE_DEV) up -d

dev-down:
	$(COMPOSE_DEV) down

dev-logs:
	$(COMPOSE_DEV) logs -f $(s)

dev-shell:
	$(COMPOSE_DEV) exec $(s) bash

migrate:
	$(COMPOSE_DEV) exec api .venv/bin/alembic -c storage/migrations/alembic.ini upgrade head

revision:
	@if [ -z "$(m)" ]; then echo "请提供迁移说明：make revision m='add new column'"; exit 1; fi
	$(COMPOSE_DEV) exec api .venv/bin/alembic -c storage/migrations/alembic.ini revision --autogenerate -m "$(m)"

lint:
	$(COMPOSE_DEV) exec api bash -lc "ruff check . && ruff format --check . && mypy apps services packages"

test:
	$(COMPOSE_DEV) exec api .venv/bin/pytest

build:
	$(COMPOSE) build

prod:
	$(COMPOSE) up -d
