"""Replay harness to populate in-memory market caches for local testing.

This script is intentionally separate from production code. It writes to
`data.upstox_market` internal caches (_price_store, _ohlcv_cache, _option_ltp_store)
so you can run the backend locally and feed synthetic historical data without
changing production code paths.

Usage:
  python tools/replay_harness.py --symbol NIFTY --ohlcv sample.csv --rate 1

CSV format: timestamp,open,high,low,close,volume  (timestamp ISO format accepted)
"""
import argparse
import csv
import time
from datetime import datetime
import asyncio


def load_csv(path):
    rows = []
    with open(path, "r", newline="") as fh:
        r = csv.reader(fh)
        for row in r:
            if not row:
                continue
            # Support header row detection
            try:
                float(row[1])
            except Exception:
                continue
            ts = row[0]
            rows.append({
                "timestamp": ts,
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": int(float(row[5])),
            })
    return rows


async def run(symbol, ohlcv_csv, rate):
    from data import upstox_market
    rows = load_csv(ohlcv_csv)
    if not rows:
        print("No rows loaded from CSV")
        return

    print(f"Loaded {len(rows)} bars — feeding to in-memory caches for {symbol}")
    for row in rows:
        # update OHLCV cache per the fetch_ohlcv cache_key
        key = f"ohlcv_{symbol}_5d_5m"
        import pandas as pd
        df = pd.DataFrame([row]).set_index("timestamp")
        upstox_market._ohlcv_cache[key] = {"data": df, "ts": datetime.now().isoformat()}

        # update price store with latest close
        upstox_market._price_store[symbol.upper()] = {
            "price": row["close"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "volume": row["volume"],
            "change_pct": 0.0,
            "timestamp": row["timestamp"],
            "symbol": symbol.upper(),
            "source": "replay_harness",
        }

        print(f"[{row['timestamp']}] price={row['close']}")
        await asyncio.sleep(1.0 / max(rate, 1))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--ohlcv", required=True)
    p.add_argument("--rate", type=float, default=1.0, help="bars per second")
    args = p.parse_args()
    asyncio.run(run(args.symbol, args.ohlcv, args.rate))


if __name__ == "__main__":
    main()
