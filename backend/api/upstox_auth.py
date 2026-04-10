"""
Upstox OAuth Authentication
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW IT WORKS:
  1. Frontend calls GET /api/upstox/login  → gets the Upstox login URL
  2. You open that URL on your phone/browser → login with Upstox credentials
  3. Upstox redirects to your callback URL with a `code`
  4. Backend exchanges code for access_token → saves it to DATABASE
  5. Token survives Render restarts (stored in DB, not just in memory)
  6. Bot reads token from DB every time it needs to place an order

TOKEN LIFETIME: Upstox tokens expire daily at midnight.
  → You need to login ONCE per day (takes 30 seconds on mobile)
  → The frontend will show a "Login Required" button when token is expired
"""

import aiosqlite
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
import httpx
from loguru import logger
from config import settings

router = APIRouter()

DB_PATH = "trading_bot.db"


# ─── Token storage in database ────────────────────────────────────────────────

async def save_upstox_token(access_token: str):
    """Save Upstox access token to database so it survives server restarts."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)",
            ("upstox_access_token", access_token)
        )
        await db.commit()
    logger.info("✅ Upstox access token saved to database")


async def get_upstox_token() -> str:
    """
    Get Upstox token. Priority:
    1. Database (saved after OAuth login)
    2. Environment variable (set in Render as fallback)
    """
    # Try DB first (most up-to-date)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT value FROM bot_config WHERE key = 'upstox_access_token'"
        )
        row = await cur.fetchone()
        if row and row[0]:
            return row[0]

    # Fallback to env variable
    if settings.UPSTOX_ACCESS_TOKEN:
        return settings.UPSTOX_ACCESS_TOKEN

    return ""


async def clear_upstox_token():
    """Clear expired token from database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)",
            ("upstox_access_token", "")
        )
        await db.commit()


# ─── API Endpoints ────────────────────────────────────────────────────────────

@router.get("/login")
async def upstox_login():
    """
    Step 1: Get the Upstox login URL.
    Frontend opens this URL → user logs in → Upstox redirects to /callback.
    """
    if not settings.UPSTOX_API_KEY:
        return {"error": "UPSTOX_API_KEY not set in environment variables"}

    login_url = (
        f"https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code"
        f"&client_id={settings.UPSTOX_API_KEY}"
        f"&redirect_uri={settings.UPSTOX_REDIRECT_URI}"
    )
    return {"login_url": login_url}


@router.get("/callback")
async def upstox_callback(code: str):
    """
    Step 2: Upstox calls this after user logs in.
    Exchanges auth code for access token and saves it to database.
    """
    if not settings.UPSTOX_API_KEY:
        return {"error": "UPSTOX_API_KEY not configured"}

    token_url = "https://api.upstox.com/v2/login/authorization/token"
    payload = {
        "code":          code,
        "client_id":     settings.UPSTOX_API_KEY,
        "client_secret": settings.UPSTOX_API_SECRET,
        "redirect_uri":  settings.UPSTOX_REDIRECT_URI,
        "grant_type":    "authorization_code",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(token_url, data=payload, headers=headers)
        data = resp.json()

        access_token = data.get("access_token")
        if not access_token:
            logger.error(f"Upstox token exchange failed: {data}")
            return {"error": "Token exchange failed", "details": data}

        # SAVE TOKEN TO DATABASE — this is the key fix
        await save_upstox_token(access_token)

        logger.info("✅ Upstox login successful, token saved")
        return {
            "status":  "success",
            "message": "✅ Upstox login successful! Token saved. You can now start the bot in Live mode.",
            "token_preview": access_token[:20] + "...",
        }

    except Exception as e:
        logger.error(f"Upstox callback error: {e}")
        return {"error": str(e)}


@router.get("/status")
async def upstox_status():
    """Check if a valid Upstox token exists."""
    token = await get_upstox_token()
    if not token:
        return {
            "connected":   False,
            "message":     "Not logged in. Click Login to connect Upstox.",
            "login_required": True,
        }

    # Quick validation — try to fetch profile
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://api.upstox.com/v2/user/profile",
                headers={"Authorization": f"Bearer {token}"}
            )
        if resp.status_code == 200:
            profile = resp.json().get("data", {})
            return {
                "connected":   True,
                "message":     "✅ Upstox connected",
                "name":        profile.get("user_name", ""),
                "login_required": False,
            }
        else:
            # Token expired
            await clear_upstox_token()
            return {
                "connected":   False,
                "message":     "Token expired. Please login again.",
                "login_required": True,
            }
    except Exception:
        return {
            "connected":   False,
            "message":     "Could not verify token",
            "login_required": True,
        }


@router.post("/logout")
async def upstox_logout():
    """Clear the saved token."""
    await clear_upstox_token()
    return {"status": "logged_out"}
