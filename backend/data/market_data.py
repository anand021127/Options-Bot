"""
Market Data Module
Fetches OHLCV, options chain, and calculates indicators.
Uses yfinance (100% free, no API key needed).

Limitations:
- ~15 min delay for options data
- Rate limited — we cache aggressively
- NSE options chain via yfinance has some gaps
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import yfinance as yf
from loguru import logger

# ─── Symbol mapping (NSE → Yahoo Finance tickers) ─────────────────────────────
SYMBOL_MAP = {
    "NIFTY":    "^NSEI",
    "BANKNIFTY":"^NSEBANK",
    "SENSEX":   "^BSESN",
    "RELIANCE": "RELIANCE.NS",
    "TCS":      "TCS.NS",
    "INFY":     "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
}


def get_yf_symbol(symbol: str) -> str:
    return SYMBOL_MAP.get(symbol.upper(), f"{symbol}.NS")


# ─── Data cache ───────────────────────────────────────────────────────────────
_price_cache: Dict[str, Dict] = {}
_options_cache: Dict[str, Dict] = {}
CACHE_TTL = 60  # seconds


def _is_cache_valid(cache_entry: Dict, ttl: int = CACHE_TTL) -> bool:
    if not cache_entry:
        return False
    age = (datetime.now() - cache_entry.get("fetched_at", datetime.min)).seconds
    return age < ttl


# ─── Price & OHLCV ────────────────────────────────────────────────────────────

async def fetch_ohlcv(symbol: str, period: str = "5d", interval: str = "5m") -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candlestick data.
    interval options: 1m, 2m, 5m, 15m, 30m, 60m, 1d
    period  options: 1d, 5d, 1mo, 3mo
    Note: 1m data only available for last 7 days via yfinance.
    """
    yf_sym = get_yf_symbol(symbol)
    try:
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: yf.download(yf_sym, period=period, interval=interval,
                                 progress=False, auto_adjust=True)
        )
        if df is None or df.empty:
            logger.warning(f"No OHLCV data for {symbol}")
            return None

        df.index = pd.to_datetime(df.index)
        df.columns = [c.lower() for c in df.columns]
        # Flatten MultiIndex if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        logger.debug(f"Fetched {len(df)} candles for {symbol}")
        return df

    except Exception as e:
        logger.error(f"OHLCV fetch error for {symbol}: {e}")
        return None


async def fetch_live_price(symbol: str) -> Optional[Dict]:
    """
    Fetch latest price with caching.
    Returns dict: {price, open, high, low, volume, change_pct, timestamp}
    """
    cache_key = f"price_{symbol}"
    cached = _price_cache.get(cache_key, {})
    if _is_cache_valid(cached):
        return cached["data"]

    yf_sym = get_yf_symbol(symbol)
    try:
        loop = asyncio.get_event_loop()
        ticker = await loop.run_in_executor(None, lambda: yf.Ticker(yf_sym))
        info = await loop.run_in_executor(None, lambda: ticker.fast_info)

        price = float(info.last_price) if hasattr(info, 'last_price') and info.last_price else None

        # Fallback: grab latest from 1d OHLCV
        if not price:
            df = await fetch_ohlcv(symbol, period="1d", interval="1m")
            if df is not None and not df.empty:
                price = float(df["close"].iloc[-1])

        if not price:
            return None

        # Get day's high/low/open from 1d data
        df_day = await fetch_ohlcv(symbol, period="2d", interval="1d")
        open_p = high_p = low_p = volume = change_pct = 0
        if df_day is not None and not df_day.empty:
            row = df_day.iloc[-1]
            open_p   = float(row.get("open", price))
            high_p   = float(row.get("high", price))
            low_p    = float(row.get("low", price))
            volume   = int(row.get("volume", 0))
            prev_close = float(df_day.iloc[-2]["close"]) if len(df_day) > 1 else price
            change_pct = round(((price - prev_close) / prev_close) * 100, 2)

        data = {
            "price": round(price, 2),
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low":  round(low_p, 2),
            "volume": volume,
            "change_pct": change_pct,
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
        }
        _price_cache[cache_key] = {"data": data, "fetched_at": datetime.now()}
        return data

    except Exception as e:
        logger.error(f"Live price fetch error for {symbol}: {e}")
        return None


# ─── Options Chain ────────────────────────────────────────────────────────────

async def fetch_options_chain(symbol: str, expiry: Optional[str] = None) -> Optional[Dict]:
    """
    Fetch options chain (CE + PE) for nearest/specified expiry.
    Returns structured dict with calls and puts DataFrames.
    Note: ~15min delay via yfinance free tier.
    """
    cache_key = f"opts_{symbol}_{expiry}"
    cached = _options_cache.get(cache_key, {})
    if _is_cache_valid(cached, ttl=300):  # 5 min cache for options
        return cached["data"]

    yf_sym = get_yf_symbol(symbol)
    try:
        loop = asyncio.get_event_loop()
        ticker = await loop.run_in_executor(None, lambda: yf.Ticker(yf_sym))
        expirations = await loop.run_in_executor(None, lambda: ticker.options)

        if not expirations:
            logger.warning(f"No options expiries available for {symbol}")
            return None

        # Pick nearest expiry or specified
        target_expiry = expiry if expiry and expiry in expirations else expirations[0]

        opt_chain = await loop.run_in_executor(
            None, lambda: ticker.option_chain(target_expiry)
        )

        calls = opt_chain.calls.copy()
        puts  = opt_chain.puts.copy()

        # Standardise column names
        for df in [calls, puts]:
            df.rename(columns={
                "strike": "strike",
                "lastPrice": "ltp",
                "bid": "bid",
                "ask": "ask",
                "volume": "volume",
                "openInterest": "oi",
                "impliedVolatility": "iv",
                "inTheMoney": "itm",
            }, inplace=True, errors="ignore")

        # Get ATM strike from current price
        price_data = await fetch_live_price(symbol)
        spot = price_data["price"] if price_data else 0

        result = {
            "symbol": symbol,
            "expiry": target_expiry,
            "spot": spot,
            "available_expiries": list(expirations[:5]),
            "calls": calls.to_dict("records"),
            "puts":  puts.to_dict("records"),
            "timestamp": datetime.now().isoformat(),
        }

        _options_cache[cache_key] = {"data": result, "fetched_at": datetime.now()}
        logger.info(f"Fetched options chain for {symbol} expiry={target_expiry}")
        return result

    except Exception as e:
        logger.error(f"Options chain fetch error for {symbol}: {e}")
        return None


async def get_atm_option(symbol: str, option_type: str = "CE") -> Optional[Dict]:
    """
    Return the At-The-Money option contract for trading signal.
    option_type: "CE" (Call) or "PE" (Put)
    """
    chain = await fetch_options_chain(symbol)
    if not chain:
        return None

    spot = chain["spot"]
    contracts = chain["calls"] if option_type == "CE" else chain["puts"]

    if not contracts:
        return None

    # Find ATM (closest strike to spot)
    df = pd.DataFrame(contracts)
    df["diff"] = (df["strike"] - spot).abs()
    atm_row = df.sort_values("diff").iloc[0]

    return {
        "symbol": symbol,
        "option_type": option_type,
        "strike": float(atm_row["strike"]),
        "expiry": chain["expiry"],
        "ltp": float(atm_row.get("ltp", 0)),
        "iv": float(atm_row.get("iv", 0)),
        "oi": int(atm_row.get("oi", 0)),
        "volume": int(atm_row.get("volume", 0)),
        "spot": spot,
    }


# ─── Market status ────────────────────────────────────────────────────────────

def is_market_open() -> bool:
    """Check if NSE market is currently open (Mon–Fri, 09:15–15:30 IST)"""
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.now(ist)

    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def minutes_to_market_open() -> int:
    """Returns minutes until market opens, 0 if already open"""
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.now(ist)
    target = now.replace(hour=9, minute=15, second=0, microsecond=0)
    if now > target:
        # next day
        target += timedelta(days=1)
    diff = (target - now).seconds // 60
    return diff
