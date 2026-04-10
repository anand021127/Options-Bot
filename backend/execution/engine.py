"""
Execution Engine — v3 Fixed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Supports:
  - Upstox API   (your broker — token read from DB)
  - Angel One    (alternative)
  - Fyers        (alternative)
  - Paper mode   (realistic simulation)

Upstox token flow:
  1. User logs in via /api/upstox/login (OAuth, once per day)
  2. Token saved to SQLite DB by upstox_auth.py
  3. engine.py reads token from DB for every order
  4. Token survives Render restarts because it's in the DB
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Optional
from loguru import logger
from config import settings


class OrderStatus:
    PENDING   = "PENDING"
    FILLED    = "FILLED"
    REJECTED  = "REJECTED"
    CANCELLED = "CANCELLED"


def _make_exec_result(
    success: bool, order_id: str, fill_price: float, requested_price: float,
    quantity: int, status: str, slippage_pct: float, latency_ms: float,
    error: str = "", broker: str = "paper",
) -> Dict:
    return {
        "success":         success,
        "order_id":        order_id,
        "status":          status,
        "fill_price":      round(fill_price, 2),
        "requested_price": round(requested_price, 2),
        "slippage_pct":    round(slippage_pct, 3),
        "slippage_amount": round(abs(fill_price - requested_price), 2),
        "quantity":        quantity,
        "latency_ms":      round(latency_ms, 1),
        "broker":          broker,
        "error":           error,
        "timestamp":       datetime.now().isoformat(),
    }


# ─── Paper simulation ─────────────────────────────────────────────────────────

def _simulate_fill(ltp: float, action: str, slippage_pct: float) -> float:
    import random
    noise    = random.uniform(0.6, 1.2)
    slip_amt = ltp * (slippage_pct / 100) * noise
    return round(ltp + slip_amt if action == "BUY" else ltp - slip_amt, 2)


async def paper_execute(
    symbol: str, option_type: str, strike: float,
    expiry: str, quantity: int, action: str, ltp: float,
) -> Dict:
    """Enhanced paper execution with realistic slippage simulation."""
    t0         = time.time()
    await asyncio.sleep(0.05)
    fill_price = _simulate_fill(ltp, action, settings.SLIPPAGE_PCT)
    actual_slip = abs(fill_price - ltp) / ltp * 100
    latency     = (time.time() - t0) * 1000
    logger.info(
        f"📄 PAPER {action} | {option_type} {strike} | "
        f"LTP={ltp} → Fill={fill_price} | Slip={actual_slip:.2f}% | Qty={quantity}"
    )
    return _make_exec_result(
        success=True, order_id=f"PAPER-{int(time.time())}",
        fill_price=fill_price, requested_price=ltp,
        quantity=quantity, status=OrderStatus.FILLED,
        slippage_pct=actual_slip, latency_ms=latency, broker="paper",
    )


# ─── Upstox execution ─────────────────────────────────────────────────────────

async def _upstox_execute(
    symbol: str, option_type: str, strike: float,
    expiry: str, quantity: int, action: str, ltp: float,
) -> Dict:
    """
    Execute real order on Upstox.
    Reads access token from DB (saved by OAuth login).
    instrument_token format for NSE options: NSE_FO|<numeric_token>
    We construct symbol and let Upstox resolve it.
    """
    t0 = time.time()
    try:
        from core.broker import place_order, get_ltp

        # Construct Upstox instrument token for NSE F&O
        # Format: NSE_FO|NIFTY25JAN2024CE24000
        trading_symbol  = f"{symbol}{expiry}{option_type}{int(strike)}"
        instrument_token = f"NSE_FO|{trading_symbol}"

        result = await place_order(
            instrument_token=instrument_token,
            quantity=quantity,
            action=action,
            order_type=settings.ORDER_TYPE,
            price=ltp if settings.ORDER_TYPE == "LIMIT" else 0.0,
        )

        latency = (time.time() - t0) * 1000

        if result:
            order_id   = result.get("data", {}).get("order_id", "")
            # Try to get actual fill price, fallback to LTP
            fill_price = ltp
            try:
                actual = await get_ltp(instrument_token)
                if actual:
                    fill_price = actual
            except Exception:
                pass

            slip_pct = abs(fill_price - ltp) / ltp * 100
            return _make_exec_result(
                success=True, order_id=order_id,
                fill_price=fill_price, requested_price=ltp,
                quantity=quantity, status=OrderStatus.FILLED,
                slippage_pct=slip_pct, latency_ms=latency, broker="upstox",
            )
        else:
            return _make_exec_result(
                success=False, order_id="",
                fill_price=ltp, requested_price=ltp,
                quantity=quantity, status=OrderStatus.REJECTED,
                slippage_pct=0, latency_ms=latency,
                error="Order rejected by Upstox", broker="upstox",
            )

    except RuntimeError as e:
        # Token not available — login required
        latency = (time.time() - t0) * 1000
        logger.error(f"Upstox auth error: {e}")
        return _make_exec_result(
            success=False, order_id="",
            fill_price=ltp, requested_price=ltp,
            quantity=quantity, status=OrderStatus.REJECTED,
            slippage_pct=0, latency_ms=latency,
            error=str(e), broker="upstox",
        )
    except Exception as e:
        latency = (time.time() - t0) * 1000
        logger.error(f"Upstox execute error: {e}")
        return _make_exec_result(
            success=False, order_id="",
            fill_price=ltp, requested_price=ltp,
            quantity=quantity, status=OrderStatus.REJECTED,
            slippage_pct=0, latency_ms=latency,
            error=str(e), broker="upstox",
        )


# ─── Angel One execution ──────────────────────────────────────────────────────

_angel_client    = None
_angel_connected = False


async def _angel_login() -> bool:
    global _angel_client, _angel_connected
    try:
        from SmartApi import SmartConnect
        import pyotp
        loop   = asyncio.get_event_loop()
        client = await loop.run_in_executor(
            None, lambda: SmartConnect(api_key=settings.BROKER_API_KEY)
        )
        totp = pyotp.TOTP(settings.BROKER_TOTP_SECRET).now()
        data = await loop.run_in_executor(
            None,
            lambda: client.generateSession(
                settings.BROKER_CLIENT_CODE, settings.BROKER_API_KEY, totp
            )
        )
        if data.get("status"):
            _angel_client    = client
            _angel_connected = True
            logger.info(f"✅ Angel One connected | {settings.BROKER_CLIENT_CODE}")
            return True
        logger.error(f"Angel login failed: {data.get('message')}")
        return False
    except ImportError:
        logger.error("SmartAPI not installed: pip install smartapi-python pyotp")
        return False
    except Exception as e:
        logger.error(f"Angel login error: {e}")
        return False


async def _angel_place_order(
    trading_symbol: str, token: str, quantity: int, action: str, price: float = 0
) -> Dict:
    global _angel_client
    t0     = time.time()
    params = {
        "variety": "NORMAL", "tradingsymbol": trading_symbol,
        "symboltoken": token, "transactiontype": action,
        "exchange": "NFO", "ordertype": settings.ORDER_TYPE,
        "producttype": "INTRADAY", "duration": "DAY",
        "price": str(price) if settings.ORDER_TYPE == "LIMIT" else "0",
        "squareoff": "0", "stoploss": "0", "quantity": str(quantity),
    }
    try:
        loop   = asyncio.get_event_loop()
        resp   = await loop.run_in_executor(None, lambda: _angel_client.placeOrder(params))
        latency = (time.time() - t0) * 1000
        if resp.get("status"):
            order_id = resp.get("data", {}).get("orderid", "")
            return _make_exec_result(
                success=True, order_id=order_id,
                fill_price=price or 0, requested_price=price or 0,
                quantity=quantity, status=OrderStatus.FILLED,
                slippage_pct=settings.SLIPPAGE_PCT, latency_ms=latency, broker="angel",
            )
        msg = resp.get("message", "Unknown")
        return _make_exec_result(
            success=False, order_id="", fill_price=price or 0, requested_price=price or 0,
            quantity=quantity, status=OrderStatus.REJECTED,
            slippage_pct=0, latency_ms=latency, error=msg, broker="angel",
        )
    except Exception as e:
        return _make_exec_result(
            success=False, order_id="", fill_price=price or 0, requested_price=price or 0,
            quantity=quantity, status=OrderStatus.REJECTED,
            slippage_pct=0, latency_ms=(time.time()-t0)*1000, error=str(e), broker="angel",
        )


# ─── Main router ─────────────────────────────────────────────────────────────

async def execute_order(
    symbol:      str,
    option_type: str,
    strike:      float,
    expiry:      str,
    quantity:    int,
    action:      str,
    ltp:         float,
    token:       str = "",
    mode:        str = "paper",
) -> Dict:
    """
    Route order to the correct broker.
    Retries up to ORDER_RETRY_MAX times on failure (live mode only).
    """
    max_retries = settings.ORDER_RETRY_MAX if mode == "live" else 0
    attempt     = 0
    last_result = None

    while attempt <= max_retries:
        if attempt > 0:
            logger.warning(f"Order retry {attempt}/{max_retries}")
            await asyncio.sleep(settings.ORDER_RETRY_DELAY)

        broker = settings.BROKER.lower()

        if mode == "paper":
            result = await paper_execute(
                symbol, option_type, strike, expiry, quantity, action, ltp
            )
        elif broker == "upstox":
            result = await _upstox_execute(
                symbol, option_type, strike, expiry, quantity, action, ltp
            )
        elif broker == "angel":
            if not _angel_connected:
                await _angel_login()
            trading_sym = f"{symbol}{expiry}{option_type}{int(strike)}"
            result = await _angel_place_order(trading_sym, token, quantity, action, ltp)
        else:
            # Fallback to paper if broker not configured
            logger.warning(f"Broker '{broker}' not configured — using paper mode")
            result = await paper_execute(
                symbol, option_type, strike, expiry, quantity, action, ltp
            )

        last_result = result
        if result["success"]:
            logger.info(
                f"✅ Order filled | {action} {option_type}{strike} x{quantity} "
                f"| Fill=₹{result['fill_price']} | Slip={result['slippage_pct']:.2f}% "
                f"| {result['broker'].upper()} | {result['latency_ms']:.0f}ms"
            )
            return result

        attempt += 1

    logger.error(f"❌ Order FAILED after {attempt} attempts: {last_result.get('error')}")
    return last_result


async def connect_broker() -> bool:
    """Connect to configured broker at startup."""
    broker = settings.BROKER.lower()

    if broker == "none" or not broker:
        logger.info("No broker configured — paper trading mode")
        return True

    if broker == "upstox":
        from core.broker import connect_broker as upstox_connect
        return await upstox_connect()

    if broker == "angel":
        return await _angel_login()

    logger.warning(f"Broker '{broker}' not implemented — falling back to paper")
    return True
