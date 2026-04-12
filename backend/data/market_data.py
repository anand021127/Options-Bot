"""
market_data.py — DEPRECATED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This module previously used yfinance. It is now DEPRECATED.
All market data comes from data/upstox_market.py exclusively.

This file exists only to prevent ImportError in legacy code paths.
Any function call will raise RuntimeError to surface misuse immediately.
"""

from loguru import logger


def _raise(fn: str):
    raise RuntimeError(
        f"❌ market_data.{fn}() called — this module is DEPRECATED. "
        f"Use data.upstox_market instead. No yfinance or fallback allowed."
    )


async def fetch_ohlcv(*a, **kw):
    _raise("fetch_ohlcv")


async def fetch_live_price(*a, **kw):
    _raise("fetch_live_price")


async def fetch_options_chain(*a, **kw):
    _raise("fetch_options_chain")


async def get_atm_option(*a, **kw):
    _raise("get_atm_option")


def is_market_open() -> bool:
    """Kept callable (no side effects) for routes.py compat import."""
    from data.upstox_market import is_market_open as _real
    return _real()


def get_yf_symbol(symbol: str) -> str:
    _raise("get_yf_symbol")
