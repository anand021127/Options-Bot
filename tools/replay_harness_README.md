Replay Harness — README
=======================

Purpose
-------
This small helper replays historical intraday OHLCV into the backend's in-memory
market caches for local testing. It is intentionally isolated from production
code and writes directly into `data.upstox_market` caches so you can run the
trading logic without a live Upstox token.

CSV format
----------
Required columns (no header required; header rows are ignored if present):

- timestamp (ISO8601 or any string)
- open
- high
- low
- close
- volume

Example row:

2026-06-21T09:15:00,18000,18020,17980,18010,1000

Quick start
-----------
1. Start your backend as usual (the replay harness writes to the running app's
   in-memory caches):

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

2. Run the harness against a CSV:

```powershell
python tools/replay_harness.py --symbol NIFTY --ohlcv sample.csv --rate 1
```

Notes & safety
--------------
- The harness modifies in-memory caches only and does not change database
  content or production code paths.
- Use this for local testing only — do not commit synthetic market data into
  production databases.

Troubleshooting
---------------
- If you see no effect, ensure the backend is running and that `data/upstox_market.py`
  defines `_price_store` and `_ohlcv_cache` (they exist in the current codebase).
