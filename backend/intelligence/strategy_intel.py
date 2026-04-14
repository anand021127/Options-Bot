"""
Strategy Intelligence — v3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Per-strategy performance tracking and adaptive weight adjustment.

Strategies tracked:
  - BREAKOUT:  confirmed 2-candle breakout above/below level
  - PULLBACK:  pullback to EMA20 in trending market
  - VWAP:      VWAP bounce/rejection
  - RETEST:    retest of broken S/R level
  - BTST:      overnight carry strategy

Per-strategy metrics:
  - Trade count, wins, losses
  - Win rate, avg P&L, best/worst trade
  - Score weight multiplier (auto-adjusted)

Weight adjustment logic:
  - Win rate > 60% over 10+ trades → increase contribution weight
  - Win rate < 40% over 10+ trades → reduce contribution weight
  - Disable if win rate < 30% over 15+ trades
"""

import json
import aiosqlite
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


DB_PATH = "trading_bot.db"

# Strategy types
class StrategyType:
    BREAKOUT = "BREAKOUT"
    PULLBACK = "PULLBACK"
    VWAP     = "VWAP"
    RETEST   = "RETEST"
    BTST     = "BTST"
    UNKNOWN  = "UNKNOWN"


def classify_trade_strategy(signal: Dict) -> str:
    """
    Classify a trade's entry strategy from signal data.
    Used at trade entry time.
    """
    if not signal:
        return StrategyType.UNKNOWN

    reasons = " ".join(signal.get("reasons", [])).upper()
    ind     = signal.get("indicators", {})

    if signal.get("btst_trade"):
        return StrategyType.BTST
    if ind.get("conf_breakout") or "BREAKOUT" in reasons:
        return StrategyType.BREAKOUT
    if ind.get("vwap_bounce") or "VWAP" in reasons:
        return StrategyType.VWAP
    if ind.get("pullback") or "PULLBACK" in reasons:
        return StrategyType.PULLBACK
    if ind.get("retest") or "RETEST" in reasons:
        return StrategyType.RETEST
    return StrategyType.UNKNOWN


# ─── DB helpers ───────────────────────────────────────────────────────────────

async def _ensure_strategy_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS strategy_performance (
                strategy        TEXT PRIMARY KEY,
                trades          INTEGER DEFAULT 0,
                wins            INTEGER DEFAULT 0,
                losses          INTEGER DEFAULT 0,
                total_pnl       REAL DEFAULT 0,
                best_trade      REAL DEFAULT 0,
                worst_trade     REAL DEFAULT 0,
                weight_mult     REAL DEFAULT 1.0,
                enabled         INTEGER DEFAULT 1,
                last_updated    TEXT
            )
        """)
        for strat in [StrategyType.BREAKOUT, StrategyType.PULLBACK,
                      StrategyType.VWAP, StrategyType.RETEST, StrategyType.BTST]:
            await db.execute("""
                INSERT OR IGNORE INTO strategy_performance (strategy, last_updated)
                VALUES (?, ?)
            """, (strat, datetime.now().isoformat()))
        await db.commit()


async def record_strategy_result(strategy: str, pnl: float):
    """Record trade result for strategy performance tracking."""
    await _ensure_strategy_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur  = await db.execute("SELECT * FROM strategy_performance WHERE strategy=?", (strategy,))
        row  = await cur.fetchone()

        if not row:
            return

        trades  = row["trades"] + 1
        wins    = row["wins"]  + (1 if pnl > 0 else 0)
        losses  = row["losses"] + (1 if pnl < 0 else 0)
        total   = row["total_pnl"] + pnl
        best    = max(row["best_trade"], pnl)
        worst   = min(row["worst_trade"], pnl)

        # Adaptive weight calculation
        win_rate   = wins / max(trades, 1) * 100
        weight_mult = _calculate_weight(win_rate, trades, row["weight_mult"])
        enabled    = 1 if win_rate >= 30 or trades < 15 else 0  # disable if consistently bad

        await db.execute("""
            UPDATE strategy_performance SET
                trades=?, wins=?, losses=?, total_pnl=?,
                best_trade=?, worst_trade=?, weight_mult=?,
                enabled=?, last_updated=?
            WHERE strategy=?
        """, (trades, wins, losses, total, best, worst, weight_mult,
              enabled, datetime.now().isoformat(), strategy))
        await db.commit()

        logger.info(
            f"📊 Strategy [{strategy}] | WR={win_rate:.0f}% ({wins}/{trades}) | "
            f"Weight={weight_mult:.2f} | {'✅ ENABLED' if enabled else '❌ DISABLED'}"
        )


def _calculate_weight(win_rate: float, trades: int, current_weight: float) -> float:
    """
    Adaptive weight multiplier for scoring engine.
    More trades = more confidence in the adjustment.
    """
    if trades < 10:
        return current_weight   # Not enough data yet

    if win_rate >= 65:
        target = 1.3            # High performer: +30% weight
    elif win_rate >= 55:
        target = 1.1            # Above average: +10%
    elif win_rate >= 45:
        target = 1.0            # Average: neutral
    elif win_rate >= 35:
        target = 0.7            # Below average: -30%
    else:
        target = 0.4            # Poor: -60%

    # Smooth adjustment (don't jump immediately)
    new_weight = current_weight * 0.7 + target * 0.3
    return round(max(0.2, min(1.5, new_weight)), 2)


async def get_strategy_performance() -> List[Dict]:
    """Return all strategy performance records."""
    await _ensure_strategy_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur  = await db.execute("SELECT * FROM strategy_performance ORDER BY trades DESC")
        rows = await cur.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["win_rate"] = round(d["wins"] / max(d["trades"], 1) * 100, 1)
            d["avg_pnl"]  = round(d["total_pnl"] / max(d["trades"], 1), 2)
            results.append(d)
        return results


async def get_strategy_weights() -> Dict[str, float]:
    """Get current weight multipliers for all strategies."""
    await _ensure_strategy_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur  = await db.execute("SELECT strategy, weight_mult, enabled FROM strategy_performance")
        rows = await cur.fetchall()
        return {
            r["strategy"]: r["weight_mult"] if r["enabled"] else 0.0
            for r in rows
        }


async def is_strategy_enabled(strategy: str) -> bool:
    """Check if a strategy is enabled (not auto-disabled)."""
    await _ensure_strategy_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT enabled FROM strategy_performance WHERE strategy=?", (strategy,)
        )
        row = await cur.fetchone()
        return bool(row[0]) if row else True
