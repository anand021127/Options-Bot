"""
BTST (Buy Today Sell Tomorrow) Strategy Module — v3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Completely separate from intraday strategy.
Runs only after 14:45 IST on non-expiry days.

ENTRY CONDITIONS (ALL must be true):
  1. Time window: 14:45 – 15:15 IST
  2. ADX >= 25 (strong trend — no choppy overnight holds)
  3. Confirmed 15min breakout (not just 5min)
  4. Volume above average
  5. RSI not extreme (25–70 zone)
  6. IV Rank < 60 (don't overpay for overnight premium)
  7. Not expiry day (Thursday for weekly, last Thursday for monthly)
  8. No high-impact events flagged
  9. Max 1 BTST trade per day

EXIT CONDITIONS (next morning):
  1. Primary: 09:20 AM exit (captures overnight gap)
  2. Early exit if gap profit >= 40%
  3. Early exit if strong reverse signal detected

RISK:
  - Max 1% capital risk (tighter than intraday)
  - 30% SL on option premium (held overnight)
"""

import asyncio
from datetime import datetime, date, time as dtime
from typing import Dict, Optional
from loguru import logger
from zoneinfo import ZoneInfo

from strategy.indicators import (
    compute_all_indicators, adx, market_structure, market_regime,
    volume_confirmation, iv_rank_proxy, rsi as calc_rsi,
    detect_confirmed_breakout, get_sr_levels,
)
from data.market_data import fetch_ohlcv, fetch_live_price, get_atm_option
from intelligence.market_intel import is_expiry_day, is_high_impact_event_today
from config import settings

IST = ZoneInfo("Asia/Kolkata")


# ─── BTST Time Gates ──────────────────────────────────────────────────────────

def is_btst_entry_window() -> bool:
    """14:45 – 15:10 IST entry window."""
    now   = datetime.now(IST).time()
    start = dtime(settings.BTST_ENTRY_HOUR, settings.BTST_ENTRY_MIN)   # 14:45
    end   = dtime(15, 10)
    return start <= now <= end


def is_btst_exit_window() -> bool:
    """09:15 – 09:25 IST next-day exit window."""
    now   = datetime.now(IST).time()
    start = dtime(settings.BTST_EXIT_HOUR, settings.BTST_EXIT_MIN)     # 09:20
    end   = dtime(9, 25)
    return start <= now <= end


# ─── BTST Signal Generator ────────────────────────────────────────────────────

async def generate_btst_signal(symbol: str = "NIFTY") -> Dict:
    """
    Generate BTST signal for overnight position.
    Much stricter than intraday — overnight holds have more uncertainty.

    Returns same schema as intraday signal but with btst_trade=True.
    """
    result = {
        "signal_type":   "NO_BTST",
        "btst_trade":    True,
        "score":         0,
        "reasons":       [],
        "blocked_by":    None,
        "option":        None,
        "sl_pct":        30.0,
        "target_pct":    0.0,
        "sl_price":      0.0,
        "target_price":  0.0,
        "price_data":    None,
        "indicators":    {},
        "timestamp":     datetime.now().isoformat(),
    }

    # ── Gate 1: Time window ───────────────────────────────────────────────────
    if not is_btst_entry_window():
        now = datetime.now(IST).time()
        result["reasons"].append(f"⏰ Outside BTST window (14:45–15:10). Now: {now.strftime('%H:%M')}")
        result["blocked_by"] = "TIME"
        return result

    # ── Gate 2: Expiry day check ──────────────────────────────────────────────
    if is_expiry_day():
        result["reasons"].append("🚫 Expiry day — no BTST (theta crush overnight)")
        result["blocked_by"] = "EXPIRY_DAY"
        return result

    # ── Gate 3: High-impact events ────────────────────────────────────────────
    if is_high_impact_event_today():
        result["reasons"].append("🚫 High-impact event today — no BTST")
        result["blocked_by"] = "EVENT"
        return result

    # ── Gate 4: Data ──────────────────────────────────────────────────────────
    price_data = await fetch_live_price(symbol)
    if not price_data:
        result["reasons"].append("No price data")
        result["blocked_by"] = "NO_DATA"
        return result
    result["price_data"] = price_data

    # Use 15min data for BTST (higher timeframe = cleaner signals)
    df15 = await fetch_ohlcv(symbol, period="5d", interval="15m")
    if df15 is None or len(df15) < 20:
        result["reasons"].append("Insufficient 15m data")
        result["blocked_by"] = "NO_DATA"
        return result

    df15  = compute_all_indicators(df15)
    df_adx = adx(df15.tail(60))
    latest = df15.iloc[-1]

    adx_val  = float(df_adx["adx"].iloc[-1]) if not df_adx["adx"].isna().iloc[-1] else 15.0
    plus_di  = float(df_adx["plus_di"].iloc[-1])
    minus_di = float(df_adx["minus_di"].iloc[-1])
    close    = float(latest["close"])
    rsi_val  = float(latest["rsi"])
    vol_ok   = volume_confirmation(df15)
    iv_data  = iv_rank_proxy(df15)
    struct   = market_structure(df15)
    conf_bo  = detect_confirmed_breakout(df15)

    indicators = {
        "close": round(close, 2), "adx": round(adx_val, 1),
        "plus_di": round(plus_di, 1), "minus_di": round(minus_di, 1),
        "rsi": round(rsi_val, 1), "structure": struct,
        "conf_breakout": conf_bo, "vol_ok": vol_ok, "iv_rank": iv_data,
    }
    result["indicators"] = indicators

    # ── Gate 5: ADX strength (strict for BTST) ────────────────────────────────
    if adx_val < 25:
        result["reasons"].append(f"🚫 ADX {adx_val:.0f} < 25 — no clear trend for BTST")
        result["blocked_by"] = "WEAK_TREND"
        return result

    # ── Gate 6: IV environment ────────────────────────────────────────────────
    if iv_data["iv_rank"] > 60:
        result["reasons"].append(f"🚫 IV Rank {iv_data['iv_rank']} too high — overnight premium risky")
        result["blocked_by"] = "HIGH_IV"
        return result

    # ── Gate 7: RSI not extreme ───────────────────────────────────────────────
    if rsi_val > 72 or rsi_val < 28:
        result["reasons"].append(f"🚫 RSI {rsi_val:.0f} extreme — reversal risk overnight")
        result["blocked_by"] = "RSI_EXTREME"
        return result

    # ── Gate 8: Volume confirmation ───────────────────────────────────────────
    if not vol_ok:
        result["reasons"].append("🚫 Volume below average — weak conviction for overnight")
        result["blocked_by"] = "LOW_VOLUME"
        return result

    # ── Gate 9: Require confirmed 15min breakout ──────────────────────────────
    if not conf_bo:
        result["reasons"].append("🚫 No confirmed 15min breakout — BTST requires strong momentum")
        result["blocked_by"] = "NO_BREAKOUT"
        return result

    # ── Scoring ───────────────────────────────────────────────────────────────
    score     = 0
    direction = None

    if conf_bo == "CONFIRMED_BREAKOUT_UP" and plus_di > minus_di and struct == "BULLISH":
        direction = "CE"
        score += 5
        result["reasons"].append(f"✅ 15min confirmed breakout UP | ADX {adx_val:.0f} | +DI>{minus_di:.0f}")
        result["reasons"].append(f"✅ Structure BULLISH | RSI {rsi_val:.0f} | Volume OK")
        result["reasons"].append(f"✅ IV Rank {iv_data['iv_rank']} — acceptable overnight premium")

    elif conf_bo == "CONFIRMED_BREAKOUT_DOWN" and minus_di > plus_di and struct == "BEARISH":
        direction = "PE"
        score += 5
        result["reasons"].append(f"✅ 15min confirmed breakdown | ADX {adx_val:.0f} | -DI>{plus_di:.0f}")
        result["reasons"].append(f"✅ Structure BEARISH | RSI {rsi_val:.0f} | Volume OK")
        result["reasons"].append(f"✅ IV Rank {iv_data['iv_rank']} — acceptable overnight premium")

    if not direction:
        result["reasons"].append("No directional confluence for BTST")
        result["blocked_by"] = "NO_CONFLUENCE"
        return result

    result["score"] = score

    # ── Option selection ──────────────────────────────────────────────────────
    option = await get_atm_option(symbol, direction)
    if not option or option.get("ltp", 0) <= 0:
        result["reasons"].append("Option LTP unavailable")
        result["blocked_by"] = "NO_OPTION_DATA"
        return result

    ltp        = option["ltp"]
    sl_pct     = 30.0             # 30% SL — wider for overnight holds
    target_pct = 50.0             # 50% target (gap play)
    sl_price   = round(ltp * 0.70, 2)
    tgt_price  = round(ltp * 1.50, 2)

    result.update({
        "signal_type":   f"BTST_{direction}",
        "option":        option,
        "sl_pct":        sl_pct,
        "target_pct":    target_pct,
        "sl_price":      sl_price,
        "target_price":  tgt_price,
        "partial_target": round(ltp * 1.30, 2),  # early exit at +30%
    })

    logger.info(
        f"🌙 BTST SIGNAL: {direction} | {symbol} {option['strike']} | "
        f"LTP={ltp} | SL={sl_price} | Target={tgt_price} | ADX={adx_val:.0f}"
    )
    return result


# ─── BTST Exit Logic ──────────────────────────────────────────────────────────

async def should_exit_btst(trade: Dict, current_ltp: float) -> Optional[str]:
    """
    Check if BTST position should be exited.
    Called in position monitor loop.
    Returns exit reason string or None.
    """
    entry_price = trade["entry_price"]
    sl_price    = trade["sl_price"]
    target      = trade["target_price"]
    gap_tgt_pct = settings.BTST_GAP_PROFIT_EXIT_PCT / 100

    # Primary: time-based exit window (09:20–09:25)
    if is_btst_exit_window():
        return "BTST_TIME_EXIT"

    # Gap profit exit
    if current_ltp >= entry_price * (1 + gap_tgt_pct):
        return f"BTST_GAP_PROFIT({gap_tgt_pct*100:.0f}%)"

    # SL hit
    if current_ltp <= sl_price:
        return "BTST_SL_HIT"

    # Target hit
    if current_ltp >= target:
        return "BTST_TARGET_HIT"

    return None
