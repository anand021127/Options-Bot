"""
Execution Engine — v3.1 (Zero-Assumption)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT RULES:
  ❌ Never construct instrument token from strings (e.g. "NSE_FO|NIFTY24JAN...")
  ✅ Always use instrument_key from the option object (from Upstox API)

  ❌ Never assume lot size
  ✅ lot_size passed from option["lot_size"] (from Upstox instruments API)

  Paper mode: uses REAL market LTP for price simulation, only money is fake
  Live mode:  real orders via Upstox REST API using the actual instrument_key

Logging: every order logs entry_spot, entry_premium, strike, expiry,
         lot_size, instrument_key, order_id, fill_price, latency_ms.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Optional
from loguru import logger
from config import settings
from utils.time import now_ist_iso


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
        "timestamp":       now_ist_iso(),
    }


# ─── Paper mode ───────────────────────────────────────────────────────────────

def _simulate_fill(ltp: float, action: str, slip_pct: float) -> float:
    """
    Simulate realistic fill with configurable slippage.
    Uses REAL market LTP — only the money is simulated.
    """
    import random
    noise    = random.uniform(0.6, 1.2)
    slip_amt = ltp * (slip_pct / 100) * noise
    return round(ltp + slip_amt if action == "BUY" else ltp - slip_amt, 2)


async def paper_execute(
    instrument_key: str,
    quantity: int,
    action: str,
    ltp: float,
    lot_size: int,
    strike: float,
    option_type: str,
    expiry: str,
    entry_spot: float,
) -> Dict:
    """
    Paper execution using REAL market data (price is real, money is simulated).
    Logs the same fields as a live order for consistent audit trail.
    """
    t0         = time.time()
    await asyncio.sleep(0.05)   # simulate network round-trip
    fill_price = _simulate_fill(ltp, action, settings.SLIPPAGE_PCT)
    slip_pct   = abs(fill_price - ltp) / ltp * 100
    latency    = (time.time() - t0) * 1000
    lots       = quantity // lot_size

    logger.info(
        f"📄 PAPER {action} | {option_type} {strike} exp={expiry} | "
        f"Spot=₹{entry_spot:.0f} | LTP=₹{ltp} → Fill=₹{fill_price} | "
        f"Slip={slip_pct:.2f}% | {lots}L ({quantity}u) | lot_size={lot_size} | "
        f"key={instrument_key[:50]}"
    )

    return _make_exec_result(
        success=True, order_id=f"PAPER-{int(time.time())}",
        fill_price=fill_price, requested_price=ltp,
        quantity=quantity, status=OrderStatus.FILLED,
        slippage_pct=slip_pct, latency_ms=latency, broker="paper",
    )


# ─── Upstox live execution ────────────────────────────────────────────────────

async def _upstox_execute(
    instrument_key: str,   # ← from Upstox API, never constructed
    quantity: int,
    action: str,
    ltp: float,
    lot_size: int,
    strike: float,
    option_type: str,
    expiry: str,
    entry_spot: float,
) -> Dict:
    """
    Execute real order on Upstox using the actual instrument_key from API.
    ❌ Does NOT construct "NSE_FO|SYMBOL..." strings — uses the key directly.
    """
    t0 = time.time()

    if not instrument_key:
        return _make_exec_result(
            success=False, order_id="", fill_price=ltp, requested_price=ltp,
            quantity=quantity, status=OrderStatus.REJECTED, slippage_pct=0,
            latency_ms=0, error="instrument_key missing — cannot place live order",
            broker="upstox",
        )

    try:
        import httpx
        from api.upstox_auth import get_upstox_token

        token = await get_upstox_token()
        if not token:
            return _make_exec_result(
                success=False, order_id="", fill_price=ltp, requested_price=ltp,
                quantity=quantity, status=OrderStatus.REJECTED, slippage_pct=0,
                latency_ms=(time.time()-t0)*1000,
                error="NO_TOKEN: Login to Upstox via dashboard first",
                broker="upstox",
            )

        payload = {
            "quantity":          quantity,
            "product":           "D",          # intraday
            "validity":          "DAY",
            "price":             ltp if settings.ORDER_TYPE == "LIMIT" else 0,
            "tag":               "optbot",
            "instrument_token":  instrument_key,   # ← exact key from API
            "order_type":        settings.ORDER_TYPE,
            "transaction_type":  action,
            "disclosed_quantity": 0,
            "trigger_price":     0,
            "is_amo":            False,
        }

        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(
                "https://api.upstox.com/v2/order/place",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type":  "application/json",
                    "Accept":        "application/json",
                },
            )

        latency    = (time.time() - t0) * 1000
        resp_data  = resp.json()
        order_id   = resp_data.get("data", {}).get("order_id", "")
        lots       = quantity // lot_size

        if resp.status_code == 200 and order_id:
            # Get actual fill price from Upstox after order placed
            fill_price = ltp   # start with LTP
            try:
                from data.upstox_market import _get_ltp_rest
                actual = await _get_ltp_rest(instrument_key)
                if actual:
                    fill_price = actual
            except Exception:
                pass

            slip_pct = abs(fill_price - ltp) / ltp * 100

            logger.info(
                f"✅ LIVE {action} | order_id={order_id} | "
                f"{option_type} {strike} exp={expiry} | "
                f"Spot=₹{entry_spot:.0f} | LTP=₹{ltp} → Fill=₹{fill_price} | "
                f"Slip={slip_pct:.2f}% | {lots}L ({quantity}u) lot_size={lot_size} | "
                f"key={instrument_key[:50]} | {latency:.0f}ms"
            )

            return _make_exec_result(
                success=True, order_id=order_id,
                fill_price=fill_price, requested_price=ltp,
                quantity=quantity, status=OrderStatus.FILLED,
                slippage_pct=slip_pct, latency_ms=latency, broker="upstox",
            )

        # Order failed
        err_msg = resp_data.get("message") or resp_data.get("errors") or str(resp_data)
        logger.error(
            f"❌ LIVE {action} REJECTED | {option_type} {strike} | "
            f"key={instrument_key[:50]} | status={resp.status_code} | {err_msg}"
        )
        return _make_exec_result(
            success=False, order_id="", fill_price=ltp, requested_price=ltp,
            quantity=quantity, status=OrderStatus.REJECTED, slippage_pct=0,
            latency_ms=latency, error=str(err_msg), broker="upstox",
        )

    except Exception as e:
        latency = (time.time() - t0) * 1000
        logger.error(f"Upstox execute exception: {e}")
        return _make_exec_result(
            success=False, order_id="", fill_price=ltp, requested_price=ltp,
            quantity=quantity, status=OrderStatus.REJECTED, slippage_pct=0,
            latency_ms=latency, error=str(e), broker="upstox",
        )


# ─── Main router with retry ───────────────────────────────────────────────────

async def execute_order(
    instrument_key: str,    # ← always from Upstox API
    option_type:    str,
    strike:         float,
    expiry:         str,
    quantity:       int,
    action:         str,    # BUY | SELL
    ltp:            float,
    lot_size:       int,    # ← from Upstox instruments API
    entry_spot:     float,  # ← Nifty spot at time of order
    mode:           str = "paper",
    # Legacy kwargs — ignored, kept for compat
    symbol:         str = "",
    token:          str = "",
) -> Dict:
    """
    Route order to paper or live execution with retry.

    VALIDATION before any order:
      - instrument_key must exist
      - lot_size must be > 0 (from API)
      - ltp must be > 0
      - quantity must be > 0

    Retries up to ORDER_RETRY_MAX times on live failure.
    """
    # ── Pre-execution validation ───────────────────────────────────────────────
    if not instrument_key:
        logger.error("❌ ORDER BLOCKED: instrument_key missing")
        return _make_exec_result(
            success=False, order_id="", fill_price=0, requested_price=0,
            quantity=quantity, status=OrderStatus.REJECTED, slippage_pct=0,
            latency_ms=0, error="VALIDATION_FAIL: instrument_key missing",
        )

    if not lot_size or lot_size <= 0:
        logger.error(f"❌ ORDER BLOCKED: lot_size={lot_size} (must be > 0 from API)")
        return _make_exec_result(
            success=False, order_id="", fill_price=0, requested_price=0,
            quantity=quantity, status=OrderStatus.REJECTED, slippage_pct=0,
            latency_ms=0, error="VALIDATION_FAIL: lot_size missing/zero",
        )

    if ltp <= 0:
        logger.error(f"❌ ORDER BLOCKED: LTP={ltp} (must be > 0)")
        return _make_exec_result(
            success=False, order_id="", fill_price=0, requested_price=0,
            quantity=quantity, status=OrderStatus.REJECTED, slippage_pct=0,
            latency_ms=0, error="VALIDATION_FAIL: LTP is zero/negative",
        )

    if quantity <= 0:
        logger.error(f"❌ ORDER BLOCKED: quantity={quantity}")
        return _make_exec_result(
            success=False, order_id="", fill_price=0, requested_price=0,
            quantity=quantity, status=OrderStatus.REJECTED, slippage_pct=0,
            latency_ms=0, error="VALIDATION_FAIL: quantity is zero",
        )

    # ── Execute ────────────────────────────────────────────────────────────────
    max_retries = settings.ORDER_RETRY_MAX if mode == "live" else 0
    attempt     = 0
    last_result = None

    while attempt <= max_retries:
        if attempt > 0:
            logger.warning(f"Retry {attempt}/{max_retries} for {instrument_key[:40]}")
            await asyncio.sleep(settings.ORDER_RETRY_DELAY)

        if mode == "paper" or settings.BROKER.lower() not in ("upstox", "angel", "fyers"):
            result = await paper_execute(
                instrument_key=instrument_key, quantity=quantity,
                action=action, ltp=ltp, lot_size=lot_size,
                strike=strike, option_type=option_type,
                expiry=expiry, entry_spot=entry_spot,
            )
        else:
            result = await _upstox_execute(
                instrument_key=instrument_key, quantity=quantity,
                action=action, ltp=ltp, lot_size=lot_size,
                strike=strike, option_type=option_type,
                expiry=expiry, entry_spot=entry_spot,
            )

        last_result = result
        if result["success"]:
            return result

        attempt += 1

    logger.error(f"❌ Order FAILED after {attempt} attempt(s): {last_result.get('error')}")
    return last_result


async def connect_broker() -> bool:
    """Verify broker connectivity at bot startup."""
    broker = settings.BROKER.lower()

    if broker == "none" or not broker:
        logger.info("No live broker configured — paper mode")
        return True

    if broker == "upstox":
        from core.broker import connect_broker as ub_connect
        return await ub_connect()

    logger.warning(f"Broker '{broker}' not implemented — paper fallback")
    return True
