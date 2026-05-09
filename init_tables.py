import sys, asyncio
sys.stdout.reconfigure(line_buffering=True)

async def create_schemas_and_tables():
    import asyncpg
    
    conn = await asyncpg.connect(host="127.0.0.1", port=5432, user="erp", password="erp_secret", database="erp_db")
    print("Connected to erp_db!", flush=True)
    
    schemas = ["iam", "pdm", "som", "ads", "oms", "scm", "wms", "fba", "tms", "crm", "fms", "bi", "sys", "dashboard"]
    for s in schemas:
        await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
    print(f"Created {len(schemas)} schemas", flush=True)
    
    extensions = await conn.fetch("SELECT extname FROM pg_extension WHERE extname = 'uuid-ossp'")
    if not extensions:
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
        print("Created uuid-ossp extension", flush=True)
    
    await conn.close()
    print("Schemas created successfully!", flush=True)
    
    from erp.bootstrap.config import get_settings
    from erp.shared.db.session import init_db_engine, get_engine
    from erp.shared.db.base import Base

    settings = get_settings()
    init_db_engine(settings.db)
    engine = get_engine()

    import erp.modules.iam.domain.models
    import erp.modules.oms.domain.models
    import erp.modules.wms.domain.models
    import erp.modules.scm.domain.models
    import erp.modules.crm.domain.models
    import erp.modules.tms.domain.models
    import erp.modules.fba.domain.models
    import erp.modules.pdm.domain.models
    import erp.modules.som.domain.models
    import erp.modules.ads.domain.models
    import erp.modules.fms.domain.models
    import erp.modules.bi.domain.models
    import erp.modules.sys.domain.models
    import erp.modules.dashboard.domain.models
    print("All domain models imported", flush=True)

    async with engine.begin() as conn2:
        await conn2.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!", flush=True)

    tables = sorted(Base.metadata.tables.keys())
    print(f"Total tables: {len(tables)}", flush=True)
    for t in tables:
        print(f"  {t}", flush=True)

asyncio.run(create_schemas_and_tables())
