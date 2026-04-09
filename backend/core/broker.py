"""
Live Broker Adapter — Angel One SmartAPI (FREE)
-----------------------------------------------
Angel One SmartAPI is completely free with a demat account.
Register at: https://smartapi.angelbroking.com

Install:  pip install smartapi-python pyotp

Set in .env:
  BROKER=angel
  BROKER_API_KEY=your_api_key
  BROKER_CLIENT_CODE=R123456
  BROKER_TOTP_SECRET=your_totp_base32_secret

This module handles:
  - Login with TOTP (no manual OTP needed)
  - Place BUY/SELL orders for CE and PE options
  - Fetch live option LTP
  - Error handling and duplicate prevention
"""

import asyncio
import hashlib
from datetime import datetime
from typing import Dict, Optional
from loguru import logger
from config import settings

# ─── Singleton broker client ──────────────────────────────────────────────────
_client = None
_last_order_hashes: set = set()  # Prevent duplicate orders


def _get_totp() -> str:
    """Generate TOTP code from secret (replaces SMS OTP)."""
    try:
        import pyotp
        return pyotp.TOTP(settings.BROKER_TOTP_SECRET).now()
    except ImportError:
        raise RuntimeError("Install pyotp: pip install pyotp")
    except Exception as e:
        raise RuntimeError(f"TOTP generation failed: {e}")


async def connect_broker() -> bool:
    """
    Connect to Angel One SmartAPI.
    Returns True on success.
    """
    global _client

    if settings.BROKER != "angel":
        logger.warning(f"Broker '{settings.BROKER}' not implemented. Only 'angel' supported.")
        return False

    if not settings.BROKER_API_KEY:
        logger.error("BROKER_API_KEY not set in .env")
        return False

    try:
        from SmartApi import SmartConnect
        loop = asyncio.get_event_loop()

        def _login():
            client = SmartConnect(api_key=settings.BROKER_API_KEY)
            totp   = _get_totp()
            data   = client.generateSession(
                settings.BROKER_CLIENT_CODE,
                settings.BROKER_API_KEY,
                totp
            )
            if data["status"]:
                logger.info(f"✅ Angel One login success | Client: {settings.BROKER_CLIENT_CODE}")
                return client
            else:
                raise RuntimeError(f"Login failed: {data.get('message')}")

        _client = await loop.run_in_executor(None, _login)
        return True

    except ImportError:
        logger.error("SmartAPI not installed. Run: pip install smartapi-python")
        return False
    except Exception as e:
        logger.error(f"Broker connection error: {e}")
        return False


def _order_hash(symbol: str, option_type: str, strike: float, action: str) -> str:
    """Generate unique hash to prevent duplicate orders within 60 seconds."""
    minute_bucket = datetime.now().strftime("%Y%m%d%H%M")
    key = f"{symbol}|{option_type}|{strike}|{action}|{minute_bucket}"
    return hashlib.md5(key.encode()).hexdigest()


async def place_order(
    symbol:      str,
    option_type: str,   # "CE" or "PE"
    strike:      float,
    expiry:      str,   # "25JAN2024" format
    quantity:    int,
    action:      str,   # "BUY" or "SELL"
    order_type:  str = "MARKET",  # "MARKET" or "LIMIT"
    price:       float = 0.0,
) -> Optional[Dict]:
    """
    Place an options order via Angel One SmartAPI.

    Returns order response dict or None on failure.
    Prevents duplicate orders (same symbol/strike/action within same minute).
    """
    global _client

    if _client is None:
        logger.error("Broker not connected. Call connect_broker() first.")
        return None

    # Duplicate order guard
    dup_hash = _order_hash(symbol, option_type, strike, action)
    if dup_hash in _last_order_hashes:
        logger.warning(f"Duplicate order blocked: {action} {option_type} {strike}")
        return None
    _last_order_hashes.add(dup_hash)
    # Expire old hashes (keep last 20)
    if len(_last_order_hashes) > 20:
        _last_order_hashes.pop()

    # Construct trading symbol (Angel One format)
    # Example: NIFTY25JAN2024CE24000
    trading_symbol = f"{symbol}{expiry}{option_type}{int(strike)}"

    order_params = {
        "variety":          "NORMAL",
        "tradingsymbol":    trading_symbol,
        "symboltoken":      await _lookup_token(trading_symbol),
        "transactiontype":  action,              # BUY / SELL
        "exchange":         "NFO",               # NSE Futures & Options
        "ordertype":        order_type,
        "producttype":      "INTRADAY",
        "duration":         "DAY",
        "price":            str(price) if order_type == "LIMIT" else "0",
        "squareoff":        "0",
        "stoploss":         "0",
        "quantity":         str(quantity),
    }

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: _client.placeOrder(order_params)
        )

        if response.get("status"):
            order_id = response.get("data", {}).get("orderid")
            logger.info(f"✅ Order placed: {action} {trading_symbol} x{quantity} | ID: {order_id}")
            return {"success": True, "order_id": order_id, "response": response}
        else:
            logger.error(f"Order failed: {response.get('message')}")
            return {"success": False, "error": response.get("message")}

    except Exception as e:
        logger.error(f"Order placement error: {e}")
        return {"success": False, "error": str(e)}


async def _lookup_token(trading_symbol: str) -> str:
    """
    Look up the Angel One symbol token for an options contract.
    In production, maintain a local symbol token master file.
    Download from: https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json
    """
    # Simplified: in production, load token master JSON and lookup by trading_symbol
    # For now returns empty string (Angel One may auto-resolve for MARKET orders)
    logger.debug(f"Token lookup for {trading_symbol} — use symbol master in production")
    return ""


async def get_ltp(trading_symbol: str, token: str = "") -> Optional[float]:
    """
    Get Last Traded Price for an option contract.
    More accurate than yfinance for live trading.
    """
    global _client
    if _client is None:
        return None
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            lambda: _client.ltpData("NFO", trading_symbol, token)
        )
        if data.get("status"):
            return float(data["data"]["ltp"])
    except Exception as e:
        logger.error(f"LTP fetch error: {e}")
    return None


async def get_positions() -> list:
    """Fetch all open positions from broker."""
    global _client
    if _client is None:
        return []
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _client.position)
        return data.get("data", []) if data.get("status") else []
    except Exception as e:
        logger.error(f"Position fetch error: {e}")
        return []


async def square_off_all() -> bool:
    """Emergency: close all open positions."""
    positions = await get_positions()
    success = True
    for pos in positions:
        if int(pos.get("netqty", 0)) != 0:
            qty     = abs(int(pos["netqty"]))
            action  = "SELL" if int(pos["netqty"]) > 0 else "BUY"
            result  = await place_order(
                symbol=pos["tradingsymbol"],
                option_type="",   # Already in tradingsymbol
                strike=0,
                expiry="",
                quantity=qty,
                action=action,
            )
            if not result or not result.get("success"):
                logger.error(f"Failed to square off {pos['tradingsymbol']}")
                success = False
    return success
