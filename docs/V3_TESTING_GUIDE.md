# Options Bot v3 — Complete Testing Checklist & Integration Plan

---

## UPGRADE STEPS (v2 → v3)

### Step 1: New files to add
```
backend/execution/__init__.py       ← NEW module
backend/execution/engine.py         ← Real order execution
backend/execution/sizing.py         ← Adaptive position sizing
backend/intelligence/__init__.py    ← NEW module
backend/intelligence/market_intel.py  ← Events, sentiment, no-trade day
backend/intelligence/strategy_intel.py  ← Per-strategy tracking
backend/btst/__init__.py            ← NEW module
backend/btst/strategy.py            ← BTST overnight strategy
```

### Step 2: Files replaced (v2 → v3)
```
backend/config.py              ← +BTST, +execution, +safety settings
backend/core/database.py       ← +execution_audit, +btst_trades, +strategy_performance
backend/core/bot_engine.py     ← +real execution, +BTST loop, +adaptive sizing
backend/strategy/signal_engine.py  ← +market intel, +adaptive weights, +strategy classification
backend/api/routes.py          ← +BTST, +intelligence, +audit, +halt/resume
```

### Step 3: New frontend components
```
frontend/src/components/MarketStatusPanel.tsx  ← Market regime + IV + sentiment + expiry
frontend/src/components/StrategyAnalytics.tsx  ← Per-strategy win rates + weights
frontend/src/components/BTSTPanel.tsx          ← Overnight position display
```

### Step 4: Database migration
```bash
# The new schema is backward-compatible via CREATE TABLE IF NOT EXISTS
# New columns use ALTER TABLE — run this once:

sqlite3 trading_bot.db "
ALTER TABLE trades ADD COLUMN fill_price REAL DEFAULT 0;
ALTER TABLE trades ADD COLUMN lots INTEGER DEFAULT 1;
ALTER TABLE trades ADD COLUMN lot_size INTEGER DEFAULT 50;
ALTER TABLE trades ADD COLUMN strategy_type TEXT DEFAULT 'UNKNOWN';
ALTER TABLE trades ADD COLUMN confidence TEXT DEFAULT 'LOW';
ALTER TABLE trades ADD COLUMN risk_pct_applied REAL DEFAULT 1.5;
ALTER TABLE trades ADD COLUMN slippage_pct REAL DEFAULT 0;
ALTER TABLE trades ADD COLUMN order_id TEXT DEFAULT '';
ALTER TABLE trades ADD COLUMN btst_trade INTEGER DEFAULT 0;
"
# Or simply delete the DB and let v3 recreate it (loses history):
# rm trading_bot.db
```

### Step 5: New .env variables
```bash
# Add to existing .env:
MAX_LOSS_STREAK_DAY_STOP=3
BTST_ENABLED=false
BTST_RISK_PCT=1.0
RISK_SCORE_LOW=1.0
RISK_SCORE_MID=1.5
RISK_SCORE_HIGH=2.0
RISK_HIGH_ATR_MULT=0.7
RISK_LOSS_STREAK_MULT=0.5
GLOBAL_SENTIMENT_ENABLED=true
NO_TRADE_DAY_AUTO=true
SLIPPAGE_PCT=0.5
ORDER_RETRY_MAX=2
```

---

## TESTING CHECKLIST

### Phase 1: Unit Tests (Backend)

#### Execution Engine
- [ ] `paper_execute()` returns valid result with realistic slippage
- [ ] `paper_execute()` BUY fills above LTP (slippage positive)
- [ ] `paper_execute()` SELL fills below LTP (slippage negative)
- [ ] `execute_order()` retries up to ORDER_RETRY_MAX times on failure
- [ ] Execution audit saved to DB after each order

```bash
# Test manually:
cd backend
python -c "
import asyncio
from execution.engine import paper_execute
result = asyncio.run(paper_execute('NIFTY','CE',24000,'2024-01-25',50,'BUY',142.0))
print(result)
assert result['success'] == True
assert result['fill_price'] > 142.0  # BUY should fill above LTP
print('✅ Paper execution OK')
"
```

#### Adaptive Sizing
- [ ] Score 5 → ~1.0% risk
- [ ] Score 8 → ~2.0% risk
- [ ] High ATR → reduced size
- [ ] 2 consecutive losses → 50% size cut
- [ ] Lot size rounding correct (NIFTY=50, BANKNIFTY=15)

```bash
python -c "
from execution.sizing import calculate_adaptive_size
r1 = calculate_adaptive_size(100000, 5, 142, 30, 50, 24000, 0)
r2 = calculate_adaptive_size(100000, 8, 142, 30, 50, 24000, 0)
r3 = calculate_adaptive_size(100000, 5, 142, 30, 50, 24000, 2)
print(f'Score 5: {r1[\"risk_pct_applied\"]}% | Score 8: {r2[\"risk_pct_applied\"]}% | Streak: {r3[\"risk_pct_applied\"]}%')
assert r1['risk_pct_applied'] < r2['risk_pct_applied'], 'Score scaling failed'
assert r3['risk_pct_applied'] < r1['risk_pct_applied'], 'Streak penalty failed'
print('✅ Adaptive sizing OK')
"
```

#### Market Intelligence
- [ ] `is_expiry_day()` returns True on Thursdays
- [ ] `is_high_impact_event_today()` returns True for blocked dates
- [ ] `get_global_sentiment()` returns valid dict with direction/signal
- [ ] `is_no_trade_day()` returns (bool, reason) tuple
- [ ] Adding/removing blocked dates works

```bash
python -c "
import asyncio
from intelligence.market_intel import *
# Test expiry
print('Expiry day:', is_expiry_day())
# Test blocked dates
add_blocked_date('2099-01-01', 'Test event')
assert '2099-01-01' in get_blocked_dates()
remove_blocked_date('2099-01-01')
assert '2099-01-01' not in get_blocked_dates()
print('✅ Market intel OK')
"
```

#### BTST Strategy
- [ ] `is_btst_entry_window()` True only 14:45–15:10
- [ ] `is_btst_exit_window()` True only 09:20–09:25
- [ ] BTST signal returns NO_BTST outside entry window
- [ ] BTST signal blocks on expiry days
- [ ] `should_exit_btst()` triggers at 40% gap profit

```bash
python -c "
import asyncio
from btst.strategy import generate_btst_signal
result = asyncio.run(generate_btst_signal('NIFTY'))
print('BTST signal:', result['signal_type'], '| Blocked by:', result.get('blocked_by'))
print('✅ BTST strategy OK')
"
```

#### Strategy Classification
- [ ] BREAKOUT trades tagged correctly
- [ ] VWAP trades tagged correctly
- [ ] Performance recording updates DB

```bash
python -c "
import asyncio
from intelligence.strategy_intel import *
asyncio.run(record_strategy_result('BREAKOUT', 1200))
asyncio.run(record_strategy_result('BREAKOUT', -400))
perf = asyncio.run(get_strategy_performance())
bo = next(p for p in perf if p['strategy'] == 'BREAKOUT')
print(f'BREAKOUT: {bo[\"trades\"]} trades, WR={bo[\"win_rate\"]}%, weight={bo[\"weight_mult\"]}')
print('✅ Strategy intel OK')
"
```

---

### Phase 2: API Integration Tests

```bash
# Start backend first
uvicorn main:app --reload

# 1. Health check
curl http://localhost:8000/health

# 2. Market status (new v3 endpoint)
curl http://localhost:8000/api/market/status?symbol=NIFTY | python -m json.tool

# 3. Signal with all filters
curl http://localhost:8000/api/signal/NIFTY | python -m json.tool

# 4. Start bot (paper)
curl -X POST http://localhost:8000/api/bot/start \
  -H "Content-Type: application/json" \
  -d '{"symbol":"NIFTY","capital":100000,"mode":"paper"}'

# 5. Live config update
curl -X POST http://localhost:8000/api/bot/config \
  -H "Content-Type: application/json" \
  -d '{"min_score":6,"risk_pct":1.0,"btst_enabled":true}'

# 6. Add blocked date
curl -X POST http://localhost:8000/api/intelligence/blocked-date \
  -H "Content-Type: application/json" \
  -d '{"date":"2024-12-25","reason":"Christmas"}'

# 7. Strategy performance
curl http://localhost:8000/api/intelligence/strategy-performance

# 8. Halt / resume
curl -X POST http://localhost:8000/api/bot/halt
curl -X POST http://localhost:8000/api/bot/resume

# 9. BTST signal preview
curl http://localhost:8000/api/btst/signal/NIFTY

# 10. Emergency stop
curl -X POST http://localhost:8000/api/bot/emergency-stop
```

---

### Phase 3: Paper Trading Validation (30+ days)

#### Week 1–2: Strategy Quality
- [ ] Run bot daily 09:30–15:00 IST, paper mode
- [ ] Check signal log — confirm SIDEWAYS markets are blocked
- [ ] Confirm HIGH_IV trades are skipped
- [ ] Verify all signals have correct strategy_type classification
- [ ] Check execution audit for slippage values (should be ~0.3–0.8%)
- [ ] Verify partial booking fires at T1 (1:1 RR)
- [ ] Confirm trailing SL moves correctly after T1

#### Metrics to track daily:
```
Signal quality: % blocked by regime vs IV vs time
Win rate by strategy: BREAKOUT vs PULLBACK vs VWAP
Avg slippage: should be <1%
Daily P&L vs daily_loss_cap: never breach
Consecutive losses: cooldown firing correctly?
Drawdown: max_drawdown staying below 5%?
```

#### Week 3–4: BTST Validation
- [ ] Enable BTST: POST /api/bot/config {"btst_enabled": true}
- [ ] Monitor 14:45–15:00 for BTST entries
- [ ] Verify exit at 09:20 next morning
- [ ] Check gap analysis working
- [ ] Compare BTST vs intraday win rate

#### End of month checklist:
- [ ] Win rate ≥ 50% (target 55%+)
- [ ] R:R ratio ≥ 1.5
- [ ] Max drawdown ≤ 5%
- [ ] No day breached daily loss cap
- [ ] All emergency stop triggers working
- [ ] Strategy weights adapting (check weight_mult in strategy_performance)

---

### Phase 4: Live Trading Preparation

#### Pre-live checklist:
- [ ] Angel One demat + SmartAPI registration complete
- [ ] API key, client code, TOTP secret in .env
- [ ] Test Angel login: `asyncio.run(connect_broker())`
- [ ] Test LTP fetch for one option contract
- [ ] Test paper order placement (verify it's NOT paper accidentally)
- [ ] Set MAX_DAILY_TRADES = 2 (very conservative start)
- [ ] Set RISK_PER_TRADE_PCT = 0.5 (half of paper level)
- [ ] Set DAILY_LOSS_CAP_PCT = 1.5 (tighter for live)
- [ ] Confirm broker SMS alerts enabled (independent from bot)

#### Go-live day 1:
- [ ] Start with 1 lot only regardless of sizing calculation
- [ ] Monitor every trade manually
- [ ] Compare fill prices to paper simulation
- [ ] Check actual slippage vs configured SLIPPAGE_PCT
- [ ] Verify order IDs are saved in execution_audit table

#### After 1 week live:
- [ ] Increase to full calculated lot sizes
- [ ] Enable BTST if intraday performing well
- [ ] Review strategy weights — any strategies being auto-disabled?

---

## COMMON ISSUES & FIXES

### "Signal always returns NO_TRADE"
```
1. Check: GET /api/market/status — is no_trade_day=true?
2. Check: GET /api/market/indicators/NIFTY — is regime=SIDEWAYS?
3. Lower min_score: POST /api/bot/config {"min_score": 4}
4. Disable some filters temporarily to debug which is blocking
5. Check signals_log table: SELECT blocked_by, COUNT(*) FROM signals_log GROUP BY blocked_by
```

### "Execution audit shows high slippage"
```
1. Increase SLIPPAGE_PCT in .env (paper mode default: 0.5%)
2. For live: switch to LIMIT orders (ORDER_TYPE=LIMIT in .env)
3. Check if options have sufficient liquidity (volume in options chain)
```

### "BTST never triggers"
```
1. Verify current time is 14:45-15:10 IST
2. Check: is_expiry_day() — Thursday blocks BTST
3. Check ADX: must be ≥ 25
4. Check IV Rank: must be < 60
5. Check confirmed 15min breakout exists
```

### "Strategy weights not adapting"
```
Weights only adapt after 10+ trades per strategy.
Check: GET /api/intelligence/strategy-performance
Verify strategy_type column is being populated in trades table.
```

### "Bot stops unexpectedly"
```
Check notifications: GET /api/notifications?limit=20
Common causes:
- 3 consecutive losses (day stop) → POST /api/bot/resume
- API failure (check logs for Angel/yfinance errors)
- Daily loss cap hit → resets next day automatically
```

---

## PERFORMANCE BENCHMARKS (Realistic Targets)

| Metric | Conservative | Good | Excellent |
|--------|-------------|------|-----------|
| Daily win rate | 45% | 55% | 65% |
| Monthly R:R | 1.2 | 1.8 | 2.5 |
| Max drawdown | <8% | <5% | <3% |
| Trades/day | 2–3 | 3–5 | 4–6 |
| BTST win rate | 45% | 55% | 60% |
| Slippage avg | <1.5% | <0.8% | <0.5% |

**Note**: These are targets for a well-calibrated system after 60+ days of paper trading.
Markets are dynamic. Always validate before increasing capital.

---

## FILE STRUCTURE (v3 Complete)

```
options-bot/
├── backend/
│   ├── main.py
│   ├── config.py           ← UPGRADED
│   ├── requirements.txt    ← UPGRADED
│   ├── api/
│   │   ├── routes.py       ← UPGRADED (+BTST, +intel, +audit)
│   │   └── websocket.py
│   ├── btst/               ← NEW MODULE
│   │   ├── __init__.py
│   │   └── strategy.py     ← BTST signal + exit logic
│   ├── core/
│   │   ├── bot_engine.py   ← UPGRADED (+real exec, +BTST loop, +sizing)
│   │   ├── broker.py
│   │   └── database.py     ← UPGRADED (+audit, +btst_trades, +strategy_perf)
│   ├── data/
│   │   └── market_data.py
│   ├── execution/          ← NEW MODULE
│   │   ├── __init__.py
│   │   ├── engine.py       ← Angel/Fyers/paper with retry + audit
│   │   └── sizing.py       ← Adaptive confidence-based sizing
│   ├── intelligence/       ← NEW MODULE
│   │   ├── __init__.py
│   │   ├── market_intel.py ← Events, sentiment, no-trade day, gap analysis
│   │   └── strategy_intel.py  ← Per-strategy tracking + adaptive weights
│   └── strategy/
│       ├── indicators.py
│       └── signal_engine.py  ← UPGRADED (+intel gates, +adaptive weights)
└── frontend/
    └── src/
        ├── app/page.tsx    ← UPGRADED (+Analytics tab, +BTST)
        ├── components/
        │   ├── MarketStatusPanel.tsx  ← NEW
        │   ├── StrategyAnalytics.tsx  ← NEW
        │   ├── BTSTPanel.tsx          ← NEW
        │   ├── BotControls.tsx        ← UPGRADED (+halt, +BTST, +events)
        │   ├── PortfolioCard.tsx      ← UPGRADED (+day stop, +BTST count)
        │   └── IndicatorsPanel.tsx    ← UPGRADED (+ADX panel, +patterns)
        └── utils/api.ts    ← UPGRADED (+all v3 endpoints)
```
