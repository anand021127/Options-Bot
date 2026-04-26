"""
Morning Market Intelligence Engine — v1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pre-market bias scoring from 6 independent data sources:

  1. Global sentiment    (reuses market_intel.get_global_sentiment)
  2. Gap / Gift Nifty    (reuses market_intel.analyse_gap)
  3. Option chain PCR    (NEW — from Upstox option chain OI)
  4. India VIX           (NEW — from Upstox index quote)
  5. FII/DII activity    (NEW — from NSE API)
  6. Technical levels    (NEW wrapper — reuses indicators module)

Gate Modes (configurable from dashboard):
  STRICT  — Hard gate: blocks trade if bias = NO_TRADE
  SMART   — Hybrid (DEFAULT): allows high-confidence trades through
  FREE    — Advisory only: logs bias but never blocks

Safety layers:
  - Skip first N minutes after market open
  - Auto-skip on VIX spike
  - Mixed signal detection → reduce confidence

This module is 100% opt-in and plug-and-play.
"""

import asyncio
import time
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from loguru import logger
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# ── Caches ────────────────────────────────────────────────────────────────────
_pcr_cache:       Dict = {}
_vix_cache:       Dict = {}
_fii_dii_cache:   Dict = {}
_tech_cache:      Dict = {}
_bias_cache:      Dict = {}

_CACHE_TTL = 300          # 5 minutes
_VIX_CACHE_TTL = 120      # 2 minutes (more sensitive)
_BIAS_CACHE_TTL = 180     # 3 minutes

# Gate mode constants
MODE_STRICT = "STRICT"    # Hard gate — blocks if NO_TRADE
MODE_SMART  = "SMART"     # Hybrid — allows high-confidence through
MODE_FREE   = "FREE"      # Advisory — never blocks


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. PCR — Put-Call Ratio from Option Chain OI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def compute_pcr(symbol: str = "NIFTY") -> Dict:
    """
    Calculate Put-Call Ratio from Upstox option chain OI data.

    PCR > 1.0  → More PUT writing → Market support → BULLISH signal
    PCR 0.7–1.0 → Neutral
    PCR < 0.7  → More CALL writing → Overhead resistance → BEARISH signal

    Returns: {pcr, total_put_oi, total_call_oi, interpretation, source}
    """
    global _pcr_cache
    cache_key = f"pcr_{symbol}"
    cached = _pcr_cache.get(cache_key, {})
    if cached and (time.time() - cached.get("_ts", 0)) < _CACHE_TTL:
        return cached["data"]

    try:
        from data.upstox_market import get_option_chain
        chain = await get_option_chain(symbol)
        if not chain:
            return _pcr_fallback("Option chain unavailable")

        calls = chain.get("calls", [])
        puts  = chain.get("puts", [])

        if not calls or not puts:
            return _pcr_fallback("Empty option chain")

        total_call_oi = sum(c.get("oi", 0) for c in calls)
        total_put_oi  = sum(p.get("oi", 0) for p in puts)

        if total_call_oi <= 0:
            return _pcr_fallback("Zero CALL OI")

        pcr = round(total_put_oi / total_call_oi, 3)

        # Interpretation
        if pcr > 1.2:
            interpretation = "STRONGLY_BULLISH"
        elif pcr > 1.0:
            interpretation = "BULLISH"
        elif pcr > 0.7:
            interpretation = "NEUTRAL"
        elif pcr > 0.5:
            interpretation = "BEARISH"
        else:
            interpretation = "STRONGLY_BEARISH"

        # Max pain calculation (strike with maximum pain for option writers)
        max_pain = _calculate_max_pain(calls, puts)

        data = {
            "pcr":            pcr,
            "total_put_oi":   total_put_oi,
            "total_call_oi":  total_call_oi,
            "interpretation": interpretation,
            "max_pain":       max_pain,
            "source":         "upstox_chain",
            "timestamp":      datetime.now(IST).isoformat(),
        }
        _pcr_cache[cache_key] = {"data": data, "_ts": time.time()}
        logger.debug(f"PCR {symbol}: {pcr} ({interpretation}) | PUT_OI={total_put_oi} CALL_OI={total_call_oi}")
        return data

    except Exception as e:
        logger.warning(f"PCR compute error: {e}")
        return _pcr_fallback(f"Error: {e}")


def _calculate_max_pain(calls: List[Dict], puts: List[Dict]) -> float:
    """Calculate max pain strike from option chain data."""
    try:
        strikes = set(c["strike"] for c in calls) | set(p["strike"] for p in puts)
        if not strikes:
            return 0.0

        call_oi_map = {c["strike"]: c.get("oi", 0) for c in calls}
        put_oi_map  = {p["strike"]: p.get("oi", 0) for p in puts}

        min_pain   = float("inf")
        pain_strike = 0.0

        for test_strike in strikes:
            call_pain = sum(
                max(0, test_strike - s) * call_oi_map.get(s, 0) for s in strikes
            )
            put_pain = sum(
                max(0, s - test_strike) * put_oi_map.get(s, 0) for s in strikes
            )
            total_pain = call_pain + put_pain
            if total_pain < min_pain:
                min_pain    = total_pain
                pain_strike = test_strike

        return pain_strike
    except Exception:
        return 0.0


def _pcr_fallback(reason: str) -> Dict:
    return {
        "pcr": 0.85, "total_put_oi": 0, "total_call_oi": 0,
        "interpretation": "NEUTRAL", "max_pain": 0,
        "source": f"fallback ({reason})", "timestamp": datetime.now(IST).isoformat(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. India VIX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_india_vix() -> Dict:
    """
    Fetch India VIX (fear index) from Upstox.
    VIX instrument key: NSE_INDEX|India VIX

    VIX interpretation:
      < 13   → Low fear → trending market → BULLISH
      13-18  → Normal → no signal modification
      18-25  → Elevated → caution
      > 25   → High fear → BEARISH / skip trading
      Rising → Fear increasing → BEARISH
      Falling → Fear decreasing → BULLISH

    Returns: {vix, direction, rising, falling, spike, interpretation}
    """
    global _vix_cache
    cached = _vix_cache.get("vix", {})
    if cached and (time.time() - cached.get("_ts", 0)) < _VIX_CACHE_TTL:
        return cached["data"]

    try:
        import httpx
        from api.upstox_auth import get_upstox_token

        token = await get_upstox_token()
        if not token:
            return _vix_fallback("No Upstox token")

        # Fetch VIX LTP
        vix_key = "NSE_INDEX|India VIX"
        async with httpx.AsyncClient(timeout=6) as c:
            resp = await c.get(
                "https://api.upstox.com/v2/market-quote/ltp",
                params={"instrument_key": vix_key},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
            )

        if resp.status_code != 200:
            return _vix_fallback(f"HTTP {resp.status_code}")

        data = resp.json().get("data", {})
        feed = (data.get(vix_key) or
                data.get(vix_key.replace(" ", "%20")) or
                (next(iter(data.values()), None) if data else None))

        if not feed:
            return _vix_fallback("No VIX data in response")

        vix_val = float(feed.get("last_price") or feed.get("ltp") or 0)
        if vix_val <= 0:
            return _vix_fallback("VIX value is zero")

        # Try to get previous VIX for direction
        prev_vix = _vix_cache.get("prev_val", vix_val)
        change   = vix_val - prev_vix
        change_pct = (change / max(prev_vix, 0.01)) * 100

        rising   = change_pct > 3     # VIX up >3% → fear increasing
        falling  = change_pct < -3    # VIX down >3% → fear decreasing
        spike    = vix_val > 25 or change_pct > 10  # Major VIX spike

        from config import settings
        vix_spike_threshold = getattr(settings, 'MORNING_BIAS_VIX_SPIKE', 25.0)

        if vix_val > vix_spike_threshold:
            interpretation = "EXTREME_FEAR"
        elif vix_val > 20:
            interpretation = "HIGH_FEAR"
        elif vix_val > 15:
            interpretation = "ELEVATED"
        elif vix_val > 12:
            interpretation = "NORMAL"
        else:
            interpretation = "LOW_FEAR"

        result = {
            "vix":             round(vix_val, 2),
            "prev_vix":        round(prev_vix, 2),
            "change":          round(change, 2),
            "change_pct":      round(change_pct, 2),
            "rising":          rising,
            "falling":         falling,
            "spike":           spike,
            "interpretation":  interpretation,
            "source":          "upstox",
            "timestamp":       datetime.now(IST).isoformat(),
        }

        _vix_cache["vix"]      = {"data": result, "_ts": time.time()}
        _vix_cache["prev_val"] = vix_val  # save for next comparison
        logger.debug(f"VIX: {vix_val} ({interpretation}) Δ={change_pct:+.1f}%")
        return result

    except Exception as e:
        logger.warning(f"India VIX fetch error: {e}")
        return _vix_fallback(f"Error: {e}")


def _vix_fallback(reason: str) -> Dict:
    return {
        "vix": 15.0, "prev_vix": 15.0, "change": 0, "change_pct": 0,
        "rising": False, "falling": False, "spike": False,
        "interpretation": "NORMAL", "source": f"fallback ({reason})",
        "timestamp": datetime.now(IST).isoformat(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. FII/DII Activity
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_fii_dii() -> Dict:
    """
    Fetch latest FII/DII cash market activity from NSE API.

    FII net buying  → BULLISH
    FII net selling → BEARISH
    DII net buying  → usually counters FII selling (support)

    Returns: {fii_net, dii_net, fii_buying, fii_selling, interpretation}
    """
    global _fii_dii_cache
    cached = _fii_dii_cache.get("data", {})
    if cached and (time.time() - cached.get("_ts", 0)) < _CACHE_TTL:
        return cached["data"]

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(
                "https://www.nseindia.com/api/fiidiiActivity",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.nseindia.com/reports-indices",
                },
            )

        if resp.status_code != 200:
            return _fii_dii_fallback(f"NSE HTTP {resp.status_code}")

        data = resp.json()

        # NSE returns a list of category-wise activity
        # Try multiple response formats
        fii_net = 0.0
        dii_net = 0.0

        if isinstance(data, list):
            for row in data:
                category = str(row.get("category", "")).upper()
                net_val  = float(row.get("netValue", row.get("net", 0)) or 0)
                if "FII" in category or "FPI" in category:
                    fii_net = net_val
                elif "DII" in category:
                    dii_net = net_val
        elif isinstance(data, dict):
            # Alternative format
            fii_data = data.get("fpiData") or data.get("fiiData") or {}
            dii_data = data.get("diiData") or {}
            if isinstance(fii_data, dict):
                fii_net = float(fii_data.get("netValue", fii_data.get("net", 0)) or 0)
            if isinstance(dii_data, dict):
                dii_net = float(dii_data.get("netValue", dii_data.get("net", 0)) or 0)

        fii_buying  = fii_net > 0
        fii_selling = fii_net < 0

        if fii_net > 500:
            interpretation = "STRONG_FII_BUY"
        elif fii_net > 0:
            interpretation = "FII_BUY"
        elif fii_net > -500:
            interpretation = "FII_SELL"
        else:
            interpretation = "STRONG_FII_SELL"

        result = {
            "fii_net":         round(fii_net, 2),
            "dii_net":         round(dii_net, 2),
            "fii_buying":      fii_buying,
            "fii_selling":     fii_selling,
            "dii_buying":      dii_net > 0,
            "interpretation":  interpretation,
            "source":          "nse_api",
            "timestamp":       datetime.now(IST).isoformat(),
        }
        _fii_dii_cache["data"] = {"data": result, "_ts": time.time()}
        logger.debug(f"FII/DII: FII={fii_net:+.0f}Cr DII={dii_net:+.0f}Cr ({interpretation})")
        return result

    except Exception as e:
        logger.warning(f"FII/DII fetch error: {e}")
        return _fii_dii_fallback(f"Error: {e}")


def _fii_dii_fallback(reason: str) -> Dict:
    return {
        "fii_net": 0, "dii_net": 0, "fii_buying": False, "fii_selling": False,
        "dii_buying": False, "interpretation": "NEUTRAL",
        "source": f"fallback ({reason})", "timestamp": datetime.now(IST).isoformat(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. Technical Levels (wrapper around existing indicators)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_technical_levels(symbol: str = "NIFTY") -> Dict:
    """
    Compute VWAP position, pivot levels, and market structure from
    existing indicators module. No new indicator logic — just a wrapper.

    Returns: {above_vwap, below_vwap, structure, regime, close, vwap, pivots}
    """
    global _tech_cache
    cache_key = f"tech_{symbol}"
    cached = _tech_cache.get(cache_key, {})
    if cached and (time.time() - cached.get("_ts", 0)) < _CACHE_TTL:
        return cached["data"]

    try:
        from data.upstox_market import fetch_ohlcv
        from strategy.indicators import (
            compute_all_indicators, get_sr_levels, market_structure,
            market_regime,
        )

        df = await fetch_ohlcv(symbol, period="5d", interval="5m")
        if df is None or len(df) < 30:
            return _tech_fallback("Insufficient OHLCV data")

        df      = compute_all_indicators(df)
        latest  = df.iloc[-1]
        close   = float(latest["close"])
        vwap_v  = float(latest["vwap"])
        ema9    = float(latest["ema9"])
        ema20   = float(latest["ema20"])
        ema50   = float(latest["ema50"])
        sr      = get_sr_levels(df)
        struct  = market_structure(df)
        regime  = market_regime(df)

        above_vwap = close > vwap_v
        below_vwap = close < vwap_v

        # EMA alignment scoring
        ema_bullish = close > ema9 > ema20 > ema50
        ema_bearish = close < ema9 < ema20 < ema50

        result = {
            "close":       round(close, 2),
            "vwap":        round(vwap_v, 2),
            "above_vwap":  above_vwap,
            "below_vwap":  below_vwap,
            "ema9":        round(ema9, 2),
            "ema20":       round(ema20, 2),
            "ema50":       round(ema50, 2),
            "ema_bullish": ema_bullish,
            "ema_bearish": ema_bearish,
            "structure":   struct,
            "regime":      regime,
            "support":     sr.get("support", []),
            "resistance":  sr.get("resistance", []),
            "source":      "indicators",
            "timestamp":   datetime.now(IST).isoformat(),
        }
        _tech_cache[cache_key] = {"data": result, "_ts": time.time()}
        logger.debug(
            f"Tech {symbol}: {close:.0f} vs VWAP={vwap_v:.0f} | "
            f"{struct} | {regime} | EMA_bull={ema_bullish}"
        )
        return result

    except Exception as e:
        logger.warning(f"Technical levels error: {e}")
        return _tech_fallback(f"Error: {e}")


def _tech_fallback(reason: str) -> Dict:
    return {
        "close": 0, "vwap": 0, "above_vwap": False, "below_vwap": False,
        "ema9": 0, "ema20": 0, "ema50": 0,
        "ema_bullish": False, "ema_bearish": False,
        "structure": "UNKNOWN", "regime": "UNKNOWN",
        "support": [], "resistance": [],
        "source": f"fallback ({reason})", "timestamp": datetime.now(IST).isoformat(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. MASTER FUNCTION — Morning Bias Scoring
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_morning_bias(symbol: str = "NIFTY") -> Dict:
    """
    Master function: computes morning market bias from 6 data sources.

    Scoring:
      Each factor contributes ±1 to the score.
      Max possible: +6 (all bullish) / -6 (all bearish)

      score >= 4  → BULLISH → suggest CALL
      score <= -4 → BEARISH → suggest PUT
      else        → SIDEWAYS → NO_TRADE

    Returns structured JSON:
      {
        bias, score, max_score, trade, signals, details,
        safety, gate_mode, override_allowed, timestamp
      }
    """
    global _bias_cache
    cache_key = f"bias_{symbol}"
    cached = _bias_cache.get(cache_key, {})
    if cached and (time.time() - cached.get("_ts", 0)) < _BIAS_CACHE_TTL:
        return cached["data"]

    score   = 0
    signals = []
    details = {}

    # ── 1. Global Sentiment (reuse existing) ──────────────────────────────────
    try:
        from intelligence.market_intel import get_global_sentiment
        global_data = await get_global_sentiment()
        details["global_sentiment"] = global_data

        direction = global_data.get("direction", "NEUTRAL")
        if direction == "BULLISH":
            score += 1
            signals.append("🌍 Global BULLISH (S&P risk-on)")
        elif direction == "BEARISH":
            score -= 1
            signals.append("🌍 Global BEARISH (S&P risk-off)")
        else:
            signals.append("🌍 Global NEUTRAL")
    except Exception as e:
        logger.debug(f"Global sentiment skipped: {e}")
        details["global_sentiment"] = {"error": str(e)}

    # ── 2. Gap / Gift Nifty Proxy (reuse existing) ────────────────────────────
    try:
        from intelligence.market_intel import analyse_gap
        gap_data = await analyse_gap(symbol)
        details["gap_analysis"] = gap_data

        gap_dir = gap_data.get("direction", "FLAT")
        gap_pct = abs(gap_data.get("gap_pct", 0))
        if gap_dir == "GAP_UP" and gap_pct > 0.3:
            score += 1
            signals.append(f"📈 Gap UP +{gap_data['gap_pct']:.1f}%")
        elif gap_dir == "GAP_DOWN" and gap_pct > 0.3:
            score -= 1
            signals.append(f"📉 Gap DOWN {gap_data['gap_pct']:.1f}%")
        else:
            signals.append(f"➡️ Flat open ({gap_data.get('gap_pct', 0):.1f}%)")
    except Exception as e:
        logger.debug(f"Gap analysis skipped: {e}")
        details["gap_analysis"] = {"error": str(e)}

    # ── 3. Option Chain PCR (new) ─────────────────────────────────────────────
    try:
        pcr_data = await compute_pcr(symbol)
        details["pcr"] = pcr_data

        pcr_val = pcr_data.get("pcr", 0.85)
        if pcr_val > 1.0:
            score += 1
            signals.append(f"📊 PCR {pcr_val:.2f} (PUT support → Bullish)")
        elif pcr_val < 0.7:
            score -= 1
            signals.append(f"📊 PCR {pcr_val:.2f} (CALL pressure → Bearish)")
        else:
            signals.append(f"📊 PCR {pcr_val:.2f} (Neutral)")
    except Exception as e:
        logger.debug(f"PCR skipped: {e}")
        details["pcr"] = {"error": str(e)}

    # ── 4. India VIX (new) ────────────────────────────────────────────────────
    try:
        vix_data = await get_india_vix()
        details["vix"] = vix_data

        if vix_data.get("falling"):
            score += 1
            signals.append(f"😌 VIX falling {vix_data['vix']:.1f} (fear ↓)")
        elif vix_data.get("rising"):
            score -= 1
            signals.append(f"😰 VIX rising {vix_data['vix']:.1f} (fear ↑)")
        else:
            signals.append(f"📏 VIX stable {vix_data.get('vix', 0):.1f}")
    except Exception as e:
        logger.debug(f"VIX skipped: {e}")
        details["vix"] = {"error": str(e)}

    # ── 5. FII/DII (new) ─────────────────────────────────────────────────────
    try:
        fii_data = await get_fii_dii()
        details["fii_dii"] = fii_data

        if fii_data.get("fii_buying"):
            score += 1
            signals.append(f"🏦 FII buying +₹{fii_data['fii_net']:.0f}Cr")
        elif fii_data.get("fii_selling"):
            score -= 1
            signals.append(f"🏦 FII selling ₹{fii_data['fii_net']:.0f}Cr")
        else:
            signals.append("🏦 FII/DII neutral")
    except Exception as e:
        logger.debug(f"FII/DII skipped: {e}")
        details["fii_dii"] = {"error": str(e)}

    # ── 6. Technical Levels (new wrapper) ─────────────────────────────────────
    try:
        tech_data = await get_technical_levels(symbol)
        details["technical"] = tech_data

        if tech_data.get("above_vwap") and tech_data.get("ema_bullish"):
            score += 1
            signals.append(f"📐 Above VWAP + EMA bullish stack")
        elif tech_data.get("below_vwap") and tech_data.get("ema_bearish"):
            score -= 1
            signals.append(f"📐 Below VWAP + EMA bearish stack")
        elif tech_data.get("above_vwap"):
            signals.append(f"📐 Above VWAP (partial bullish)")
        elif tech_data.get("below_vwap"):
            signals.append(f"📐 Below VWAP (partial bearish)")
        else:
            signals.append("📐 Technical neutral")
    except Exception as e:
        logger.debug(f"Technical levels skipped: {e}")
        details["technical"] = {"error": str(e)}

    # ── Safety Checks ─────────────────────────────────────────────────────────
    safety = _compute_safety(details)

    # ── Final Decision ────────────────────────────────────────────────────────
    from config import settings
    min_bias_score = getattr(settings, 'MORNING_BIAS_MIN_SCORE', 4)
    gate_mode      = getattr(settings, 'MORNING_BIAS_MODE', MODE_SMART)

    if score >= min_bias_score:
        bias  = "BULLISH"
        trade = "CALL"
    elif score <= -min_bias_score:
        bias  = "BEARISH"
        trade = "PUT"
    else:
        bias  = "SIDEWAYS"
        trade = "NO_TRADE"

    # Safety overrides
    if safety.get("vix_spike"):
        bias  = "SIDEWAYS"
        trade = "NO_TRADE"
        signals.append("🚨 VIX SPIKE — auto-skip")

    if safety.get("skip_opening"):
        trade = "NO_TRADE"
        signals.append(f"⏳ Opening buffer active ({safety.get('skip_minutes', 0)}min)")

    # Whether signal engine can override bias (for SMART mode)
    mixed_signals = abs(score) <= 1 and len(signals) >= 4
    override_allowed = _compute_override_allowed(gate_mode, score, mixed_signals)

    result = {
        "bias":              bias,
        "score":             score,
        "max_score":         6,
        "trade":             trade,
        "signals":           signals,
        "details":           details,
        "safety":            safety,
        "gate_mode":         gate_mode,
        "override_allowed":  override_allowed,
        "mixed_signals":     mixed_signals,
        "timestamp":         datetime.now(IST).isoformat(),
    }

    _bias_cache[cache_key] = {"data": result, "_ts": time.time()}

    logger.info(
        f"🌅 MORNING BIAS [{symbol}] | Bias={bias} | Score={score}/±6 | "
        f"Trade={trade} | Mode={gate_mode} | "
        f"Override={'yes' if override_allowed else 'no'} | "
        f"Signals: {', '.join(s.split(' ', 1)[-1] for s in signals[:4])}"
    )
    return result


def _compute_safety(details: Dict) -> Dict:
    """Compute safety flags from collected data."""
    from config import settings

    now          = datetime.now(IST)
    market_open  = now.replace(hour=9, minute=15, second=0, microsecond=0)
    skip_minutes = getattr(settings, 'MORNING_BIAS_SKIP_MINUTES', 10)
    skip_until   = market_open.replace(minute=market_open.minute + skip_minutes)

    skip_opening = now < skip_until

    # VIX spike
    vix_data = details.get("vix", {})
    vix_spike = vix_data.get("spike", False)

    # Mixed signals — if both bullish and bearish signals are present
    # (handled at caller level using abs(score))

    vix_threshold = getattr(settings, 'MORNING_BIAS_VIX_SPIKE', 25.0)

    return {
        "skip_opening":    skip_opening,
        "skip_minutes":    skip_minutes,
        "vix_spike":       vix_spike,
        "vix_threshold":   vix_threshold,
        "market_time":     now.strftime("%H:%M:%S"),
    }


def _compute_override_allowed(gate_mode: str, score: int, mixed: bool) -> bool:
    """
    Determine if the signal engine can override morning bias.

    STRICT: never override — if bias says NO_TRADE, skip
    SMART:  override allowed if signal is high confidence
    FREE:   always override — bias is advisory only
    """
    if gate_mode == MODE_FREE:
        return True
    if gate_mode == MODE_STRICT:
        return False
    # SMART (default) — override if score isn't too negative and not mixed
    return not mixed


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. GATE CHECK — Called by bot_engine before signal generation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def check_morning_bias_gate(
    symbol: str,
    signal_score: int = 0,
) -> Tuple[bool, str, Dict]:
    """
    Gate function called by bot_engine before signal generation.

    Returns:
      (allow_trade, reason, bias_data)

    Behaviour by mode:
      STRICT: blocks if bias = NO_TRADE
      SMART:  allows if signal_score >= 8 even when bias = NO_TRADE
      FREE:   always allows
    """
    from config import settings

    enabled = getattr(settings, 'MORNING_BIAS_ENABLED', False)
    if not enabled:
        return True, "Morning bias disabled", {}

    bias_data = await get_morning_bias(symbol)
    trade     = bias_data.get("trade", "NO_TRADE")
    gate_mode = bias_data.get("gate_mode", MODE_SMART)
    override  = bias_data.get("override_allowed", True)
    score     = bias_data.get("score", 0)

    # If bias has a direction → allow
    if trade in ("CALL", "PUT"):
        return True, f"Morning bias: {bias_data['bias']} ({trade})", bias_data

    # trade == "NO_TRADE" — behaviour depends on mode
    if gate_mode == MODE_FREE:
        return True, f"Morning bias: NO_TRADE (FREE mode — advisory only)", bias_data

    if gate_mode == MODE_STRICT:
        return False, (
            f"Morning bias: NO_TRADE (STRICT mode — score={score}) | "
            f"Signals: {', '.join(bias_data.get('signals', [])[:3])}"
        ), bias_data

    # SMART (default) — allow high-confidence trades through
    smart_override_score = getattr(settings, 'MORNING_BIAS_SMART_OVERRIDE_SCORE', 8)
    if signal_score >= smart_override_score:
        return True, (
            f"Morning bias: NO_TRADE but signal score={signal_score} >= {smart_override_score} — "
            f"OVERRIDE allowed (SMART mode)"
        ), bias_data

    # SMART mode: check if specific strong patterns exist
    # (this will be called again after signal is generated — see bot_engine)
    # For the pre-check, we allow through and let post-check decide
    return True, (
        f"Morning bias: NO_TRADE (SMART mode — pending signal confirmation)"
    ), bias_data


async def post_signal_bias_check(
    symbol: str,
    signal: Dict,
    bias_data: Dict = None,
) -> Tuple[bool, str]:
    """
    Post-signal check for SMART mode.
    Called AFTER generate_signal() returns a trade signal.

    In SMART mode, if morning bias is NO_TRADE, only allow trade if:
      - Signal score >= smart_override_score (e.g., 8)
      - OR confirmed breakout exists
      - OR strong volume confirmation

    Returns: (allow, reason)
    """
    from config import settings

    enabled = getattr(settings, 'MORNING_BIAS_ENABLED', False)
    if not enabled:
        return True, "Morning bias disabled"

    if not bias_data:
        bias_data = await get_morning_bias(symbol)

    trade     = bias_data.get("trade", "NO_TRADE")
    gate_mode = bias_data.get("gate_mode", MODE_SMART)

    # If bias has direction or mode is FREE, allow
    if trade in ("CALL", "PUT") or gate_mode == MODE_FREE:
        return True, "Bias allows trade"

    if gate_mode == MODE_STRICT:
        return False, f"STRICT mode — morning bias NO_TRADE (score={bias_data.get('score', 0)})"

    # SMART mode — check signal quality
    sig_score  = signal.get("score", 0)
    indicators = signal.get("indicators", {})
    smart_override_score = getattr(settings, 'MORNING_BIAS_SMART_OVERRIDE_SCORE', 8)

    # Override condition 1: High signal score
    if sig_score >= smart_override_score:
        return True, f"SMART override: signal score {sig_score} >= {smart_override_score}"

    # Override condition 2: Confirmed breakout
    if indicators.get("conf_breakout"):
        return True, f"SMART override: confirmed breakout ({indicators['conf_breakout']})"

    # Override condition 3: Strong volume + pattern
    if indicators.get("vol_ok") and (
        indicators.get("vwap_bounce") or indicators.get("pullback")
    ):
        return True, f"SMART override: volume confirmed pattern"

    # Not enough confidence — skip
    return False, (
        f"SMART block: morning bias NO_TRADE & signal score {sig_score} < {smart_override_score}, "
        f"no confirmed breakout/volume pattern"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. DEBUG HELPERS — For dashboard debug tab
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_morning_bias_debug(symbol: str = "NIFTY") -> Dict:
    """
    Full debug output for the morning bias engine.
    Includes all intermediate data, cache states, and timing.
    """
    from config import settings

    t0 = time.time()
    result = {
        "enabled":     getattr(settings, 'MORNING_BIAS_ENABLED', False),
        "gate_mode":   getattr(settings, 'MORNING_BIAS_MODE', MODE_SMART),
        "skip_minutes": getattr(settings, 'MORNING_BIAS_SKIP_MINUTES', 10),
        "min_score":   getattr(settings, 'MORNING_BIAS_MIN_SCORE', 4),
        "vix_spike":   getattr(settings, 'MORNING_BIAS_VIX_SPIKE', 25.0),
        "smart_override_score": getattr(settings, 'MORNING_BIAS_SMART_OVERRIDE_SCORE', 8),
    }

    # Run each component independently with error capture
    components = {}

    # 1. Global sentiment
    try:
        from intelligence.market_intel import get_global_sentiment
        components["global_sentiment"] = await get_global_sentiment()
    except Exception as e:
        components["global_sentiment"] = {"error": str(e)}

    # 2. Gap analysis
    try:
        from intelligence.market_intel import analyse_gap
        components["gap_analysis"] = await analyse_gap(symbol)
    except Exception as e:
        components["gap_analysis"] = {"error": str(e)}

    # 3. PCR
    try:
        components["pcr"] = await compute_pcr(symbol)
    except Exception as e:
        components["pcr"] = {"error": str(e)}

    # 4. India VIX
    try:
        components["india_vix"] = await get_india_vix()
    except Exception as e:
        components["india_vix"] = {"error": str(e)}

    # 5. FII/DII
    try:
        components["fii_dii"] = await get_fii_dii()
    except Exception as e:
        components["fii_dii"] = {"error": str(e)}

    # 6. Technical levels
    try:
        components["technical_levels"] = await get_technical_levels(symbol)
    except Exception as e:
        components["technical_levels"] = {"error": str(e)}

    # 7. Full bias
    try:
        components["morning_bias"] = await get_morning_bias(symbol)
    except Exception as e:
        components["morning_bias"] = {"error": str(e)}

    result["components"]   = components
    result["cache_sizes"]  = {
        "pcr_cache":     len(_pcr_cache),
        "vix_cache":     len(_vix_cache),
        "fii_dii_cache": len(_fii_dii_cache),
        "tech_cache":    len(_tech_cache),
        "bias_cache":    len(_bias_cache),
    }
    result["latency_ms"] = round((time.time() - t0) * 1000, 1)
    result["timestamp"]  = datetime.now(IST).isoformat()

    return result


def clear_morning_bias_cache():
    """Clear all morning bias caches — for debug/testing."""
    global _pcr_cache, _vix_cache, _fii_dii_cache, _tech_cache, _bias_cache
    _pcr_cache.clear()
    _vix_cache.clear()
    _fii_dii_cache.clear()
    _tech_cache.clear()
    _bias_cache.clear()
    logger.info("🧹 Morning bias caches cleared")
    return {"status": "cleared"}
