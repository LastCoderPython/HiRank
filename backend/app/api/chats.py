from collections import defaultdict
import time

from fastapi import APIRouter, HTTPException, Cookie, Request
from pydantic import BaseModel
from typing import Optional
import logging

from app.db.supabase import (
    create_chat, get_user_chats, get_chat_by_id, update_chat_title,
    delete_chat, add_message, get_chat_messages,
    create_temp_chat, get_temp_chat, add_temp_message, get_temp_messages,
    transfer_temp_to_user_chat, clear_all_chats
)
from app.api.auth import verify_jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["chats"])


class CreateChatRequest(BaseModel):
    model_config = {"extra": "forbid"}
    title: str = "New Chat"
    temp_session_id: Optional[str] = None

class AddMessageRequest(BaseModel):
    model_config = {"extra": "forbid"}
    chat_id: Optional[str] = None
    temp_session_id: Optional[str] = None
    role: str
    content: str
    metadata: Optional[dict] = None

class UpdateChatRequest(BaseModel):
    model_config = {"extra": "forbid"}
    title: str


async def get_user_from_token(sb_access_token: Optional[str] = Cookie(None)) -> Optional[dict]:
    """Extract user from JWT cookie using shared verify_jwt from auth.py."""
    if not sb_access_token:
        return None

    payload = verify_jwt(sb_access_token)
    if not payload:
        return None

    return {
        "id": payload.get("sub"),
        "email": payload.get("email")
    }

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
                logger.warning("Failed to transfer temp chat: %s", e)
        
        return {"chat_id": chat["id"]}
    else:
        raise HTTPException(status_code=401, detail="Authentication required")

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

@router.post("/chats/clear")
async def clear_chats(
    sb_access_token: Optional[str] = Cookie(None)
):
    user = await get_user_from_token(sb_access_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    deleted_count = await clear_all_chats(user["id"])
    return {"success": True, "deleted": deleted_count}

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

_temp_chat_limits: dict = defaultdict(list)

@router.get("/temp-chats/{session_id}")
async def get_temp_chat_messages(session_id: str, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = _temp_chat_limits[client_ip]
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= 10:
        raise HTTPException(status_code=429, detail="Too many requests")
    window.append(now)

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
