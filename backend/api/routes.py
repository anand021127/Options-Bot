"""API Routes — v3"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import httpx
from loguru import logger

from api.upstox_auth import get_upstox_token
from core.database import (
    get_open_trades, get_trade_history, get_stats, get_equity_curve,
    get_config, set_config, get_all_config,
    get_notifications, mark_notifications_read,
    get_execution_audit, get_open_btst_trades, get_btst_history,
)
from data.upstox_market import (
    get_live_price as fetch_live_price,
    get_option_chain as fetch_options_chain,
    fetch_ohlcv,
    is_market_open,
    get_ws_status,
)
from data.market_data import is_market_open as _yf_market_open_unused   # kept for import compat only
from strategy.signal_engine import generate_signal
from strategy.indicators import get_indicator_snapshot
from intelligence.market_intel import get_market_status, add_blocked_date, remove_blocked_date
from intelligence.strategy_intel import get_strategy_performance

router = APIRouter()


class BotStartRequest(BaseModel):
    symbol:  Optional[str]   = "NIFTY"
    capital: Optional[float] = 100000.0
    mode:    Optional[str]   = "paper"

class ConfigUpdateRequest(BaseModel):
    risk_pct:               Optional[float] = None
    daily_loss_cap:         Optional[float] = None
    max_daily_trades:       Optional[int]   = None
    max_consecutive_losses: Optional[int]   = None
    cooldown_minutes:       Optional[int]   = None
    min_score:              Optional[int]   = None
    symbol:                 Optional[str]   = None
    btst_enabled:           Optional[bool]  = None
    use_adx_filter:         Optional[bool]  = None
    use_iv_filter:          Optional[bool]  = None
    use_time_filter:        Optional[bool]  = None
    use_mtf:                Optional[bool]  = None
    use_volume_filter:      Optional[bool]  = None
    use_spike_filter:       Optional[bool]  = None
    slippage_pct:           Optional[float] = None
    global_sentiment_enabled: Optional[bool] = None
    no_trade_day_auto:      Optional[bool]  = None
    event_block_enabled:    Optional[bool]  = None
    # Morning Intelligence Engine
    morning_bias_enabled:   Optional[bool]  = None
    morning_bias_mode:      Optional[str]   = None   # STRICT | SMART | FREE
    morning_bias_skip_minutes: Optional[int] = None
    morning_bias_min_score: Optional[int]   = None
    morning_bias_vix_spike: Optional[float] = None
    morning_bias_smart_override_score: Optional[int] = None

class FiltersRequest(BaseModel):
    filters: Dict[str, Any]

class BlockedDateRequest(BaseModel):
    date: str
    reason: str


# ─── Bot Control ──────────────────────────────────────────────────────────────

@router.post("/bot/start")
async def start_bot(req: BotStartRequest, request: Request):
    bot = request.app.state.bot_engine
    if bot.is_running:
        raise HTTPException(400, "Bot already running")
    await bot.start(req.symbol, req.capital, req.mode)
    return {"status": "started", "mode": req.mode, "symbol": req.symbol, "capital": req.capital}


@router.post("/bot/stop")
async def stop_bot(request: Request):
    bot = request.app.state.bot_engine
    if not bot.is_running:
        raise HTTPException(400, "Bot not running")
    await bot.stop()
    return {"status": "stopped"}


@router.post("/bot/emergency-stop")
async def emergency_stop(request: Request):
    await request.app.state.bot_engine.emergency_stop()
    return {"status": "emergency_stopped"}


@router.get("/bot/status")
async def bot_status(request: Request):
    return request.app.state.bot_engine.get_portfolio_state()


@router.post("/bot/config")
async def update_bot_config(req: ConfigUpdateRequest, request: Request):
    bot     = request.app.state.bot_engine
    updates = {k: v for k, v in req.dict(exclude_none=True).items()}
    # Normalize booleans to lowercase strings for DB consistency
    # str(True) = "True" but bot_engine expects "true" — this caused BTST toggle bug
    for k, v in updates.items():
        if isinstance(v, bool):
            updates[k] = "true" if v else "false"
    if updates:
        await bot.update_config(updates)
    return {"status": "updated", "changes": updates}


@router.post("/bot/filters")
async def update_filters(req: FiltersRequest, request: Request):
    await request.app.state.bot_engine.update_config(req.filters)
    return {"status": "filters_updated"}


@router.post("/bot/halt")
async def halt_trading(request: Request):
    """Manually halt new trades without closing existing positions."""
    bot = request.app.state.bot_engine
    bot.trading_halted_today = True
    return {"status": "halted", "message": "No new trades will be taken today"}


@router.post("/bot/resume")
async def resume_trading(request: Request):
    bot = request.app.state.bot_engine
    bot.trading_halted_today = False
    bot.cooldown_until = None
    return {"status": "resumed"}


# ─── Market Data ──────────────────────────────────────────────────────────────

@router.get("/market/price/{symbol}")
async def get_price(symbol: str):
    data = await fetch_live_price(symbol)
    if not data:
        raise HTTPException(503, f"Price unavailable for {symbol}")
    data["market_open"] = is_market_open()
    return data


@router.get("/market/options/{symbol}")
async def get_options(symbol: str, expiry: Optional[str] = None):
    data = await fetch_options_chain(symbol, expiry)
    if not data:
        raise HTTPException(503, "Options chain unavailable")
    return data


@router.get("/market/indicators/{symbol}")
async def get_indicators(symbol: str, period: str = "5d", interval: str = "5m"):
    df = await fetch_ohlcv(symbol, period=period, interval=interval)
    if df is None:
        raise HTTPException(503, "No OHLCV data")
    return get_indicator_snapshot(df)


@router.get("/market/candles/{symbol}")
async def get_candles(symbol: str, period: str = "5d", interval: str = "5m"):
    df = await fetch_ohlcv(symbol, period=period, interval=interval)
    if df is None:
        raise HTTPException(503, "No candle data")
    df = df.reset_index()
    df.columns = [str(c).lower() for c in df.columns]
    time_col = df.columns[0]
    df["time"] = df[time_col].astype(str)
    return {"candles": df[["time", "open", "high", "low", "close", "volume"]].to_dict("records")}


@router.get("/market/status")
async def market_status(symbol: str = "NIFTY"):
    """Full market intelligence status."""
    return await get_market_status(symbol)


# ─── Trades ───────────────────────────────────────────────────────────────────

@router.get("/trades/open")
async def open_trades():
    return await get_open_trades()


@router.get("/trades/history")
async def trade_history(limit: int = 50):
    return await get_trade_history(limit)


@router.get("/trades/stats")
async def trade_stats():
    return await get_stats()


@router.get("/trades/equity-curve")
async def equity_curve():
    return await get_equity_curve(200)


@router.get("/trades/daily-summary")
async def daily_summary():
    """Daily trading summary — wins, losses, net P&L, trade count."""
    from utils.time import today_ist_str
    import aiosqlite
    today = today_ist_str()
    async with aiosqlite.connect("trading_bot.db") as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN pnl = 0 THEN 1 ELSE 0 END) as breakeven,
                COALESCE(SUM(pnl), 0) as net_pnl,
                COALESCE(MAX(pnl), 0) as best_trade,
                COALESCE(MIN(pnl), 0) as worst_trade,
                COALESCE(AVG(CASE WHEN pnl > 0 THEN pnl END), 0) as avg_win,
                COALESCE(AVG(CASE WHEN pnl < 0 THEN pnl END), 0) as avg_loss,
                COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open_trades
            FROM trades WHERE entry_time LIKE ?
        """, (f"{today}%",))
        row = dict(await cur.fetchone())
        total = max(row.get("total_trades") or 1, 1)
        wins = row.get("wins") or 0
        row["win_rate"] = round((wins / total) * 100, 1)
        row["date"] = today
        return row


@router.get("/trades/execution-audit")
async def execution_audit(trade_id: Optional[int] = None, limit: int = 50):
    return await get_execution_audit(trade_id, limit)


# ─── BTST ─────────────────────────────────────────────────────────────────────

@router.get("/btst/open")
async def btst_open():
    return await get_open_btst_trades()


@router.get("/btst/history")
async def btst_history(limit: int = 20):
    return await get_btst_history(limit)


@router.get("/btst/signal/{symbol}")
async def btst_signal(symbol: str):
    from btst.strategy import generate_btst_signal
    return await generate_btst_signal(symbol)


# ─── Intelligence ─────────────────────────────────────────────────────────────

@router.get("/intelligence/market")
async def market_intel(symbol: str = "NIFTY"):
    return await get_market_status(symbol)


@router.get("/intelligence/strategy-performance")
async def strategy_perf():
    return await get_strategy_performance()


@router.post("/intelligence/blocked-date")
async def add_event(req: BlockedDateRequest):
    add_blocked_date(req.date, req.reason)
    return {"status": "added", "date": req.date, "reason": req.reason}


@router.delete("/intelligence/blocked-date/{date}")
async def remove_event(date: str):
    remove_blocked_date(date)
    return {"status": "removed", "date": date}


# ─── Morning Market Intelligence Engine ──────────────────────────────────────

@router.get("/intelligence/morning-bias/{symbol}")
async def morning_bias(symbol: str):
    """Get morning market bias analysis for a symbol."""
    from intelligence.morning_bias import get_morning_bias
    return await get_morning_bias(symbol)


@router.get("/intelligence/vix")
async def india_vix():
    """Get current India VIX data."""
    from intelligence.morning_bias import get_india_vix
    return await get_india_vix()


@router.get("/intelligence/pcr/{symbol}")
async def pcr_data(symbol: str):
    """Get Put-Call Ratio computed from option chain OI."""
    from intelligence.morning_bias import compute_pcr
    return await compute_pcr(symbol)


@router.get("/intelligence/fii-dii")
async def fii_dii():
    """Get latest FII/DII activity data."""
    from intelligence.morning_bias import get_fii_dii
    return await get_fii_dii()


# ─── Signal ───────────────────────────────────────────────────────────────────

@router.get("/signal/{symbol}")
async def get_signal(symbol: str, request: Request):
    bot     = request.app.state.bot_engine
    filters = bot.filters if bot.is_running else {}
    score   = bot.min_score if bot.is_running else 5
    return await generate_signal(symbol, min_score=score, filters=filters)


# ─── Config ───────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_bot_config():
    return await get_all_config()


@router.put("/config")
async def update_config(req: ConfigUpdateRequest, request: Request):
    updates = {k: v for k, v in req.dict(exclude_none=True).items()}
    if updates:
        await request.app.state.bot_engine.update_config(updates)
    return {"status": "updated"}


# ─── Notifications ────────────────────────────────────────────────────────────

@router.get("/notifications")
async def get_notifs(limit: int = 20, unread_only: bool = False):
    return await get_notifications(limit=limit, unread_only=unread_only)


@router.post("/notifications/read")
async def mark_read():
    await mark_notifications_read()
    return {"status": "marked_read"}


# ─── Real-time market data (Upstox) ──────────────────────────────────────────




@router.get("/market/live-premiums")
async def live_premiums(request: Request):
    """Get current live premiums for all open trades."""
    bot    = request.app.state.bot_engine
    trades = bot.open_trades if bot else []
    try:
        from data.upstox_market import get_premiums_for_open_trades
        ltps = await get_premiums_for_open_trades(trades)
        return {"premiums": ltps, "count": len(ltps)}
    except Exception as e:
        return {"premiums": {}, "error": str(e)}


# ─── Instruments & Expiries (from Upstox API — no assumptions) ───────────────

@router.get("/market/expiries/{symbol}")
async def get_expiries(symbol: str):
    """Return available expiry dates loaded from Upstox instruments API."""
    from data.upstox_market import get_available_expiries, load_instruments, _instruments_loaded
    if not _instruments_loaded.get(symbol.upper()):
        ok = await load_instruments(symbol.upper())
        if not ok:
            raise HTTPException(503, f"Could not load instruments for {symbol}. Login to Upstox first.")
    expiries = await get_available_expiries(symbol.upper())
    if not expiries:
        raise HTTPException(503, f"No expiry dates available for {symbol}")
    return {"symbol": symbol.upper(), "expiries": expiries, "count": len(expiries)}


@router.post("/market/load-instruments/{symbol}")
async def load_instruments_endpoint(symbol: str):
    """Manually trigger instruments load for a symbol."""
    from data.upstox_market import load_instruments, _instruments_loaded
    _instruments_loaded[symbol.upper()] = False   # force reload
    ok = await load_instruments(symbol.upper())
    if not ok:
        raise HTTPException(503, f"Failed to load instruments for {symbol}")
    from data.upstox_market import get_available_expiries
    expiries = await get_available_expiries(symbol.upper())
    return {"status": "loaded", "symbol": symbol.upper(), "expiries_found": len(expiries)}


@router.get("/market/ws-status")
async def ws_status():
    """WebSocket + instruments status — for dashboard RT DATA indicator."""
    try:
        return get_ws_status()
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.get("/debug/logs")
async def debug_logs():
    from data.upstox_market import _instruments_cache, _instruments_loaded, _price_store

    token = await get_upstox_token()
    ws = get_ws_status()
    return {
        "upstox_token": "SET" if token else "MISSING",
        "data_connected": ws.get("connected", False),
        "market_open": is_market_open(),
        "instruments_count": len(_instruments_cache),
        "instruments_loaded": dict(_instruments_loaded),
        "prices_cached": _price_store,
        "subscribed_count": ws.get("subscribed_count", 0),
        "ws_status": ws,
    }


@router.get("/debug/upstox/{endpoint}")
async def debug_upstox(endpoint: str, symbol: str = "NIFTY"):
    endpoint = endpoint.lower()
    if endpoint not in {"profile", "ltp", "contract", "chain", "ohlcv"}:
        raise HTTPException(404, "Unknown debug endpoint")

    from data.upstox_market import load_instruments, get_available_expiries

    token = await get_upstox_token()
    if not token:
        raise HTTPException(401, "No Upstox token available. Please login via the dashboard.")

    if endpoint == "profile":
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.upstox.com/v2/user/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
        body = resp.json() if resp.content else {}
        return {
            "status_code": resp.status_code,
            "sample_keys": list(body.keys()),
            "sample_item": body,
        }

    if endpoint == "ltp":
        data = await fetch_live_price(symbol)
        if not data:
            raise HTTPException(503, f"Live price unavailable for {symbol}")
        return {
            "status_code": 200,
            "sample_item": data,
            "sample_keys": list(data.keys()),
        }

    if endpoint == "contract":
        loaded = await load_instruments(symbol)
        sample = None
        total = 0
        if loaded:
            from data.upstox_market import _instruments_cache
            sample = next(iter(_instruments_cache.values()), None)
            total = len(_instruments_cache)
        return {
            "status_code": 200 if loaded else 503,
            "total_items": total,
            "sample_keys": list(sample.keys()) if sample else [],
            "sample_item": sample,
        }

    if endpoint == "chain":
        expiries = await get_available_expiries(symbol)
        if not expiries:
            raise HTTPException(503, f"No expiry data available for {symbol}")
        chain_data = await fetch_options_chain(symbol, expiries[0])
        if not chain_data:
            raise HTTPException(503, f"Option chain unavailable for {symbol} {expiries[0]}")
        sample = chain_data.get("calls") or chain_data.get("puts") or []
        return {
            "status_code": 200,
            "total_items": len(sample),
            "sample_keys": list(chain_data.keys()),
            "sample_item": {
                "symbol": chain_data.get("symbol"),
                "expiry": chain_data.get("expiry"),
                "spot": chain_data.get("spot"),
            },
        }

    if endpoint == "ohlcv":
        data = await fetch_ohlcv(symbol, period="5d", interval="5m")
        if data is None:
            raise HTTPException(503, f"OHLCV unavailable for {symbol}")
        sample = data.reset_index().head(1).to_dict("records")[0] if not data.empty else {}
        return {
            "status_code": 200,
            "total_items": len(data),
            "sample_keys": list(sample.keys()),
            "sample_item": sample,
        }


# ─── Morning Bias Debug Endpoints ─────────────────────────────────────────────

@router.get("/debug/morning-bias/{symbol}")
async def debug_morning_bias(symbol: str):
    """
    Full debug output for morning bias engine.
    Shows all components, cache state, settings, and timing.
    """
    from intelligence.morning_bias import get_morning_bias_debug
    return await get_morning_bias_debug(symbol)


@router.get("/debug/morning-bias-component/{component}")
async def debug_morning_bias_component(component: str, symbol: str = "NIFTY"):
    """
    Test individual morning bias components.
    Components: pcr, vix, fii_dii, technical, gap, sentiment, bias
    """
    component = component.lower()
    valid = {"pcr", "vix", "fii_dii", "technical", "gap", "sentiment", "bias"}
    if component not in valid:
        raise HTTPException(404, f"Unknown component '{component}'. Valid: {sorted(valid)}")

    import time
    t0 = time.time()

    if component == "pcr":
        from intelligence.morning_bias import compute_pcr
        data = await compute_pcr(symbol)
    elif component == "vix":
        from intelligence.morning_bias import get_india_vix
        data = await get_india_vix()
    elif component == "fii_dii":
        from intelligence.morning_bias import get_fii_dii
        data = await get_fii_dii()
    elif component == "technical":
        from intelligence.morning_bias import get_technical_levels
        data = await get_technical_levels(symbol)
    elif component == "gap":
        from intelligence.market_intel import analyse_gap
        data = await analyse_gap(symbol)
    elif component == "sentiment":
        from intelligence.market_intel import get_global_sentiment
        data = await get_global_sentiment()
    elif component == "bias":
        from intelligence.morning_bias import get_morning_bias
        data = await get_morning_bias(symbol)
    else:
        data = {}

    return {
        "component": component,
        "symbol": symbol,
        "data": data,
        "latency_ms": round((time.time() - t0) * 1000, 1),
    }


@router.post("/debug/morning-bias/clear-cache")
async def debug_clear_morning_bias_cache():
    """Clear all morning bias caches for fresh testing."""
    from intelligence.morning_bias import clear_morning_bias_cache
    return clear_morning_bias_cache()


# ─── AI Advisor ───────────────────────────────────────────────────────────────

@router.get("/ai/status")
async def ai_status():
    """Get AI advisor status."""
    from intelligence.ai_advisor import get_ai_status
    return get_ai_status()


@router.get("/ai/history")
async def ai_history(limit: int = 20):
    """Get recent AI verdicts."""
    from intelligence.ai_advisor import get_ai_history
    return get_ai_history(limit)


@router.post("/ai/toggle")
async def toggle_ai(request: Request):
    """Toggle AI on/off."""
    from config import settings
    current = getattr(settings, 'AI_ENABLED', False)
    settings.AI_ENABLED = not current
    return {"ai_enabled": settings.AI_ENABLED}


class AIConfigRequest(BaseModel):
    ai_enabled: Optional[bool] = None
    ai_min_confidence: Optional[int] = None

@router.post("/ai/config")
async def update_ai_config(req: AIConfigRequest):
    """Update AI configuration."""
    from config import settings
    if req.ai_enabled is not None:
        settings.AI_ENABLED = req.ai_enabled
    if req.ai_min_confidence is not None:
        settings.AI_MIN_CONFIDENCE = req.ai_min_confidence
    return {
        "ai_enabled": settings.AI_ENABLED,
        "ai_min_confidence": settings.AI_MIN_CONFIDENCE,
    }


@router.get("/ai/analysis")
async def ai_analysis(symbol: str = "NIFTY"):
    """Trigger proactive AI market analysis using current indicators."""
    from intelligence.ai_advisor import analyze_market_conditions
    try:
        df = await fetch_ohlcv(symbol, period="5d", interval="5m")
        if df is not None and len(df) >= 50:
            indicators = get_indicator_snapshot(df)
            result = await analyze_market_conditions(symbol, indicators)
            return result
        return {
            "market_outlook": "NEUTRAL",
            "confidence": 0,
            "analysis": "Insufficient market data for analysis",
            "source": "fallback",
        }
    except Exception as e:
        return {
            "market_outlook": "NEUTRAL",
            "confidence": 0,
            "analysis": f"Analysis error: {str(e)[:100]}",
            "source": "error",
        }


@router.get("/market/trading-day")
async def trading_day_check():
    """Check if today is a valid NSE trading day (fetched from live API)."""
    from intelligence.market_intel import is_trading_day, get_nse_holidays_cached
    is_td, reason = await is_trading_day()
    return {
        "is_trading_day": is_td,
        "reason": reason,
        "market_open": is_market_open(),
        "nse_holidays": get_nse_holidays_cached(),
    }


# ─── Signal Decision Log ─────────────────────────────────────────────────────

@router.get("/signals/log")
async def signal_log(limit: int = 50):
    """Get signal decision history."""
    async with __import__('aiosqlite').connect("trading_bot.db") as db:
        db.row_factory = __import__('aiosqlite').Row
        cur = await db.execute(
            "SELECT * FROM signals_log ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return [dict(r) for r in await cur.fetchall()]

