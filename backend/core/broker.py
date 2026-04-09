"""
Upstox Broker Adapter
---------------------
Uses manual access token (simple method)

Env variables required:
- UPSTOX_API_KEY
- UPSTOX_API_SECRET
- UPSTOX_ACCESS_TOKEN
"""

import os
import requests
from typing import Optional, Dict
from loguru import logger

BASE_URL = "https://api.upstox.com/v2"


# ─────────────────────────────────────────────────────────────
# Helper: Get headers
# ─────────────────────────────────────────────────────────────
def get_headers() -> Dict[str, str]:
    token = os.getenv("UPSTOX_ACCESS_TOKEN")

    if not token:
        raise RuntimeError("❌ UPSTOX_ACCESS_TOKEN not set in environment")

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ─────────────────────────────────────────────────────────────
# Check connection
# ─────────────────────────────────────────────────────────────
def connect_broker() -> bool:
    try:
        profile = get_profile()
        if profile:
            logger.info("✅ Connected to Upstox successfully")
            return True
        return False
    except Exception as e:
        logger.error(f"Upstox connection failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# Get user profile
# ─────────────────────────────────────────────────────────────
def get_profile() -> Optional[Dict]:
    try:
        url = f"{BASE_URL}/user/profile"
        response = requests.get(url, headers=get_headers())

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Profile error: {response.text}")
            return None

    except Exception as e:
        logger.error(f"Profile fetch error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Place order
# ─────────────────────────────────────────────────────────────
def place_order(
    instrument_token: str,
    quantity: int,
    action: str = "BUY",  # BUY or SELL
    order_type: str = "MARKET",
    price: float = 0.0,
) -> Optional[Dict]:

    try:
        url = f"{BASE_URL}/order/place"

        payload = {
            "quantity": quantity,
            "product": "D",  # Intraday
            "validity": "DAY",
            "price": price if order_type == "LIMIT" else 0,
            "tag": "options-bot",
            "instrument_token": instrument_token,
            "order_type": order_type,
            "transaction_type": action,
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": False,
        }

        response = requests.post(url, json=payload, headers=get_headers())

        data = response.json()

        if response.status_code == 200:
            logger.info(f"✅ Order placed: {action} {instrument_token}")
            return data
        else:
            logger.error(f"❌ Order failed: {data}")
            return None

    except Exception as e:
        logger.error(f"Order error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Get LTP (Last Traded Price)
# ─────────────────────────────────────────────────────────────
def get_ltp(instrument_token: str) -> Optional[float]:
    try:
        url = f"{BASE_URL}/market-quote/ltp?instrument_key={instrument_token}"

        response = requests.get(url, headers=get_headers())
        data = response.json()

        if response.status_code == 200:
            return data["data"][instrument_token]["last_price"]

        else:
            logger.error(f"LTP error: {data}")
            return None

    except Exception as e:
        logger.error(f"LTP fetch error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Get positions
# ─────────────────────────────────────────────────────────────
def get_positions() -> list:
    try:
        url = f"{BASE_URL}/portfolio/positions"
        response = requests.get(url, headers=get_headers())

        if response.status_code == 200:
            return response.json().get("data", [])

        return []

    except Exception as e:
        logger.error(f"Positions error: {e}")
        return []


# ─────────────────────────────────────────────────────────────
# Square off all positions
# ─────────────────────────────────────────────────────────────
def square_off_all() -> bool:
    positions = get_positions()

    success = True

    for pos in positions:
        qty = abs(int(pos.get("quantity", 0)))

        if qty == 0:
            continue

        action = "SELL" if pos["quantity"] > 0 else "BUY"

        result = place_order(
            instrument_token=pos["instrument_token"],
            quantity=qty,
            action=action,
        )

        if not result:
            success = False
          
    return success
