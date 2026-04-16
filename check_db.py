import asyncio, aiosqlite

async def main():
    async with aiosqlite.connect('backend/trading_bot.db') as db:
        cur = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = await cur.fetchall()
        print('Tables:', tables)

        # Check each table for token-related data
        for table_name, in tables:
            print(f'\n--- {table_name} ---')
            try:
                cur = await db.execute(f"PRAGMA table_info({table_name})")
                columns = await cur.fetchall()
                print('Columns:', [col[1] for col in columns])

                cur = await db.execute(f"SELECT * FROM {table_name} LIMIT 5")
                rows = await cur.fetchall()
                print('Sample data:', rows)
            except Exception as e:
                print(f'Error: {e}')

asyncio.run(main())