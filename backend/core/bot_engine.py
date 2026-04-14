"""
Bot Engine — v3.1 (Real-Time)
Changes from v3:
  - Uses upstox_market.get_live_price() instead of yfinance for spot
  - Uses upstox_market.get_option_live_ltp() for real option premium tracking
  - Trade object now includes: entry_spot_price, entry_option_price, instrument_key
  - Broadcasts "premium_tick" every 30s for live frontend P&L display
  - Monitor loop uses real option LTP (not spot-delta proxy) when Upstox available
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Set
from loguru import logger

from core.database import (
    save_trade, close_trade, mark_partial_booked,
    get_open_trades, get_stats, get_daily_trades_count,
    get_config, set_config, get_all_config,
    save_equity_snapshot, log_signal, add_notification,
    save_execution_audit, save_btst_trade, close_btst_trade,
    get_open_btst_trades,
)
# Real-time data layer
from data.upstox_market import (
    get_live_price,
    get_option_live_ltp,
    get_premiums_for_open_trades,
    is_market_open,
)
from strategy.signal_engine import generate_signal
from execution.engine import execute_order, connect_broker
from execution.sizing import calculate_adaptive_size
from intelligence.strategy_intel import (
    classify_trade_strategy, record_strategy_result, StrategyType
)
from intelligence.market_intel import get_market_status, is_no_trade_day
from btst.strategy import generate_btst_signal, should_exit_btst, is_btst_entry_window
from config import settings

_broadcast_fn = None


def set_broadcast_fn(fn):
    global _broadcast_fn
    _broadcast_fn = fn


async def _broadcast(event: str, data: dict):
    if _broadcast_fn:
        try:
            await _broadcast_fn({"event": event, "data": data})
        except Exception as e:
            logger.warning(f"Broadcast error: {e}")


class BotEngine:
    def __init__(self):
        self.is_running        = False
        self.mode              = "paper"
        self.symbol            = settings.DEFAULT_SYMBOL
        self.capital           = settings.DEFAULT_CAPITAL
        self.initial_capital   = settings.DEFAULT_CAPITAL
        self.peak_capital      = settings.DEFAULT_CAPITAL
        self.risk_pct          = settings.RISK_PER_TRADE_PCT
        self.daily_loss_cap    = settings.DAILY_LOSS_CAP_PCT
        self.max_daily_trades  = settings.MAX_DAILY_TRADES
        self.max_open_trades   = settings.MAX_OPEN_TRADES
        self.max_consec_losses = settings.MAX_CONSECUTIVE_LOSSES
        self.day_stop_losses   = settings.MAX_LOSS_STREAK_DAY_STOP
        self.cooldown_minutes  = settings.COOLDOWN_MINUTES
        self.min_score         = settings.MIN_SCORE
        self.btst_enabled      = settings.BTST_ENABLED

        self.total_pnl            = 0.0
        self.daily_pnl            = 0.0
        self.last_trade_date: Optional[date] = None
        self.cooldown_until:  Optional[datetime] = None
        self.consecutive_losses   = 0
        self.daily_trades_count   = 0
        self.max_drawdown         = 0.0
        self.win_streak           = 0
        self.loss_streak          = 0
        self.trading_halted_today = False
        self.api_fail_count       = 0

        self.open_trades: List[Dict]          = []
        self.btst_trades: List[Dict]          = []
        self.trailing_stops: Dict[int, float] = {}
        self.partial_done:   Set[int]         = set()
        # Live LTP cache: trade_id → current premium
        self.live_ltps: Dict[int, float]      = {}
        self.filters: Dict                    = {}

        self._task:         Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._btst_task:    Optional[asyncio.Task] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def start(self, symbol: str = None, capital: float = None, mode: str = "paper"):
        if self.is_running:
            return

        self.symbol          = symbol  or self.symbol
        self.capital         = capital or self.capital
        self.initial_capital = self.capital
        self.peak_capital    = self.capital
        self.mode            = mode

        await self._reload_config()

        if mode == "live":
            ok = await connect_broker()
            if not ok and settings.HARD_STOP_ON_API_FAIL:
                logger.error("Broker connection failed")
                await add_notification(
                    "EMERGENCY", "Broker Failed",
                    "Cannot connect. For Upstox: login via dashboard first."
                )
                return

        self.open_trades        = await get_open_trades()
        self.btst_trades        = await get_open_btst_trades()
        self.daily_trades_count = await get_daily_trades_count()
        self.is_running         = True

        await set_config("bot_status", "running")
        await set_config("mode",       mode)
        await set_config("symbol",     self.symbol)
        await set_config("capital",    str(self.capital))

        self._task         = asyncio.create_task(self._signal_loop())
        self._monitor_task = asyncio.create_task(self._position_monitor_loop())
        self._btst_task    = asyncio.create_task(self._btst_loop())

        msg = f"{mode.upper()} | {self.symbol} | ₹{self.capital:,.0f} | Score≥{self.min_score}"
        await add_notification("INFO", "Bot Started", msg)
        await _broadcast("bot_status", {
            "running": True, "mode": mode,
            "symbol": self.symbol, "capital": self.capital
        })
        logger.info(f"🟢 Bot STARTED | {msg}")

    async def stop(self):
        self.is_running = False
        for t in [self._task, self._monitor_task, self._btst_task]:
            if t:
                t.cancel()
        await set_config("bot_status", "stopped")
        await _broadcast("bot_status", {"running": False})
        logger.info("🔴 Bot STOPPED")

    async def _reload_config(self):
        cfg = await get_all_config()
        self.risk_pct          = float(cfg.get("risk_pct",               settings.RISK_PER_TRADE_PCT))
        self.daily_loss_cap    = float(cfg.get("daily_loss_cap",          settings.DAILY_LOSS_CAP_PCT))
        self.max_daily_trades  = int(  cfg.get("max_daily_trades",        settings.MAX_DAILY_TRADES))
        self.max_consec_losses = int(  cfg.get("max_consecutive_losses",  settings.MAX_CONSECUTIVE_LOSSES))
        self.day_stop_losses   = int(  cfg.get("max_loss_streak_day_stop",settings.MAX_LOSS_STREAK_DAY_STOP))
        self.cooldown_minutes  = int(  cfg.get("cooldown_minutes",        settings.COOLDOWN_MINUTES))
        self.min_score         = int(  cfg.get("min_score",               settings.MIN_SCORE))
        self.btst_enabled      = cfg.get("btst_enabled", "false") == "true"
        self.filters = {
            "use_adx_filter":    cfg.get("use_adx_filter",    "true") == "true",
            "use_iv_filter":     cfg.get("use_iv_filter",     "true") == "true",
            "use_time_filter":   cfg.get("use_time_filter",   "true") == "true",
            "use_mtf":           cfg.get("use_mtf",           "true") == "true",
            "use_volume_filter": cfg.get("use_volume_filter", "true") == "true",
            "use_spike_filter":  cfg.get("use_spike_filter",  "true") == "true",
        }

    # ── Signal loop ───────────────────────────────────────────────────────────

    async def _signal_loop(self):
        logger.info(f"Signal loop — every {settings.DATA_FETCH_INTERVAL}s")
        while self.is_running:
            try:
                await self._check_and_trade()
                await asyncio.sleep(settings.DATA_FETCH_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Signal loop error: {e}")
                await asyncio.sleep(10)

    async def _check_and_trade(self):
        today = date.today()

        if self.last_trade_date != today:
            self.daily_pnl            = 0.0
            self.daily_trades_count   = await get_daily_trades_count()
            self.last_trade_date      = today
            self.consecutive_losses   = 0
            self.trading_halted_today = False
            self.api_fail_count       = 0
            logger.info(f"📅 New day {today}")
            await _broadcast("daily_reset", {"date": str(today)})

        await self._reload_config()

        if self.trading_halted_today:
            return

        daily_cap = self.initial_capital * self.daily_loss_cap / 100
        if self.daily_pnl <= -daily_cap:
            self.trading_halted_today = True
            msg = f"Daily loss cap hit (₹{self.daily_pnl:.0f}) — halting"
            logger.warning(f"⚠️ {msg}")
            await _broadcast("alert", {"type": "DAILY_CAP", "message": msg})
            return

        if self.daily_trades_count >= self.max_daily_trades:
            return

        if self.cooldown_until and datetime.now() < self.cooldown_until:
            rem = int((self.cooldown_until - datetime.now()).total_seconds() / 60)
            await _broadcast("cooldown", {"remaining_minutes": rem})
            return

        if len(self.open_trades) >= self.max_open_trades:
            return

        try:
            signal = await generate_signal(self.symbol, self.min_score, self.filters)
            self.api_fail_count = 0
        except Exception as e:
            self.api_fail_count += 1
            logger.error(f"Signal error ({self.api_fail_count}): {e}")
            if self.api_fail_count >= 3 and settings.HARD_STOP_ON_API_FAIL:
                await self.emergency_stop()
            return

        await log_signal(
            self.symbol, signal["signal_type"],
            "; ".join(signal["reasons"][:3]),
            signal["price_data"]["price"] if signal["price_data"] else 0,
            acted=(signal["signal_type"] != "NO_TRADE"),
            blocked_by=signal.get("blocked_by", ""),
            score=signal.get("score", 0),
            strategy=signal.get("strategy_type", ""),
        )
        await _broadcast("signal", signal)

        if signal["signal_type"] == "NO_TRADE":
            return

        await self._enter_trade(signal)

    # ── Trade entry ───────────────────────────────────────────────────────────

    async def _enter_trade(self, signal: Dict):
        option      = signal["option"]
        ltp         = option["ltp"]           # real-time premium from Upstox
        sl_pct      = signal["sl_pct"]
        sl_price    = signal["sl_price"]
        tgt_price   = signal["target_price"]
        partial_tgt = signal.get("partial_target", round(ltp * 1.15, 2))
        strategy    = signal.get("strategy_type", StrategyType.UNKNOWN)
        atr_val     = signal.get("atr_val", 0)
        spot        = signal.get("spot_price", 0)   # Nifty spot at entry
        inst_key    = option.get("instrument_key", "")
        lot_size_api = option.get("lot_size")        # ← from Upstox instruments API

        # ── Validate required API fields before doing anything ──────────────
        if not inst_key:
            logger.error("❌ TRADE BLOCKED: instrument_key missing from option data — NOT TRADING")
            await add_notification("WARNING", "Trade Blocked", "instrument_key missing from API")
            return

        if not lot_size_api or int(lot_size_api) <= 0:
            logger.error(f"❌ TRADE BLOCKED: lot_size={lot_size_api} missing from API — NOT TRADING")
            await add_notification("WARNING", "Trade Blocked", f"lot_size missing — NOT TRADING")
            return

        if ltp <= 0:
            logger.error(f"❌ TRADE BLOCKED: LTP={ltp} — premium unavailable")
            await add_notification("WARNING", "Trade Blocked", "Premium LTP is zero — NOT TRADING")
            return

        # ── Adaptive sizing — lot_size comes from Upstox API ───────────────
        sizing = calculate_adaptive_size(
            capital=self.capital, signal_score=signal["score"],
            option_ltp=ltp, sl_pct=sl_pct,
            atr_val=atr_val, spot_price=spot,
            consecutive_losses=self.consecutive_losses,
            lot_size_from_api=int(lot_size_api),   # ← API value, never hardcoded
        )

        if sizing is None:
            logger.error("❌ TRADE BLOCKED: sizing returned None (lot_size issue) — NOT TRADING")
            await add_notification("WARNING", "Trade Blocked", "Position sizing failed — NOT TRADING")
            return

        qty      = sizing["quantity"]
        lots     = sizing["lots"]
        lot_size = sizing["lot_size"]

        # ── Execute order — uses instrument_key from API ────────────────────
        exec_result = await execute_order(
            instrument_key=inst_key,
            option_type=option["option_type"],
            strike=option["strike"],
            expiry=option["expiry"],
            quantity=qty,
            action="BUY",
            ltp=ltp,
            lot_size=lot_size,
            entry_spot=spot,
            mode=self.mode,
        )

        if not exec_result["success"]:
            logger.error(f"Order failed: {exec_result['error']}")
            await add_notification("WARNING", "Order Failed", exec_result["error"])
            return

        fill_price = exec_result["fill_price"]

        # ── Trade object — includes all fields needed by TradeTracker UI ──
        trade = {
            "symbol":             self.symbol,
            "option_type":        option["option_type"],
            "strike":             option["strike"],
            "expiry":             option["expiry"],
            "entry_price":        ltp,           # option premium at entry (requested)
            "fill_price":         fill_price,    # actual fill
            "entry_option_price": fill_price,    # alias — for TradeTracker UI clarity
            "entry_spot_price":   spot,          # Nifty/BankNifty spot at entry
            "current_premium":    fill_price,    # updated by monitor loop
            "instrument_key":     inst_key,      # Upstox key for live LTP polling
            "quantity":           qty,
            "lots":               lots,
            "lot_size":           lot_size,
            "sl_price":           sl_price,
            "target_price":       tgt_price,
            "partial_target":     partial_tgt,
            "status":             "OPEN",
            "entry_time":         datetime.now().isoformat(),
            "signal":             signal,
            "regime":             signal.get("regime", ""),
            "iv_regime":          signal.get("iv_regime", ""),
            "mtf_bias":           signal.get("mtf_bias", ""),
            "score":              signal.get("score", 0),
            "strategy_type":      strategy,
            "confidence":         sizing["confidence"],
            "risk_pct_applied":   sizing["risk_pct_applied"],
            "slippage_pct":       exec_result["slippage_pct"],
            "order_id":           exec_result["order_id"],
            "btst_trade":         False,
            "notes": (
                f"Score={signal['score']} Strategy={strategy} "
                f"Conf={sizing['confidence']} Risk={sizing['risk_pct_applied']:.1f}% "
                f"Broker={exec_result['broker']} Spot={spot}"
            ),
        }

        trade_id = await save_trade(trade)
        trade["id"] = trade_id
        await save_execution_audit(trade_id, "BUY", exec_result)
        self.open_trades.append(trade)
        self.trailing_stops[trade_id] = sl_price
        self.live_ltps[trade_id]      = fill_price
        self.daily_trades_count += 1

        notif = (
            f"BUY {option['option_type']} ₹{option['strike']} | "
            f"Spot ₹{spot:.0f} | Premium ₹{fill_price} | "
            f"{lots}L | Score={signal['score']} | {exec_result['broker'].upper()}"
        )
        await add_notification("TRADE", "Trade Entered", notif)

        # Broadcast with full entry context for TradeTracker
        await _broadcast("trade_entered", {
            **trade,
            "id":      trade_id,
            "sizing":  sizing,
        })
        logger.info(
            f"📈 ENTERED #{trade_id} | {option['option_type']} {option['strike']} "
            f"| Spot=₹{spot:.0f} | Premium=₹{fill_price} "
            f"| SL=₹{sl_price} | T2=₹{tgt_price} | {lots}L"
        )

    # ── Position monitor — uses real Upstox LTP ───────────────────────────────

    async def _position_monitor_loop(self):
        while self.is_running:
            try:
                if self.open_trades:
                    await self._monitor_positions()
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(10)

    async def _monitor_positions(self):
        # Get current spot price (real-time)
        spot_data = await get_live_price(self.symbol)
        if not spot_data:
            return
        spot = spot_data["price"]

        # Get real option LTPs for all open trades in one batch
        real_ltps = await get_premiums_for_open_trades(self.open_trades)

        closed_ids: Set[int] = set()
        premium_ticks: List[Dict] = []   # for frontend live update

        for trade in list(self.open_trades):
            tid         = trade["id"]
            entry       = trade["entry_price"]
            qty         = trade["quantity"]
            sl          = self.trailing_stops.get(tid, trade["sl_price"])
            target      = trade["target_price"]
            partial_tgt = trade.get("partial_target", target * 0.6)
            opt_type    = trade["option_type"]
            strategy    = trade.get("strategy_type", StrategyType.UNKNOWN)
            inst_key    = trade.get("instrument_key", "")

            # ── Get current option LTP ─────────────────────────────────────
            # Priority: batch real_ltps → individual Upstox → delta proxy
            est_ltp = real_ltps.get(tid)

            if not est_ltp or est_ltp <= 0:
                # Try individual fetch
                if inst_key:
                    est_ltp = await get_option_live_ltp(inst_key)

            if not est_ltp or est_ltp <= 0:
                # Delta-based proxy (fallback — less accurate)
                entry_spot = trade.get("entry_spot_price", spot)
                chg_pct    = (spot - entry_spot) / max(entry_spot, 1)
                delta      = trade.get("signal", {}).get("option", {}).get("delta", 0.5) or 0.5
                est_ltp    = max(
                    round(entry * (1 + chg_pct / delta if opt_type == "CE"
                                  else 1 - chg_pct / delta), 2),
                    0.05
                )

            est_ltp = round(float(est_ltp), 2)

            # Update live LTP cache
            self.live_ltps[tid]       = est_ltp
            trade["current_premium"]  = est_ltp

            # Live running P&L for this trade
            running_pnl = round((est_ltp - entry) * qty, 2)
            pnl_pct     = round(((est_ltp - entry) / max(entry, 0.01)) * 100, 1)

            premium_ticks.append({
                "id":              tid,
                "symbol":          trade["symbol"],
                "option_type":     opt_type,
                "strike":          trade["strike"],
                "expiry":          trade["expiry"],
                "entry_spot":      trade.get("entry_spot_price", 0),
                "entry_premium":   entry,
                "current_premium": est_ltp,
                "current_spot":    spot,
                "running_pnl":     running_pnl,
                "pnl_pct":         pnl_pct,
                "sl_price":        sl,
                "target_price":    target,
                "partial_target":  partial_tgt,
                "entry_time":      trade.get("entry_time", ""),
                "quantity":        qty,
                "lots":            trade.get("lots", 1),
            })

            # ── Partial booking at T1 (1:1 RR) ────────────────────────────
            if tid not in self.partial_done and est_ltp >= partial_tgt:
                half_qty    = qty // 2
                partial_pnl = round((partial_tgt - entry) * half_qty, 2)
                self.daily_pnl += partial_pnl
                self.total_pnl += partial_pnl
                self.capital   += partial_pnl
                trade["quantity"] = qty - half_qty
                new_sl            = round(entry * 1.001, 2)
                self.trailing_stops[tid] = new_sl
                self.partial_done.add(tid)
                await mark_partial_booked(tid)

                exec_r = await execute_order(
                    instrument_key=trade.get("instrument_key", ""),
                    option_type=opt_type,
                    strike=trade["strike"],
                    expiry=trade["expiry"],
                    quantity=half_qty,
                    action="SELL",
                    ltp=partial_tgt,
                    lot_size=trade.get("lot_size", 1),
                    entry_spot=spot,
                    mode=self.mode,
                )
                await save_execution_audit(tid, "PARTIAL_SELL", exec_r)
                await add_notification(
                    "TRADE", "Partial Booking",
                    f"#{tid} | {half_qty}u @ ₹{partial_tgt} | +₹{partial_pnl:.0f} | SL→BE"
                )
                await _broadcast("partial_booked", {
                    "id": tid, "partial_price": partial_tgt,
                    "partial_pnl": partial_pnl, "new_sl": new_sl,
                })
                logger.info(
                    f"📦 PARTIAL #{tid} | {half_qty}u @ ₹{partial_tgt} "
                    f"| +₹{partial_pnl:.0f} | SL→BE={new_sl}"
                )
                continue

            # ── Trailing SL ────────────────────────────────────────────────
            if est_ltp > entry:
                new_sl = round(entry + (est_ltp - entry) * 0.6, 2)
                if new_sl > sl:
                    self.trailing_stops[tid] = new_sl
                    sl = new_sl

            # ── Exit conditions ────────────────────────────────────────────
            exit_reason = None
            if est_ltp <= sl:
                exit_reason = "SL_HIT"
            elif est_ltp >= target:
                exit_reason = "TARGET_HIT"

            if exit_reason:
                exec_r = await execute_order(
                    instrument_key=trade.get("instrument_key", ""),
                    option_type=opt_type,
                    strike=trade["strike"],
                    expiry=trade["expiry"],
                    quantity=trade["quantity"],
                    action="SELL",
                    ltp=est_ltp,
                    lot_size=trade.get("lot_size", 1),
                    entry_spot=spot,
                    mode=self.mode,
                )
                fill = exec_r["fill_price"]
                pnl  = round((fill - entry) * trade["quantity"], 2)
                await close_trade(tid, fill, exit_reason, pnl)
                await save_execution_audit(tid, "SELL", exec_r)

                self.daily_pnl += pnl
                self.total_pnl += pnl
                self.capital   += pnl
                closed_ids.add(tid)
                self.live_ltps.pop(tid, None)

                if self.capital > self.peak_capital:
                    self.peak_capital = self.capital
                dd = round(((self.peak_capital - self.capital) / self.peak_capital) * 100, 2)
                self.max_drawdown = max(self.max_drawdown, dd)

                await record_strategy_result(strategy, pnl)

                if pnl > 0:
                    self.consecutive_losses = 0
                    self.win_streak  += 1
                    self.loss_streak  = 0
                else:
                    self.consecutive_losses += 1
                    self.loss_streak  += 1
                    self.win_streak   = 0
                    if self.consecutive_losses >= self.day_stop_losses:
                        self.trading_halted_today = True
                        msg = f"{self.day_stop_losses} losses — halted for today"
                        logger.warning(f"🛑 {msg}")
                        await add_notification("EMERGENCY", "Day Stop", msg)
                        await _broadcast("alert", {"type": "DAY_STOP", "message": msg})
                    elif self.consecutive_losses >= self.max_consec_losses:
                        self.cooldown_until = datetime.now() + timedelta(minutes=self.cooldown_minutes)
                        await add_notification(
                            "WARNING", "Cooldown",
                            f"{self.consecutive_losses} losses → {self.cooldown_minutes}min pause"
                        )

                icon = "🟢" if pnl > 0 else "🔴"
                logger.info(
                    f"{icon} CLOSED #{tid} | {exit_reason} | Premium={fill} "
                    f"| P&L=₹{pnl:+.0f} | {exec_r['broker'].upper()}"
                )
                await add_notification(
                    "TRADE" if pnl > 0 else "WARNING",
                    f"Trade {exit_reason.replace('_', ' ')}",
                    f"#{tid} | P&L ₹{pnl:+.0f} | Exit ₹{fill}"
                )
                await _broadcast("trade_closed", {
                    "id": tid, "exit_price": fill, "status": exit_reason,
                    "pnl": pnl, "daily_pnl": self.daily_pnl,
                    "total_pnl": self.total_pnl,
                    "consecutive_losses": self.consecutive_losses,
                    "slippage_pct": exec_r["slippage_pct"],
                })
                await save_equity_snapshot(
                    self.capital, self.daily_pnl, self.total_pnl,
                    len(self.open_trades) - 1, dd
                )

        self.open_trades = [t for t in self.open_trades if t["id"] not in closed_ids]

        # ── Broadcast premium ticks — powers TradeTracker UI ──────────────
        if premium_ticks:
            await _broadcast("premium_tick", {
                "ticks":      premium_ticks,
                "spot":       spot,
                "timestamp":  datetime.now().isoformat(),
            })

        await _broadcast("portfolio_update", {
            "capital":            round(self.capital, 2),
            "daily_pnl":          round(self.daily_pnl, 2),
            "total_pnl":          round(self.total_pnl, 2),
            "open_trades":        len(self.open_trades),
            "daily_trades":       self.daily_trades_count,
            "max_drawdown":       round(self.max_drawdown, 2),
            "win_streak":         self.win_streak,
            "loss_streak":        self.loss_streak,
            "consecutive_losses": self.consecutive_losses,
            "trading_halted":     self.trading_halted_today,
            "spot":               spot,
        })

    # ── BTST loop ─────────────────────────────────────────────────────────────

    async def _btst_loop(self):
        while self.is_running:
            try:
                await self._reload_config()
                if self.btst_enabled:
                    await self._check_btst()
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"BTST loop error: {e}")
                await asyncio.sleep(60)

    async def _check_btst(self):
        spot_data = await get_live_price(self.symbol)
        if not spot_data:
            return
        spot = spot_data["price"]

        for bt in list(self.btst_trades):
            ltp_now = await get_option_live_ltp(bt.get("instrument_key", "")) or spot
            reason  = await should_exit_btst(bt, ltp_now)
            if reason:
                exec_r  = await execute_order(
                    instrument_key=bt.get("instrument_key", ""),
                    option_type=bt["option_type"],
                    strike=bt["strike"],
                    expiry=bt["expiry"],
                    quantity=bt["quantity"],
                    action="SELL",
                    ltp=ltp_now,
                    lot_size=bt.get("lot_size", 1),
                    entry_spot=spot,
                    mode=self.mode,
                )
                fill    = exec_r["fill_price"]
                pnl     = round((fill - bt["entry_price"]) * bt["quantity"], 2)
                gap_pct = round((fill - bt["entry_price"]) / bt["entry_price"] * 100, 2)
                await close_btst_trade(bt["id"], fill, pnl, reason, gap_pct)
                self.daily_pnl += pnl
                self.total_pnl += pnl
                self.capital   += pnl
                self.btst_trades.remove(bt)
                await add_notification("TRADE", f"BTST Exit: {reason}", f"P&L ₹{pnl:+.0f}")
                await _broadcast("btst_closed", {"id": bt["id"], "pnl": pnl, "reason": reason})
                logger.info(f"🌅 BTST CLOSED #{bt['id']} | {reason} | ₹{pnl:+.0f}")

        if not is_btst_entry_window():
            return

        btst_today = sum(
            1 for bt in self.btst_trades
            if bt.get("entry_time", "").startswith(str(date.today()))
        )
        if btst_today >= settings.BTST_MAX_PER_DAY:
            return

        signal = await generate_btst_signal(self.symbol)
        if signal["signal_type"] == "NO_BTST":
            return

        opt          = signal["option"]
        ltp          = opt["ltp"]
        lot_size_api = opt.get("lot_size")

        # Validate lot_size from API — never hardcode
        if not lot_size_api or int(lot_size_api) <= 0:
            logger.error("❌ BTST BLOCKED: lot_size missing from API — NOT TRADING")
            return
        if not opt.get("instrument_key"):
            logger.error("❌ BTST BLOCKED: instrument_key missing — NOT TRADING")
            return

        lot_size = int(lot_size_api)
        risk_a   = self.capital * settings.BTST_RISK_PCT / 100
        sl_pu    = ltp * (signal["sl_pct"] / 100)
        if sl_pu <= 0:
            logger.error("❌ BTST BLOCKED: SL per unit is zero — NOT TRADING")
            return
        raw_qty  = int(risk_a / sl_pu)
        lots     = max(1, raw_qty // lot_size)
        qty      = lots * lot_size

        exec_r = await execute_order(
            instrument_key=opt["instrument_key"],
            option_type=opt["option_type"],
            strike=opt["strike"],
            expiry=opt["expiry"],
            quantity=qty,
            action="BUY",
            ltp=ltp,
            lot_size=lot_size,
            entry_spot=spot,
            mode=self.mode,
        )
        if not exec_r["success"]:
            return

        fill     = exec_r["fill_price"]
        bt_trade = {
            "symbol": self.symbol, "option_type": opt["option_type"],
            "strike": opt["strike"], "expiry": opt["expiry"],
            "entry_price": ltp, "fill_price": fill, "quantity": qty,
            "lot_size": lot_size,
            "sl_price": signal["sl_price"], "target_price": signal["target_price"],
            "status": "OPEN", "entry_time": datetime.now().isoformat(),
            "score": signal["score"],
            "instrument_key": opt.get("instrument_key", ""),
        }
        bt_id          = await save_btst_trade(bt_trade)
        bt_trade["id"] = bt_id
        self.btst_trades.append(bt_trade)
        await add_notification("TRADE", "BTST Entered",
            f"BUY {opt['option_type']} ₹{opt['strike']} | Fill ₹{fill}")
        await _broadcast("btst_entered", bt_trade)
        logger.info(f"🌙 BTST #{bt_id} | {opt['option_type']} {opt['strike']} | ₹{fill}")

    # ── Emergency & controls ──────────────────────────────────────────────────

    async def emergency_stop(self):
        logger.warning("🚨 EMERGENCY STOP!")
        for trade in list(self.open_trades):
            exit_p = round(trade["entry_price"] * 0.95, 2)
            pnl    = round((exit_p - trade["entry_price"]) * trade["quantity"], 2)
            await close_trade(trade["id"], exit_p, "EMERGENCY_STOP", pnl)
            self.daily_pnl += pnl; self.total_pnl += pnl; self.capital += pnl

        for bt in list(self.btst_trades):
            ltp = bt["entry_price"] * 0.95
            pnl = round((ltp - bt["entry_price"]) * bt["quantity"], 2)
            await close_btst_trade(bt["id"], ltp, pnl, "EMERGENCY_STOP")
            self.daily_pnl += pnl; self.total_pnl += pnl; self.capital += pnl

        self.open_trades = []; self.btst_trades = []; self.live_ltps = {}
        await add_notification("EMERGENCY", "Emergency Stop", "All positions closed.")
        await self.stop()
        await _broadcast("emergency_stop", {"message": "All positions closed. Bot stopped."})

    async def update_config(self, updates: Dict):
        for k, v in updates.items():
            await set_config(k, str(v))
        await self._reload_config()
        await _broadcast("config_updated", updates)

    def get_portfolio_state(self) -> Dict:
        rem = max(self.initial_capital * self.daily_loss_cap / 100 + self.daily_pnl, 0)
        return {
            "is_running":           self.is_running,
            "mode":                 self.mode,
            "symbol":               self.symbol,
            "capital":              round(self.capital, 2),
            "initial_capital":      round(self.initial_capital, 2),
            "daily_pnl":            round(self.daily_pnl, 2),
            "total_pnl":            round(self.total_pnl, 2),
            "open_trades":          len(self.open_trades),
            "btst_trades":          len(self.btst_trades),
            "daily_trades":         self.daily_trades_count,
            "max_daily_trades":     self.max_daily_trades,
            "pnl_pct":              round((self.total_pnl / max(self.initial_capital, 1)) * 100, 2),
            "max_drawdown":         round(self.max_drawdown, 2),
            "consecutive_losses":   self.consecutive_losses,
            "win_streak":           self.win_streak,
            "loss_streak":          self.loss_streak,
            "filters":              self.filters,
            "min_score":            self.min_score,
            "risk_pct":             self.risk_pct,
            "daily_loss_cap":       self.daily_loss_cap,
            "btst_enabled":         self.btst_enabled,
            "cooldown_active":      bool(self.cooldown_until and datetime.now() < self.cooldown_until),
            "trading_halted_today": self.trading_halted_today,
            "remaining_daily_risk": round(rem, 2),
        }
