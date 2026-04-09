# 📘 Options Trading Bot — Complete Documentation
## Zero-Cost NSE Options Trading Bot

---

## 1. ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                        FREE CLOUD STACK                         │
├──────────────────────────┬──────────────────────────────────────┤
│   FRONTEND (Vercel)      │      BACKEND (Render)                │
│   Next.js 14             │      FastAPI + Python                │
│   TailwindCSS            │      WebSocket Server                │
│   TradingView Widget     │      APScheduler                     │
│   Recharts               │      SQLite / MongoDB Atlas          │
├──────────────────────────┴──────────────────────────────────────┤
│                     DATA SOURCES (FREE)                         │
│   yfinance → Yahoo Finance API (15-min delayed)                 │
│   NSE public endpoints (via yfinance)                           │
└─────────────────────────────────────────────────────────────────┘

Data Flow:
  Yahoo Finance → yfinance → FastAPI → WebSocket → Next.js Dashboard
                                    ↕
                              SQLite DB (trades, equity, config)
```

---

## 2. COMPLETE FOLDER STRUCTURE

```
options-bot/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Settings (env vars)
│   ├── requirements.txt           # Python deps
│   ├── render.yaml                # Render deploy config
│   ├── trading_bot.db             # SQLite (auto-created)
│   ├── .env                       # Local env (never commit!)
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # REST endpoints
│   │   └── websocket.py           # WS manager + /ws endpoint
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── bot_engine.py          # Main trading loop
│   │   └── database.py            # SQLite CRUD + schema
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   └── market_data.py         # yfinance wrapper + cache
│   │
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── indicators.py          # EMA, VWAP, S/R, RSI, structure
│   │   └── signal_engine.py       # Signal scoring + position sizing
│   │
│   └── utils/
│       ├── __init__.py
│       └── keep_alive.py          # Ping script (prevents Render sleep)
│
└── frontend/
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── .env.example               # Copy → .env.local
    │
    └── src/
        ├── app/
        │   ├── layout.tsx          # Root layout + Google Fonts
        │   └── page.tsx            # Dashboard main page
        │
        ├── components/
        │   ├── Header.tsx          # Price ticker + WS status
        │   ├── PortfolioCard.tsx   # Capital + P&L summary
        │   ├── BotControls.tsx     # Start/Stop/Emergency buttons
        │   ├── SignalCard.tsx      # Live signal + scoring display
        │   ├── OpenTrades.tsx      # Active positions
        │   ├── TradeHistory.tsx    # Closed trades list
        │   ├── EquityCurve.tsx     # Recharts area chart
        │   ├── MarketChart.tsx     # TradingView free widget
        │   ├── IndicatorsPanel.tsx # EMA/VWAP/RSI/Structure
        │   └── StatsBar.tsx        # Win rate, totals bar
        │
        ├── hooks/
        │   └── useWebSocket.ts     # WS hook with auto-reconnect
        │
        ├── utils/
        │   └── api.ts              # Typed API client
        │
        └── styles/
            └── globals.css         # Tailwind + custom CSS vars
```

---

## 3. STEP-BY-STEP DEPLOYMENT GUIDE (100% FREE)

### STEP 1: Prerequisites
```bash
# Install locally
python 3.10+   → https://python.org
node 18+       → https://nodejs.org
git            → https://git-scm.com
```

### STEP 2: Clone and set up backend locally
```bash
cd options-bot/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env — set SECRET_KEY to any random string

# Run locally
uvicorn main:app --reload --port 8000

# Test: http://localhost:8000/health  → should return {"status":"healthy"}
```

### STEP 3: Set up frontend locally
```bash
cd options-bot/frontend

# Install dependencies
npm install

# Create local env
cp .env.example .env.local
# Edit .env.local:
#   NEXT_PUBLIC_API_URL=http://localhost:8000
#   NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws

# Run dev server
npm run dev

# Open: http://localhost:3000
```

### STEP 4: Push to GitHub
```bash
cd options-bot

# Initialize git
git init
echo "backend/venv/" >> .gitignore
echo "backend/.env" >> .gitignore
echo "backend/trading_bot.db" >> .gitignore
echo "frontend/.env.local" >> .gitignore
echo "frontend/node_modules/" >> .gitignore
echo "frontend/.next/" >> .gitignore

git add .
git commit -m "Initial commit: Options Trading Bot"

# Push to GitHub (create repo first at github.com)
git remote add origin https://github.com/YOUR_USERNAME/options-bot.git
git push -u origin main
```

### STEP 5: Deploy Backend to Render (FREE)

1. Go to → https://render.com → Sign up free
2. Click **New** → **Web Service**
3. Connect your GitHub repo
4. Configure:
   ```
   Name:          options-bot-backend
   Root Directory: backend
   Runtime:       Python 3
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
   Instance Type: Free
   ```
5. Add Environment Variables:
   ```
   APP_ENV          = production
   SECRET_KEY       = <generate a long random string>
   ALLOWED_ORIGINS  = ["https://your-frontend.vercel.app"]
   DEFAULT_CAPITAL  = 100000
   DEFAULT_SYMBOL   = NIFTY
   ```
6. Click **Deploy**
7. Wait ~3 minutes. Copy your Render URL:
   `https://options-bot-backend.onrender.com`

### STEP 6: Deploy Frontend to Vercel (FREE)

1. Go to → https://vercel.com → Sign up free
2. Click **Add New Project** → Import from GitHub
3. Select your repo, set **Root Directory** to `frontend`
4. Add Environment Variables:
   ```
   NEXT_PUBLIC_API_URL = https://options-bot-backend.onrender.com
   NEXT_PUBLIC_WS_URL  = wss://options-bot-backend.onrender.com/ws
   ```
5. Click **Deploy**
6. Copy your Vercel URL: `https://options-bot.vercel.app`

### STEP 7: Update Render CORS
Go back to Render → Environment Variables → Update:
```
ALLOWED_ORIGINS = ["https://options-bot.vercel.app"]
```
Redeploy Render service.

### STEP 8: Keep-Alive (Prevent Render Sleep)

**Option A: GitHub Actions (Recommended — completely free)**

Create file `.github/workflows/keep_alive.yml` in your repo:

```yaml
name: Keep Render Alive
on:
  schedule:
    - cron: '*/10 3-12 * * 1-5'   # Every 10 min, Mon-Fri 9-6 IST (UTC 3-12)
  workflow_dispatch:

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping backend
        run: |
          curl -f https://options-bot-backend.onrender.com/health
          echo "Pinged at $(date)"
```

**Option B: UptimeRobot (free tier)**
1. Register at https://uptimerobot.com (free)
2. Add monitor → HTTP(S) → your Render URL + `/health`
3. Set interval: 5 minutes

---

## 4. STRATEGY LOGIC EXPLAINED

### Signal Scoring System (out of 10 points)

```
BULLISH signals (BUY CE):
  +2  Market Structure BULLISH (HH + HL confirmed)
  +2  Price > EMA20 > EMA50 (full trend alignment)
  +1  Price > EMA20 only (partial)
  +1  Price > VWAP
  +2  Breakout above resistance
  +1  Retest of broken resistance as support
  +1  Volume above 20-period average
  -1  RSI > 75 (overbought penalty)

BEARISH signals (BUY PE):
  +2  Market Structure BEARISH (LH + LL confirmed)
  +2  Price < EMA20 < EMA50
  +1  Price < EMA20 only
  +1  Price < VWAP
  +2  Breakout below support
  +1  Retest of broken support as resistance
  +1  Volume above average
  -1  RSI < 25 (oversold penalty)

Minimum score to trade: 4/10
```

### Risk Management Rules
```
Risk per trade:   1.5% of capital (configurable)
Daily loss cap:   3% of initial capital (bot pauses)
SL on option:     30% of premium paid
Target on option: 60% of premium paid (1:2 RR)
Trailing SL:      Moves to 50% of profit once in profit
Max open trades:  2 simultaneous positions
Cooldown:         15 minutes after any losing trade
```

### Option Selection
```
Type:   ATM (At-The-Money) — closest strike to spot price
Expiry: Nearest weekly expiry
Entry:  CE for bullish signal, PE for bearish
```

---

## 5. API ENDPOINTS REFERENCE

```
GET  /health                     → Health check (used for keep-alive)
GET  /api/bot/status             → Bot running state + portfolio
POST /api/bot/start              → Start bot {symbol, capital, mode}
POST /api/bot/stop               → Stop bot gracefully
POST /api/bot/emergency-stop     → Close all + stop immediately

GET  /api/market/price/{symbol}  → Live price + OHLC
GET  /api/market/options/{symbol}→ Options chain (CE + PE)
GET  /api/market/indicators/{sym}→ EMA/VWAP/RSI/S&R snapshot
GET  /api/market/candles/{symbol}→ OHLCV data for charting

GET  /api/trades/open            → Active positions
GET  /api/trades/history         → Closed trade history
GET  /api/trades/stats           → Win rate, P&L, etc.
GET  /api/trades/equity-curve    → Time series for chart

GET  /api/signal/{symbol}        → Preview signal (no trade taken)
GET  /api/config                 → Current bot config
PUT  /api/config                 → Update config {risk_pct, symbol...}

WS   /ws                         → Real-time event stream
```

### WebSocket Events (server → client)
```json
{"event": "bot_status",       "data": {"running": true, "mode": "paper"}}
{"event": "portfolio_update", "data": {"capital": 99500, "daily_pnl": -500}}
{"event": "signal",           "data": {"signal_type": "BUY_CE", "score": 6, ...}}
{"event": "trade_entered",    "data": {"id": 42, "strike": 24000, ...}}
{"event": "trade_closed",     "data": {"id": 42, "pnl": 1200, "status": "TARGET_HIT"}}
{"event": "alert",            "data": {"message": "Daily loss cap hit"}}
{"event": "emergency_stop",   "data": {"message": "All positions closed"}}
```

---

## 6. PHASE 2: LIVE TRADING SETUP

### Free Broker API Options (India)

#### Option A: Zerodha Kite Connect
- API cost: ₹2,000/month (NOT free)
- Workaround: Use Kite's free web automation with Playwright (unofficial)

#### Option B: Angel One SmartAPI (RECOMMENDED — FREE)
- API is completely FREE with Angel One demat account
- Register: https://smartapi.angelbroking.com
- Steps:
  1. Open Angel One demat (free)
  2. Register app at SmartAPI portal
  3. Get API key, client code, TOTP secret
  4. Add to .env:
     ```
     BROKER=angel
     BROKER_API_KEY=your_api_key
     BROKER_CLIENT_CODE=your_client_code
     BROKER_TOTP_SECRET=your_totp_secret
     ```
  5. Install: `pip install smartapi-python pyotp`

#### Option C: Fyers API (FREE)
- Free API with Fyers account
- Register: https://myapi.fyers.in

#### Option D: Upstox API (FREE)
- Free API with Upstox account
- Register: https://developer.upstox.com

### Live Trading Safety Checklist
```
✅ Paper trade for at least 1 month first
✅ Verify signal accuracy manually before going live
✅ Start with smallest possible capital
✅ Set strict daily loss cap (₹500 max to start)
✅ Test emergency stop button
✅ Never leave live bot unattended
✅ Enable broker SMS/email alerts separately
✅ Keep broker app open on phone as backup
```

---

## 7. FREE TIER LIMITATIONS

| Service      | Free Limit                    | Impact                          | Workaround                       |
|-------------|-------------------------------|----------------------------------|----------------------------------|
| Render       | Sleeps after 15min idle       | Bot pauses when no users online  | GitHub Actions keep-alive pings  |
| Render       | 512MB RAM                     | Can't run heavy ML models        | Stick to TA indicators (fine)    |
| Render       | 750 hrs/month                 | ~31 days = barely enough         | One service only                 |
| yfinance     | 15-min delayed options data   | Can't scalp / high-frequency     | Use for swing/positional signals |
| yfinance     | Rate limits (unofficial API)  | Occasional fetch failures        | Aggressive caching (60s TTL)     |
| SQLite       | No concurrent writes          | Single-user fine                 | Upgrade to Postgres for teams    |
| Vercel       | 100GB bandwidth/month         | Should be more than enough       | None needed                      |
| GitHub Actions| 2000 min/month free          | Keep-alive needs ~900 min/month  | Well within limit                |

---

## 8. UPGRADE PATH (Optional — when profitable)

### Tier 1 — ₹500/month
- **Render Starter**: Always-on server, 1GB RAM
- **MongoDB Atlas M2**: Better concurrent DB
- → Enables: Faster polling (30s), multiple symbols

### Tier 2 — ₹2,000/month
- **Zerodha Kite Connect API**: True real-time data + order execution
- → Enables: Real-time options chain, instant order execution

### Tier 3 — ₹5,000/month
- **Dedicated VPS** (DigitalOcean/Hetzner): Full control
- **True tick data** (Truedata/Global Datafeeds): Millisecond precision
- → Enables: High-frequency, multi-strategy, backtesting

---

## 9. LOCAL DEVELOPMENT QUICK START

```bash
# Terminal 1 — Backend
cd options-bot/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Terminal 2 — Frontend
cd options-bot/frontend
npm install && npm run dev

# Open dashboard: http://localhost:3000
# API docs:       http://localhost:8000/docs   ← Swagger UI (auto-generated!)
```

---

## 10. TROUBLESHOOTING

### "No data returned from yfinance"
- yfinance has unofficial rate limits. Wait 60 seconds and retry.
- Market closed? Data still returns but with last closing prices.
- Try: `import yfinance as yf; yf.download("^NSEI", period="1d")`

### "WebSocket keeps disconnecting"
- Render free tier may throttle long-lived connections.
- The `useWebSocket` hook auto-reconnects every 3 seconds.
- Check browser console for WS errors.

### "Bot generates NO_TRADE for hours"
- This is correct — the bot waits for genuine signals.
- Check `/api/signal/NIFTY` to see current score.
- Reduce `MIN_SCORE` in `signal_engine.py` from 4 to 3 for more trades.
- During sideways/low-volatility markets, signals are rare by design.

### "Options chain returns empty"
- yfinance options data is US-market focused. NSE options have limited coverage.
- The bot falls back to simulated ATM pricing when chain data unavailable.
- For production, upgrade to Angel SmartAPI for proper NSE options chain.

### "Render build fails"
- Check Python version: Render uses 3.11 by default.
- Add `runtime.txt` with content `python-3.11.0` to backend folder.

---

## 11. ENVIRONMENT VARIABLES REFERENCE

### Backend (.env)
```bash
APP_ENV=development
SECRET_KEY=your-super-secret-key-here

# CORS — add your Vercel URL in production
ALLOWED_ORIGINS=["http://localhost:3000"]

# SQLite (default) — no setup needed
DATABASE_URL=sqlite+aiosqlite:///./trading_bot.db

# Trading params
DEFAULT_SYMBOL=NIFTY
DEFAULT_CAPITAL=100000
RISK_PER_TRADE_PCT=1.5
DAILY_LOSS_CAP_PCT=3.0
REWARD_RATIO=2.0
DATA_FETCH_INTERVAL=60

# Broker (Phase 2 only)
BROKER=none
BROKER_API_KEY=
BROKER_API_SECRET=
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

---

*Built with ❤️ for Indian retail traders. Trade responsibly.*
*This is for educational/research purposes. Not financial advice.*
