"""
Options Trading Bot — Main v3.1 (Real-Time Upstox)
Starts Upstox WebSocket on startup. Auto-resumes bot after Render sleep.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.routes import router
from api.websocket import ws_router
from api.upstox_auth import router as upstox_router
from core.bot_engine import BotEngine
from core.database import init_db, get_all_config
from config import settings

bot_engine: BotEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_engine
    logger.info("🚀 Starting Options Trading Bot v3.1 (Real-Time)...")

    await init_db()
    logger.info("✅ Database ready")

    # Start Upstox WebSocket (real-time market data)
    try:
        from data.upstox_market import connect_websocket
        await connect_websocket(symbols=["NIFTY", "BANKNIFTY"])
        logger.info("📡 Upstox WebSocket started")
    except Exception as e:
        logger.warning(f"WebSocket not started ({e}) — using yfinance fallback")

    # Create bot engine
    bot_engine = BotEngine()
    app.state.bot_engine = bot_engine

    # Auto-restart if was running before sleep
    try:
        cfg          = await get_all_config()
        last_status  = cfg.get("bot_status", "stopped")
        last_mode    = cfg.get("mode", "paper")
        last_symbol  = cfg.get("symbol", settings.DEFAULT_SYMBOL)
        last_capital = float(cfg.get("capital", settings.DEFAULT_CAPITAL))

        if last_status == "running":
            logger.info(f"🔄 Auto-resuming: {last_mode.upper()} | {last_symbol}")
            await asyncio.sleep(3)
            await bot_engine.start(symbol=last_symbol, capital=last_capital, mode=last_mode)
            logger.info("✅ Bot auto-resumed")
        else:
            logger.info("ℹ️  Bot idle — press Start in dashboard")
    except Exception as e:
        logger.error(f"Auto-restart error: {e}")

    yield

    logger.info("🛑 Shutting down...")
    if bot_engine and bot_engine.is_running:
        await bot_engine.stop()


app = FastAPI(title="Options Trading Bot API", version="3.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router,        prefix="/api")
app.include_router(ws_router)
app.include_router(upstox_router, prefix="/api/upstox")


@app.get("/")
async def root():
    return {"status": "online", "version": "3.1.0"}


@app.get("/health")
async def health():
    bot = app.state.bot_engine
    try:
        from data.upstox_market import get_ws_status
        ws = get_ws_status()
    except Exception:
        ws = {"connected": False}
    return {
        "status":       "healthy",
        "bot_running":  bot.is_running if bot else False,
        "mode":         bot.mode if bot else "idle",
        "ws_connected": ws.get("connected", False),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
