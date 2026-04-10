"""
Options Trading Bot — Main Entry Point v3 Fixed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY FIX: Auto-restart bot on Render wake-up.
  - On every startup, reads bot_status from database
  - If status was "running", automatically resumes the bot
  - This means you only press Start Bot ONCE ever
  - Render can sleep/wake as much as it wants — bot resumes automatically
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
from core.database import init_db, get_config, get_all_config
from config import settings

bot_engine: BotEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_engine
    logger.info("🚀 Starting Options Trading Bot v3...")

    # 1. Initialize database (creates tables if first run)
    await init_db()
    logger.info("✅ Database initialized")

    # 2. Create bot engine
    bot_engine = BotEngine()
    app.state.bot_engine = bot_engine
    logger.info("✅ Bot engine created")

    # 3. AUTO-RESTART: Check if bot was running before server went down
    # Render free tier sleeps — this brings the bot back automatically
    try:
        cfg            = await get_all_config()
        last_status    = cfg.get("bot_status", "stopped")
        last_mode      = cfg.get("mode", "paper")
        last_symbol    = cfg.get("symbol", settings.DEFAULT_SYMBOL)
        last_capital   = float(cfg.get("capital", settings.DEFAULT_CAPITAL))

        if last_status == "running":
            logger.info(
                f"🔄 Bot was running before restart — auto-resuming "
                f"({last_mode.upper()} | {last_symbol} | ₹{last_capital:,.0f})"
            )
            # Small delay so all routes are registered first
            await asyncio.sleep(2)
            await bot_engine.start(
                symbol=last_symbol,
                capital=last_capital,
                mode=last_mode,
            )
            logger.info("✅ Bot auto-resumed successfully")
        else:
            logger.info("ℹ️  Bot was stopped — waiting for manual Start from dashboard")

    except Exception as e:
        logger.error(f"Auto-restart check failed: {e} — bot will need manual start")

    yield  # App runs here

    # Shutdown
    logger.info("🛑 Shutting down...")
    if bot_engine and bot_engine.is_running:
        await bot_engine.stop()
    logger.info("✅ Shutdown complete")


app = FastAPI(
    title="Options Trading Bot API",
    description="NSE Options Trading Bot with Upstox Live Trading",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS — allow Vercel frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routes
app.include_router(router, prefix="/api")
app.include_router(ws_router)
app.include_router(upstox_router, prefix="/api/upstox")


@app.get("/")
async def root():
    return {
        "status":  "online",
        "message": "Options Trading Bot API v3",
        "version": "3.0.0",
    }


@app.get("/health")
async def health():
    """Health check — used by UptimeRobot to keep Render awake."""
    bot = app.state.bot_engine
    return {
        "status":      "healthy",
        "bot_running": bot.is_running if bot else False,
        "mode":        bot.mode if bot else "idle",
        "symbol":      bot.symbol if bot else "",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
