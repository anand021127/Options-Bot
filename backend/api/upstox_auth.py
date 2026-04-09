from fastapi import APIRouter
import requests
import os

router = APIRouter()

UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")
UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET")
REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")

@router.get("/login")
def upstox_login():
    url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={UPSTOX_API_KEY}&redirect_uri={REDIRECT_URI}"
    return {"login_url": url}


@router.get("/callback")
def upstox_callback(code: str):
    token_url = "https://api.upstox.com/v2/login/authorization/token"

    payload = {
        "code": code,
        "client_id": UPSTOX_API_KEY,
        "client_secret": UPSTOX_API_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(token_url, data=payload, headers=headers)
    data = response.json()

    access_token = data.get("access_token")

    return {
        "access_token": access_token
    }
