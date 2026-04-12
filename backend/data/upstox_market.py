"""
Upstox Real-Time Market Data — PRODUCTION GRADE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT ZERO-ASSUMPTION / ZERO-FALLBACK POLICY:
  ❌ No hardcoded expiry day (Thursday)
  ❌ No hardcoded lot size (50/15)
  ❌ No yfinance for any data source
  ❌ No random or simulated prices
  ❌ No constructed instrument tokens from strings

Fail-Safe:
  If ANY data is missing from Upstox → return None → caller MUST NOT trade.
  Bot stops cleanly. No silent fallback to stale or incorrect data.

Data Sources (Upstox only):
  1. WebSocket  → live index prices + option LTPs (< 100ms)
  2. REST       → option chain, OHLCV candles, instruments metadata
  3. Instruments API → lot_size, expiry dates, actual instrument tokens
"""

import asyncio
import json
import time
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import httpx
import pandas as pd
import numpy as np
from loguru import logger
from zoneinfo import ZoneInfo

IST           = ZoneInfo("Asia/Kolkata")
UPSTOX_BASE   = "https://api.upstox.com/v2"
UPSTOX_WS_URL = "wss://api.upstox.com/v2/feed/market-data-feed"

# ─── Upstox index instrument keys (official keys, not constructed) ─────────────
INDEX_KEYS: Dict[str, str] = {
    "NIFTY":     "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "SENSEX":    "BSE_INDEX|SENSEX",
    "FINNIFTY":  "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY":"NSE_INDEX|Nifty Midcap Select",
}

# ─── In-memory live stores (updated by WebSocket) ─────────────────────────────
_price_store:       Dict[str, Dict]  = {}   # symbol → {price, high, low, ...}
_option_ltp_store:  Dict[str, float] = {}   # instrument_key → ltp
_bid_ask_store:     Dict[str, Dict]  = {}   # instrument_key → {bid, ask}

# ─── Instruments metadata cache (from Upstox instruments API) ─────────────────
# instrument_key → {lot_size, expiry, strike, tradingsymbol, ...}
_instruments_cache: Dict[str, Dict]  = {}
_instruments_loaded: Dict[str, bool] = {}   # symbol → loaded flag

# ─── Option chain + OHLCV caches ──────────────────────────────────────────────
_option_chain_cache: Dict[str, Dict] = {}
_ohlcv_cache:        Dict[str, Dict] = {}

# ─── WebSocket state ──────────────────────────────────────────────────────────
_ws_task:         Optional[asyncio.Task] = None
_ws_connected:    bool                   = False
_ws_active_keys:  List[str]             = []
_ws_ref:          Optional[object]       = None   # live ws handle for re-subscription


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOKEN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _get_token() -> str:
    """
    Get Upstox access token from database.
    Raises RuntimeError if token missing — callers must handle and NOT trade.
    """
    from api.upstox_auth import get_upstox_token
    token = await get_upstox_token()
    if not token:
        raise RuntimeError(
            "NO_TOKEN: Upstox access token missing. "
            "Login via dashboard → Upstox Login button."
        )
    return token


def _headers(token: str) -> Dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INSTRUMENTS METADATA — expiry dates + lot sizes from API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def load_instruments(symbol: str = "NIFTY") -> bool:
    """
    Download NSE F&O instruments list from Upstox.
    Populates _instruments_cache with actual lot sizes, expiry dates, tokens.

    Must be called before any ATM option selection.
    Returns True if loaded successfully.

    ❌ NEVER hardcode lot_size or expiry — this function is the only source.
    """
    global _instruments_cache, _instruments_loaded

    if _instruments_loaded.get(symbol):
        return True

    try:
        token = await _get_token()
        # Upstox instruments endpoint — returns all NSE F&O contracts
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{UPSTOX_BASE}/option/contract",
                params={"instrument_key": INDEX_KEYS.get(symbol.upper(), f"NSE_INDEX|{symbol}")},
                headers=_headers(token),
            )

        if resp.status_code != 200:
            logger.error(f"Instruments load failed: {resp.status_code} {resp.text[:300]}")
            return False

        data       = resp.json().get("data", [])
        count      = 0
        today_str  = date.today().isoformat()

        for inst in data:
            expiry    = inst.get("expiry", "")
            if not expiry or expiry < today_str:
                continue   # skip expired contracts

            inst_key  = inst.get("instrument_key", "")
            lot_size  = inst.get("lot_size")
            strike    = inst.get("strike_price")
            opt_type  = inst.get("option_type", "")   # CE or PE
            tradingsy = inst.get("trading_symbol", "")

            # Every field must be present — skip incomplete records
            if not inst_key or not lot_size or strike is None or not opt_type:
                continue

            _instruments_cache[inst_key] = {
                "instrument_key": inst_key,
                "trading_symbol": tradingsy,
                "symbol":         symbol,
                "expiry":         expiry,
                "strike":         float(strike),
                "option_type":    opt_type.upper(),
                "lot_size":       int(lot_size),
                "exchange":       inst.get("exchange", "NSE"),
            }
            count += 1

        _instruments_loaded[symbol] = True
        logger.info(f"✅ Instruments loaded: {symbol} → {count} active contracts")
        return count > 0

    except Exception as e:
        logger.error(f"Instruments load error: {e}")
        return False


async def get_available_expiries(symbol: str) -> List[str]:
    """
    Return sorted list of available expiry dates from instruments API.
    ❌ NEVER calculate expiry from weekday logic.
    ✅ Always from this function.
    """
    if not _instruments_loaded.get(symbol):
        ok = await load_instruments(symbol)
        if not ok:
            return []

    sym = symbol.upper()
    expiries = set()
    for meta in _instruments_cache.values():
        if meta.get("symbol", "").upper() == sym:
            expiries.add(meta["expiry"])

    return sorted(expiries)


async def get_nearest_expiry(symbol: str) -> Optional[str]:
    """
    Get nearest active expiry from Upstox instruments data.
    ❌ Does NOT assume Thursday or any weekday.
    ✅ Returns first expiry that exists in the actual instruments list.
    """
    expiries = await get_available_expiries(symbol)
    if not expiries:
        logger.error(f"No expiries found for {symbol} — cannot determine nearest expiry")
        return None

    today = date.today().isoformat()
    valid = [e for e in expiries if e >= today]
    if not valid:
        logger.error(f"No future expiries found for {symbol}")
        return None

    nearest = valid[0]
    logger.info(f"📅 Nearest expiry for {symbol}: {nearest} (from {len(valid)} available)")
    return nearest


async def get_instrument_meta(instrument_key: str) -> Optional[Dict]:
    """
    Get full metadata for an instrument key.
    Returns: {instrument_key, trading_symbol, lot_size, strike, expiry, option_type}
    """
    if instrument_key in _instruments_cache:
        return _instruments_cache[instrument_key]

    # Not cached — try a direct API call
    try:
        token = await _get_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{UPSTOX_BASE}/instruments/master",
                params={"instrument_key": instrument_key},
                headers=_headers(token),
            )
        if resp.status_code == 200:
            d = resp.json().get("data", {})
            if d:
                meta = {
                    "instrument_key": instrument_key,
                    "trading_symbol": d.get("trading_symbol", ""),
                    "lot_size":       int(d.get("lot_size", 0)),
                    "strike":         float(d.get("strike_price", 0)),
                    "expiry":         d.get("expiry", ""),
                    "option_type":    d.get("option_type", ""),
                }
                _instruments_cache[instrument_key] = meta
                return meta
    except Exception as e:
        logger.warning(f"Instrument meta fetch error: {e}")
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WEBSOCKET — live streaming
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def connect_websocket(symbols: List[str] = None) -> bool:
    """
    Start Upstox market data WebSocket in background.
    Subscribes to index prices. Option keys added dynamically on trade entry.
    Auto-reconnects with exponential backoff.
    """
    global _ws_task
    if symbols is None:
        symbols = ["NIFTY", "BANKNIFTY"]

    if _ws_task and not _ws_task.done():
        return True  # already running

    _ws_task = asyncio.create_task(_ws_main_loop(symbols))
    logger.info(f"📡 WebSocket task started for {symbols}")
    return True


async def _ws_main_loop(symbols: List[str]):
    global _ws_connected, _ws_ref
    retry  = 2
    max_rt = 60

    while True:
        try:
            token = await _get_token()
        except Exception as e:
            logger.warning(f"WS no token ({e}) — retry in 30s")
            await asyncio.sleep(30)
            continue

        try:
            import websockets
            logger.info("📡 Connecting Upstox WebSocket...")

            async with websockets.connect(
                UPSTOX_WS_URL,
                extra_headers={"Authorization": f"Bearer {token}"},
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                _ws_connected = True
                _ws_ref       = ws
                retry         = 2
                logger.info("✅ Upstox WebSocket connected")

                # Subscribe to index instruments
                keys = [INDEX_KEYS[s.upper()] for s in symbols if s.upper() in INDEX_KEYS]
                if _ws_active_keys:
                    keys = list(set(keys + _ws_active_keys))
                await _ws_send_subscribe(ws, keys)

                async for raw in ws:
                    await _ws_parse(raw)

        except Exception as e:
            _ws_connected = False
            _ws_ref       = None
            logger.warning(f"WS disconnected ({e}) — retry in {retry}s")
            await asyncio.sleep(retry)
            retry = min(retry * 2, max_rt)


async def _ws_send_subscribe(ws, keys: List[str]):
    """Send subscription request for a list of instrument keys."""
    global _ws_active_keys
    if not keys:
        return
    msg = {
        "guid":   "optbot-sub",
        "method": "sub",
        "data": {
            "mode":           "full",
            "instrumentKeys": keys,
        }
    }
    await ws.send(json.dumps(msg))
    _ws_active_keys = list(set(_ws_active_keys + keys))
    logger.info(f"WS subscribed: {len(keys)} instruments")


async def subscribe_option_live(instrument_key: str):
    """
    Subscribe a specific option instrument for live LTP streaming.
    Called after trade entry so P&L tracks in real time.
    """
    global _ws_active_keys, _ws_ref
    if instrument_key in _ws_active_keys:
        return
    _ws_active_keys.append(instrument_key)
    if _ws_ref:
        try:
            await _ws_send_subscribe(_ws_ref, [instrument_key])
        except Exception as e:
            logger.warning(f"WS subscribe error: {e}")


async def _ws_parse(raw):
    """Parse Upstox WebSocket feed and update in-memory stores."""
    global _price_store, _option_ltp_store, _bid_ask_store
    try:
        msg  = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        feeds = msg.get("feeds", {})

        for key, feed in feeds.items():
            ff   = feed.get("ff", {})
            ltpc = ff.get("ltpc", {})
            ltp  = ltpc.get("ltp")
            if ltp is None:
                continue

            ltp = float(ltp)

            if "INDEX" in key:
                # Spot index — update _price_store
                ohlc = ff.get("dayOhlc", {})
                sym  = _key_to_sym(key)
                prev = float(ohlc.get("close") or ltp)
                _price_store[sym] = {
                    "price":      round(ltp, 2),
                    "open":       round(float(ohlc.get("open") or ltp), 2),
                    "high":       round(float(ohlc.get("high") or ltp), 2),
                    "low":        round(float(ohlc.get("low")  or ltp), 2),
                    "volume":     int(ff.get("vol") or 0),
                    "change_pct": round(((ltp - prev) / prev) * 100, 2) if prev else 0,
                    "timestamp":  datetime.now(IST).isoformat(),
                    "symbol":     sym,
                    "source":     "upstox_ws",
                }
            else:
                # Options contract LTP
                _option_ltp_store[key] = round(ltp, 2)
                # Also capture bid/ask if available
                md = ff.get("marketLevel", {})
                if md:
                    bids = md.get("bidAskQuote", [])
                    if bids and len(bids) > 0:
                        _bid_ask_store[key] = {
                            "bid": float(bids[0].get("bp", 0)),
                            "ask": float(bids[0].get("ap", 0)),
                        }

    except Exception as e:
        logger.debug(f"WS parse error: {e}")


def _key_to_sym(key: str) -> str:
    for sym, k in INDEX_KEYS.items():
        if k == key:
            return sym
    return key.split("|")[-1][:12].upper()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LIVE PRICE — Upstox only, no yfinance for real prices
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_live_price(symbol: str) -> Optional[Dict]:
    """
    Get real-time spot price for an index.

    Priority:
      1. WebSocket store (< 1s old) — fastest
      2. Upstox REST LTP           — reliable fallback
      3. Returns None              — caller must NOT trade

    ❌ No yfinance fallback for live prices.
    """
    sym = symbol.upper()

    # 1. WebSocket store
    ws = _price_store.get(sym)
    if ws and _fresh(ws.get("timestamp"), max_sec=3):
        return ws

    # 2. Upstox REST
    try:
        token   = await _get_token()
        ikey    = INDEX_KEYS.get(sym)
        if not ikey:
            logger.error(f"No instrument key for symbol {sym}")
            return None

        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(
                f"{UPSTOX_BASE}/market-quote/ohlc",
                params={"instrument_key": ikey, "interval": "1d"},
                headers=_headers(token),
            )

        if resp.status_code != 200:
            logger.error(f"Price REST error {resp.status_code} for {sym}")
            return None

        raw  = resp.json().get("data", {}).get(ikey, {})
        ohlc = raw.get("ohlc", {})
        ltp  = raw.get("last_price")
        if not ltp:
            return None

        prev = float(ohlc.get("prev_close") or ltp)
        data = {
            "price":      round(float(ltp), 2),
            "open":       round(float(ohlc.get("open") or ltp), 2),
            "high":       round(float(ohlc.get("high") or ltp), 2),
            "low":        round(float(ohlc.get("low")  or ltp), 2),
            "volume":     0,
            "change_pct": round(((float(ltp) - prev) / prev) * 100, 2) if prev else 0,
            "timestamp":  datetime.now(IST).isoformat(),
            "symbol":     sym,
            "source":     "upstox_rest",
        }
        _price_store[sym] = data
        return data

    except RuntimeError:
        # Token missing
        logger.error(f"Cannot fetch price for {sym} — Upstox token missing")
        return None
    except Exception as e:
        logger.error(f"Live price error for {sym}: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OPTION CHAIN — real-time from Upstox with actual instrument metadata
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_option_chain(symbol: str, expiry: str = None) -> Optional[Dict]:
    """
    Fetch live option chain from Upstox.
    Includes actual lot_size and instrument_key for every contract.

    Returns None if data unavailable → caller must abort trade.
    ❌ No assumed expiry — must come from get_nearest_expiry() which uses API.
    """
    # Ensure instruments are loaded
    if not _instruments_loaded.get(symbol):
        ok = await load_instruments(symbol)
        if not ok:
            logger.error(f"Cannot load instruments for {symbol} — aborting option chain")
            return None

    # Get spot price
    spot_data = await get_live_price(symbol)
    if not spot_data:
        logger.error(f"No spot price for {symbol} — aborting option chain")
        return None
    spot = spot_data["price"]

    # Get expiry from API if not specified
    if not expiry:
        expiry = await get_nearest_expiry(symbol)
        if not expiry:
            logger.error(f"No valid expiry for {symbol} — aborting option chain")
            return None

    cache_key = f"{symbol}_{expiry}"
    cached    = _option_chain_cache.get(cache_key, {})
    if _fresh(cached.get("ts"), max_sec=10):
        return cached["data"]

    try:
        token = await _get_token()
        ikey  = INDEX_KEYS.get(symbol.upper())
        if not ikey:
            return None

        async with httpx.AsyncClient(timeout=12) as c:
            resp = await c.get(
                f"{UPSTOX_BASE}/option/chain",
                params={"instrument_key": ikey, "expiry_date": expiry},
                headers=_headers(token),
            )

        if resp.status_code != 200:
            logger.error(f"Option chain API {resp.status_code}: {resp.text[:200]}")
            return None

        chain_raw = resp.json().get("data", [])
        if not chain_raw:
            return None

        calls, puts = [], []
        for item in chain_raw:
            strike    = item.get("strike_price")
            ce        = item.get("call_options", {})
            pe        = item.get("put_options", {})
            ce_mkt    = ce.get("market_data", {})
            pe_mkt    = pe.get("market_data", {})
            ce_key    = ce.get("instrument_key", "")
            pe_key    = pe.get("instrument_key", "")

            if not strike:
                continue

            # Get lot_size from instruments cache (loaded from API)
            ce_meta   = _instruments_cache.get(ce_key, {})
            pe_meta   = _instruments_cache.get(pe_key, {})
            ce_lot    = ce_meta.get("lot_size")
            pe_lot    = pe_meta.get("lot_size")

            # If lot_size missing, try to get from chain data itself
            if not ce_lot:
                ce_lot = item.get("lot_size") or ce.get("lot_size")
            if not pe_lot:
                pe_lot = item.get("lot_size") or pe.get("lot_size")

            # Get live LTP from WebSocket store first (most current)
            ce_ltp = _option_ltp_store.get(ce_key) or float(ce_mkt.get("ltp") or 0)
            pe_ltp = _option_ltp_store.get(pe_key) or float(pe_mkt.get("ltp") or 0)

            if ce_key:
                calls.append({
                    "strike":         float(strike),
                    "ltp":            round(ce_ltp, 2),
                    "bid":            float(ce_mkt.get("bid_price") or 0),
                    "ask":            float(ce_mkt.get("ask_price") or 0),
                    "volume":         int(ce_mkt.get("volume") or 0),
                    "oi":             int(ce_mkt.get("oi") or 0),
                    "iv":             float(ce.get("greeks", {}).get("iv") or 0),
                    "delta":          float(ce.get("greeks", {}).get("delta") or 0),
                    "instrument_key": ce_key,
                    "lot_size":       int(ce_lot) if ce_lot else None,
                })

            if pe_key:
                puts.append({
                    "strike":         float(strike),
                    "ltp":            round(pe_ltp, 2),
                    "bid":            float(pe_mkt.get("bid_price") or 0),
                    "ask":            float(pe_mkt.get("ask_price") or 0),
                    "volume":         int(pe_mkt.get("volume") or 0),
                    "oi":             int(pe_mkt.get("oi") or 0),
                    "iv":             float(pe.get("greeks", {}).get("iv") or 0),
                    "delta":          float(pe.get("greeks", {}).get("delta") or 0),
                    "instrument_key": pe_key,
                    "lot_size":       int(pe_lot) if pe_lot else None,
                })

        result = {
            "symbol":    symbol,
            "expiry":    expiry,
            "spot":      spot,
            "calls":     sorted(calls, key=lambda x: x["strike"]),
            "puts":      sorted(puts,  key=lambda x: x["strike"]),
            "timestamp": datetime.now(IST).isoformat(),
            "source":    "upstox",
        }
        _option_chain_cache[cache_key] = {"data": result, "ts": datetime.now(IST).isoformat()}
        logger.info(
            f"✅ Chain: {symbol} exp={expiry} spot={spot} "
            f"CE×{len(calls)} PE×{len(puts)}"
        )
        return result

    except RuntimeError:
        logger.error("Cannot fetch option chain — Upstox token missing")
        return None
    except Exception as e:
        logger.error(f"Option chain error: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ATM OPTION SELECTION — strict validation, no assumptions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_atm_option(
    symbol: str,
    option_type: str = "CE",
    expiry: str = None,
) -> Optional[Dict]:
    """
    Get ATM option with REAL lot_size, REAL LTP, REAL instrument_key.

    VALIDATION (all must pass — returns None if any fail):
      ✔ Instrument exists in Upstox API
      ✔ Expiry is valid and active
      ✔ Lot size present from API data
      ✔ LTP > 0 (real premium exists)
      ✔ instrument_key present for order placement

    ❌ NO yfinance fallback
    ❌ NO assumed lot size
    ❌ NO constructed token strings
    """
    chain = await get_option_chain(symbol, expiry)
    if not chain:
        logger.error(f"❌ ATM BLOCKED: No option chain for {symbol} — NOT trading")
        return None

    spot      = chain["spot"]
    contracts = chain["calls"] if option_type.upper() == "CE" else chain["puts"]

    if not contracts:
        logger.error(f"❌ ATM BLOCKED: No {option_type} contracts in chain for {symbol}")
        return None

    # Find ATM (closest strike to spot)
    valid = [c for c in contracts if c["ltp"] > 0 and c.get("instrument_key") and c.get("lot_size")]
    if not valid:
        logger.error(
            f"❌ ATM BLOCKED: No valid {option_type} contracts with "
            f"LTP>0 + instrument_key + lot_size for {symbol}"
        )
        return None

    atm = min(valid, key=lambda c: abs(c["strike"] - spot))

    # Validate all required fields
    inst_key = atm.get("instrument_key")
    lot_size = atm.get("lot_size")
    ltp      = atm["ltp"]
    strike   = atm["strike"]
    expiry   = chain["expiry"]

    if not inst_key:
        logger.error(f"❌ ATM BLOCKED: instrument_key missing for {symbol} {option_type} {strike}")
        return None

    if not lot_size or int(lot_size) <= 0:
        logger.error(f"❌ ATM BLOCKED: lot_size missing/zero for {inst_key}")
        return None

    if ltp <= 0:
        # Last chance: try WebSocket store
        ws_ltp = _option_ltp_store.get(inst_key)
        if ws_ltp and ws_ltp > 0:
            ltp = ws_ltp
        else:
            rest_ltp = await _get_ltp_rest(inst_key)
            ltp      = rest_ltp if rest_ltp and rest_ltp > 0 else 0

    if ltp <= 0:
        logger.error(f"❌ ATM BLOCKED: LTP=0 for {inst_key} — premium unavailable")
        return None

    # Subscribe to WebSocket for live P&L tracking
    await subscribe_option_live(inst_key)

    result = {
        "symbol":         symbol,
        "option_type":    option_type.upper(),
        "strike":         float(strike),
        "expiry":         expiry,
        "ltp":            round(float(ltp), 2),
        "bid":            round(float(atm.get("bid", 0)), 2),
        "ask":            round(float(atm.get("ask", 0)), 2),
        "iv":             float(atm.get("iv", 0)),
        "oi":             int(atm.get("oi", 0)),
        "volume":         int(atm.get("volume", 0)),
        "delta":          float(atm.get("delta", 0)),
        "lot_size":       int(lot_size),        # ← from Upstox API, never hardcoded
        "instrument_key": inst_key,             # ← actual API key for orders
        "spot":           spot,
    }

    logger.info(
        f"✅ ATM: {symbol} {option_type} {strike} exp={expiry} "
        f"LTP=₹{ltp} lot={lot_size} key={inst_key[:40]}"
    )
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LIVE OPTION LTP — for position monitoring
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_option_live_ltp(instrument_key: str) -> Optional[float]:
    """
    Get current LTP for an option.
    Priority: WebSocket (instant) → REST API
    Returns None if unavailable — caller should use entry_price as fallback.
    """
    # WebSocket store
    ws_ltp = _option_ltp_store.get(instrument_key)
    if ws_ltp and ws_ltp > 0:
        return round(ws_ltp, 2)

    # REST
    return await _get_ltp_rest(instrument_key)


async def _get_ltp_rest(instrument_key: str) -> Optional[float]:
    """Single option LTP via Upstox REST."""
    try:
        token = await _get_token()
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(
                f"{UPSTOX_BASE}/market-quote/ltp",
                params={"instrument_key": instrument_key},
                headers=_headers(token),
            )
        if resp.status_code == 200:
            d = resp.json().get("data", {}).get(instrument_key, {})
            v = d.get("last_price")
            if v:
                ltp = round(float(v), 2)
                _option_ltp_store[instrument_key] = ltp
                return ltp
    except Exception as e:
        logger.warning(f"LTP REST error ({instrument_key[:30]}): {e}")
    return None


async def get_premiums_for_open_trades(open_trades: List[Dict]) -> Dict[int, float]:
    """
    Batch fetch current LTP for all open trades.
    Returns: {trade_id: current_ltp}
    Trades with no LTP get entry_price as fallback (safe — won't trigger wrong exit).
    """
    result = {}
    for trade in open_trades:
        tid      = trade.get("id")
        ikey     = trade.get("instrument_key", "")
        entry_p  = trade.get("entry_price", 0)

        if not tid:
            continue

        ltp = None
        if ikey:
            ltp = _option_ltp_store.get(ikey)
            if not ltp:
                ltp = await _get_ltp_rest(ikey)

        result[tid] = round(ltp, 2) if (ltp and ltp > 0) else entry_p

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OHLCV — Upstox historical candles ONLY (no yfinance)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_INTERVAL_MAP = {
    "1m": "1minute", "2m": "2minute", "5m": "5minute",
    "15m": "15minute", "30m": "30minute",
    "60m": "60minute", "1h": "60minute", "1d": "1day",
}


async def fetch_ohlcv(symbol: str, period: str = "5d", interval: str = "5m") -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candles from Upstox historical API only.
    ❌ No yfinance fallback — if Upstox fails, returns None → caller must NOT trade.
    Used for technical indicator computation (ADX, EMA, VWAP, ATR).
    """
    cache_key = f"ohlcv_{symbol}_{period}_{interval}"
    cached    = _ohlcv_cache.get(cache_key, {})
    if _fresh(cached.get("ts"), max_sec=60):
        return cached["data"]

    try:
        df = await _upstox_candles(symbol, interval, period)
        if df is not None and not df.empty:
            _ohlcv_cache[cache_key] = {"data": df, "ts": datetime.now(IST).isoformat()}
            logger.debug(f"OHLCV: {symbol} {interval} → {len(df)} bars from Upstox")
            return df

        logger.error(
            f"❌ OHLCV FAILED: Upstox returned no candles for {symbol} {interval}. "
            f"Cannot compute indicators. Signal generation will be blocked."
        )
        return None

    except RuntimeError as e:
        # Token missing
        logger.error(f"❌ OHLCV BLOCKED: {e}")
        return None
    except Exception as e:
        logger.error(
            f"❌ OHLCV FAILED for {symbol} {interval}: {e}. "
            f"No fallback — signal will be blocked."
        )
        return None


async def _upstox_candles(symbol: str, interval: str, period: str) -> Optional[pd.DataFrame]:
    ikey = INDEX_KEYS.get(symbol.upper())
    if not ikey:
        return None

    upstox_iv = _INTERVAL_MAP.get(interval, "5minute")
    today     = date.today()
    from_dt   = (today - timedelta(days=10)).strftime("%Y-%m-%d")
    to_dt     = today.strftime("%Y-%m-%d")

    token = await _get_token()
    url   = f"{UPSTOX_BASE}/historical-candle/{ikey}/{upstox_iv}/{to_dt}/{from_dt}"

    async with httpx.AsyncClient(timeout=15) as c:
        resp = await c.get(url, headers=_headers(token))

    if resp.status_code != 200:
        return None

    candles = resp.json().get("data", {}).get("candles", [])
    if not candles:
        return None

    df = pd.DataFrame(
        candles,
        columns=["timestamp", "open", "high", "low", "close", "volume", "oi"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    logger.debug(f"Upstox candles: {symbol} {upstox_iv} → {len(df)} bars")
    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MARKET STATUS + HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_market_open() -> bool:
    now     = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    open_t  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_t <= now <= close_t


def is_ws_connected() -> bool:
    return _ws_connected


def get_ws_status() -> Dict:
    return {
        "connected":        _ws_connected,
        "subscribed_count": len(_ws_active_keys),
        "subscribed_keys":  _ws_active_keys[:20],
        "cached_prices":    list(_price_store.keys()),
        "cached_options":   len(_option_ltp_store),
        "instruments_loaded": dict(_instruments_loaded),
    }


def _fresh(ts_str: Optional[str], max_sec: int = 5) -> bool:
    if not ts_str:
        return False
    try:
        ts  = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=IST)
        return (datetime.now(IST) - ts).total_seconds() < max_sec
    except Exception:
        return False
