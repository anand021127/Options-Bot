# 🚀 Options Bot v2 — Upgrade Summary
## High-Probability Strategy Upgrade

---

## WHAT CHANGED (v1 → v2)

### Files Modified/Replaced

| File | Status | Key Changes |
|------|--------|-------------|
| `strategy/indicators.py` | **REPLACED** | +ADX, +ATR, +IV Rank proxy, +VWAP bounce, +confirmed breakout, +pullback entry, +candle quality filter |
| `strategy/signal_engine.py` | **REPLACED** | Full rewrite with 10 filters, dynamic scoring, time gates, MTF, ATR-based SL/Target |
| `core/bot_engine.py` | **REPLACED** | Partial booking, consecutive loss cooldown, daily trade cap, live config reload, drawdown tracking |
| `core/database.py` | **REPLACED** | New tables: notifications, daily_summary. New columns: partial_booked, regime, iv_regime, mtf_bias, score |
| `config.py` | **REPLACED** | 12 new config keys for all new features |
| `api/routes.py` | **REPLACED** | New endpoints: /bot/config, /bot/filters, /notifications, live filter toggles |
| `frontend/src/components/PortfolioCard.tsx` | **REPLACED** | Daily usage bars, drawdown, streaks, remaining risk |
| `frontend/src/components/BotControls.tsx` | **REPLACED** | Capital panel, all 6 filter toggles, score slider, risk/cap inputs |
| `frontend/src/components/SignalCard.tsx` | **REPLACED** | ADX gauge, MTF bias, IV rank, T1/T2 targets, blocked reason display |
| `frontend/src/components/StatsBar.tsx` | **REPLACED** | Added R:R ratio, avg P&L |
| `frontend/src/components/Header.tsx` | **REPLACED** | Notification bell with unread badge |
| `frontend/src/components/NotificationsPanel.tsx` | **NEW** | Full notification center |
| `frontend/src/app/page.tsx` | **REPLACED** | Notification integration, typed alerts, config change handler |
| `frontend/src/utils/api.ts` | **REPLACED** | New API calls for config, filters, notifications |

---

## STRATEGY LOGIC v2 — How it Works

### Signal Flow (in order)

```
Every 60 seconds:
  ↓
[1] GATE: Time filter
    → No trades 09:15–09:30 (opening chaos)
    → No trades 15:00–15:30 (closing + theta crush)
    → Lunch caution 13:00–14:00 (score -1)

  ↓
[2] GATE: Candle quality
    → Reject if wick > 3× body (fake spike / manipulation)

  ↓
[3] GATE: Volume
    → Reject if current volume < 50% of 30-bar average

  ↓
[4] GATE: Market regime (ADX)
    → SIDEWAYS (ADX < 20)  → SKIP (no edge)
    → VOLATILE (ATR > 1.5%) → SKIP (options overpriced)
    → WEAK_TREND (ADX 20-25) → allowed, lower score
    → TRENDING (ADX ≥ 25)  → full scoring

  ↓
[5] GATE: IV environment
    → HIGH_IV (IVR 60-80)   → SKIP (premium expensive)
    → EXTREME_IV (IVR > 80) → SKIP (will crush buyers)
    → LOW_IV (IVR < 30)     → +1 bonus point (cheap)

  ↓
[6] SCORE: Bull vs Bear (max ~12 pts, threshold ≥ 5)
    +2  Market structure (HH+HL BULLISH / LH+LL BEARISH)
    +2  EMA stack (price > EMA20 > EMA50 full alignment)
    +1  EMA partial (price > EMA9 > EMA20)
    +1  VWAP position (above = bull, below = bear)
    +1  ADX directional (+DI vs -DI)
    +2  Entry pattern:
          → Confirmed 2-candle breakout (strongest)
          → VWAP bounce/rejection (high prob)
          → Pullback to EMA20 in trend (reliable)
    +1  Retest of broken level (bonus)
    +1  MTF 15min alignment (+DI vs -DI)
    +1  Volume above average
    +1  Low IV bonus
    -2  RSI extreme (> 75 overbought, < 25 oversold)
    -1  Lunch hour soft penalty

  ↓
[7] OPTION SELECTION
    → Low IV  → ATM strike (cheap, more gamma)
    → High IV → slight ITM (more intrinsic, less vega risk)

  ↓
[8] ATR-BASED SL/TARGET
    → SL  = ATR × 1.5 × 3 as % of premium (range: 20–45%)
    → T1  = 1:1 RR point (partial booking)
    → T2  = 1:2 RR point (final target)
```

### Risk Management Flow

```
Trade ENTERED:
  → SL set at ATR-based level
  → Partial target at 1:1 (T1)
  → Final target at 1:2 (T2)

Monitor every 30s:
  → Estimated LTP via spot delta proxy (delta = 0.5)

  If LTP >= T1 (partial target):
    → Exit 50% of position at T1
    → Move SL to breakeven (+0.1%)
    → Record partial P&L
    → Continue monitoring remaining 50%

  If LTP > entry (in profit):
    → Trail SL to capture 60% of peak profit

  If LTP <= SL:
    → Close 100% → SL_HIT

  If LTP >= T2:
    → Close 100% → TARGET_HIT

After each loss:
  → consecutive_losses++
  → If consecutive_losses >= max_consec_losses (default 2):
      → cooldown_until = now + cooldown_minutes (default 20)

Daily checks:
  → daily_pnl <= -(capital × daily_loss_cap%) → stop new trades
  → daily_trades_count >= max_daily_trades → stop new trades
```

---

## IMPLEMENTATION — Step-by-Step

### Step 1: Update Backend Files

Replace these files with v2 versions:
```bash
# All files are already in-place in the ZIP
# If upgrading existing installation, replace:
backend/strategy/indicators.py     ← NEW (ADX, ATR, IV Rank etc)
backend/strategy/signal_engine.py  ← NEW (full strategy rewrite)
backend/core/bot_engine.py         ← NEW (partial booking, cooldown etc)
backend/core/database.py           ← NEW (notifications, new schema)
backend/config.py                  ← NEW (12 new config keys)
backend/api/routes.py              ← NEW (new endpoints)
backend/requirements.txt           ← UPDATED (aiosqlite explicit)
```

### Step 2: Reset Database (IMPORTANT)

The DB schema changed. Delete old DB and let it recreate:
```bash
# Backup old trades first if needed:
cp trading_bot.db trading_bot.db.bak

# Delete old DB — new schema will auto-create on startup:
rm trading_bot.db

# Start backend — DB creates itself:
uvicorn main:app --reload
```

### Step 3: Update Frontend Files

```bash
# Replace these:
frontend/src/app/page.tsx
frontend/src/utils/api.ts
frontend/src/components/Header.tsx
frontend/src/components/PortfolioCard.tsx
frontend/src/components/BotControls.tsx
frontend/src/components/SignalCard.tsx
frontend/src/components/StatsBar.tsx

# New file:
frontend/src/components/NotificationsPanel.tsx
```

### Step 4: Update .env (Backend)

Add new optional config to `.env`:
```bash
# New in v2 — all have sensible defaults
MAX_DAILY_TRADES=5
MAX_OPEN_TRADES=2
MAX_CONSECUTIVE_LOSSES=2
COOLDOWN_MINUTES=20
MIN_SCORE=5

# Filters (true/false)
USE_ADX_FILTER=true
USE_IV_FILTER=true
USE_TIME_FILTER=true
USE_MTF=true
USE_VOLUME_FILTER=true
USE_SPIKE_FILTER=true
```

### Step 5: Test Strategy Locally

```bash
# Start backend
cd backend && uvicorn main:app --reload

# Test signal endpoint (no trade, just preview):
curl http://localhost:8000/api/signal/NIFTY

# Check what filters blocked:
# Look for "blocked_by" field in response

# Test indicators:
curl http://localhost:8000/api/market/indicators/NIFTY
```

---

## NEW API ENDPOINTS

```
POST /api/bot/config          → Live update risk/score/caps without restart
POST /api/bot/filters         → Toggle individual filters on/off live
GET  /api/notifications       → Get notification history
POST /api/notifications/read  → Mark all as read
```

### Live Filter Toggle Example (from cURL)
```bash
# Disable ADX filter (trade in sideways too — not recommended)
curl -X POST http://localhost:8000/api/bot/filters \
  -H "Content-Type: application/json" \
  -d '{"filters": {"use_adx_filter": false}}'

# Raise min score to 7 for higher quality trades only
curl -X POST http://localhost:8000/api/bot/config \
  -H "Content-Type: application/json" \
  -d '{"min_score": 7}'
```

---

## REALISTIC EXPECTATIONS

| Metric | v1 (estimated) | v2 (target) |
|--------|---------------|-------------|
| Trade frequency | High (many bad setups) | Lower (only high-edge setups) |
| Win rate (backtest target) | 40–50% | 55–65% |
| R:R ratio | Fixed 1:2 | Dynamic 1:2+ (ATR based) |
| Sideways market protection | None | Blocked by ADX filter |
| High IV protection | None | Blocked by IV filter |
| Fake breakout protection | None | Confirmed 2-candle pattern |
| Capital efficiency | Poor (fixed lot) | Risk-based position sizing |

**Important**: These are targets, not guarantees. Markets are dynamic. Always paper trade for 30+ days before going live.

---

## TUNING GUIDE

### If bot takes TOO FEW trades:
1. Lower `min_score` from 5 → 4 (dashboard slider)
2. Disable `use_time_filter` (allow opening hour trades)
3. Disable `use_iv_filter` (trade in higher IV)
4. Lower `use_adx_filter` ADX threshold (edit indicators.py: `>= 25` → `>= 20`)

### If bot takes TOO MANY bad trades:
1. Raise `min_score` to 6 or 7
2. Enable all filters
3. Require confirmed breakout only (disable retest bonus in signal_engine.py)
4. Reduce `max_daily_trades` to 3

### If SL too wide (losing too much per trade):
- Lower `atr_mult` in `atr_sl_target()` from 1.5 → 1.0
- This tightens SL but increases chance of SL being hit before target

### If SL too tight (getting stopped out too early):
- Raise `atr_mult` from 1.5 → 2.0
- Options need breathing room — too tight = gets stopped on noise

---

*v2 — Built for capital protection and high-probability entries.*  
*Always paper trade first. Never risk money you cannot afford to lose.*
