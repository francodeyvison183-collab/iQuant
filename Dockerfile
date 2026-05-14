# ==============================================================================
# iQuant 后端生产镜像
# 多阶段构建：构建期安装依赖，运行期镜像只保留运行时
# ==============================================================================
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /workspace

# 系统编译依赖（构建期）：asyncpg/psycopg/numpy 等可能用到
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（统一依赖管理）
RUN pip install --upgrade pip && pip install uv==0.5.11

# 仅复制依赖元数据用于构建期缓存
COPY pyproject.toml uv.lock* ./
COPY apps/api/pyproject.toml ./apps/api/
COPY apps/worker/pyproject.toml ./apps/worker/
COPY services/market-service/pyproject.toml ./services/market-service/
COPY packages/domain/pyproject.toml ./packages/domain/
COPY packages/market-data/pyproject.toml ./packages/market-data/

# 同步依赖到统一 .venv
RUN uv sync --frozen --no-install-project --all-extras || \
    uv sync --no-install-project --all-extras

# 复制源代码并安装本地 workspace 包
COPY apps ./apps
COPY services ./services
COPY packages ./packages
COPY storage ./storage

RUN uv sync --frozen --all-extras || uv sync --all-extras


# ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/workspace/.venv/bin:$PATH"

# 运行时最小系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tini \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# 非 root 用户
RUN useradd --create-home --uid 10001 iquant

WORKDIR /workspace
COPY --from=builder --chown=iquant:iquant /workspace /workspace

USER iquant
EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
# 默认启动 API；worker 用 docker-compose 覆盖 command
CMD ["gunicorn", "iquant_api.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "2", \
     "-b", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--graceful-timeout", "30"]
