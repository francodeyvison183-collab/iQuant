"""创建首个超级管理员（仅库内无管理员时可用）。"""
from __future__ import annotations

import argparse
import asyncio
import sys

from iquant_identity_service.usecases.bootstrap import bootstrap_admin


async def _run(*, username: str | None, password: str | None) -> None:
    result = await bootstrap_admin(username=username, password=password)
    print(f"管理员已创建: {result['username']} (id={result['admin_id']})")


def main() -> None:
    parser = argparse.ArgumentParser(description="创建首个 iQuant 管理员账号")
    parser.add_argument("--username", help="覆盖 IQUANT_ADMIN_BOOTSTRAP_USERNAME")
    parser.add_argument("--password", help="覆盖 IQUANT_ADMIN_BOOTSTRAP_PASSWORD")
    args = parser.parse_args()
    try:
        asyncio.run(_run(username=args.username, password=args.password))
    except Exception as exc:  # noqa: BLE001
        print(f"bootstrap 失败: {exc}", file=sys.stderr)
        print(
            "提示: 请在项目根 .env 设置 IQUANT_ADMIN_BOOTSTRAP_USERNAME / "
            "IQUANT_ADMIN_BOOTSTRAP_PASSWORD（密码≥8位），或使用 --username / --password。",
            file=sys.stderr,
        )
        print(
            "若刚修改 .env，可执行: docker compose -f docker-compose.dev.yml up -d api",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
