"""
Upstox Broker Adapter — Fixed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reads access token from DATABASE (not just env var).
Token saved by upstox_auth.py after OAuth login.
Falls back to UPSTOX_ACCESS_TOKEN env var if DB token missing.
"""

import httpx
from typing import Optional, Dict
from loguru import logger

BASE_URL = "https://api.upstox.com/v2"


async def _get_token() -> str:
    """Get token from DB (saved by OAuth login) or env var fallback."""
    from api.upstox_auth import get_upstox_token
    token = await get_upstox_token()
    if not token:
        raise RuntimeError(
            "❌ Upstox not logged in. "
            "Go to the dashboard → Upstox Login button → login once."
        )
    return token


def _headers(token: str) -> Dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


async def connect_broker() -> bool:
    """Verify Upstox connection using stored token."""
    try:
        token = await _get_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/user/profile",
                headers=_headers(token)
            )
        if resp.status_code == 200:
            name = resp.json().get("data", {}).get("user_name", "Unknown")
            logger.info(f"✅ Upstox connected | User: {name}")
            return True
        logger.error(f"Upstox profile check failed: {resp.status_code} {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Upstox connection error: {e}")
        return False


async def place_order(
    instrument_token: str,
    quantity:         int,
    action:           str = "BUY",   # BUY or SELL
    order_type:       str = "MARKET",
    price:            float = 0.0,
) -> Optional[Dict]:
    """Place order on Upstox."""
    try:
        token = await _get_token()
        payload = {
            "quantity":          quantity,
            "product":           "D",          # Intraday
            "validity":          "DAY",
            "price":             price if order_type == "LIMIT" else 0,
            "tag":               "options-bot",
            "instrument_token":  instrument_token,
            "order_type":        order_type,
            "transaction_type":  action,
            "disclosed_quantity": 0,
            "trigger_price":     0,
            "is_amo":            False,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{BASE_URL}/order/place",
                json=payload,
                headers=_headers(token)
            )
        data = resp.json()
        if resp.status_code == 200:
            order_id = data.get("data", {}).get("order_id", "")
            logger.info(f"✅ Upstox order placed: {action} {instrument_token} x{quantity} | ID={order_id}")
            return data
        logger.error(f"❌ Upstox order failed: {data}")
        return None
    except Exception as e:
        logger.error(f"Upstox order error: {e}")
        return None


async def get_ltp(instrument_token: str) -> Optional[float]:
    """Get Last Traded Price for an instrument."""
    try:
        token = await _get_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/market-quote/ltp?instrument_key={instrument_token}",
                headers=_headers(token)
            )
        if resp.status_code == 200:
            return resp.json()["data"][instrument_token]["last_price"]
        logger.error(f"LTP error: {resp.text}")
        return None
    except Exception as e:
        logger.error(f"LTP fetch error: {e}")
        return None


async def get_positions() -> list:
    """Get all open positions."""
    try:
        token = await _get_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/portfolio/positions",
                headers=_headers(token)
            )
        if resp.status_code == 200:
            return resp.json().get("data", [])
        return []
    except Exception as e:
        logger.error(f"Positions error: {e}")
        return []


async def square_off_all() -> bool:
    """Emergency: close all open positions on Upstox."""
    positions = await get_positions()
    success = True
    for pos in positions:
        qty = abs(int(pos.get("quantity", 0)))
        if qty == 0:
            continue
        action = "SELL" if pos["quantity"] > 0 else "BUY"
        result = await place_order(
            instrument_token=pos["instrument_token"],
            quantity=qty,
            action=action,
        )
        if not result:
            success = False
    return success
