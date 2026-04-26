"""
IST Timezone Utilities
━━━━━━━━━━━━━━━━━━━━━━
All timestamps in the trading bot must use IST (UTC+5:30).
Servers (Render, etc.) run in UTC — so datetime.now() returns UTC.
This module provides IST-aware helpers to ensure correct timestamps
in the database, trade logs, and frontend display.
"""

from datetime import datetime, date
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Return the current datetime in IST (Asia/Kolkata), timezone-aware."""
    return datetime.now(IST)


def today_ist() -> date:
    """Return today's date in IST."""
    return datetime.now(IST).date()


def today_ist_str() -> str:
    """Return today's date in IST as YYYY-MM-DD string."""
    return datetime.now(IST).strftime("%Y-%m-%d")


def now_ist_iso() -> str:
    """Return the current IST datetime as ISO string (for DB storage)."""
    return datetime.now(IST).isoformat()
