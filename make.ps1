# ==============================================================================
# iQuant 常用命令（Windows PowerShell 版）
# 用法：.\make.ps1 <命令> [-s <服务名>] [-m <迁移说明>]
# ==============================================================================
param(
    [Parameter(Position = 0)]
    [string]$Command = "help",

    [Alias("s")]
    [string]$Service = "api",

    [Alias("m")]
    [string]$Message = ""
)

function Set-IQuantConsoleEncoding {
  if ($PSVersionTable.PSEdition -ne "Desktop") {
    return
  }

  try {
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = $utf8
    $OutputEncoding = $utf8
    $null = cmd.exe /c chcp 65001 >$null 2>&1
  } catch {
    # 控制台编码不可用时忽略，避免影响命令执行
  }
}

Set-IQuantConsoleEncoding

$ComposeDev = "docker compose -f docker-compose.dev.yml"
$ComposeProd = "docker compose -f docker-compose.yml"

function Show-IQuantHelp {
  Write-Host "iQuant 常用命令（Windows PowerShell）："
  Write-Host "  .\make.ps1 env                     # 复制 .env.example 为 .env（如不存在）"
  Write-Host "  .\make.ps1 dev                     # 启动开发环境（带热更新）"
  Write-Host "  .\make.ps1 dev-bg                  # 后台启动开发环境"
  Write-Host "  .\make.ps1 dev-down                # 停止开发环境"
  Write-Host "  .\make.ps1 dev-logs -s api         # 实时查看某个服务日志"
  Write-Host "  .\make.ps1 dev-shell -s api        # 进入某个服务的容器"
  Write-Host "  .\make.ps1 migrate                 # 在 api 容器内执行 Alembic 升级到 head"
  Write-Host "  .\make.ps1 migrate-ts              # 时序库 Alembic 升级到 head"
  Write-Host "  .\make.ps1 admin-bootstrap         # 创建首个管理员（需已 migrate）"
  Write-Host "  .\make.ps1 seed-cyb                # 投递创业板近 6 个月日 K 测试数据任务"
  Write-Host "  .\make.ps1 revision -m `"说明`"      # 生成新 Alembic 迁移文件"
  Write-Host "  .\make.ps1 lint                    # ruff + mypy"
  Write-Host "  .\make.ps1 test                    # pytest"
  Write-Host "  .\make.ps1 build                   # 构建生产镜像"
  Write-Host "  .\make.ps1 prod                    # 启动生产 compose"
}

switch ($Command) {
  "help" {
    Show-IQuantHelp
  }

  "env" {
    if (-not (Test-Path ".env")) {
      Copy-Item ".env.example" ".env"
      Write-Host "已生成 .env，请按需修改" -ForegroundColor Green
    } else {
      Write-Host ".env 已存在，跳过" -ForegroundColor Yellow
    }
  }

  "dev" {
    Invoke-Expression "$ComposeDev up"
  }

  "dev-bg" {
    Invoke-Expression "$ComposeDev up -d"
  }

  "dev-down" {
    Invoke-Expression "$ComposeDev down"
  }

  "dev-logs" {
    Invoke-Expression "$ComposeDev logs -f $Service"
  }

  "dev-shell" {
    Invoke-Expression "$ComposeDev exec $Service bash"
  }

  "migrate" {
    Invoke-Expression "$ComposeDev exec api .venv/bin/alembic -c storage/migrations/alembic.ini upgrade head"
  }

  "migrate-ts" {
    Invoke-Expression "$ComposeDev exec api .venv/bin/alembic -c storage/migrations/alembic.ini -n timescale upgrade head"
  }

  "admin-bootstrap" {
    # 使用 run 以便重新读取 .env；挂载的 /workspace/.env 也会被 identity 配置加载
    Invoke-Expression "$ComposeDev run --rm --no-deps api .venv/bin/python -m iquant_api.cli.admin_bootstrap"
  }

  "seed-cyb" {
    Invoke-Expression "$ComposeDev exec api .venv/bin/python -m iquant_api.cli.seed_test_cyb"
  }

  "revision" {
    if ([string]::IsNullOrWhiteSpace($Message)) {
      Write-Host "请提供迁移说明：.\make.ps1 revision -m '说明'" -ForegroundColor Red
      exit 1
    }
    Invoke-Expression "$ComposeDev exec api .venv/bin/alembic -c storage/migrations/alembic.ini revision --autogenerate -m `"$Message`""
  }

  "lint" {
    Invoke-Expression "$ComposeDev exec api bash -lc 'ruff check . && ruff format --check . && mypy apps services packages'"
  }

  "test" {
    Invoke-Expression "$ComposeDev exec api .venv/bin/pytest"
  }

  "build" {
    Invoke-Expression "$ComposeProd build"
  }

  "prod" {
    Invoke-Expression "$ComposeProd up -d"
  }

  default {
    Write-Host "未知命令: $Command，运行 .\make.ps1 help 查看帮助" -ForegroundColor Red
  }
}
