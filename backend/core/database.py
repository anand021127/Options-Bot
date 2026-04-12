"""
Database — v3 Fixed
Adds: upstox_access_token storage, capital/symbol/mode persistence for auto-restart
"""

import json
import aiosqlite
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from loguru import logger

DB_PATH = "trading_bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # ── Trades ───────────────────────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol           TEXT NOT NULL,
                option_type      TEXT NOT NULL,
                strike           REAL NOT NULL,
                expiry           TEXT NOT NULL,
                entry_price      REAL NOT NULL,
                exit_price       REAL,
                fill_price       REAL,
                quantity         INTEGER NOT NULL,
                lots             INTEGER DEFAULT 1,
                lot_size         INTEGER DEFAULT 50,
                sl_price         REAL NOT NULL,
                target_price     REAL NOT NULL,
                partial_target   REAL DEFAULT 0,
                partial_booked   INTEGER DEFAULT 0,
                status           TEXT DEFAULT 'OPEN',
                pnl              REAL DEFAULT 0,
                entry_time       TEXT NOT NULL,
                exit_time        TEXT,
                signal           TEXT,
                notes            TEXT,
                regime           TEXT,
                iv_regime        TEXT,
                mtf_bias         TEXT,
                score            INTEGER DEFAULT 0,
                strategy_type    TEXT DEFAULT 'UNKNOWN',
                confidence       TEXT DEFAULT 'LOW',
                risk_pct_applied REAL DEFAULT 1.5,
                slippage_pct     REAL DEFAULT 0,
                order_id         TEXT,
                btst_trade       INTEGER DEFAULT 0,
                created_at       TEXT DEFAULT (datetime('now'))
            )
        """)

        # ── Execution audit ──────────────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS execution_audit (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id         INTEGER,
                timestamp        TEXT NOT NULL,
                action           TEXT NOT NULL,
                symbol           TEXT NOT NULL,
                requested_price  REAL NOT NULL,
                fill_price       REAL NOT NULL,
                slippage_pct     REAL NOT NULL,
                slippage_amount  REAL NOT NULL,
                latency_ms       REAL NOT NULL,
                order_id         TEXT,
                broker           TEXT DEFAULT 'paper',
                status           TEXT NOT NULL,
                error            TEXT DEFAULT ''
            )
        """)

        # ── Equity snapshots ─────────────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS equity_snapshots (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    TEXT NOT NULL,
                capital      REAL NOT NULL,
                daily_pnl    REAL NOT NULL,
                total_pnl    REAL NOT NULL,
                open_trades  INTEGER DEFAULT 0,
                drawdown_pct REAL DEFAULT 0
            )
        """)

        # ── Bot config — stores ALL persistent settings ───────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # ── Signals log ──────────────────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS signals_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                symbol      TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                reason      TEXT,
                blocked_by  TEXT,
                price       REAL,
                score       INTEGER DEFAULT 0,
                strategy    TEXT DEFAULT '',
                acted       INTEGER DEFAULT 0
            )
        """)

        # ── Notifications ────────────────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                type      TEXT NOT NULL,
                title     TEXT NOT NULL,
                message   TEXT NOT NULL,
                read      INTEGER DEFAULT 0
            )
        """)

        # ── Strategy performance ─────────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS strategy_performance (
                strategy     TEXT PRIMARY KEY,
                trades       INTEGER DEFAULT 0,
                wins         INTEGER DEFAULT 0,
                losses       INTEGER DEFAULT 0,
                total_pnl    REAL DEFAULT 0,
                best_trade   REAL DEFAULT 0,
                worst_trade  REAL DEFAULT 0,
                weight_mult  REAL DEFAULT 1.0,
                enabled      INTEGER DEFAULT 1,
                last_updated TEXT
            )
        """)

        # ── BTST trades ──────────────────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS btst_trades (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol       TEXT NOT NULL,
                option_type  TEXT NOT NULL,
                strike       REAL NOT NULL,
                expiry       TEXT NOT NULL,
                entry_price  REAL NOT NULL,
                fill_price   REAL,
                exit_price   REAL,
                quantity     INTEGER NOT NULL,
                sl_price     REAL NOT NULL,
                target_price REAL NOT NULL,
                status       TEXT DEFAULT 'OPEN',
                pnl          REAL DEFAULT 0,
                entry_time   TEXT NOT NULL,
                exit_time    TEXT,
                exit_reason  TEXT,
                gap_pct      REAL DEFAULT 0,
                score        INTEGER DEFAULT 0,
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        # ── Blocked dates ────────────────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_dates (
                date_str   TEXT PRIMARY KEY,
                reason     TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # ── Default config values ────────────────────────────────────────────
        from config import settings
        defaults = {
            # Trading params
            "capital":                    str(settings.DEFAULT_CAPITAL),
            "risk_pct":                   str(settings.RISK_PER_TRADE_PCT),
            "daily_loss_cap":             str(settings.DAILY_LOSS_CAP_PCT),
            "max_daily_trades":           str(settings.MAX_DAILY_TRADES),
            "max_consecutive_losses":     str(settings.MAX_CONSECUTIVE_LOSSES),
            "max_loss_streak_day_stop":   str(settings.MAX_LOSS_STREAK_DAY_STOP),
            "cooldown_minutes":           str(settings.COOLDOWN_MINUTES),
            "min_score":                  str(settings.MIN_SCORE),
            # Bot state — persisted so auto-restart works
            "mode":                       "paper",
            "bot_status":                 "stopped",
            "symbol":                     settings.DEFAULT_SYMBOL,
            # Strategy filters
            "use_adx_filter":             "true",
            "use_iv_filter":              "true",
            "use_time_filter":            "true",
            "use_mtf":                    "true",
            "use_volume_filter":          "true",
            "use_spike_filter":           "true",
            # Features
            "btst_enabled":               "false",
            "global_sentiment_enabled":   "true",
            "no_trade_day_auto":          "true",
            "event_block_enabled":        "true",
            "slippage_pct":               str(settings.SLIPPAGE_PCT),
            # Upstox token — empty by default, filled by OAuth login
            "upstox_access_token":        "",
        }
        for k, v in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO bot_config (key, value) VALUES (?, ?)", (k, v)
            )

        # Strategy performance defaults
        from intelligence.strategy_intel import StrategyType
        for s in [StrategyType.BREAKOUT, StrategyType.PULLBACK,
                  StrategyType.VWAP,     StrategyType.RETEST, StrategyType.BTST]:
            await db.execute(
                "INSERT OR IGNORE INTO strategy_performance (strategy, last_updated) VALUES (?, ?)",
                (s, datetime.now().isoformat())
            )

        await db.commit()
    logger.info("✅ Database v3 initialized")


# ─── Trade CRUD ───────────────────────────────────────────────────────────────

async def save_trade(trade: Dict[str, Any]) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO trades
            (symbol, option_type, strike, expiry, entry_price, fill_price,
             quantity, lots, lot_size, sl_price, target_price, partial_target,
             status, entry_time, signal, notes, regime, iv_regime, mtf_bias,
             score, strategy_type, confidence, risk_pct_applied,
             slippage_pct, order_id, btst_trade)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            trade["symbol"],      trade["option_type"],  trade["strike"],
            trade["expiry"],      trade["entry_price"],
            trade.get("fill_price", trade["entry_price"]),
            trade["quantity"],    trade.get("lots", 1),  trade.get("lot_size", 50),
            trade["sl_price"],    trade["target_price"], trade.get("partial_target", 0),
            trade.get("status", "OPEN"), trade["entry_time"],
            json.dumps(trade.get("signal", {})), trade.get("notes", ""),
            trade.get("regime", ""),  trade.get("iv_regime", ""),
            trade.get("mtf_bias", ""), trade.get("score", 0),
            trade.get("strategy_type", "UNKNOWN"), trade.get("confidence", "LOW"),
            trade.get("risk_pct_applied", 1.5),    trade.get("slippage_pct", 0),
            trade.get("order_id", ""),             int(trade.get("btst_trade", False)),
        ))
        await db.commit()
        return cur.lastrowid


async def close_trade(trade_id: int, exit_price: float, status: str, pnl: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE trades SET exit_price=?, status=?, pnl=?, exit_time=? WHERE id=?",
            (exit_price, status, pnl, datetime.now().isoformat(), trade_id)
        )
        await db.commit()


async def mark_partial_booked(trade_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE trades SET partial_booked=1 WHERE id=?", (trade_id,))
        await db.commit()


async def get_open_trades() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur  = await db.execute(
            "SELECT * FROM trades WHERE status='OPEN' AND btst_trade=0 ORDER BY entry_time DESC"
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_trade_history(limit: int = 50) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur  = await db.execute(
            "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                SUM(pnl) as total_pnl, AVG(pnl) as avg_pnl,
                MAX(pnl) as best_trade, MIN(pnl) as worst_trade,
                AVG(CASE WHEN pnl > 0 THEN pnl ELSE NULL END) as avg_win,
                AVG(CASE WHEN pnl < 0 THEN pnl ELSE NULL END) as avg_loss
            FROM trades WHERE status != 'OPEN'
        """)
        stats = dict(await cur.fetchone())

        today = datetime.now().strftime("%Y-%m-%d")
        cur2  = await db.execute("""
            SELECT SUM(pnl) as daily_pnl, COUNT(*) as daily_trades,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as daily_wins
            FROM trades WHERE status != 'OPEN' AND entry_time LIKE ?
        """, (f"{today}%",))
        stats.update(dict(await cur2.fetchone()))

        wins  = stats.get("wins") or 0
        total = max(stats.get("total_trades") or 1, 1)
        avg_w = abs(stats.get("avg_win")  or 1)
        avg_l = abs(stats.get("avg_loss") or 1)
        stats["win_rate"] = round((wins / total) * 100, 1)
        stats["rr_ratio"] = round(avg_w / max(avg_l, 0.01), 2)
        return stats


async def get_daily_trades_count() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM trades WHERE entry_time LIKE ?", (f"{today}%",)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


# ─── Execution audit ──────────────────────────────────────────────────────────

async def save_execution_audit(trade_id: int, action: str, exec_result: Dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO execution_audit
            (trade_id, timestamp, action, symbol, requested_price, fill_price,
             slippage_pct, slippage_amount, latency_ms, order_id, broker, status, error)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            trade_id,
            exec_result.get("timestamp", datetime.now().isoformat()),
            action,
            exec_result.get("symbol", ""),
            exec_result.get("requested_price", 0),
            exec_result.get("fill_price", 0),
            exec_result.get("slippage_pct", 0),
            exec_result.get("slippage_amount", 0),
            exec_result.get("latency_ms", 0),
            exec_result.get("order_id", ""),
            exec_result.get("broker", "paper"),
            exec_result.get("status", ""),
            exec_result.get("error", ""),
        ))
        await db.commit()


async def get_execution_audit(trade_id: int = None, limit: int = 50) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if trade_id:
            cur = await db.execute(
                "SELECT * FROM execution_audit WHERE trade_id=? ORDER BY timestamp DESC",
                (trade_id,)
            )
        else:
            cur = await db.execute(
                "SELECT * FROM execution_audit ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        return [dict(r) for r in await cur.fetchall()]


# ─── BTST ─────────────────────────────────────────────────────────────────────

async def save_btst_trade(trade: Dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO btst_trades
            (symbol, option_type, strike, expiry, entry_price, fill_price,
             quantity, sl_price, target_price, status, entry_time, score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            trade["symbol"],      trade["option_type"], trade["strike"],
            trade["expiry"],      trade["entry_price"],
            trade.get("fill_price", trade["entry_price"]),
            trade["quantity"],    trade["sl_price"],    trade["target_price"],
            "OPEN", trade["entry_time"], trade.get("score", 0),
        ))
        await db.commit()
        return cur.lastrowid


async def close_btst_trade(
    btst_id: int, exit_price: float, pnl: float,
    exit_reason: str, gap_pct: float = 0
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE btst_trades
            SET exit_price=?, pnl=?, status=?, exit_time=?, exit_reason=?, gap_pct=?
            WHERE id=?
        """, (exit_price, pnl, "CLOSED",
              datetime.now().isoformat(), exit_reason, gap_pct, btst_id))
        await db.commit()


async def get_open_btst_trades() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur  = await db.execute("SELECT * FROM btst_trades WHERE status='OPEN'")
        return [dict(r) for r in await cur.fetchall()]


async def get_btst_history(limit: int = 20) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur  = await db.execute(
            "SELECT * FROM btst_trades ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cur.fetchall()]


# ─── Config ───────────────────────────────────────────────────────────────────

async def get_config(key: str) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT value FROM bot_config WHERE key=?", (key,)
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def set_config(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)", (key, value)
        )
        await db.commit()


async def get_all_config() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur  = await db.execute("SELECT key, value FROM bot_config")
        rows = await cur.fetchall()
        return {r["key"]: r["value"] for r in rows}


# ─── Equity snapshots ─────────────────────────────────────────────────────────

async def save_equity_snapshot(
    capital: float, daily_pnl: float, total_pnl: float,
    open_trades: int, drawdown_pct: float = 0
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO equity_snapshots
            (timestamp, capital, daily_pnl, total_pnl, open_trades, drawdown_pct)
            VALUES (?,?,?,?,?,?)
        """, (datetime.now().isoformat(), capital, daily_pnl,
              total_pnl, open_trades, drawdown_pct))
        await db.commit()


async def get_equity_curve(limit: int = 200) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur  = await db.execute(
            "SELECT * FROM equity_snapshots ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return list(reversed([dict(r) for r in rows]))


# ─── Notifications ────────────────────────────────────────────────────────────

async def add_notification(type_: str, title: str, message: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO notifications (timestamp, type, title, message)
            VALUES (?,?,?,?)
        """, (datetime.now().isoformat(), type_, title, message))
        await db.commit()


async def get_notifications(limit: int = 20, unread_only: bool = False) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        where = "WHERE read=0 " if unread_only else ""
        cur   = await db.execute(
            f"SELECT * FROM notifications {where}ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cur.fetchall()]


async def mark_notifications_read():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE notifications SET read=1")
        await db.commit()


# ─── Signals log ─────────────────────────────────────────────────────────────

async def log_signal(
    symbol: str, signal_type: str, reason: str, price: float,
    acted: bool = False, blocked_by: str = "", score: int = 0, strategy: str = ""
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO signals_log
            (timestamp, symbol, signal_type, reason, blocked_by, price, score, strategy, acted)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            datetime.now().isoformat(), symbol, signal_type, reason,
            blocked_by, price, score, strategy, int(acted)
        ))
        await db.commit()
