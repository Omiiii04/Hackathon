import asyncio
import asyncpg

async def main():
    print("Testing asyncpg TCP connection to Docker Postgres...")
    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="omii",
            password="omii00",
            database="osint_verify",
        )
        user = await conn.fetchval("SELECT current_user")
        db = await conn.fetchval("SELECT current_database()")
        tables = await conn.fetchval("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
        await conn.close()
        print(f"SUCCESS: user={user} db={db} tables={tables}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

asyncio.run(main())
