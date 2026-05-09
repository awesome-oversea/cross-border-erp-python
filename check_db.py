import sys, asyncio
sys.stdout.reconfigure(line_buffering=True)

async def find_superuser():
    import asyncpg
    
    for user in ["postgres", "erp_python", "erp", "admin", "root", "aitools"]:
        try:
            conn = await asyncpg.connect(host="127.0.0.1", port=5432, user=user, database="postgres")
            print(f"Connected as {user}!", flush=True)
            roles = await conn.fetch("SELECT rolname, rolsuper FROM pg_roles")
            for r in roles:
                print(f"  Role: {r['rolname']}, superuser: {r['rolsuper']}", flush=True)
            await conn.close()
            return user
        except Exception as e:
            print(f"{user}: {e}", flush=True)
    
    try:
        import os
        username = os.getlogin()
        print(f"Trying OS username: {username}", flush=True)
        conn = await asyncpg.connect(host="127.0.0.1", port=5432, user=username, database="postgres")
        print(f"Connected as {username}!", flush=True)
        roles = await conn.fetch("SELECT rolname, rolsuper FROM pg_roles")
        for r in roles:
            print(f"  Role: {r['rolname']}, superuser: {r['rolsuper']}", flush=True)
        await conn.close()
        return username
    except Exception as e:
        print(f"{username}: {e}", flush=True)
    
    return None

asyncio.run(find_superuser())
