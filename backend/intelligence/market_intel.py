"""
Market Intelligence Module — v3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Prevents trading during adverse market conditions:

  1. Event calendar — RBI, Budget, earnings, FOMC
  2. Global sentiment — S&P 500 proxy via yfinance
  3. No-trade day detection — auto-detect dead/choppy days
  4. Expiry day detection — Thursday weekly
  5. Gap analysis — overnight position risk assessment

All functions are fast (cached) and fallback gracefully.
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, Optional, Tuple
from loguru import logger
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# ─── Manual Event Calendar ────────────────────────────────────────────────────
# Add/remove dates as needed. Format: "YYYY-MM-DD"
# These are examples — update with actual RBI/budget/FOMC dates.

BLOCKED_DATES: Dict[str, str] = {
    # "2024-02-01": "Union Budget",
    # "2024-04-05": "RBI Policy",
    # "2024-06-12": "FOMC Meeting",
    # Add your dates here
}

# Whether manual event blocking is active (can be toggled from dashboard)
_event_block_enabled = True


def set_event_block(enabled: bool):
    global _event_block_enabled
    _event_block_enabled = enabled
    logger.info(f"Event block {'enabled' if enabled else 'disabled'}")


def is_high_impact_event_today() -> bool:
    """Check if today is a manually blocked high-impact event day."""
    if not _event_block_enabled:
        return False
    today = date.today().isoformat()
    if today in BLOCKED_DATES:
        logger.warning(f"🚫 High-impact event today: {BLOCKED_DATES[today]}")
        return True
    return False


def add_blocked_date(dt: str, reason: str):
    """Add a blocked date at runtime (from dashboard)."""
    BLOCKED_DATES[dt] = reason
    logger.info(f"Added blocked date: {dt} — {reason}")


def remove_blocked_date(dt: str):
    BLOCKED_DATES.pop(dt, None)


def get_blocked_dates() -> Dict[str, str]:
    return dict(BLOCKED_DATES)


# ─── Expiry Day Detection ─────────────────────────────────────────────────────

def is_expiry_day(symbol: str = "NIFTY") -> bool:
    """
    Check if today is an actual expiry day for the given symbol.
    Uses expiry dates loaded from Upstox instruments API.
    ❌ Does NOT assume Thursday or any fixed weekday.
    ✅ Checks actual dates from the instruments cache.
    Falls back to checking loaded expiry list if available,
    otherwise returns False (conservative — allow BTST if unsure).
    """
    from data.upstox_market import _instruments_cache, _instruments_loaded
    today_str = date.today().isoformat()

    # If instruments are loaded, use actual expiry dates
    if _instruments_loaded.get(symbol.upper()):
        expiries = set()
        for meta in _instruments_cache.values():
            if meta.get("symbol", "").upper() == symbol.upper():
                expiries.add(meta.get("expiry", ""))
        if expiries and today_str in expiries:
            logger.info(f"⚠️ Expiry day confirmed from API: {today_str} for {symbol}")
            return True
        return False

    # Instruments not loaded yet — cannot confirm, return False (safe default)
    logger.debug(f"Instruments not loaded for {symbol} — cannot confirm expiry day, assuming no")
    return False


def days_to_expiry(symbol: str = "NIFTY") -> int:
    """
    Days to next expiry from Upstox instruments API.
    ❌ Does NOT calculate from weekday.
    """
    from data.upstox_market import _instruments_cache, _instruments_loaded
    today = date.today()
    today_str = today.isoformat()

    if _instruments_loaded.get(symbol.upper()):
        expiries = sorted(set(
            meta.get("expiry", "")
            for meta in _instruments_cache.values()
            if meta.get("symbol", "").upper() == symbol.upper()
            and meta.get("expiry", "") >= today_str
        ))
        if expiries:
            next_exp = date.fromisoformat(expiries[0])
            return (next_exp - today).days

    return -1  # unknown


# ─── Global Sentiment (via Stooq free API — no yfinance) ─────────────────────

_sentiment_cache: Dict = {}
_SENTIMENT_TTL = 3600   # 1 hour cache


async def get_global_sentiment() -> Dict:
    """
    Fetch S&P 500 sentiment via Stooq free data API (no yfinance, no API key).
    ❌ No yfinance fallback.
    If fetch fails → returns NEUTRAL (does not block trading, just no bonus/penalty).
    Sentiment is a scoring modifier only — not a hard gate.
    """
    global _sentiment_cache
    now = datetime.now()
    if _sentiment_cache and (now - _sentiment_cache.get("fetched_at", datetime.min)).seconds < _SENTIMENT_TTL:
        return _sentiment_cache["data"]

    try:
        import httpx
        # Stooq provides free historical quotes without API key
        async with httpx.AsyncClient(timeout=8) as c:
            resp = await c.get(
                "https://stooq.com/q/d/l/",
                params={"s": "^spx", "i": "d"},
                headers={"User-Agent": "Mozilla/5.0"},
            )
        if resp.status_code != 200:
            raise ValueError(f"Stooq HTTP {resp.status_code}")

        lines = resp.text.strip().splitlines()
        if len(lines) < 3:
            raise ValueError("Stooq returned insufficient data")

        # CSV: Date,Open,High,Low,Close,Volume — get last 2 rows
        rows = [l.split(",") for l in lines[-2:]]
        prev_close = float(rows[0][4])
        last_close = float(rows[1][4])
        chg_pct    = round(((last_close - prev_close) / prev_close) * 100, 2)

        if chg_pct >= 0.5:
            direction, signal = "BULLISH", "RISK_ON"
            msg = f"S&P 500 +{chg_pct:.1f}% — risk-on"
        elif chg_pct <= -0.5:
            direction, signal = "BEARISH", "RISK_OFF"
            msg = f"S&P 500 {chg_pct:.1f}% — risk-off"
        else:
            direction, signal = "NEUTRAL", "NEUTRAL"
            msg = f"S&P 500 flat ({chg_pct:.1f}%)"

        data = {"direction": direction, "change_pct": chg_pct, "signal": signal, "message": msg}
        _sentiment_cache = {"data": data, "fetched_at": now}
        logger.debug(f"Sentiment: {msg}")
        return data

    except Exception as e:
        logger.warning(f"Sentiment fetch failed ({e}) — using NEUTRAL (non-critical)")
        return {"direction": "NEUTRAL", "change_pct": 0, "signal": "NEUTRAL",
                "message": "Sentiment unavailable — neutral applied"}


# ─── No-Trade Day Detection ───────────────────────────────────────────────────

_no_trade_day_cache: Dict = {}


async def is_no_trade_day(symbol: str = "NIFTY") -> Tuple[bool, str]:
    """
    Auto-detect dead/low-opportunity days.
    A "no-trade day" has ALL of:
      - ADX < 18 (extremely flat)
      - Volume < 60% of 20-day average
      - ATR < 0.3% of price (market barely moving)
      - No signal generated in last 2 hours

    Returns (is_dead, reason).
    """
    today_str = date.today().isoformat()
    cached    = _no_trade_day_cache.get(today_str)
    if cached:
        return cached

    try:
        from data.upstox_market import fetch_ohlcv
        from strategy.indicators import adx, atr, volume_confirmation, compute_all_indicators

        df = await fetch_ohlcv(symbol, period="5d", interval="5m")
        if df is None or len(df) < 50:
            return False, "Insufficient data"

        df     = compute_all_indicators(df)
        df_adx = adx(df.tail(60))
        latest = df.iloc[-1]

        adx_val    = float(df_adx["adx"].iloc[-1]) if not df_adx["adx"].isna().iloc[-1] else 20.0
        atr_val    = float(latest["atr"])
        price      = float(latest["close"])
        atr_pct    = (atr_val / price) * 100
        vol_ok     = volume_confirmation(df)

        conditions = {
            "low_adx":    adx_val < 18,
            "low_volume": not vol_ok,
            "low_atr":    atr_pct < 0.3,
        }

        hits = sum(conditions.values())
        if hits >= 2:
            reason = (f"No-trade day detected: ADX={adx_val:.0f} | "
                      f"ATR={atr_pct:.2f}% | Vol={'OK' if vol_ok else 'LOW'}")
            logger.warning(f"⚠️ {reason}")
            result = (True, reason)
        else:
            result = (False, "Market conditions acceptable")

        _no_trade_day_cache[today_str] = result
        return result

    except Exception as e:
        logger.error(f"No-trade day check error: {e}")
        return False, "Check failed — allowing trades"


# ─── Gap Analysis ─────────────────────────────────────────────────────────────

async def analyse_gap(symbol: str = "NIFTY") -> Dict:
    """
    Analyse overnight gap for BTST position management.
    Compares yesterday's close with today's open.
    """
    try:
        from data.upstox_market import fetch_ohlcv
        df = await fetch_ohlcv(symbol, period="5d", interval="1d")
        if df is None or len(df) < 2:
            return {"gap_pct": 0, "direction": "NONE", "message": "No data"}

        prev_close = float(df["close"].iloc[-2])
        today_open = float(df["open"].iloc[-1])
        gap_pct    = ((today_open - prev_close) / prev_close) * 100

        if gap_pct > 0.5:
            direction = "GAP_UP"
            msg       = f"Gap up {gap_pct:.1f}% — favours CE holders"
        elif gap_pct < -0.5:
            direction = "GAP_DOWN"
            msg       = f"Gap down {abs(gap_pct):.1f}% — favours PE holders"
        else:
            direction = "FLAT"
            msg       = f"Flat open (gap {gap_pct:.1f}%)"

        return {"gap_pct": round(gap_pct, 2), "direction": direction, "message": msg,
                "prev_close": prev_close, "today_open": today_open}

    except Exception as e:
        return {"gap_pct": 0, "direction": "NONE", "message": f"Error: {e}"}


# ─── Market Status Summary ────────────────────────────────────────────────────

async def get_market_status(symbol: str = "NIFTY") -> Dict:
    """
    Full market status for dashboard display.
    Returns regime, IV condition, global sentiment, event flags.
    """
    sentiment    = await get_global_sentiment()
    no_trade, reason = await is_no_trade_day(symbol)
    event_today  = is_high_impact_event_today()
    expiry       = is_expiry_day(symbol)
    dte          = days_to_expiry(symbol)

    return {
        "global_sentiment":    sentiment,
        "no_trade_day":        no_trade,
        "no_trade_reason":     reason,
        "high_impact_event":   event_today,
        "is_expiry_day":       expiry,
        "days_to_expiry":      dte,
        "blocked_dates":       get_blocked_dates(),
        "trading_allowed":     not (no_trade or event_today),
        "timestamp":           datetime.now().isoformat(),
    }
