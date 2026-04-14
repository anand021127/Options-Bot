# 🤖 Options Bot — Complete Deployment Guide (₹0 Cost)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    YOUR PHONE / BROWSER                         │
│                  Next.js Dashboard (Vercel)                     │
└────────────────────┬────────────────────────┬───────────────────┘
                     │ REST API                │ WebSocket (WSS)
                     ▼                         ▼
┌─────────────────────────────────────────────────────────────────┐
│               FastAPI Backend (Render Free Tier)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Bot Engine  │  │ Signal Engine│  │   WebSocket Manager  │  │
│  │  (Trading    │  │  (Strategy   │  │  (Real-time updates) │  │
│  │   Loop)      │  │   Logic)     │  │                      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘  │
│         │                 │                                      │
│  ┌──────▼─────────────────▼──────────────────────────────────┐  │
│  │             SQLite Database (Render disk)                  │  │
│  └───────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │  yfinance (free)
                            ▼
                    Yahoo Finance API
                 (Price, OHLCV, Options)
```

---

## PHASE 1: Local Setup & Testing

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### 1. Clone / Setup

```bash
# Create project directory
mkdir options-bot && cd options-bot

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env
cp .env.example .env              # Edit with your values
```

### 2. Run Backend Locally

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Open: http://localhost:8000/docs  (Swagger UI — test all endpoints)

### 3. Run Frontend Locally

```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local:
#   NEXT_PUBLIC_API_URL=http://localhost:8000
#   NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws

npm run dev
```

Open: http://localhost:3000

### 4. Test Paper Trading

1. Open dashboard at http://localhost:3000
2. Click "Configure & Start" → set capital to ₹1,00,000
3. Select "Paper" mode → click "Start Bot"
4. Go to Signal tab → click Refresh to generate a signal manually
5. Watch trade appear in Open Positions when signal triggers
6. Monitor equity curve and P&L

---

## PHASE 2: Free Cloud Deployment

### Step 1: Deploy Backend to Render

1. **Create account**: https://render.com (free, no card needed)

2. **Push backend to GitHub**:
   ```bash
   cd backend
   git init
   git add .
   git commit -m "Initial options bot backend"
   git remote add origin https://github.com/YOUR_USERNAME/options-bot-backend.git
   git push -u origin main
   ```

3. **Create Web Service on Render**:
   - New → Web Service
   - Connect your GitHub repo
   - Settings:
     - **Runtime**: Python 3
     - **Build**: `pip install -r requirements.txt`
     - **Start**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
     - **Instance**: Free

4. **Set Environment Variables** on Render:
   ```
   APP_ENV=production
   SECRET_KEY=<generate-random-32-char-string>
   ALLOWED_ORIGINS=["https://your-app.vercel.app"]
   DEFAULT_CAPITAL=100000
   DEFAULT_SYMBOL=NIFTY
   ```

5. **Copy your Render URL**: `https://options-bot-xxxx.onrender.com`

### Step 2: Deploy Frontend to Vercel

1. **Create account**: https://vercel.com (free, no card needed)

2. **Push frontend to GitHub**:
   ```bash
   cd frontend
   git init
   git add .
   git commit -m "Initial options bot dashboard"
   git remote add origin https://github.com/YOUR_USERNAME/options-bot-frontend.git
   git push -u origin main
   ```

3. **Import on Vercel**:
   - New Project → Import your frontend repo
   - Framework: Next.js (auto-detected)
   - Add Environment Variables:
     ```
     NEXT_PUBLIC_API_URL=https://options-bot-xxxx.onrender.com
     NEXT_PUBLIC_WS_URL=wss://options-bot-xxxx.onrender.com/ws
     ```
   - Deploy!

4. **Update Render** ALLOWED_ORIGINS with your Vercel URL.

### Step 3: Prevent Render Sleep (Free Tier Fix)

Render free tier sleeps after 15 minutes of no traffic. Fix with GitHub Actions:

Create `.github/workflows/keep-alive.yml`:
```yaml
name: Keep Backend Alive
on:
  schedule:
    - cron: '*/10 3-12 * * 1-5'  # Every 10min, Mon-Fri 09:00-18:00 IST (UTC+5:30)
  workflow_dispatch:

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping backend
        run: curl -f https://options-bot-xxxx.onrender.com/health
```

This uses GitHub Actions free tier (2000 min/month) — plenty for this.

---

## PHASE 3: Live Trading Setup

### Free Broker Options for India

| Broker       | API Cost    | Notes                                          |
|--------------|-------------|------------------------------------------------|
| **Zerodha**  | ₹2000/year  | Best API (Kite Connect). Not free but cheapest |
| **AngelOne** | FREE        | Smart API — genuinely free                     |
| **Dhan**     | FREE        | Free API, good docs                            |
| **Upstox**   | FREE        | Free API tier available                        |

### Recommended: AngelOne Smart API (FREE)

1. Open demat account at AngelOne (free)
2. Get API access from SmartAPI portal
3. Add to backend `.env`:
   ```
   BROKER=angel
   BROKER_API_KEY=your_api_key
   BROKER_CLIENT_ID=your_client_id
   BROKER_PASSWORD=your_mpin
   BROKER_TOTP_SECRET=your_totp_secret
   ```
4. Switch dashboard to "Live" mode

### Live Order Execution (Add to backend)

```python
# backend/core/live_broker.py
# Uses SmartAPI (AngelOne) — free

from SmartApi import SmartConnect
import pyotp

def get_broker_session(api_key, client_id, password, totp_secret):
    obj = SmartConnect(api_key=api_key)
    totp = pyotp.TOTP(totp_secret).now()
    data = obj.generateSession(client_id, password, totp)
    return obj, data["data"]["jwtToken"]

async def place_order(obj, symbol, option_type, strike, qty, action="BUY"):
    order_params = {
        "variety": "NORMAL",
        "tradingsymbol": f"NIFTY{strike}{option_type}",  # Format varies
        "symboltoken": "...",  # Look up via searchScrip
        "transactiontype": action,
        "exchange": "NFO",
        "ordertype": "MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "quantity": qty,
    }
    return obj.placeOrder(order_params)
```

---

## System Limits (Free Tier)

| Constraint                    | Free Limit            | Impact                              |
|-------------------------------|-----------------------|-------------------------------------|
| yfinance data delay           | ~15 min               | Paper trading only; not HFT         |
| Render free RAM               | 512 MB                | Sufficient for this bot             |
| Render free sleep             | After 15 min idle     | Fixed by keep-alive GitHub Action   |
| Vercel bandwidth              | 100 GB/month          | Way more than needed                |
| MongoDB Atlas                 | 512 MB storage        | Swap SQLite to Atlas when needed    |
| yfinance API rate limit       | ~2000 req/day         | 1 req/min × 7hrs = 420/day ✓        |

---

## Bot Settings Reference

| Setting             | Default  | Description                            |
|---------------------|----------|----------------------------------------|
| `DEFAULT_CAPITAL`   | ₹1,00,000| Starting paper capital                 |
| `RISK_PER_TRADE_PCT`| 1.5%     | Risk ₹1,500 per trade on 1L capital    |
| `DAILY_LOSS_CAP_PCT`| 3.0%     | Stop after ₹3,000 daily loss           |
| `REWARD_RATIO`      | 2.0      | Target = 2× stop loss distance        |
| `DATA_FETCH_INTERVAL`| 60s     | Signal check every 60 seconds          |
| `MIN_SCORE`         | 4/10     | Min confidence to take a trade         |

---

## Folder Structure

```
options-bot/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings from .env
│   ├── requirements.txt         # Python dependencies
│   ├── render.yaml              # Render deployment config
│   ├── api/
│   │   ├── routes.py            # REST API endpoints
│   │   └── websocket.py         # WebSocket manager
│   ├── core/
│   │   ├── bot_engine.py        # Main trading loop
│   │   └── database.py          # SQLite CRUD
│   ├── data/
│   │   └── market_data.py       # yfinance data fetcher
│   ├── strategy/
│   │   ├── signal_engine.py     # Signal scoring system
│   │   └── indicators.py        # EMA, VWAP, S/R, breakout
│   └── utils/
│       └── keep_alive.py        # Render keep-alive pinger
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx       # Root layout
│   │   │   └── page.tsx         # Main dashboard page
│   │   ├── components/
│   │   │   ├── Header.tsx       # Top bar + symbol selector
│   │   │   ├── PortfolioBar.tsx # Scrollable stats bar
│   │   │   ├── BotControls.tsx  # Start/Stop/Emergency
│   │   │   ├── PriceCard.tsx    # Live price display
│   │   │   ├── IndicatorCard.tsx# EMA/VWAP/RSI/Structure
│   │   │   ├── EquityChart.tsx  # Recharts equity curve
│   │   │   ├── OpenTrades.tsx   # Live positions
│   │   │   ├── TradeHistory.tsx # Closed trades log
│   │   │   ├── SignalPanel.tsx  # Signal analysis view
│   │   │   ├── OptionsChain.tsx # CE/PE chain table
│   │   │   └── AlertToast.tsx   # Real-time notifications
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts  # Auto-reconnect WS hook
│   │   ├── utils/
│   │   │   └── api.ts           # All API calls
│   │   └── styles/
│   │       └── globals.css      # Dark theme + fonts
│   ├── package.json
│   ├── tailwind.config.js
│   ├── next.config.js
│   └── tsconfig.json
│
└── docs/
    └── DEPLOYMENT.md            # This file
```

---

## Troubleshooting

| Problem                        | Solution                                            |
|--------------------------------|-----------------------------------------------------|
| Bot not taking trades          | Lower MIN_SCORE to 3 in signal_engine.py            |
| Options chain empty            | yfinance may not have NSE options — try BANKNIFTY   |
| Render keeps sleeping          | Set up GitHub Actions keep-alive (Step 3 above)     |
| WebSocket disconnects          | The hook auto-reconnects every 3 seconds            |
| Price data stale               | Reduce DATA_FETCH_INTERVAL to 30s in config.py      |
| CORS errors                    | Update ALLOWED_ORIGINS in Render env vars           |

---

## Upgrade Path (Optional Paid)

| From (Free)        | To (Paid)              | Benefit                           | Cost      |
|--------------------|------------------------|-----------------------------------|-----------|
| Render free        | Render starter         | No sleep, 512MB→2GB RAM           | $7/mo     |
| SQLite             | MongoDB Atlas M2       | Better querying, backups          | $9/mo     |
| yfinance           | Upstox/Zerodha data    | Real-time streaming               | ₹2000/yr  |
| Paper trading      | AngelOne live          | Real order execution              | Free API  |
| Manual keep-alive  | UptimeRobot free       | Better monitoring                 | Free      |
