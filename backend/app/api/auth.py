from fastapi import APIRouter, Request, Response, HTTPException, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import httpx
import jwt
import logging
import secrets
from datetime import datetime
from urllib.parse import quote
from app.config import settings

logger = logging.getLogger("rankroute.api.auth")

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
            audience="authenticated",
            options={"verify_aud": True}
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

@router.get("/session", response_model=SessionResponse)
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

    redirect_uri = f"{settings.backend_url.rstrip('/')}/api/auth/callback"

    # C-02: Generate CSRF state token
    state = secrets.token_urlsafe(32)

    auth_url = (
        f"{project_url}/auth/v1/authorize"
        f"?provider=google"
        f"&redirect_to={redirect_uri}"
        f"&state={state}"
    )

    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=300,
        path="/",
    )
    return response

@router.get("/callback")
async def auth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    oauth_state: Optional[str] = Cookie(None),
):
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth_error={quote(error)}")

    if not code:
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth_error=no_code")

    # C-02: Validate CSRF state
    if not state or not oauth_state or not secrets.compare_digest(state, oauth_state):
        logger.warning("OAuth state mismatch — possible CSRF attack")
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth_error=state_mismatch")

    project_url = _get_supabase_project_url()
    if not project_url:
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth_error=config_error")

    redirect_uri = f"{settings.backend_url.rstrip('/')}/api/auth/callback"

    data = await _exchange_code_for_session(project_url, code, redirect_uri)
    if not data:
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth_error=token_exchange_failed")

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    expires_in = data.get("expires_in", 3600)

    if not access_token or not refresh_token:
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth_error=token_missing")
    
    response = RedirectResponse(url=FRONTEND_URL)
    
    response.set_cookie(
        key="sb_access_token",
        value=access_token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=expires_in,
        path="/"
    )
    
    response.set_cookie(
        key="sb_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.debug,
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
        secure=not settings.debug,
        samesite="lax",
        max_age=expires_in,
        path="/"
    )
    
    if refresh_token != sb_refresh_token:
        response.set_cookie(
            key="sb_refresh_token",
            value=refresh_token,
            httponly=True,
            secure=not settings.debug,
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

    redirect_uri = f"{settings.backend_url.rstrip('/')}/api/auth/callback"

    # C-02: Generate CSRF state token
    state = secrets.token_urlsafe(32)

    auth_url = (
        f"{project_url}/auth/v1/authorize"
        f"?provider=google"
        f"&redirect_to={redirect_uri}"
        f"&state={state}"
    )

    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=300,
        path="/",
    )
    return response


# ── Email OTP Authentication ──────────────────────────────────────────
# Delivery chain: FastAPI → Supabase Auth API → Resend SMTP relay → User inbox
# No Redis needed. Email IS the identity — no pre-storage required.

from app.services.email_validator import validate_and_normalize_email


class EmailSendOtpRequest(BaseModel):
    model_config = {"extra": "forbid"}
    email: str = Field(..., description="User's email address")


class EmailVerifyRequest(BaseModel):
    model_config = {"extra": "forbid"}
    email: str
    token: str = Field(..., description="6-digit OTP code")
    session_id: Optional[str] = Field(None, description="FingerprintJS Visitor ID for chat transfer")
    # Onboarding data — sent together with verify to save a round trip
    exam: Optional[str] = None
    rank: Optional[int] = None
    percentile: Optional[float] = None
    category: Optional[str] = None
    onboarding_complete: Optional[bool] = None


@router.post("/email/send-otp")
async def send_email_otp(body: EmailSendOtpRequest):
    """Send a 6-digit OTP to the user's email via Supabase + Resend SMTP.

    Flow:
    1. Normalize email (strip Gmail aliases/dots, lowercase)
    2. Check against disposable domain blocklist
    3. Call Supabase Auth OTP endpoint — Supabase generates the code
       and sends it via the configured Resend SMTP relay
    """
    project_url = _get_supabase_project_url()
    if not project_url:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    normalized_email, error = validate_and_normalize_email(body.email)
    if error:
        raise HTTPException(status_code=400, detail=error)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{project_url}/auth/v1/otp",
                json={"email": normalized_email},
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Content-Type": "application/json",
                },
            )

        if response.status_code not in (200, 201):
            error_detail = response.json().get("msg", response.text)
            logger.error("Supabase email OTP send failed: %s", error_detail)
            raise HTTPException(
                status_code=400,
                detail=f"Failed to send OTP: {error_detail}",
            )

        logger.info("Email OTP sent to %s", normalized_email)
        return {"success": True, "email": normalized_email}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Email OTP send error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to send OTP")


@router.post("/email/verify")
async def verify_email_otp(body: EmailVerifyRequest, response: Response):
    """Verify email OTP and create/update user profile.

    On successful verification:
    1. Creates Supabase auth user (if new)
    2. Creates/updates the profiles row with onboarding data (if provided)
    3. Transfers anonymous chat history to the new account (by FingerprintJS ID)
    4. Sets httpOnly auth cookies (same pattern as Google OAuth callback)

    Onboarding data is sent in the same request to avoid an extra round trip.
    """
    project_url = _get_supabase_project_url()
    if not project_url:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    normalized_email, error = validate_and_normalize_email(body.email)
    if error:
        raise HTTPException(status_code=400, detail=error)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            verify_response = await client.post(
                f"{project_url}/auth/v1/token?grant_type=email_otp",
                json={
                    "email": normalized_email,
                    "token": body.token,
                    "type": "email",
                },
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Content-Type": "application/json",
                },
            )

        if verify_response.status_code != 200:
            error_detail = verify_response.json().get("msg", "Invalid or expired OTP")
            raise HTTPException(status_code=401, detail=error_detail)

        data = verify_response.json()
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in", 3600)
        user_data = data.get("user", {})
        user_id = user_data.get("id")

        if not access_token or not refresh_token or not user_id:
            raise HTTPException(
                status_code=500,
                detail="Invalid token response from Supabase",
            )

        # Auto-derive name from email prefix (no name field in our form)
        auto_name = normalized_email.split("@")[0].replace(".", " ").title()

        # Create/update profile with onboarding data if submitted
        try:
            from app.db.supabase import create_or_update_profile
            await create_or_update_profile(
                user_id=user_id,
                email=normalized_email,
                name=auto_name,
                exam=body.exam,
                rank=body.rank,
                percentile=body.percentile,
                category=body.category,
                onboarding_complete=body.onboarding_complete,
                fingerprint_id=body.session_id,
            )
        except Exception as e:
            logger.error("Profile upsert failed (non-fatal): %s", e)

        # Transfer anonymous chat history (keyed by FingerprintJS Visitor ID)
        if body.session_id:
            try:
                from app.db.supabase import transfer_temp_to_user_chat
                await transfer_temp_to_user_chat(body.session_id, user_id)
                logger.info(
                    "Transferred temp chat: %s → %s",
                    body.session_id[:12], user_id,
                )
            except Exception as e:
                logger.error("Chat transfer failed (non-fatal): %s", e)

        # Set httpOnly auth cookies (identical to Google OAuth callback)
        response.set_cookie(
            key="sb_access_token",
            value=access_token,
            httponly=True,
            secure=not settings.debug,
            samesite="lax",
            max_age=expires_in,
            path="/",
        )
        response.set_cookie(
            key="sb_refresh_token",
            value=refresh_token,
            httponly=True,
            secure=not settings.debug,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
            path="/",
        )

        return {
            "success": True,
            "user": {
                "id": user_id,
                "email": normalized_email,
                "name": auto_name,
                "onboarding_complete": body.onboarding_complete or False,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Email OTP verify error: %s", e)
        raise HTTPException(status_code=500, detail="Verification failed")

