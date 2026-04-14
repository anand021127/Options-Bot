"""API Routes — v3"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from loguru import logger

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