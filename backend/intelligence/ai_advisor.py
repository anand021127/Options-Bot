"""
AI Advisor — Gemini-Powered Signal Validator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Uses Google Gemini to provide AI-assisted trade validation:

  1. Receives signal + indicators + market context
  2. Returns: approved (bool), confidence (0-100), reasoning, risk_notes
  3. Non-blocking: if AI is unavailable, trade proceeds (advisory only)
  4. Cached: same signal fingerprint doesn't call API twice

Configurable via dashboard:
  - AI_ENABLED: true/false
  - GEMINI_API_KEY: from env
  - AI_MIN_CONFIDENCE: minimum AI confidence to not flag warning (default 50)
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime
from typing import Dict, Optional
from loguru import logger


# ── In-memory cache ───────────────────────────────────────────────────────────
_ai_cache: Dict[str, Dict] = {}
_AI_CACHE_TTL = 300  # 5 minutes
_ai_history: list = []  # recent AI verdicts for dashboard
_AI_HISTORY_MAX = 50


def _make_fingerprint(signal: Dict, indicators: Dict) -> str:
    """Hash signal+indicators to avoid duplicate API calls."""
    key_data = {
        "signal_type": signal.get("signal_type", ""),
        "score": signal.get("score", 0),
        "strategy": str(signal.get("strategy_type", "")),
        "regime": indicators.get("regime", ""),
        "adx": round(indicators.get("adx", 0), 0),
        "rsi": round(indicators.get("rsi", 0), 0),
        "structure": indicators.get("structure", ""),
    }
    return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()[:12]


async def validate_signal(
    signal: Dict,
    indicators: Dict,
    symbol: str = "NIFTY",
) -> Dict:
    """
    Ask Gemini AI to evaluate a trading signal.

    Returns:
    {
        "approved": True/False,
        "confidence": 0-100,
        "reasoning": "...",
        "risk_notes": "...",
        "source": "gemini" | "cache" | "fallback",
        "latency_ms": float,
    }

    NEVER blocks trading — returns fallback approval if anything fails.
    """
    from config import settings

    # Check if AI is enabled
    if not getattr(settings, 'AI_ENABLED', False):
        return _fallback("AI disabled in settings", source="disabled")

    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        return _fallback("No GEMINI_API_KEY configured", source="no_key")

    # Check cache
    fp = _make_fingerprint(signal, indicators)
    cached = _ai_cache.get(fp)
    if cached and (time.time() - cached.get("_ts", 0)) < _AI_CACHE_TTL:
        cached_result = {**cached, "source": "cache"}
        cached_result.pop("_ts", None)
        return cached_result

    # Build prompt
    prompt = _build_prompt(signal, indicators, symbol)

    t0 = time.time()
    try:
        result = await _call_gemini(api_key, prompt)
        result["latency_ms"] = round((time.time() - t0) * 1000, 1)
        result["source"] = "gemini"
        result["timestamp"] = datetime.now().isoformat()
        result["symbol"] = symbol
        result["signal_type"] = signal.get("signal_type", "")
        result["score"] = signal.get("score", 0)

        # Cache it
        _ai_cache[fp] = {**result, "_ts": time.time()}

        # Add to history
        _ai_history.insert(0, result)
        if len(_ai_history) > _AI_HISTORY_MAX:
            _ai_history.pop()

        icon = "✅" if result["approved"] else "⚠️"
        logger.info(
            f"🤖 AI {icon} | {symbol} {signal.get('signal_type', '')} | "
            f"Conf={result['confidence']}% | {result['reasoning'][:80]}"
        )
        return result

    except Exception as e:
        logger.warning(f"AI advisor error: {e} — approving by default")
        return _fallback(f"API error: {str(e)[:60]}", source="error")


def _fallback(reason: str, source: str = "fallback") -> Dict:
    """Default: approve the trade (AI is advisory, not mandatory)."""
    return {
        "approved": True,
        "confidence": 50,
        "reasoning": f"AI unavailable ({reason}) — proceeding with signal score",
        "risk_notes": "",
        "source": source,
        "latency_ms": 0,
    }


def _build_prompt(signal: Dict, indicators: Dict, symbol: str) -> str:
    """Build comprehensive prompt for Gemini."""
    direction = signal.get("signal_type", "UNKNOWN")
    score = signal.get("score", 0)
    max_score = signal.get("max_score", 16)
    strategy = str(signal.get("strategy_type", "UNKNOWN"))

    # Indicator summary
    ind = indicators
    close = ind.get("close", 0)
    ema9 = ind.get("ema9", 0)
    ema20 = ind.get("ema20", 0)
    ema50 = ind.get("ema50", 0)
    vwap = ind.get("vwap", 0)
    rsi = ind.get("rsi", 50)
    adx = ind.get("adx", 0)
    atr = ind.get("atr", 0)
    structure = ind.get("structure", "UNKNOWN")
    regime = ind.get("regime", "UNKNOWN")
    vol_ok = ind.get("vol_ok", False)
    conf_breakout = ind.get("conf_breakout", None)
    pullback = ind.get("pullback", None)
    vwap_bounce = ind.get("vwap_bounce", None)
    iv_data = ind.get("iv_rank", {})
    iv_rank = iv_data.get("iv_rank", 50) if isinstance(iv_data, dict) else 50
    iv_regime = iv_data.get("regime", "NORMAL_IV") if isinstance(iv_data, dict) else "NORMAL_IV"

    # Gate results
    gate_log = signal.get("gate_log", [])
    gates_str = "\n".join(f"  - {g}" for g in gate_log) if gate_log else "  No gate log available"

    # Reasons
    reasons = signal.get("reasons", [])
    reasons_str = "\n".join(f"  - {r}" for r in reasons[:6])

    return f"""You are a professional Indian options trader analyzing a signal from an algorithmic trading bot.

SIGNAL SUMMARY:
- Symbol: {symbol}
- Direction: {direction}
- Strategy: {strategy}
- Score: {score}/{max_score}
- Entry Pattern: breakout={conf_breakout}, pullback={pullback}, vwap_bounce={vwap_bounce}

TECHNICAL INDICATORS:
- Close: ₹{close:.0f} | EMA9: ₹{ema9:.0f} | EMA20: ₹{ema20:.0f} | EMA50: ₹{ema50:.0f}
- VWAP: ₹{vwap:.0f} | RSI: {rsi:.1f} | ADX: {adx:.1f} | ATR: {atr:.2f}
- Structure: {structure} | Regime: {regime}
- Volume OK: {vol_ok} | IV Rank: {iv_rank} ({iv_regime})

GATE RESULTS:
{gates_str}

SCORING REASONS:
{reasons_str}

TASK: Evaluate this signal as a risk manager. Respond in EXACTLY this JSON format:
{{
  "approved": true or false,
  "confidence": 0-100,
  "reasoning": "One concise sentence explaining your decision",
  "risk_notes": "Key risk factor to watch (or empty string)"
}}

RULES:
- If score >= 5 with confirming pattern, APPROVE with high confidence
- If score >= 5 but RSI extreme or IV HIGH, approve with caution
- If multiple indicators conflict, reduce confidence
- Focus on PRACTICAL trading — don't over-analyze, be actionable
- For Indian indices: ATR of 0.5-1.5% is NORMAL, not volatile"""


async def _call_gemini(api_key: str, prompt: str) -> Dict:
    """Call Google Gemini API and parse response."""
    import httpx

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 256,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.post(url, json=payload)

    if resp.status_code != 200:
        raise ValueError(f"Gemini API {resp.status_code}: {resp.text[:200]}")

    data = resp.json()

    # Parse response text
    try:
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates in response")

        text = candidates[0]["content"]["parts"][0]["text"]

        # Clean up: remove markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        result = json.loads(text)

        return {
            "approved": bool(result.get("approved", True)),
            "confidence": max(0, min(100, int(result.get("confidence", 50)))),
            "reasoning": str(result.get("reasoning", ""))[:200],
            "risk_notes": str(result.get("risk_notes", ""))[:200],
        }

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning(f"Gemini response parse error: {e}")
        # Try to extract from raw text
        return {
            "approved": True,
            "confidence": 50,
            "reasoning": f"AI response unparseable — proceeding",
            "risk_notes": str(text[:100]) if 'text' in dir() else "",
        }


# ── Dashboard API helpers ─────────────────────────────────────────────────────

def get_ai_history(limit: int = 20) -> list:
    """Return recent AI verdicts for dashboard display."""
    return _ai_history[:limit]


def get_ai_status() -> Dict:
    """Return AI advisor status for dashboard."""
    from config import settings
    enabled = getattr(settings, 'AI_ENABLED', False)
    has_key = bool(getattr(settings, 'GEMINI_API_KEY', ''))

    return {
        "enabled": enabled,
        "has_key": has_key,
        "ready": enabled and has_key,
        "cache_size": len(_ai_cache),
        "history_count": len(_ai_history),
        "last_verdict": _ai_history[0] if _ai_history else None,
    }
