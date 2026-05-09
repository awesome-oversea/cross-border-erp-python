#!/usr/bin/env python3
"""
ERP命令行工具 - 运维与开发辅助

用法:
  python cli.py init-db      初始化数据库(创建Schema+表)
  python cli.py seed         填充初始化数据
  python cli.py check        系统健康检查
  python cli.py migrate      执行数据库迁移
"""
import sys


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]
    if cmd == "init-db":
        import asyncio
        asyncio.run(_init_db())
    elif cmd == "seed":
        import asyncio
        asyncio.run(_seed())
    elif cmd == "check":
        import asyncio
        asyncio.run(_check())
    elif cmd == "migrate":
        _migrate()
    else:
        print(f"未知命令: {cmd}")


async def _init_db():
    from init_tables import create_schemas_and_tables
    await create_schemas_and_tables()
    print("数据库初始化完成")


async def _seed():
    from erp.bootstrap.config import get_settings
    from erp.shared.db.session import init_db_engine, close_db, get_session
    settings = get_settings()
    init_db_engine(settings.db)
    async with get_session() as session:
        from erp.shared.bootstrap.data_initializer import DataInitializer
        init = DataInitializer(session)
        results = await init.initialize_all()
        await session.commit()
        for k, v in results.items():
            print(f"  {k}: {v.get('status', 'ok')}")
    await close_db()
    print("初始化数据填充完成")


async def _check():
    from erp.bootstrap.config import get_settings
    settings = get_settings()
    checks = [
        ("应用名称", settings.app_name),
        ("环境", settings.environment),
        ("API路径", settings.api_prefix),
        ("数据库", str(settings.db.url).split("@")[-1] if "@" in str(settings.db.url) else str(settings.db.url)),
        ("Redis", str(settings.redis.url)),
        ("Kafka", settings.kafka.bootstrap_servers),
    ]
    all_ok = True
    for name, val in checks:
        status = "OK" if val else "MISSING"
        if status == "MISSING": all_ok = False
        print(f"  [{status}] {name}: {val}")
    print(f"\n系统检查: {'全部通过' if all_ok else '存在警告'}")


def _migrate():
    import subprocess
    subprocess.run(["alembic", "upgrade", "head"])
    print("迁移完成")


if __name__ == "__main__":
    main()
