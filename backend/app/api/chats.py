from fastapi import APIRouter, HTTPException, Depends, Cookie, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid
import jwt
import json as json_module
import logging
import httpx

from app.db.supabase import (
    create_chat, get_user_chats, get_chat_by_id, update_chat_title,
    delete_chat, add_message, get_chat_messages,
    create_temp_chat, get_temp_chat, add_temp_message, get_temp_messages,
    transfer_temp_to_user_chat
)
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chats"])

SUPABASE_JWT_SECRET = settings.supabase_jwt_secret
SUPABASE_URL = settings.supabase_url
SUPABASE_ANON_KEY = settings.supabase_anon_key

class CreateChatRequest(BaseModel):
    title: str = "New Chat"
    temp_session_id: Optional[str] = None

class AddMessageRequest(BaseModel):
    chat_id: Optional[str] = None
    temp_session_id: Optional[str] = None
    role: str
    content: str
    metadata: Optional[dict] = None

class UpdateChatRequest(BaseModel):
    title: str

def _get_supabase_project_url() -> Optional[str]:
    if not SUPABASE_URL:
        return None

    url = SUPABASE_URL.strip().rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    return url


async def get_user_from_token(sb_access_token: Optional[str] = Cookie(None)) -> Optional[dict]:
    if not sb_access_token:
        return None

    if SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                sb_access_token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
            return {
                "id": payload.get("sub"),
                "email": payload.get("email")
            }
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            pass

    project_url = _get_supabase_project_url()
    if not project_url or not SUPABASE_ANON_KEY:
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{project_url}/auth/v1/user",
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {sb_access_token}",
                },
            )

        if response.status_code != 200:
            return None

        data = response.json()
        return {
            "id": data.get("id"),
            "email": data.get("email")
        }
    except Exception:
        return None

@router.post("/chats")
async def create_new_chat(
    request: Request,
    body: CreateChatRequest,
    sb_access_token: Optional[str] = Cookie(None)
):
    user = await get_user_from_token(sb_access_token)
    
    if user:
        chat = await create_chat(user["id"], body.title)
        
        if body.temp_session_id:
            try:
                transferred_chat_id = await transfer_temp_to_user_chat(body.temp_session_id, user["id"])
                if transferred_chat_id:
                    return {"chat_id": transferred_chat_id, "transferred": True}
            except Exception as e:
                logger.warning(f"Failed to transfer temp chat: {e}")
        
        return {"chat_id": chat["id"]}
    else:
        return {"error": "Authentication required", "requires_auth": True}

@router.get("/chats")
async def list_chats(
    limit: int = 50,
    offset: int = 0,
    sb_access_token: Optional[str] = Cookie(None)
):
    user = await get_user_from_token(sb_access_token)
    
    if not user:
        return {"chats": [], "authenticated": False}
    
    chats = await get_user_chats(user["id"], limit, offset)
    return {"chats": chats, "authenticated": True}

@router.get("/chats/{chat_id}")
async def get_chat(
    chat_id: str,
    sb_access_token: Optional[str] = Cookie(None)
):
    user = await get_user_from_token(sb_access_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    chat = await get_chat_by_id(chat_id, user["id"])
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    messages = await get_chat_messages(chat_id)
    
    return {
        "chat": chat,
        "messages": messages
    }

@router.patch("/chats/{chat_id}")
async def update_chat(
    chat_id: str,
    body: UpdateChatRequest,
    sb_access_token: Optional[str] = Cookie(None)
):
    user = await get_user_from_token(sb_access_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    existing = await get_chat_by_id(chat_id, user["id"])
    if not existing:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    updated = await update_chat_title(chat_id, body.title)
    return {"success": True, "chat": updated}

@router.delete("/chats/{chat_id}")
async def remove_chat(
    chat_id: str,
    sb_access_token: Optional[str] = Cookie(None)
):
    user = await get_user_from_token(sb_access_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    success = await delete_chat(chat_id, user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    return {"success": True}

@router.post("/messages")
async def save_message(
    body: AddMessageRequest,
    sb_access_token: Optional[str] = Cookie(None)
):
    user = await get_user_from_token(sb_access_token)
    
    if user and body.chat_id:
        message = await add_message(
            body.chat_id,
            body.role,
            body.content,
            body.metadata
        )
        return {"success": True, "message_id": message["id"]}
    elif not user and body.temp_session_id:
        temp_chat = await get_temp_chat(body.temp_session_id)
        if not temp_chat:
            temp_chat = await create_temp_chat(body.temp_session_id)
        
        message = await add_temp_message(
            body.temp_session_id,
            body.role,
            body.content,
            body.metadata
        )
        return {"success": True, "message_id": message["id"], "temp": True}
    elif user and not body.chat_id:
        chat = await create_chat(user["id"])
        message = await add_message(
            chat["id"],
            body.role,
            body.content,
            body.metadata
        )
        return {"success": True, "message_id": message["id"], "chat_id": chat["id"]}
    else:
        raise HTTPException(status_code=400, detail="Either authentication with chat_id, or temp_session_id required")

@router.get("/temp-chats/{session_id}")
async def get_temp_chat_messages(session_id: str):
    temp_chat = await get_temp_chat(session_id)
    if not temp_chat:
        return {"exists": False, "messages": []}
    
    messages = await get_temp_messages(session_id)
    return {"exists": True, "messages": messages, "chat": temp_chat}

@router.post("/transfer-temp-chat")
async def transfer_temp_chat(
    session_id: str,
    sb_access_token: Optional[str] = Cookie(None)
):
    user = await get_user_from_token(sb_access_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    chat_id = await transfer_temp_to_user_chat(session_id, user["id"])
    if chat_id:
        return {"success": True, "chat_id": chat_id}
    else:
        return {"success": False, "message": "No temporary chat found"}
