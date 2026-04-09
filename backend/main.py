"""
Options Trading Bot - Main Entry Point
FastAPI backend with WebSocket support for real-time updates
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.routes import router
from api.websocket import ws_router
from core.bot_engine import BotEngine
from core.database import init_db
from config import settings

# Global bot engine instance
bot_engine: BotEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle management"""
    global bot_engine
    logger.info("🚀 Starting Options Trading Bot...")

    # Initialize database
    await init_db()
    logger.info("✅ Database initialized")

    # Create bot engine (does NOT auto-start trading)
    bot_engine = BotEngine()
    app.state.bot_engine = bot_engine
    logger.info("✅ Bot engine created (idle)")

    yield  # App runs here

    # Shutdown
    logger.info("🛑 Shutting down bot...")
    if bot_engine and bot_engine.is_running:
        await bot_engine.stop()
    logger.info("✅ Shutdown complete")


app = FastAPI(
    title="Options Trading Bot API",
    description="Zero-cost paper/live options trading bot for NSE",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow frontend (Vercel) to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(router, prefix="/api")
app.include_router(ws_router)


@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Options Trading Bot API",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    """Health check endpoint - used by Render keep-alive ping"""
    bot = app.state.bot_engine
    return {
        "status": "healthy",
        "bot_running": bot.is_running if bot else False,
        "mode": bot.mode if bot else "idle",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
