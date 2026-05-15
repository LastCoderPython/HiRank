from fastapi import APIRouter, Request, Response, HTTPException, Cookie, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import httpx
import json
import jwt
import os
from datetime import datetime, timedelta
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

SUPABASE_URL = settings.supabase_url
SUPABASE_ANON_KEY = settings.supabase_anon_key
SUPABASE_JWT_SECRET = settings.supabase_jwt_secret
FRONTEND_URL = settings.frontend_url


def _get_supabase_project_url() -> Optional[str]:
    if not SUPABASE_URL:
        return None

    url = SUPABASE_URL.strip().rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    return url


async def _exchange_code_for_session(project_url: str, code: str, redirect_uri: str) -> Optional[dict]:
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }

    payloads = [
        {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        {"grant_type": "authorization_code", "auth_code": code, "redirect_uri": redirect_uri},
        {"grant_type": "pkce", "code": code},
        {"grant_type": "pkce", "auth_code": code},
    ]

    async with httpx.AsyncClient(timeout=15.0) as client:
        for payload in payloads:
            response = await client.post(
                f"{project_url}/auth/v1/token",
                json=payload,
                headers=headers,
            )
            if response.status_code != 200:
                continue

            data = response.json()
            if data.get("access_token") and data.get("refresh_token"):
                return data

    return None

class SessionResponse(BaseModel):
    authenticated: bool
    user: Optional[dict] = None

def verify_jwt(token: str) -> Optional[dict]:
    if not SUPABASE_JWT_SECRET:
        return None

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def fetch_user_from_supabase(access_token: str) -> Optional[dict]:
    project_url = _get_supabase_project_url()
    if not project_url or not SUPABASE_ANON_KEY:
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{project_url}/auth/v1/user",
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {access_token}",
                },
            )

        if response.status_code != 200:
            return None

        user_data = response.json()
        user_metadata = user_data.get("user_metadata") or {}
        email = user_data.get("email", "")
        return {
            "id": user_data.get("id"),
            "email": email,
            "name": user_metadata.get("full_name") or user_metadata.get("name") or (email.split("@")[0] if email else "User"),
            "avatar_url": user_metadata.get("avatar_url") or user_metadata.get("picture"),
        }
    except Exception:
        return None

def get_current_user(
    sb_access_token: Optional[str] = Cookie(None),
    sb_refresh_token: Optional[str] = Cookie(None)
) -> Optional[dict]:
    if not sb_access_token:
        return None
    
    payload = verify_jwt(sb_access_token)
    if payload:
        user_id = payload.get("sub")
        email = payload.get("email")
        user_metadata = payload.get("user_metadata", {})
        return {
            "id": user_id,
            "email": email,
            "name": user_metadata.get("full_name") or user_metadata.get("name") or email.split("@")[0],
            "avatar_url": user_metadata.get("avatar_url") or user_metadata.get("picture")
        }
    return None

@router.get("/session")
async def get_session(
    request: Request,
    sb_access_token: Optional[str] = Cookie(None)
):
    if not sb_access_token:
        return {"authenticated": False, "user": None}
    
    payload = verify_jwt(sb_access_token)
    if payload:
        user_id = payload.get("sub")
        email = payload.get("email")
        user_metadata = payload.get("user_metadata", {})

        user = {
            "id": user_id,
            "email": email,
            "name": user_metadata.get("full_name") or user_metadata.get("name") or email.split("@")[0],
            "avatar_url": user_metadata.get("avatar_url") or user_metadata.get("picture")
        }

        return {"authenticated": True, "user": user}

    user = await fetch_user_from_supabase(sb_access_token)
    if user:
        return {"authenticated": True, "user": user}

    return {"authenticated": False, "user": None}

@router.get("/login")
async def login(request: Request):
    project_url = _get_supabase_project_url()
    if not project_url:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    
    host = request.headers.get("host", "localhost:9000")
    scheme = request.url.scheme
    redirect_uri = f"{scheme}://{host}/api/auth/callback"
    
    auth_url = (
        f"{project_url}/auth/v1/authorize"
        f"?provider=google"
        f"&redirect_to={redirect_uri}"
    )
    
    return RedirectResponse(url=auth_url)

@router.get("/callback")
async def auth_callback(
    request: Request,
    code: Optional[str] = None,
    error: Optional[str] = None
):
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth_error={error}")
    
    if not code:
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth_error=no_code")
    
    project_url = _get_supabase_project_url()
    if not project_url:
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth_error=config_error")

    host = request.headers.get("host", "localhost:9000")
    scheme = request.url.scheme
    redirect_uri = f"{scheme}://{host}/api/auth/callback"

    data = await _exchange_code_for_session(project_url, code, redirect_uri)
    if not data:
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth_error=token_exchange_failed")

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    expires_in = data.get("expires_in", 3600)

    if not access_token or not refresh_token:
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth_error=token_missing")
    
    response = RedirectResponse(url=f"{FRONTEND_URL}/chat")
    
    response.set_cookie(
        key="sb_access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=expires_in,
        path="/"
    )
    
    response.set_cookie(
        key="sb_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
        path="/"
    )
    
    return response

@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    sb_refresh_token: Optional[str] = Cookie(None)
):
    if not sb_refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    
    project_url = _get_supabase_project_url()
    if not project_url:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{project_url}/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": sb_refresh_token},
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Content-Type": "application/json"
            }
        )
        
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Token refresh failed")
        
        data = resp.json()
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token", sb_refresh_token)
        expires_in = data.get("expires_in", 3600)
    
    response.set_cookie(
        key="sb_access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=expires_in,
        path="/"
    )
    
    if refresh_token != sb_refresh_token:
        response.set_cookie(
            key="sb_refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
            path="/"
        )
    
    return {"success": True}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="sb_access_token", path="/")
    response.delete_cookie(key="sb_refresh_token", path="/")
    return {"success": True}

@router.get("/google")
async def google_login(request: Request):
    project_url = _get_supabase_project_url()
    if not project_url:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    
    host = request.headers.get("host", "localhost:9000")
    scheme = request.url.scheme
    redirect_uri = f"{scheme}://{host}/api/auth/callback"
    
    auth_url = (
        f"{project_url}/auth/v1/authorize"
        f"?provider=google"
        f"&redirect_to={redirect_uri}"
    )
    
    return RedirectResponse(url=auth_url)
