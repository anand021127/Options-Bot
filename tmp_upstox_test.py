import asyncio, httpx, os, aiosqlite

async def main():
    # Get token from database
    token = None
    try:
        async with aiosqlite.connect('backend/trading_bot.db') as db:
            cur = await db.execute("SELECT value FROM bot_config WHERE key = 'upstox_access_token'")
            row = await cur.fetchone()
            if row:
                token = row[0]
    except Exception as e:
        print(f'DB error: {e}')

    print('TOKEN', 'FOUND' if token else 'MISSING')
    if not token:
        return

    # Test different endpoints for historical data
    endpoints = [
        'https://api.upstox.com/v2/market-quote/ohlc',
        'https://api.upstox.com/v2/historical-candle/intraday',
        'https://api.upstox.com/v2/market-quote/historical',
        'https://api.upstox.com/v2/market-quote/candle',
    ]

    intervals = ['1m', '5m', '15m', '1d', 'day']

    async with httpx.AsyncClient(timeout=15) as client:
        for url in endpoints:
            print(f'\n--- Testing {url} ---')
            for iv in intervals:
                try:
                    resp = await client.get(url, params={'instrument_key': 'NSE_INDEX|Nifty 50', 'interval': iv}, headers={'Authorization': f'Bearer {token}'})
                    print(f'{iv}: {resp.status_code} - {resp.text[:100]}')
                except Exception as e:
                    print(f'{iv}: ERROR - {e}')

asyncio.run(main())
