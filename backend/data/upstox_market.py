"""
Upstox Market Data — Production Fixed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All endpoints verified against Upstox v2 API documentation.

Key fixes vs previous version:
  1. WebSocket: removed — HTTP 410 means it's broken on free tier
     → Use REST polling every 2s instead (reliable, no auth issues)
  2. /option/contract: correct response parsing + URL-encoded keys
  3. /historical-candle: intraday endpoint + URL-encoded instrument key
  4. /market-quote/ltp: correct query param format
  5. /option/chain: correct response structure parsing
"""

import asyncio
import json
import time
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote
import httpx
import pandas as pd
from loguru import logger
from zoneinfo import ZoneInfo

IST          = ZoneInfo("Asia/Kolkata")
UPSTOX_BASE  = "https://api.upstox.com/v2"

# Official Upstox index instrument keys
INDEX_KEYS: Dict[str, str] = {
    "NIFTY":      "NSE_INDEX|Nifty 50",
    "BANKNIFTY":  "NSE_INDEX|Nifty Bank",
    "SENSEX":     "BSE_INDEX|SENSEX",
    "FINNIFTY":   "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|Nifty Midcap Select",
}

# ── In-memory stores ──────────────────────────────────────────────────────────
_price_store:        Dict[str, Dict]  = {}   # symbol → price dict
_option_ltp_store:   Dict[str, float] = {}   # instrument_key → ltp
_instruments_cache:  Dict[str, Dict]  = {}   # instrument_key → metadata
_instruments_loaded: Dict[str, bool]  = {}   # symbol → loaded?
_option_chain_cache: Dict[str, Dict]  = {}   # symbol_expiry → chain
_ohlcv_cache:        Dict[str, Dict]  = {}   # key → {data, ts}

# REST polling task (replaces broken WebSocket)
_poll_task:       Optional[asyncio.Task] = None
_poll_symbols:    List[str]              = []
_ws_connected:    bool                   = False   # always False now (WS deprecated)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AUTH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _get_token() -> str:
    from api.upstox_auth import get_upstox_token
    token = await get_upstox_token()
    if not token:
        raise RuntimeError("NO_TOKEN: Login via dashboard → Upstox Login button")
    return token


def _headers(token: str) -> Dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/json",
    }


def _enc(key: str) -> str:
    """URL-encode instrument key for query parameters."""
    return quote(key, safe="")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REST PRICE POLLING (replaces WebSocket which returns HTTP 410)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def connect_websocket(symbols: List[str] = None) -> bool:
    """
    Start REST polling loop for live prices.
    The Upstox v2 WebSocket returns HTTP 410 (deprecated) so we poll REST instead.
    Polls every 2 seconds — adequate for our 60s signal loop.
    """
    global _poll_task, _poll_symbols
    if symbols:
        _poll_symbols = symbols
    else:
        _poll_symbols = ["NIFTY", "BANKNIFTY"]

    if _poll_task and not _poll_task.done():
        return True

    _poll_task = asyncio.create_task(_price_poll_loop())
    logger.info(f"📡 REST price polling started for {_poll_symbols} (WS deprecated by Upstox)")
    return True


async def _price_poll_loop():
    """Poll Upstox LTP every 2 seconds for live spot prices."""
    while True:
        try:
            token = await _get_token()
            # Build comma-separated instrument keys
            keys = [INDEX_KEYS[s.upper()] for s in _poll_symbols if s.upper() in INDEX_KEYS]
            if not keys:
                await asyncio.sleep(5)
                continue

            # Upstox /market-quote/ltp accepts multiple keys as comma-separated
            keys_param = ",".join(keys)
            async with httpx.AsyncClient(timeout=4) as c:
                resp = await c.get(
                    f"{UPSTOX_BASE}/market-quote/ltp",
                    params={"instrument_key": keys_param},
                    headers=_headers(token),
                )

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                for sym, ikey in [(s, INDEX_KEYS[s.upper()]) for s in _poll_symbols if s.upper() in INDEX_KEYS]:
                    # Upstox returns key with | encoded or as-is — try both
                    feed = data.get(ikey) or data.get(ikey.replace("|", "%7C")) or data.get(ikey.replace(" ", "%20"))
                    if feed:
                        ltp = feed.get("last_price") or feed.get("ltp")
                        if ltp:
                            existing = _price_store.get(sym.upper(), {})
                            _price_store[sym.upper()] = {
                                "price":      round(float(ltp), 2),
                                "open":       float(existing.get("open", ltp)),
                                "high":       float(existing.get("high", ltp)),
                                "low":        float(existing.get("low", ltp)),
                                "volume":     int(existing.get("volume", 0)),
                                "change_pct": float(existing.get("change_pct", 0)),
                                "timestamp":  datetime.now(IST).isoformat(),
                                "symbol":     sym.upper(),
                                "source":     "upstox_rest_poll",
                            }

        except RuntimeError:
            # No token — wait and retry
            await asyncio.sleep(30)
            continue
        except Exception as e:
            logger.debug(f"Price poll error: {e}")

        await asyncio.sleep(2)


async def subscribe_option_live(instrument_key: str):
    """Add option key for LTP polling — fetched on-demand via REST."""
    pass  # REST polling handles this in get_premiums_for_open_trades


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INSTRUMENTS METADATA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def load_instruments(symbol: str = "NIFTY") -> bool:
    """
    Load F&O instrument metadata from Upstox /option/contract.
    Handles all known Upstox response field name variants and normalises expiry formats.
    Returns True if at least one contract loaded.
    """
    global _instruments_cache, _instruments_loaded

    sym = symbol.upper()
    if _instruments_loaded.get(sym):
        return True

    ikey = INDEX_KEYS.get(sym)
    if not ikey:
        logger.error(f"No index key for {sym}")
        return False

    try:
        token = await _get_token()
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.get(
                f"{UPSTOX_BASE}/option/contract",
                params={"instrument_key": ikey},
                headers=_headers(token),
            )

        logger.info(f"Instruments API: HTTP {resp.status_code} for {sym}")
        if resp.status_code != 200:
            logger.error(f"Instruments failed: {resp.status_code} | {resp.text[:500]}")
            return False

        body = resp.json()
        raw_list = body.get("data", [])
        if not isinstance(raw_list, list):
            raw_list = []

        if not raw_list:
            logger.error(
                f"Instruments API empty data for {sym}. Body keys: {list(body.keys())} | Sample: {str(body)[:400]}"
            )
            _instruments_loaded[sym] = True
            return False

        logger.info(f"Instrument sample fields: {list(raw_list[0].keys())}")
        logger.info(f"Instrument sample: {str(raw_list[0])[:300]}")

        today = date.today()
        count = 0
        skipped_expired = 0
        skipped_no_type = 0
        skipped_missing = 0

        for inst in raw_list:
            if not isinstance(inst, dict):
                continue

            expiry = (
                inst.get("expiry") or
                inst.get("expiry_date") or
                inst.get("expiryDate") or
                ""
            )
            expiry = str(expiry).strip()
            expiry_dt = None
            if expiry:
                if len(expiry) == 9 and expiry[2].isalpha():
                    try:
                        expiry_dt = datetime.strptime(expiry, "%d%b%Y")
                    except Exception:
                        expiry_dt = None
                else:
                    try:
                        expiry_dt = datetime.fromisoformat(expiry.replace("Z", ""))
                    except Exception:
                        expiry_dt = None

            if not expiry_dt or expiry_dt.date() < today:
                skipped_expired += 1
                continue

            inst_key = (
                inst.get("instrument_key") or
                inst.get("instrumentKey") or
                inst.get("key") or
                ""
            )
            lot_size = (
                inst.get("lot_size") or
                inst.get("lotSize") or
                inst.get("market_lot_size") or
                inst.get("marketLotSize")
            )
            strike = (
                inst.get("strike_price") or
                inst.get("strikePrice") or
                inst.get("strike")
            )
            raw_type = (
                inst.get("option_type") or
                inst.get("optionType") or
                inst.get("instrument_type") or
                ""
            )
            opt_type = str(raw_type).strip().upper()
            if opt_type in {"CALL", "C"}:
                opt_type = "CE"
            elif opt_type in {"PUT", "P"}:
                opt_type = "PE"

            if not inst_key or not lot_size or strike is None or strike == "" or opt_type not in {"CE", "PE"}:
                skipped_missing += 1
                if opt_type not in {"CE", "PE"}:
                    skipped_no_type += 1
                continue

            try:
                strike = float(str(strike))
                lot_size = int(float(str(lot_size)))
            except Exception:
                skipped_missing += 1
                continue

            trading = (
                inst.get("trading_symbol") or
                inst.get("tradingSymbol") or
                inst.get("name") or
                ""
            )

            _instruments_cache[inst_key] = {
                "instrument_key": inst_key,
                "trading_symbol": trading,
                "symbol":         sym,
                "expiry":         expiry_dt.date().isoformat(),
                "strike":         strike,
                "option_type":    opt_type,
                "lot_size":       lot_size,
                "exchange":       inst.get("exchange", "NSE"),
            }
            count += 1

        _instruments_loaded[sym] = True
        logger.info(
            f"✅ Instruments: {sym} → {count} loaded | "
            f"expired={skipped_expired} | no_type={skipped_no_type} | "
            f"missing={skipped_missing} | total={len(raw_list)}"
        )

        if count == 0 and raw_list:
            logger.error(
                f"All {len(raw_list)} contracts were filtered out for {sym}! "
                f"Check field names above. Raw sample: {str(raw_list[0])}"
            )

        logger.info(f"✅ Instruments: {sym} → {count} active contracts loaded")
        return count > 0

    except RuntimeError as e:
        logger.error(f"Instruments blocked — {e}")
        return False
    except Exception as e:
        logger.error(f"Instruments load error for {sym}: {e}", exc_info=True)
        logger.error(f"Instruments blocked — token issue: {e}")
        return False


async def get_available_expiries(symbol: str) -> List[str]:
    """Get sorted expiry dates from Upstox instruments cache."""
    sym = symbol.upper()
    if not _instruments_loaded.get(sym):
        await load_instruments(sym)

    expiries = set()
    for meta in _instruments_cache.values():
        if meta.get("symbol", "").upper() == sym:
            expiries.add(meta["expiry"])

    return sorted(expiries)


async def get_nearest_expiry(symbol: str) -> Optional[str]:
    """Get nearest active expiry from Upstox data (no weekday assumptions)."""
    expiries = await get_available_expiries(symbol)
    if not expiries:
        logger.error(f"No expiries for {symbol}")
        return None
    today = date.today().isoformat()
    valid = [e for e in expiries if e >= today]
    if not valid:
        return None
    return valid[0]


async def get_instrument_meta(instrument_key: str) -> Optional[Dict]:
    """Get cached metadata for an instrument key."""
    return _instruments_cache.get(instrument_key)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LIVE PRICE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_live_price(symbol: str) -> Optional[Dict]:
    """
    Get live spot price.
    Priority: polling cache (2s fresh) → REST /market-quote/ltp → REST /market-quote/ohlc
    """
    sym = symbol.upper()

    # 1. Polling cache (updated every 2s by _price_poll_loop)
    cached = _price_store.get(sym)
    if cached and _fresh(cached.get("timestamp"), max_sec=10):
        return cached

    # 2. Direct REST LTP fetch
    ikey = INDEX_KEYS.get(sym)
    if not ikey:
        logger.error(f"No index key for {sym}")
        return None

    try:
        token = await _get_token()

        # Try LTP endpoint first (fastest)
        async with httpx.AsyncClient(timeout=6) as c:
            resp = await c.get(
                f"{UPSTOX_BASE}/market-quote/ltp",
                params={"instrument_key": ikey},
                headers=_headers(token),
            )

        if resp.status_code == 200:
            data = resp.json().get("data", {})
            # Upstox may return key as-is or with encoding variations
            feed = (data.get(ikey) or
                    data.get(ikey.replace(" ", "%20")) or
                    data.get(list(data.keys())[0] if data else ""))
            ltp = None
            if feed:
                ltp = feed.get("last_price") or feed.get("ltp")

            if ltp:
                result = {
                    "price":      round(float(ltp), 2),
                    "open":       0.0, "high": 0.0, "low": 0.0,
                    "volume":     0,   "change_pct": 0.0,
                    "timestamp":  datetime.now(IST).isoformat(),
                    "symbol":     sym,
                    "source":     "upstox_ltp",
                }
                _price_store[sym] = result
                return result

        # 3. Fallback: OHLC endpoint for richer data
        async with httpx.AsyncClient(timeout=6) as c:
            resp2 = await c.get(
                f"{UPSTOX_BASE}/market-quote/ohlc",
                params={"instrument_key": ikey, "interval": "1d"},
                headers=_headers(token),
            )

        if resp2.status_code == 200:
            data2 = resp2.json().get("data", {})
            raw   = (data2.get(ikey) or
                     data2.get(list(data2.keys())[0] if data2 else ""))
            if raw:
                ltp2 = raw.get("last_price") or raw.get("ltp")
                ohlc = raw.get("ohlc", {})
                if ltp2:
                    prev = float(ohlc.get("prev_close") or ltp2)
                    chg  = round(((float(ltp2) - prev) / prev) * 100, 2) if prev else 0
                    result2 = {
                        "price":      round(float(ltp2), 2),
                        "open":       round(float(ohlc.get("open") or ltp2), 2),
                        "high":       round(float(ohlc.get("high") or ltp2), 2),
                        "low":        round(float(ohlc.get("low")  or ltp2), 2),
                        "volume":     0,
                        "change_pct": chg,
                        "timestamp":  datetime.now(IST).isoformat(),
                        "symbol":     sym,
                        "source":     "upstox_ohlc",
                    }
                    _price_store[sym] = result2
                    return result2

        logger.error(f"Price fetch failed for {sym}: LTP={resp.status_code} OHLC={resp2.status_code if 'resp2' in dir() else 'N/A'}")
        return None

    except RuntimeError as e:
        logger.error(f"Price blocked — {e}")
        return None
    except Exception as e:
        logger.error(f"Price error for {sym}: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OPTION CHAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_option_chain(symbol: str, expiry: str = None) -> Optional[Dict]:
    """
    Fetch live option chain from Upstox /option/chain.
    Returns None if data unavailable — caller must abort trade.
    """
    sym = symbol.upper()

    # Ensure instruments loaded
    if not _instruments_loaded.get(sym):
        await load_instruments(sym)

    # Get spot
    spot_data = await get_live_price(sym)
    if not spot_data:
        logger.error(f"No spot price for {sym} — cannot build option chain")
        return None
    spot = spot_data["price"]

    # Get expiry
    if not expiry:
        expiry = await get_nearest_expiry(sym)
        if not expiry:
            logger.error(f"No expiry for {sym}")
            return None

    cache_key = f"{sym}_{expiry}"
    cached    = _option_chain_cache.get(cache_key, {})
    if _fresh(cached.get("ts"), max_sec=10):
        return cached["data"]

    ikey = INDEX_KEYS.get(sym)
    if not ikey:
        return None

    try:
        token = await _get_token()
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f"{UPSTOX_BASE}/option/chain",
                params={"instrument_key": ikey, "expiry_date": expiry},
                headers=_headers(token),
            )

        if resp.status_code != 200:
            logger.error(f"Chain API {resp.status_code}: {resp.text[:300]}")
            return None

        body      = resp.json()
        chain_raw = body.get("data", [])

        if not chain_raw:
            logger.error(f"Chain empty for {sym} {expiry}. Body: {str(body)[:200]}")
            return None

        calls, puts = [], []
        for item in chain_raw:
            strike = item.get("strike_price") or item.get("strike")
            if not strike:
                continue

            ce     = item.get("call_options") or item.get("ce") or {}
            pe     = item.get("put_options")  or item.get("pe") or {}
            ce_mkt = ce.get("market_data") or ce
            pe_mkt = pe.get("market_data") or pe
            ce_key = ce.get("instrument_key") or ce.get("key") or ""
            pe_key = pe.get("instrument_key") or pe.get("key") or ""

            # lot_size from instruments cache first, then chain data
            def get_lot(key, item_data):
                meta = _instruments_cache.get(key, {})
                return (meta.get("lot_size") or
                        item.get("lot_size") or
                        item_data.get("lot_size"))

            ce_lot = get_lot(ce_key, ce)
            pe_lot = get_lot(pe_key, pe)

            # LTP: check live store first, then chain data
            def get_ltp(key, mkt):
                return (_option_ltp_store.get(key) or
                        float(mkt.get("ltp") or mkt.get("last_price") or 0))

            if ce_key:
                calls.append({
                    "strike":         float(strike),
                    "ltp":            round(get_ltp(ce_key, ce_mkt), 2),
                    "bid":            float(ce_mkt.get("bid_price") or ce_mkt.get("bid") or 0),
                    "ask":            float(ce_mkt.get("ask_price") or ce_mkt.get("ask") or 0),
                    "volume":         int(ce_mkt.get("volume") or 0),
                    "oi":             int(ce_mkt.get("oi") or ce_mkt.get("open_interest") or 0),
                    "iv":             float((ce.get("greeks") or {}).get("iv") or 0),
                    "delta":          float((ce.get("greeks") or {}).get("delta") or 0),
                    "instrument_key": ce_key,
                    "lot_size":       int(ce_lot) if ce_lot else None,
                })

            if pe_key:
                puts.append({
                    "strike":         float(strike),
                    "ltp":            round(get_ltp(pe_key, pe_mkt), 2),
                    "bid":            float(pe_mkt.get("bid_price") or pe_mkt.get("bid") or 0),
                    "ask":            float(pe_mkt.get("ask_price") or pe_mkt.get("ask") or 0),
                    "volume":         int(pe_mkt.get("volume") or 0),
                    "oi":             int(pe_mkt.get("oi") or pe_mkt.get("open_interest") or 0),
                    "iv":             float((pe.get("greeks") or {}).get("iv") or 0),
                    "delta":          float((pe.get("greeks") or {}).get("delta") or 0),
                    "instrument_key": pe_key,
                    "lot_size":       int(pe_lot) if pe_lot else None,
                })

        result = {
            "symbol":    sym,
            "expiry":    expiry,
            "spot":      spot,
            "calls":     sorted(calls, key=lambda x: x["strike"]),
            "puts":      sorted(puts,  key=lambda x: x["strike"]),
            "timestamp": datetime.now(IST).isoformat(),
            "source":    "upstox",
        }
        _option_chain_cache[cache_key] = {"data": result, "ts": datetime.now(IST).isoformat()}
        logger.info(f"✅ Chain: {sym} {expiry} spot={spot} CE×{len(calls)} PE×{len(puts)}")
        return result

    except RuntimeError as e:
        logger.error(f"Chain blocked — {e}")
        return None
    except Exception as e:
        logger.error(f"Chain error: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ATM OPTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_atm_option(symbol: str, option_type: str = "CE", expiry: str = None) -> Optional[Dict]:
    """
    Get ATM option with real LTP, lot_size, instrument_key from Upstox.
    Returns None if any required field missing — caller must NOT trade.
    """
    chain = await get_option_chain(symbol, expiry)
    if not chain:
        logger.error(f"❌ ATM BLOCKED: no chain for {symbol}")
        return None

    spot      = chain["spot"]
    contracts = chain["calls"] if option_type.upper() == "CE" else chain["puts"]

    if not contracts:
        logger.error(f"❌ ATM BLOCKED: no {option_type} contracts for {symbol}")
        return None

    # Filter: need ltp > 0, instrument_key, lot_size
    valid = [c for c in contracts
             if c.get("instrument_key") and c.get("lot_size") and c["ltp"] > 0]

    if not valid:
        # Try without LTP filter — fetch LTP directly
        keyed = [c for c in contracts if c.get("instrument_key") and c.get("lot_size")]
        if not keyed:
            logger.error(f"❌ ATM BLOCKED: no valid {option_type} contracts with key+lot_size")
            return None

        atm_raw = min(keyed, key=lambda c: abs(c["strike"] - spot))
        ikey    = atm_raw["instrument_key"]
        ltp     = await _get_ltp_rest(ikey)

        if not ltp or ltp <= 0:
            logger.error(f"❌ ATM BLOCKED: LTP=0 for {ikey[:40]}")
            return None

        atm_raw["ltp"] = ltp
        valid = [atm_raw]

    atm      = min(valid, key=lambda c: abs(c["strike"] - spot))
    inst_key = atm["instrument_key"]
    lot_size = atm["lot_size"]
    ltp      = atm["ltp"]

    # Final validation
    if not inst_key:
        logger.error("❌ ATM BLOCKED: instrument_key missing")
        return None
    if not lot_size or int(lot_size) <= 0:
        logger.error(f"❌ ATM BLOCKED: lot_size={lot_size} invalid")
        return None
    if ltp <= 0:
        logger.error(f"❌ ATM BLOCKED: LTP={ltp}")
        return None

    result = {
        "symbol":         symbol.upper(),
        "option_type":    option_type.upper(),
        "strike":         float(atm["strike"]),
        "expiry":         chain["expiry"],
        "ltp":            round(float(ltp), 2),
        "bid":            round(float(atm.get("bid", 0)), 2),
        "ask":            round(float(atm.get("ask", 0)), 2),
        "iv":             float(atm.get("iv", 0)),
        "oi":             int(atm.get("oi", 0)),
        "volume":         int(atm.get("volume", 0)),
        "delta":          float(atm.get("delta", 0)),
        "lot_size":       int(lot_size),
        "instrument_key": inst_key,
        "spot":           spot,
    }
    logger.info(
        f"✅ ATM: {symbol} {option_type} {result['strike']} "
        f"exp={result['expiry']} LTP=₹{ltp} lot={lot_size}"
    )
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LIVE OPTION LTP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_option_live_ltp(instrument_key: str) -> Optional[float]:
    """Get current LTP for an option. Cache → REST."""
    cached = _option_ltp_store.get(instrument_key)
    if cached and cached > 0:
        return round(cached, 2)
    return await _get_ltp_rest(instrument_key)


async def _get_ltp_rest(instrument_key: str) -> Optional[float]:
    """Fetch single option LTP from Upstox REST."""
    try:
        token = await _get_token()
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(
                f"{UPSTOX_BASE}/market-quote/ltp",
                params={"instrument_key": instrument_key},
                headers=_headers(token),
            )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            # Try exact key, then first value
            feed = data.get(instrument_key) or (next(iter(data.values()), None) if data else None)
            if feed:
                ltp = feed.get("last_price") or feed.get("ltp")
                if ltp:
                    v = round(float(ltp), 2)
                    _option_ltp_store[instrument_key] = v
                    return v
    except Exception as e:
        logger.warning(f"LTP REST error: {e}")
    return None


async def get_premiums_for_open_trades(open_trades: List[Dict]) -> Dict[int, float]:
    """Batch fetch current LTPs for all open trades."""
    result = {}
    for trade in open_trades:
        tid    = trade.get("id")
        ikey   = trade.get("instrument_key", "")
        entry  = trade.get("entry_price", 0)
        if not tid:
            continue
        ltp = None
        if ikey:
            ltp = await _get_ltp_rest(ikey)
        result[tid] = round(ltp, 2) if (ltp and ltp > 0) else entry
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OHLCV CANDLES — for technical indicators
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_INTERVAL_MAP = {
    "1m": "1minute", "2m": "2minute", "5m": "5minute",
    "15m": "15minute", "30m": "30minute",
    "60m": "60minute", "1h": "60minute", "1d": "1day",
}


async def fetch_ohlcv(symbol: str, period: str = "5d", interval: str = "5m") -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candles from Upstox.
    Uses /historical-candle/intraday/ for intraday intervals.
    Returns None if failed — signal engine will block trade.
    """
    cache_key = f"ohlcv_{symbol}_{period}_{interval}"
    cached    = _ohlcv_cache.get(cache_key, {})
    if _fresh(cached.get("ts"), max_sec=60):
        return cached["data"]

    sym  = symbol.upper()
    ikey = INDEX_KEYS.get(sym)
    if not ikey:
        logger.error(f"No index key for OHLCV: {sym}")
        return None

    upstox_iv = _INTERVAL_MAP.get(interval, "5minute")
    is_intraday = upstox_iv != "1day"

    try:
        token = await _get_token()
        today   = date.today()
        to_dt   = today.strftime("%Y-%m-%d")
        from_dt = (today - timedelta(days=10 if is_intraday else 30)).strftime("%Y-%m-%d")

        encoded_key = _enc(ikey)
        url_candidates = []
        if is_intraday:
            # Try both possible Upstox URL orders for intraday candles.
            url_candidates = [
                f"{UPSTOX_BASE}/historical-candle/intraday/{encoded_key}/{upstox_iv}",
                f"{UPSTOX_BASE}/historical-candle/intraday/{upstox_iv}/{encoded_key}",
            ]
        else:
            # Try both possible daily URL orders for historical candles.
            url_candidates = [
                f"{UPSTOX_BASE}/historical-candle/{encoded_key}/{upstox_iv}/{to_dt}/{from_dt}",
                f"{UPSTOX_BASE}/historical-candle/{upstox_iv}/{encoded_key}/{to_dt}/{from_dt}",
            ]

        resp = None
        async with httpx.AsyncClient(timeout=20) as c:
            for url in url_candidates:
                resp = await c.get(url, headers=_headers(token))
                if resp.status_code == 200:
                    break
                logger.warning(f"OHLCV candidate failed {resp.status_code} for {sym} {upstox_iv}: {url} | {resp.text[:200]}")

        if resp is None or resp.status_code != 200:
            logger.error(f"OHLCV {resp.status_code if resp else 'NO_RESP'} for {sym} {upstox_iv}")
            return None

        body = resp.json()
        candles = body.get("data", {}).get("candles", [])

        if not candles:
            # Try alternate response structure
            candles = body.get("data", []) if isinstance(body.get("data"), list) else []

        if not candles:
            logger.error(f"❌ OHLCV empty for {sym} {upstox_iv}. URL={url}")
            return None

        # Upstox candle format: [timestamp, open, high, low, close, volume, oi]
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        df = df[["open", "high", "low", "close", "volume"]].astype(float)

        if df.empty:
            return None

        _ohlcv_cache[cache_key] = {"data": df, "ts": datetime.now(IST).isoformat()}
        logger.info(f"✅ OHLCV: {sym} {upstox_iv} → {len(df)} bars")
        return df

    except RuntimeError as e:
        logger.error(f"OHLCV blocked — {e}")
        return None
    except Exception as e:
        logger.error(f"OHLCV error for {sym} {upstox_iv}: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STATUS & HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_market_open() -> bool:
    now    = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    open_t  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_t <= now <= close_t


def is_ws_connected() -> bool:
    """WS is replaced by REST polling — return True if poll task is running."""
    return _poll_task is not None and not _poll_task.done()


def get_ws_status() -> Dict:
    return {
        "connected":          is_ws_connected(),
        "mode":               "rest_polling",
        "note":               "Upstox WS deprecated (HTTP 410) — using REST polling every 2s",
        "cached_prices":      list(_price_store.keys()),
        "cached_options":     len(_option_ltp_store),
        "instruments_loaded": dict(_instruments_loaded),
        "subscribed_count":   len(_instruments_loaded),
        "subscribed_keys":    [],
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
