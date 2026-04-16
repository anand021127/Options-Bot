"""Configuration — v3 with Upstox support and auto-start"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_ENV:          str   = "development"
    SECRET_KEY:       str   = "change-this-32-char-secret-key-here"
    ALLOWED_ORIGINS:  List[str] = ["http://localhost:3000"]

    DATABASE_URL:     str   = "sqlite+aiosqlite:///./trading_bot.db"
    MONGODB_URL:      str   = ""

    DEFAULT_SYMBOL:   str   = "NIFTY"
    DEFAULT_CAPITAL:  float = 100000.0
    RISK_PER_TRADE_PCT: float = 1.5
    DAILY_LOSS_CAP_PCT: float = 3.0
    REWARD_RATIO:     float = 2.0
    MAX_DAILY_TRADES: int   = 5
    MAX_OPEN_TRADES:  int   = 2
    MAX_CONSECUTIVE_LOSSES: int = 2
    MAX_LOSS_STREAK_DAY_STOP: int = 3
    COOLDOWN_MINUTES: int   = 20
    MIN_SCORE:        int   = 5

    # Adaptive sizing
    RISK_SCORE_LOW:        float = 1.0
    RISK_SCORE_MID:        float = 1.5
    RISK_SCORE_HIGH:       float = 2.0
    RISK_HIGH_ATR_MULT:    float = 0.7
    RISK_LOSS_STREAK_MULT: float = 0.5

    # Strategy filters
    USE_ADX_FILTER:    bool = True
    USE_IV_FILTER:     bool = True
    USE_TIME_FILTER:   bool = True
    USE_MTF:           bool = True
    USE_VOLUME_FILTER: bool = True
    USE_SPIKE_FILTER:  bool = True

    # BTST
    BTST_ENABLED:             bool  = False
    BTST_ENTRY_HOUR:          int   = 14
    BTST_ENTRY_MIN:           int   = 45
    BTST_EXIT_HOUR:           int   = 9
    BTST_EXIT_MIN:            int   = 20
    BTST_RISK_PCT:            float = 1.0
    BTST_MAX_PER_DAY:         int   = 1
    BTST_GAP_PROFIT_EXIT_PCT: float = 40.0

    # Execution
    ORDER_TYPE:         str   = "MARKET"
    SLIPPAGE_PCT:       float = 0.5
    ORDER_RETRY_MAX:    int   = 2
    ORDER_RETRY_DELAY:  float = 2.0
    # ❌ LOT_SIZE_NIFTY / LOT_SIZE_BANKNIFTY removed — must come from Upstox API

    # Market intelligence
    GLOBAL_SENTIMENT_ENABLED: bool = True
    NO_TRADE_DAY_AUTO:        bool = True
    EVENT_CALENDAR_MANUAL:    bool = True

    # Safety
    HARD_STOP_ON_API_FAIL:      bool = True
    HARD_STOP_ON_DATA_MISMATCH: bool = True

    # Broker — set BROKER=upstox to use Upstox
    BROKER:              str = "none"   # "none" | "upstox" | "angel" | "fyers"

    # Angel One
    BROKER_API_KEY:      str = ""
    BROKER_CLIENT_CODE:  str = ""
    BROKER_TOTP_SECRET:  str = ""

    # Fyers
    FYERS_APP_ID:        str = ""
    FYERS_SECRET_KEY:    str = ""

    # Upstox — set these in Render Environment Variables
    UPSTOX_API_KEY:      str = ""
    UPSTOX_API_SECRET:   str = ""
    UPSTOX_REDIRECT_URI: str = ""
    # UPSTOX_ACCESS_TOKEN is stored in DB (refreshes daily via OAuth login)
    # You can also set a static one here as fallback
    UPSTOX_ACCESS_TOKEN: str = ""

    # AI Advisor — Gemini
    AI_ENABLED:          bool = True
    GEMINI_API_KEY:      str  = ""
    AI_MIN_CONFIDENCE:   int  = 50    # below this, AI flags a warning (but doesn't block)

    MARKET_OPEN:         str = "09:15"
    MARKET_CLOSE:        str = "15:30"
    DATA_FETCH_INTERVAL: int = 45     # seconds between signal checks (was 60)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
