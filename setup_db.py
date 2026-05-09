import sys, asyncio
sys.stdout.reconfigure(line_buffering=True)

async def setup_db():
    import asyncpg
    
    conn = await asyncpg.connect(host="127.0.0.1", port=5432, user="GodyChang", database="postgres")
    print("Connected as superuser!", flush=True)
    
    databases = await conn.fetch("SELECT datname FROM pg_database WHERE datistemplate = false")
    db_names = [r['datname'] for r in databases]
    print(f"Existing databases: {db_names}", flush=True)
    
    if 'erp_db' not in db_names:
        await conn.execute("CREATE USER erp WITH PASSWORD 'erp_secret' SUPERUSER")
        print("Created user: erp", flush=True)
        await conn.execute("CREATE DATABASE erp_db OWNER erp")
        print("Created database: erp_db", flush=True)
    else:
        print("erp_db already exists", flush=True)
    
    await conn.close()
    
    conn2 = await asyncpg.connect(host="127.0.0.1", port=5432, user="erp", password="erp_secret", database="erp_db")
    print("Verified: Connected as erp to erp_db!", flush=True)
    await conn2.close()

asyncio.run(setup_db())
