import os
from supabase import create_client, Client
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

_supabase_client: Optional[Client] = None


def _normalize_supabase_url(url: str) -> str:
    normalized = url.strip().rstrip("/")
    if normalized.endswith("/rest/v1"):
        normalized = normalized[: -len("/rest/v1")]
    return normalized

def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        _supabase_client = create_client(_normalize_supabase_url(supabase_url), supabase_key)
    return _supabase_client

async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_client()
    response = client.table("profiles").select("*").eq("id", user_id).execute()
    if response.data:
        return response.data[0]
    return None

async def create_or_update_profile(user_id: str, email: str, name: Optional[str] = None, avatar_url: Optional[str] = None) -> Dict[str, Any]:
    client = get_supabase_client()
    existing = await get_user_by_id(user_id)
    
    profile_data = {
        "id": user_id,
        "email": email,
        "name": name or email.split("@")[0],
        "avatar_url": avatar_url,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    if existing:
        response = client.table("profiles").update(profile_data).eq("id", user_id).execute()
    else:
        profile_data["created_at"] = datetime.utcnow().isoformat()
        response = client.table("profiles").insert(profile_data).execute()
    
    return response.data[0] if response.data else profile_data

async def create_chat(user_id: str, title: str = "New Chat") -> Dict[str, Any]:
    client = get_supabase_client()
    chat_data = {
        "user_id": user_id,
        "title": title,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    response = client.table("chats").insert(chat_data).execute()
    return response.data[0] if response.data else chat_data

async def get_user_chats(user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    response = client.table("chats")\
        .select("id, title, created_at, updated_at")\
        .eq("user_id", user_id)\
        .order("updated_at", desc=True)\
        .range(offset, offset + limit - 1)\
        .execute()
    return response.data or []

async def get_chat_by_id(chat_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_client()
    response = client.table("chats")\
        .select("*")\
        .eq("id", chat_id)\
        .eq("user_id", user_id)\
        .execute()
    if response.data:
        return response.data[0]
    return None

async def update_chat_title(chat_id: str, title: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_client()
    response = client.table("chats")\
        .update({"title": title, "updated_at": datetime.utcnow().isoformat()})\
        .eq("id", chat_id)\
        .execute()
    return response.data[0] if response.data else None

async def delete_chat(chat_id: str, user_id: str) -> bool:
    client = get_supabase_client()
    client.table("messages").delete().eq("chat_id", chat_id).execute()
    response = client.table("chats").delete().eq("id", chat_id).eq("user_id", user_id).execute()
    return len(response.data) > 0 if response.data else False

async def add_message(chat_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    client = get_supabase_client()
    message_data = {
        "chat_id": chat_id,
        "role": role,
        "content": content,
        "metadata": metadata or {},
        "created_at": datetime.utcnow().isoformat()
    }
    response = client.table("messages").insert(message_data).execute()
    
    client.table("chats")\
        .update({"updated_at": datetime.utcnow().isoformat()})\
        .eq("id", chat_id)\
        .execute()
    
    return response.data[0] if response.data else message_data

async def get_chat_messages(chat_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    response = client.table("messages")\
        .select("*")\
        .eq("chat_id", chat_id)\
        .order("created_at", desc=False)\
        .range(offset, offset + limit - 1)\
        .execute()
    return response.data or []

async def create_temp_chat(session_id: str, title: str = "Temporary Chat") -> Dict[str, Any]:
    client = get_supabase_client()
    chat_data = {
        "session_id": session_id,
        "title": title,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    response = client.table("temp_chats").insert(chat_data).execute()
    return response.data[0] if response.data else chat_data

async def get_temp_chat(session_id: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_client()
    response = client.table("temp_chats")\
        .select("*")\
        .eq("session_id", session_id)\
        .execute()
    if response.data:
        return response.data[0]
    return None

async def add_temp_message(session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    client = get_supabase_client()
    message_data = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "metadata": metadata or {},
        "created_at": datetime.utcnow().isoformat()
    }
    response = client.table("temp_messages").insert(message_data).execute()
    
    client.table("temp_chats")\
        .update({"updated_at": datetime.utcnow().isoformat()})\
        .eq("session_id", session_id)\
        .execute()
    
    return response.data[0] if response.data else message_data

async def get_temp_messages(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    response = client.table("temp_messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .order("created_at", desc=False)\
        .limit(limit)\
        .execute()
    return response.data or []

async def transfer_temp_to_user_chat(session_id: str, user_id: str) -> Optional[str]:
    client = get_supabase_client()
    
    temp_messages = await get_temp_messages(session_id)
    if not temp_messages:
        return None
    
    chat = await create_chat(user_id, "Transferred Chat")
    chat_id = chat["id"]
    
    for msg in temp_messages:
        await add_message(chat_id, msg["role"], msg["content"], msg.get("metadata"))
    
    client.table("temp_messages").delete().eq("session_id", session_id).execute()
    client.table("temp_chats").delete().eq("session_id", session_id).execute()
    
    return chat_id
