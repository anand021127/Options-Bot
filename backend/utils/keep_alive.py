"""
Keep-Alive Pinger
Render free tier sleeps after 15min of inactivity.
This script runs separately and pings the /health endpoint every 10 minutes.

Deploy this as a second Render service (cron job) OR run via GitHub Actions.

GitHub Actions free tier gives 2000 min/month — plenty for pinging.
"""

import asyncio
import httpx
import os
from datetime import datetime

BACKEND_URL = os.getenv("BACKEND_URL", "https://your-bot.onrender.com")
PING_INTERVAL = 600  # 10 minutes


async def ping():
    while True:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{BACKEND_URL}/health")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Ping → {resp.status_code} {resp.json()}")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Ping failed: {e}")
        await asyncio.sleep(PING_INTERVAL)


if __name__ == "__main__":
    print(f"🏓 Keep-alive pinger started → {BACKEND_URL}")
    asyncio.run(ping())
