"""
UPGRADED Technical Indicators — v2
New additions over v1:
  - ADX (trend strength / sideways filter)
  - ATR (volatility-based SL sizing)
  - IV Rank proxy (HV-based, no paid data needed)
  - VWAP bounce detection (high-probability entry)
  - Confirmed breakout (2-candle confirmation, reduces fake breakouts)
  - Pullback-in-trend entry
  - Candle quality filter (fake spike rejection)
  - Volume trend analysis
  - Option strike type selector (ATM vs slight ITM)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from loguru import logger


# ─── Moving Averages ──────────────────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


# ─── ATR ─────────────────────────────────────────────────────────────────────

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range — volatility measure for dynamic SL."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


# ─── ADX ─────────────────────────────────────────────────────────────────────

def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Average Directional Index.
    ADX > 25  → trending market → trade allowed
    ADX < 20  → sideways/choppy → SKIP
    Returns df copy with adx, plus_di, minus_di columns.
    """
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)

    up_move   = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm  = pd.Series(np.where((up_move > down_move)   & (up_move > 0),   up_move,   0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

    tr_s       = tr.ewm(span=period, adjust=False).mean()
    plus_dm_s  = plus_dm.ewm(span=period, adjust=False).mean()
    minus_dm_s = minus_dm.ewm(span=period, adjust=False).mean()

    plus_di  = 100 * plus_dm_s  / tr_s.replace(0, np.nan)
    minus_di = 100 * minus_dm_s / tr_s.replace(0, np.nan)

    dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_line = dx.ewm(span=period, adjust=False).mean()

    out = df.copy()
    out["adx"]      = adx_line.round(2)
    out["plus_di"]  = plus_di.round(2)
    out["minus_di"] = minus_di.round(2)
    return out


def market_regime(df: pd.DataFrame) -> str:
    """
    Classify market as TRENDING, SIDEWAYS, VOLATILE, or WEAK_TREND.
    This is the primary market condition filter.

    Thresholds calibrated for Indian indices (NIFTY/BANKNIFTY):
      - ATR > 2.5% is truly volatile (1.5% is normal intraday for Nifty)
      - ADX < 15  is genuinely sideways (< 20 was too aggressive)
    """
    if len(df) < 20:
        return "UNKNOWN"

    df_adx     = adx(df.tail(60))
    latest_adx = float(df_adx["adx"].iloc[-1]) if not df_adx["adx"].isna().iloc[-1] else 18.0
    atr_val    = float(atr(df.tail(60)).iloc[-1])
    price      = float(df["close"].iloc[-1])
    atr_pct    = (atr_val / price) * 100

    if atr_pct > 2.5:
        return "VOLATILE"
    elif latest_adx >= 25:
        return "TRENDING"
    elif latest_adx >= 20:
        return "WEAK_TREND"
    elif latest_adx < 15:
        return "SIDEWAYS"
    else:
        return "WEAK_TREND"


# ─── VWAP ────────────────────────────────────────────────────────────────────

def vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP with daily reset."""
    tp  = (df["high"] + df["low"] + df["close"]) / 3
    vol = df["volume"].replace(0, np.nan)
    return (tp * vol).cumsum() / vol.cumsum()


def vwap_bounce(df: pd.DataFrame, tol_pct: float = 0.002) -> Optional[str]:
    """
    VWAP bounce / rejection setup — high-probability entry pattern.
    BOUNCE_BULL: price dipped to VWAP and reclaimed it (buy CE)
    BOUNCE_BEAR: price popped to VWAP and got rejected (buy PE)
    """
    if "vwap" not in df.columns or len(df) < 8:
        return None

    recent    = df.tail(8)
    vwap_now  = float(recent["vwap"].iloc[-1])
    close_now = float(recent["close"].iloc[-1])

    if np.isnan(vwap_now):
        return None

    touched = any(
        abs(float(recent["low"].iloc[i])  - vwap_now) / vwap_now < tol_pct or
        abs(float(recent["high"].iloc[i]) - vwap_now) / vwap_now < tol_pct
        for i in range(-4, 0)
    )

    if not touched:
        return None

    low_now  = float(recent["low"].iloc[-1])
    high_now = float(recent["high"].iloc[-1])

    if low_now <= vwap_now * (1 + tol_pct) and close_now > vwap_now:
        return "BOUNCE_BULL"
    if high_now >= vwap_now * (1 - tol_pct) and close_now < vwap_now:
        return "BOUNCE_BEAR"
    return None


# ─── IV Rank Proxy ────────────────────────────────────────────────────────────

def historical_volatility(df: pd.DataFrame, period: int = 20) -> float:
    if len(df) < period + 1:
        return 0.0
    log_ret  = np.log(df["close"] / df["close"].shift(1)).dropna()
    hv_daily = float(log_ret.rolling(period).std().iloc[-1])
    return round(hv_daily * np.sqrt(252 * 75) * 100, 2)


def iv_rank_proxy(df: pd.DataFrame) -> Dict:
    """
    IV Rank Proxy using rolling Historical Volatility.
    IVR < 30  → Low IV   → BEST time to buy options (cheap)
    IVR 30-60 → Normal   → OK
    IVR 60-80 → High IV  → Caution (premium expensive)
    IVR > 80  → Extreme  → AVOID buying — premium will crush

    Requires at least 80 bars for reliable rolling HV.
    With insufficient data → returns NORMAL_IV (don't block trades on noise).
    """
    if len(df) < 80:
        return {"hv_current": 0, "hv_low": 0, "hv_high": 0, "iv_rank": 40, "regime": "NORMAL_IV"}

    log_ret    = np.log(df["close"] / df["close"].shift(1)).dropna()
    rolling_hv = (log_ret.rolling(20).std() * np.sqrt(252 * 75) * 100).dropna()

    if len(rolling_hv) < 20:
        return {"hv_current": 0, "hv_low": 0, "hv_high": 0, "iv_rank": 40, "regime": "NORMAL_IV"}

    hv_current = round(float(rolling_hv.iloc[-1]), 2)
    hv_low     = round(float(rolling_hv.min()), 2)
    hv_high    = round(float(rolling_hv.max()), 2)
    iv_rank    = round(((hv_current - hv_low) / max(hv_high - hv_low, 0.01)) * 100, 1)

    if iv_rank < 30:
        regime = "LOW_IV"
    elif iv_rank < 60:
        regime = "NORMAL_IV"
    elif iv_rank < 80:
        regime = "HIGH_IV"
    else:
        regime = "EXTREME_IV"

    return {"hv_current": hv_current, "hv_low": hv_low, "hv_high": hv_high,
            "iv_rank": iv_rank, "regime": regime}


# ─── Support & Resistance ─────────────────────────────────────────────────────

def find_pivot_points(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    highs, lows = df["high"], df["low"]
    pivot_highs, pivot_lows = [], []

    for i in range(window, len(df) - window):
        is_ph = all(highs.iloc[i] >= highs.iloc[i-j] and highs.iloc[i] >= highs.iloc[i+j]
                    for j in range(1, window + 1))
        is_pl = all(lows.iloc[i] <= lows.iloc[i-j] and lows.iloc[i] <= lows.iloc[i+j]
                    for j in range(1, window + 1))
        pivot_highs.append(highs.iloc[i] if is_ph else np.nan)
        pivot_lows.append(lows.iloc[i]   if is_pl else np.nan)

    pad = [np.nan] * window
    out = df.copy()
    out["pivot_high"] = pad + pivot_highs + pad
    out["pivot_low"]  = pad + pivot_lows  + pad
    return out


def get_sr_levels(df: pd.DataFrame, n_levels: int = 3) -> Dict[str, List[float]]:
    df_p        = find_pivot_points(df)
    resistances = df_p["pivot_high"].dropna().tail(20).tolist()
    supports    = df_p["pivot_low"].dropna().tail(20).tolist()

    def cluster(levels: List[float], tol_pct: float = 0.003) -> List[float]:
        if not levels:
            return []
        levels   = sorted(set(levels))
        clusters = [[levels[0]]]
        for lvl in levels[1:]:
            if abs(lvl - clusters[-1][-1]) / clusters[-1][-1] < tol_pct:
                clusters[-1].append(lvl)
            else:
                clusters.append([lvl])
        return [round(np.mean(c), 2) for c in clusters]

    return {
        "support":    sorted(cluster(supports), reverse=True)[:n_levels],
        "resistance": sorted(cluster(resistances))[:n_levels],
    }


# ─── Market Structure ─────────────────────────────────────────────────────────

def market_structure(df: pd.DataFrame) -> str:
    df_p        = find_pivot_points(df, window=3)
    pivot_highs = df_p["pivot_high"].dropna().values[-4:]
    pivot_lows  = df_p["pivot_low"].dropna().values[-4:]

    if len(pivot_highs) < 2 or len(pivot_lows) < 2:
        return "SIDEWAYS"

    hh = pivot_highs[-1] > pivot_highs[-2]
    hl = pivot_lows[-1]  > pivot_lows[-2]
    lh = pivot_highs[-1] < pivot_highs[-2]
    ll = pivot_lows[-1]  < pivot_lows[-2]

    if hh and hl:   return "BULLISH"
    elif lh and ll: return "BEARISH"
    else:           return "SIDEWAYS"


# ─── Entry Pattern Detection ──────────────────────────────────────────────────

def detect_breakout(df: pd.DataFrame, lookback: int = 20) -> Optional[str]:
    recent        = df.tail(lookback + 5)
    sr            = get_sr_levels(recent)
    current_close = float(df["close"].iloc[-1])
    prev_close    = float(df["close"].iloc[-2])

    for res in sr["resistance"]:
        if prev_close < res and current_close > res * 1.001:
            return "BREAKOUT_UP"
    for sup in sr["support"]:
        if prev_close > sup and current_close < sup * 0.999:
            return "BREAKOUT_DOWN"
    return None


def detect_confirmed_breakout(df: pd.DataFrame) -> Optional[str]:
    """
    2-candle confirmed breakout — reduces fake breakout entries.
    Requires: candle N-1 broke level AND candle N confirms beyond it.
    """
    if len(df) < 5:
        return None

    sr = get_sr_levels(df.tail(40))
    c1 = float(df["close"].iloc[-3])
    c2 = float(df["close"].iloc[-2])
    c3 = float(df["close"].iloc[-1])

    for res in sr["resistance"]:
        if c1 < res and c2 > res * 1.001 and c3 > res * 1.001:
            return "CONFIRMED_BREAKOUT_UP"
    for sup in sr["support"]:
        if c1 > sup and c2 < sup * 0.999 and c3 < sup * 0.999:
            return "CONFIRMED_BREAKOUT_DOWN"
    return None


def detect_retest(df: pd.DataFrame) -> Optional[str]:
    sr      = get_sr_levels(df)
    current = float(df["close"].iloc[-1])
    for res in sr["resistance"]:
        if abs(current - res) / res < 0.005:
            return "RETEST_SUPPORT"
    for sup in sr["support"]:
        if abs(current - sup) / sup < 0.005:
            return "RETEST_RESISTANCE"
    return None


def detect_pullback_entry(df: pd.DataFrame) -> Optional[str]:
    """
    Pullback-to-EMA20 in a trending market.
    Bullish: trending up, price pulls back to EMA20 and reclaims.
    Bearish: trending down, price pops to EMA20 and gets rejected.
    """
    if "ema20" not in df.columns or len(df) < 10:
        return None

    struct    = market_structure(df)
    recent    = df.tail(6)
    ema20_now = float(recent["ema20"].iloc[-1])
    close_now = float(recent["close"].iloc[-1])
    tol       = ema20_now * 0.002

    if struct == "BULLISH":
        touched = any(abs(float(recent["low"].iloc[i]) - ema20_now) < tol for i in range(-4, 0))
        if touched and close_now > ema20_now:
            return "PULLBACK_BULL"
    elif struct == "BEARISH":
        touched = any(abs(float(recent["high"].iloc[i]) - ema20_now) < tol for i in range(-4, 0))
        if touched and close_now < ema20_now:
            return "PULLBACK_BEAR"
    return None


# ─── Quality Filters ──────────────────────────────────────────────────────────

def is_fake_spike(df: pd.DataFrame) -> bool:
    """Detect wick-dominated candle (possible manipulation). Ratio 4x = very extreme only."""
    c         = df.iloc[-1]
    body      = abs(float(c["close"]) - float(c["open"]))
    wick_up   = float(c["high"])  - max(float(c["close"]), float(c["open"]))
    wick_down = min(float(c["close"]), float(c["open"])) - float(c["low"])
    if body < 0.01:
        return False   # doji candles are valid — don't block
    return (wick_up + wick_down) > (body * 4)


def is_low_volume_period(df: pd.DataFrame) -> bool:
    if "volume" not in df.columns or df["volume"].sum() == 0:
        return False   # no volume data available — don't block
    avg_vol  = float(df["volume"].rolling(30).mean().iloc[-1])
    if avg_vol <= 0:
        return False
    curr_vol = float(df["volume"].iloc[-1])
    return curr_vol < avg_vol * 0.3   # only block truly dead volume (30% threshold)


# ─── Volume ───────────────────────────────────────────────────────────────────

def volume_confirmation(df: pd.DataFrame) -> bool:
    if "volume" not in df.columns or df["volume"].sum() == 0:
        return True
    avg_vol  = float(df["volume"].rolling(20).mean().iloc[-1])
    curr_vol = float(df["volume"].iloc[-1])
    return curr_vol > avg_vol * 1.2


def volume_trend(df: pd.DataFrame) -> str:
    if "volume" not in df.columns:
        return "UNKNOWN"
    recent = df["volume"].tail(5)
    slope  = (float(recent.iloc[-1]) - float(recent.iloc[0])) / max(float(recent.mean()), 1)
    if slope > 0.1:   return "RISING"
    elif slope < -0.1: return "FALLING"
    return "FLAT"


# ─── RSI ─────────────────────────────────────────────────────────────────────

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ─── ATR-Based SL/Target ──────────────────────────────────────────────────────

def atr_sl_target(df: pd.DataFrame, option_ltp: float,
                  atr_mult: float = 1.5, rr: float = 2.0) -> Tuple[float, float, float, float]:
    """
    Dynamic ATR-based SL/Target for options.
    Returns (sl_price, target_price, sl_pct, target_pct)
    sl_pct is clamped to [20%, 45%] — realistic for options.
    """
    atr_val    = float(atr(df.tail(30)).iloc[-1])
    price      = float(df["close"].iloc[-1])
    atr_pct    = (atr_val / price) * 100
    sl_pct     = round(min(max(atr_pct * atr_mult * 3, 20.0), 45.0), 1)
    tgt_pct    = round(sl_pct * rr, 1)
    sl_price   = round(option_ltp * (1 - sl_pct / 100), 2)
    tgt_price  = round(option_ltp * (1 + tgt_pct / 100), 2)
    return sl_price, tgt_price, sl_pct, tgt_pct


# ─── Option Strike Selector ───────────────────────────────────────────────────

def select_strike_type(iv_rank_val: float, regime: str) -> str:
    """
    High IV → slight ITM (more intrinsic, less vega risk premium to pay).
    Low IV  → ATM is fine (cheaper, better gamma leverage).
    """
    if iv_rank_val > 60 or regime == "VOLATILE":
        return "SLIGHT_ITM"
    return "ATM"


# ─── Full Indicator Suite ─────────────────────────────────────────────────────

def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema9"]    = ema(df["close"], 9)
    df["ema20"]   = ema(df["close"], 20)
    df["ema50"]   = ema(df["close"], 50)
    df["vwap"]    = vwap(df)
    df["rsi"]     = rsi(df["close"], 14)
    df["atr"]     = atr(df, 14)
    if "volume" in df.columns:
        df["vol_avg"] = df["volume"].rolling(20).mean()
    return df


def get_indicator_snapshot(df: pd.DataFrame) -> Dict:
    if df is None or df.empty or len(df) < 50:
        return {}

    df      = compute_all_indicators(df)
    df_adx  = adx(df.tail(60))
    latest  = df.iloc[-1]
    sr      = get_sr_levels(df)
    struct  = market_structure(df)
    regime  = market_regime(df)
    iv_data = iv_rank_proxy(df)

    return {
        "close":         round(float(latest["close"]), 2),
        "ema9":          round(float(latest["ema9"]), 2),
        "ema20":         round(float(latest["ema20"]), 2),
        "ema50":         round(float(latest["ema50"]), 2),
        "vwap":          round(float(latest["vwap"]), 2),
        "rsi":           round(float(latest["rsi"]), 1),
        "atr":           round(float(latest["atr"]), 2),
        "adx":           round(float(df_adx["adx"].iloc[-1]), 1),
        "plus_di":       round(float(df_adx["plus_di"].iloc[-1]), 1),
        "minus_di":      round(float(df_adx["minus_di"].iloc[-1]), 1),
        "structure":     struct,
        "regime":        regime,
        "breakout":      detect_breakout(df),
        "conf_breakout": detect_confirmed_breakout(df),
        "pullback":      detect_pullback_entry(df),
        "vwap_bounce":   vwap_bounce(df),
        "sr":            sr,
        "support":       sr["support"],
        "resistance":    sr["resistance"],
        "vol_ok":        volume_confirmation(df),
        "vol_trend":     volume_trend(df),
        "fake_spike":    is_fake_spike(df),
        "iv_rank":       iv_data,
    }
