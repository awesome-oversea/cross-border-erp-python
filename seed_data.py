#!/usr/bin/env python3
"""
初始化数据填充脚本

用法:
  python seed_data.py          完整填充(使用DataInitializer)
  python seed_data.py --sample 填充+样例业务数据

依赖: 数据库已初始化(python cli.py init-db)
"""
import argparse
import asyncio
import sys
import uuid

sys.path.insert(0, "src")

from erp.bootstrap.config import get_settings
from erp.shared.db.session import init_db_engine, close_db, get_session


async def main(sample: bool = False):
    settings = get_settings()
    init_db_engine(settings.db)
    print(f"连接数据库: {settings.db.url}")

    async with get_session() as session:
        # 1. 系统初始化数据
        from erp.shared.bootstrap.data_initializer import DataInitializer
        init = DataInitializer(session)
        results = await init.initialize_all()
        for k, v in results.items():
            status = v.get("status", v.get("created", "ok"))
            print(f"  [{status}] {k}")

        # 2. 样例业务数据
        if sample:
            print("\n填充样例业务数据...")
            from sqlalchemy import select
            from erp.modules.pdm.domain.models import Category, Brand, SPU, SKU
            from erp.modules.scm.domain.models import Supplier
            from erp.modules.wms.domain.models import Warehouse
            from erp.modules.iam.domain.models import Tenant

            tenant = (await session.execute(select(Tenant).limit(1))).scalar_one_or_none()
            if not tenant:
                print("  没有找到租户，跳过样例数据")
            else:
                tid = tenant.id
                cat = Category(tenant_id=tid, name="电子产品", code="ELEC", level=1, status="active")
                brand = Brand(tenant_id=tid, name="测试品牌", code="TEST-BRAND", status="active")
                spu = SPU(tenant_id=tid, name="测试SPU-电子产品", code=f"SPU-{uuid.uuid4().hex[:8].upper()}", status="draft")
                sku = SKU(tenant_id=tid, spu_id="", sku_code=f"SKU-{uuid.uuid4().hex[:8].upper()}", name="测试SKU", status="active")
                sup = Supplier(tenant_id=tid, name="测试供应商", code=f"SUP-{uuid.uuid4().hex[:6].upper()}", status="active")
                wh = Warehouse(tenant_id=tid, name="主仓库", code="WH-MAIN", warehouse_type="self", status="active")

                session.add_all([cat, brand, spu, sku, sup, wh])
                print(f"  品类: {cat.name}")
                print(f"  品牌: {brand.name}")
                print(f"  SPU: {spu.name}")
                print(f"  SKU: {sku.sku_code}")
                print(f"  供应商: {sup.name}")
                print(f"  仓库: {wh.name}")

        await session.commit()

    await close_db()
    print(f"\n填充完成!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="填充初始化/样例数据")
    parser.add_argument("--sample", action="store_true", help="同时填充样例业务数据")
    args = parser.parse_args()
    asyncio.run(main(sample=args.sample))
