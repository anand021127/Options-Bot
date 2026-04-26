"""
Signal Engine — v3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
New in v3 over v2:
  - Market intelligence gates (events, global sentiment, no-trade day)
  - Strategy classification at signal time
  - Adaptive score weights (strategy performance-driven)
  - Strategy enable/disable (auto from performance data)
  - Global sentiment alignment bonus/penalty
  - Cleaner blocked_by reporting
"""

import asyncio
from datetime import datetime, time as dtime
from typing import Dict, Optional, Tuple
from loguru import logger
from zoneinfo import ZoneInfo

from strategy.indicators import (
    compute_all_indicators, adx, market_structure, market_regime,
    detect_breakout, detect_confirmed_breakout, detect_retest,
    detect_pullback_entry, vwap_bounce, volume_confirmation,
    is_fake_spike, is_persistent_fake_spike, is_low_volume_period, get_sr_levels,
    iv_rank_proxy, atr_sl_target, select_strike_type, volume_trend,
)
# ── Data layer: Upstox real-time only — no yfinance fallback ──────────────────
from data.upstox_market import (
    fetch_ohlcv,
    get_live_price  as fetch_live_price,   # real-time from WS/REST (Upstox only)
    get_atm_option,                         # real-time option LTP from Upstox only
    is_market_open,
)
from intelligence.market_intel import (
    is_high_impact_event_today, is_no_trade_day,
    get_global_sentiment, is_trading_day,
)
from intelligence.strategy_intel import (
    get_strategy_weights, is_strategy_enabled, classify_trade_strategy,
    StrategyType,
)
from config import settings

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_MIN_SCORE = 5


# ─── Helper: robust bool parsing ─────────────────────────────────────────────

def _parse_bool(val, default=True) -> bool:
    """Parse config booleans — handles 'true', 'True', True, '1', etc."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return default


# ─── Time filter ─────────────────────────────────────────────────────────────

def _is_valid_trading_time() -> Tuple[bool, str]:
    now          = datetime.now(IST).time()
    open_filter  = dtime(9, 30)
    close_filter = dtime(15, 0)
    lunch_start  = dtime(13, 0)
    lunch_end    = dtime(14, 0)

    if now < open_filter:
        return False, f"Opening filter (wait till 09:30)"
    if now >= close_filter:
        return False, "Close filter active (no new trades after 15:00)"
    if lunch_start <= now < lunch_end:
        return True, "LUNCH_CAUTION"
    return True, "OK"


# ─── 15min bias ──────────────────────────────────────────────────────────────

async def _get_15min_bias(symbol: str) -> str:
    df15 = await fetch_ohlcv(symbol, period="5d", interval="15m")
    if df15 is None or len(df15) < 20:
        return "NEUTRAL"
    df15   = compute_all_indicators(df15)
    latest = df15.iloc[-1]
    close  = float(latest["close"])
    ema20  = float(latest["ema20"])
    ema50  = float(latest["ema50"])
    struct = market_structure(df15)
    if close > ema20 > ema50 and struct == "BULLISH":
        return "BULL"
    elif close < ema20 < ema50 and struct == "BEARISH":
        return "BEAR"
    return "NEUTRAL"


# ─── Main signal generator ────────────────────────────────────────────────────

async def generate_signal(
    symbol:    str  = "NIFTY",
    min_score: int  = DEFAULT_MIN_SCORE,
    filters:   Dict = None,
) -> Dict:
    if filters is None:
        filters = {}

    use_adx   = _parse_bool(filters.get("use_adx_filter",    True))
    use_iv    = _parse_bool(filters.get("use_iv_filter",      True))
    use_time  = _parse_bool(filters.get("use_time_filter",    True))
    use_mtf   = _parse_bool(filters.get("use_mtf",            True))
    use_vol   = _parse_bool(filters.get("use_volume_filter",  True))
    use_spike = _parse_bool(filters.get("use_spike_filter",   True))

    result = {
        "signal_type":    "NO_TRADE",
        "score":          0,
        "max_score":      16,
        "reasons":        [],
        "blocked_by":     None,
        "gate_log":       [],   # transparent gate-by-gate audit
        "option":         None,
        "sl_pct":         0.0,
        "target_pct":     0.0,
        "sl_price":       0.0,
        "target_price":   0.0,
        "partial_target": 0.0,
        "price_data":     None,
        "indicators":     {},
        "strategy_type":  StrategyType.UNKNOWN,
        "filters_used":   filters,
        "timestamp":      datetime.now().isoformat(),
    }

    # ── GATE 0: Market must be open (weekend + holiday + hours) ────────────────
    trading_day, td_reason = await is_trading_day()
    if not trading_day:
        result["reasons"].append(f"🚫 {td_reason} — market closed")
        result["blocked_by"] = "MARKET_CLOSED"
        result["gate_log"].append(f"GATE0_MARKET: ❌ {td_reason}")
        return result
    if not is_market_open():
        result["reasons"].append("🚫 Outside market hours (09:15–15:30)")
        result["blocked_by"] = "MARKET_CLOSED"
        result["gate_log"].append("GATE0_MARKET: ❌ Outside trading hours")
        return result
    result["gate_log"].append("GATE0_MARKET: ✅ market open")

    # ── GATE 1: High-impact events ────────────────────────────────────────────
    if is_high_impact_event_today():
        result["reasons"].append("🚫 High-impact event today — trading suspended")
        result["blocked_by"] = "EVENT_CALENDAR"
        result["gate_log"].append("GATE1_EVENT: ❌ BLOCKED")
        return result
    result["gate_log"].append("GATE1_EVENT: ✅ clear")

    # ── GATE 2: Time filter ───────────────────────────────────────────────────
    if use_time:
        time_ok, time_msg = _is_valid_trading_time()
        if not time_ok:
            result["reasons"].append(f"⏰ {time_msg}")
            result["blocked_by"] = "TIME_FILTER"
            result["gate_log"].append(f"GATE2_TIME: ❌ {time_msg}")
            return result
        result["gate_log"].append(f"GATE2_TIME: ✅ {time_msg}")
    else:
        result["gate_log"].append("GATE2_TIME: ⏭ skipped")

    # ── GATE 3: No-trade day detection ────────────────────────────────────────
    if settings.NO_TRADE_DAY_AUTO:
        is_dead, dead_reason = await is_no_trade_day(symbol)
        if is_dead:
            result["reasons"].append(f"😴 {dead_reason}")
            result["blocked_by"] = "NO_TRADE_DAY"
            result["gate_log"].append(f"GATE3_DEAD_DAY: ❌ {dead_reason}")
            return result
        result["gate_log"].append("GATE3_DEAD_DAY: ✅ market alive")
    else:
        result["gate_log"].append("GATE3_DEAD_DAY: ⏭ disabled")

    # ── GATE 4: Price data ────────────────────────────────────────────────────
    price_data = await fetch_live_price(symbol)
    if not price_data:
        result["reasons"].append("Price data unavailable")
        result["blocked_by"] = "NO_DATA"
        result["gate_log"].append("GATE4_PRICE: ❌ no price")
        return result
    result["price_data"] = price_data
    result["gate_log"].append(f"GATE4_PRICE: ✅ ₹{price_data.get('price', 0):.0f}")

    # ── GATE 5: OHLCV data (relaxed: 20 candles = ~100 min of data) ───────────
    df5 = await fetch_ohlcv(symbol, period="5d", interval="5m")
    if df5 is None or len(df5) < 20:
        result["reasons"].append(f"Insufficient OHLCV data ({len(df5) if df5 is not None else 0} bars, need 20)")
        result["blocked_by"] = "NO_DATA"
        result["gate_log"].append(f"GATE5_OHLCV: ❌ {len(df5) if df5 is not None else 0} bars")
        return result
    result["gate_log"].append(f"GATE5_OHLCV: ✅ {len(df5)} bars")

    df5    = compute_all_indicators(df5)
    latest = df5.iloc[-1]

    # ── GATE 6: Candle quality ────────────────────────────────────────────────
    if use_spike and is_persistent_fake_spike(df5):
        result["reasons"].append("🚫 Persistent fake spikes — 2/3 candles wick-dominated")
        result["blocked_by"] = "FAKE_SPIKE"
        result["gate_log"].append("GATE6_SPIKE: ❌ persistent fake spike (2/3 candles)")
        return result
    if use_spike and is_fake_spike(df5):
        result["gate_log"].append("GATE6_SPIKE: ⚠️ single wick candle — allowed (warning only)")
    else:
        result["gate_log"].append("GATE6_SPIKE: ✅")

    # ── GATE 7: Low volume (advisory — don't hard-block, just note) ──────────
    low_vol = False
    if use_vol and is_low_volume_period(df5):
        low_vol = True
        result["gate_log"].append("GATE7_VOLUME: ⚠️ low volume — score penalty applied")
    else:
        result["gate_log"].append("GATE7_VOLUME: ✅")

    # ── Build indicators ──────────────────────────────────────────────────────
    df_adx   = adx(df5.tail(60))
    adx_val  = float(df_adx["adx"].iloc[-1]) if not df_adx["adx"].isna().iloc[-1] else 15.0
    plus_di  = float(df_adx["plus_di"].iloc[-1])
    minus_di = float(df_adx["minus_di"].iloc[-1])
    regime   = market_regime(df5)
    struct5  = market_structure(df5)
    iv_data  = iv_rank_proxy(df5)
    close    = float(latest["close"])
    ema9     = float(latest["ema9"])
    ema20    = float(latest["ema20"])
    ema50    = float(latest["ema50"])
    vwap_val = float(latest["vwap"])
    rsi_val  = float(latest["rsi"])
    atr_val  = float(latest["atr"])
    sr       = get_sr_levels(df5)
    bo_conf  = detect_confirmed_breakout(df5)
    pullback = detect_pullback_entry(df5)
    bounce   = vwap_bounce(df5)
    retest   = detect_retest(df5)
    vol_ok   = volume_confirmation(df5)

    result["indicators"] = {
        "close": round(close,2), "ema9": round(ema9,2),
        "ema20": round(ema20,2), "ema50": round(ema50,2),
        "vwap": round(vwap_val,2), "rsi": round(rsi_val,1),
        "atr": round(atr_val,2), "adx": round(adx_val,1),
        "plus_di": round(plus_di,1), "minus_di": round(minus_di,1),
        "structure": struct5, "regime": regime,
        "conf_breakout": bo_conf, "pullback": pullback,
        "vwap_bounce": bounce, "retest": retest,
        "sr": sr, "vol_ok": vol_ok, "vol_trend": volume_trend(df5),
        "iv_rank": iv_data, "fake_spike": is_fake_spike(df5),
    }

    # ── GATE 8: Regime filter (relaxed — only block ADX<15 SIDEWAYS) ──────────
    if use_adx:
        if regime == "SIDEWAYS":
            result["reasons"].append(f"🚫 SIDEWAYS market (ADX={adx_val:.0f}<15) — genuinely choppy")
            result["blocked_by"] = "SIDEWAYS_MARKET"
            result["gate_log"].append(f"GATE8_REGIME: ❌ SIDEWAYS ADX={adx_val:.0f}")
            return result
        if regime == "VOLATILE":
            result["reasons"].append(f"⚡ VOLATILE (ATR>2.5%) — avoid buying options")
            result["blocked_by"] = "VOLATILE_MARKET"
            result["gate_log"].append(f"GATE8_REGIME: ❌ VOLATILE")
            return result
        result["gate_log"].append(f"GATE8_REGIME: ✅ {regime} ADX={adx_val:.0f}")
    else:
        result["gate_log"].append("GATE8_REGIME: ⏭ skipped")

    # ── GATE 9: IV filter (only block EXTREME_IV — HIGH_IV just gets penalty) ─
    if use_iv and iv_data["regime"] == "EXTREME_IV":
        result["reasons"].append(f"🚫 EXTREME IV Rank {iv_data['iv_rank']} — premium crushing")
        result["blocked_by"] = "EXTREME_IV"
        result["gate_log"].append(f"GATE9_IV: ❌ EXTREME IVR={iv_data['iv_rank']}")
        return result
    result["gate_log"].append(f"GATE9_IV: ✅ {iv_data['regime']} IVR={iv_data['iv_rank']}")

    # ── Load strategy weights ─────────────────────────────────────────────────
    weights = await get_strategy_weights()

    # ── Global sentiment (bonus/penalty) ─────────────────────────────────────
    sentiment = {"signal": "NEUTRAL", "change_pct": 0}
    if settings.GLOBAL_SENTIMENT_ENABLED:
        try:
            sentiment = await get_global_sentiment()
        except Exception:
            pass

    # ── MTF bias ─────────────────────────────────────────────────────────────
    mtf_bias = "NEUTRAL"
    if use_mtf:
        mtf_bias = await _get_15min_bias(symbol)

    # ─────────────────────────────────────────────────────────────────────────
    # ADAPTIVE SCORING (max ~16 pts)
    # ─────────────────────────────────────────────────────────────────────────
    bull_score, bear_score = 0, 0
    r_bull, r_bear         = [], []

    # 1. Structure (2 pts)
    if struct5 == "BULLISH":
        bull_score += 2; r_bull.append("✅ Structure BULLISH (HH+HL)")
    elif struct5 == "BEARISH":
        bear_score += 2; r_bear.append("✅ Structure BEARISH (LH+LL)")
    else:
        r_bull.append("⚠️ Structure SIDEWAYS")

    # 2. EMA stack (2 pts — with partial credit for EMA9 alignment)
    if close > ema20 > ema50:
        bull_score += 2; r_bull.append(f"✅ Price>EMA20>EMA50 (full bull stack)")
    elif close < ema20 < ema50:
        bear_score += 2; r_bear.append(f"✅ Price<EMA20<EMA50 (full bear stack)")
    elif close > ema9 > ema20:
        bull_score += 1; r_bull.append("⚡ EMA9>EMA20 partial bull")
    elif close < ema9 < ema20:
        bear_score += 1; r_bear.append("⚡ EMA9<EMA20 partial bear")

    # 2b. EMA9 immediate trend (1 pt extra)
    if close > ema9:
        bull_score += 1; r_bull.append("✅ Price > EMA9 (immediate uptrend)")
    elif close < ema9:
        bear_score += 1; r_bear.append("✅ Price < EMA9 (immediate downtrend)")

    # 3. VWAP (1 pt)
    if close > vwap_val:
        bull_score += 1; r_bull.append(f"✅ Above VWAP {vwap_val:.0f}")
    else:
        bear_score += 1; r_bear.append(f"✅ Below VWAP {vwap_val:.0f}")

    # 4. ADX direction (1 pt — also give 1pt for WEAK_TREND with DI alignment)
    if adx_val >= 20:
        if plus_di > minus_di:
            bull_score += 1; r_bull.append(f"✅ ADX={adx_val:.0f} +DI>{minus_di:.0f}")
        else:
            bear_score += 1; r_bear.append(f"✅ ADX={adx_val:.0f} -DI>{plus_di:.0f}")

    # 5. Entry patterns — ADAPTIVE WEIGHT (2 pts base)
    bo_w   = weights.get(StrategyType.BREAKOUT, 1.0)
    vwap_w = weights.get(StrategyType.VWAP,     1.0)
    pb_w   = weights.get(StrategyType.PULLBACK,  1.0)
    rt_w   = weights.get(StrategyType.RETEST,    1.0)

    detected_strategy = StrategyType.UNKNOWN

    if bo_conf == "CONFIRMED_BREAKOUT_UP" and bo_w > 0:
        pts = max(1, round(2 * bo_w))
        bull_score += pts; r_bull.append(f"🚀 Confirmed breakout UP (w={bo_w:.1f})")
        detected_strategy = StrategyType.BREAKOUT
    elif bo_conf == "CONFIRMED_BREAKOUT_DOWN" and bo_w > 0:
        pts = max(1, round(2 * bo_w))
        bear_score += pts; r_bear.append(f"🚀 Confirmed breakdown (w={bo_w:.1f})")
        detected_strategy = StrategyType.BREAKOUT
    elif bounce == "BOUNCE_BULL" and vwap_w > 0:
        pts = max(1, round(2 * vwap_w))
        bull_score += pts; r_bull.append(f"🔥 VWAP bounce BULL (w={vwap_w:.1f})")
        detected_strategy = StrategyType.VWAP
    elif bounce == "BOUNCE_BEAR" and vwap_w > 0:
        pts = max(1, round(2 * vwap_w))
        bear_score += pts; r_bear.append(f"🔥 VWAP rejection BEAR (w={vwap_w:.1f})")
        detected_strategy = StrategyType.VWAP
    elif pullback == "PULLBACK_BULL" and pb_w > 0:
        pts = max(1, round(2 * pb_w))
        bull_score += pts; r_bull.append(f"📉→📈 EMA20 pullback BULL (w={pb_w:.1f})")
        detected_strategy = StrategyType.PULLBACK
    elif pullback == "PULLBACK_BEAR" and pb_w > 0:
        pts = max(1, round(2 * pb_w))
        bear_score += pts; r_bear.append(f"📈→📉 EMA20 pullback BEAR (w={pb_w:.1f})")
        detected_strategy = StrategyType.PULLBACK

    if retest == "RETEST_SUPPORT" and rt_w > 0:
        bull_score += round(rt_w); r_bull.append(f"✅ Retest support (w={rt_w:.1f})")
        if detected_strategy == StrategyType.UNKNOWN:
            detected_strategy = StrategyType.RETEST
    elif retest == "RETEST_RESISTANCE" and rt_w > 0:
        bear_score += round(rt_w); r_bear.append(f"✅ Retest resistance (w={rt_w:.1f})")
        if detected_strategy == StrategyType.UNKNOWN:
            detected_strategy = StrategyType.RETEST

    # 6. MTF (1 pt)
    if mtf_bias == "BULL":
        bull_score += 1; r_bull.append("✅ 15min BULLISH aligned")
    elif mtf_bias == "BEAR":
        bear_score += 1; r_bear.append("✅ 15min BEARISH aligned")
    else:
        r_bull.append("⚠️ 15min NEUTRAL — no MTF")

    # 7. Volume (1 pt — with low-vol penalty instead of hard block)
    if low_vol:
        bull_score -= 1; bear_score -= 1
        r_bull.append("⚠️ Low volume period — reduced conviction")
        r_bear.append("⚠️ Low volume period — reduced conviction")
    elif vol_ok:
        bull_score += 1; bear_score += 1
        r_bull.append("✅ Volume above average")
        r_bear.append("✅ Volume above average")

    # 8. RSI (penalty)
    if rsi_val > 75:
        bull_score -= 2; r_bull.append(f"🚫 RSI {rsi_val:.0f} overbought")
    elif rsi_val < 25:
        bear_score -= 2; r_bear.append(f"🚫 RSI {rsi_val:.0f} oversold")

    # 9. IV bonus (1 pt for LOW, penalty for HIGH)
    if iv_data["regime"] == "LOW_IV":
        bull_score += 1; bear_score += 1
        r_bull.append(f"✅ Low IV (IVR={iv_data['iv_rank']}) — cheap premium")
        r_bear.append(f"✅ Low IV — cheap premium")
    elif iv_data["regime"] == "HIGH_IV":
        bull_score -= 1; bear_score -= 1
        r_bull.append(f"⚠️ High IV (IVR={iv_data['iv_rank']}) — expensive premium")
        r_bear.append(f"⚠️ High IV — expensive premium")

    # 10. Global sentiment (1 pt bonus/penalty)
    s_signal = sentiment.get("signal", "NEUTRAL")
    if s_signal == "RISK_ON":
        bull_score += 1; r_bull.append(f"✅ Global RISK-ON (S&P {sentiment.get('change_pct',0):+.1f}%)")
    elif s_signal == "RISK_OFF":
        bull_score -= 1; bear_score += 1
        r_bull.append(f"⚠️ Global RISK-OFF — caution for longs")
        r_bear.append(f"✅ Global RISK-OFF — favours shorts")

    # 11. Lunch penalty
    _, time_msg = _is_valid_trading_time()
    if time_msg == "LUNCH_CAUTION":
        bull_score -= 1; bear_score -= 1
        r_bull.append("⚠️ Lunch hour — reduced conviction")

    logger.info(
        f"[{symbol}] BULL={bull_score} BEAR={bear_score} | "
        f"ADX={adx_val:.0f} Regime={regime} IVR={iv_data['iv_rank']} "
        f"MTF={mtf_bias} Strategy={detected_strategy}"
    )

    # ── Direction decision ────────────────────────────────────────────────────
    direction = None
    if bull_score >= min_score and bull_score > bear_score:
        direction = "CE"; result["score"] = bull_score; result["reasons"] = r_bull
    elif bear_score >= min_score and bear_score > bull_score:
        direction = "PE"; result["score"] = bear_score; result["reasons"] = r_bear
    else:
        result["score"]   = max(bull_score, bear_score)
        result["reasons"] = (r_bull if bull_score >= bear_score else r_bear)
        result["reasons"].append(f"Score {result['score']}/{min_score} required — no trade")
        return result

    # ── Option selection ──────────────────────────────────────────────────────
    strike_type = select_strike_type(iv_data["iv_rank"], regime)
    option = await get_atm_option(symbol, direction)
    if not option or option.get("ltp", 0) <= 0:
        result["reasons"].append("Option LTP unavailable")
        result["blocked_by"] = "NO_OPTION_DATA"
        return result

    ltp = option["ltp"]
    sl_price, tgt_price, sl_pct, tgt_pct = atr_sl_target(df5, ltp, atr_mult=1.5, rr=2.0)
    partial_target = round(ltp * (1 + sl_pct / 100), 2)

    result.update({
        "signal_type":    f"BUY_{direction}",
        "option":         option,
        "strike_type":    strike_type,
        "sl_pct":         sl_pct,
        "target_pct":     tgt_pct,
        "sl_price":       sl_price,
        "target_price":   tgt_price,
        "partial_target": partial_target,
        "mtf_bias":       mtf_bias,
        "regime":         regime,
        "iv_regime":      iv_data["regime"],
        "adx":            round(adx_val, 1),
        "strategy_type":  detected_strategy,
        "global_sentiment": sentiment.get("signal"),
        "atr_val":        round(atr_val, 2),
        "spot_price":     round(close, 2),
    })

    logger.info(
        f"✅ SIGNAL: BUY_{direction} | {symbol} {option['strike']} | "
        f"LTP={ltp} | SL={sl_price}(-{sl_pct}%) | T2={tgt_price}(+{tgt_pct}%) "
        f"| Score={result['score']} | Strategy={detected_strategy}"
    )
    return result


def calculate_position_size(capital, risk_pct, option_ltp, sl_pct, lot_size=1):
    """Legacy compat wrapper."""
    from execution.sizing import calculate_adaptive_size
    r = calculate_adaptive_size(
        capital=capital, signal_score=5, option_ltp=option_ltp,
        sl_pct=sl_pct, atr_val=0, spot_price=option_ltp*100,
        consecutive_losses=0, symbol="NIFTY",
    )
    return r["quantity"]


def compute_sl_target(option_ltp, sl_pct, target_pct):
    sl     = round(option_ltp * (1 - sl_pct / 100), 2)
    target = round(option_ltp * (1 + target_pct / 100), 2)
    return sl, target
