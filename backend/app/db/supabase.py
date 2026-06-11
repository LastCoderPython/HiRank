from supabase import create_client, Client
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid

from starlette.concurrency import run_in_threadpool
from app.config import settings

_supabase_client: Optional[Client] = None


def _normalize_supabase_url(url: str) -> str:
    normalized = url.strip().rstrip("/")
    if normalized.endswith("/rest/v1"):
        normalized = normalized[: -len("/rest/v1")]
    return normalized

def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        supabase_url = settings.supabase_url
        supabase_key = settings.supabase_service_key
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        _supabase_client = create_client(_normalize_supabase_url(supabase_url), supabase_key)
    return _supabase_client

async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_client()
    query = client.table("profiles").select("*").eq("id", user_id)
    response = await run_in_threadpool(query.execute)
    if response.data:
        return response.data[0]
    return None

async def set_user_role(user_id: str, role: str) -> bool:
    """Set (or promote/demote) a user's role. Admin-only operation."""
    client = get_supabase_client()
    query = client.table("profiles").update({"role": role, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", user_id)
    response = await run_in_threadpool(query.execute)
    return bool(response.data)


async def create_or_update_profile(
    user_id: str,
    email: str,
    name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    phone: Optional[str] = None,
    role: Optional[str] = None,
    exam: Optional[str] = None,
    rank: Optional[int] = None,
    percentile: Optional[float] = None,
    category: Optional[str] = None,
    home_state: Optional[str] = None,
    branch_preferences: Optional[list] = None,
    whatsapp_number: Optional[str] = None,
    fingerprint_id: Optional[str] = None,
    onboarding_complete: Optional[bool] = None,
    budget_range: Optional[str] = None,
    hostel_required: Optional[bool] = None,
    location_preference: Optional[str] = None,
) -> Dict[str, Any]:
    client = get_supabase_client()
    existing = await get_user_by_id(user_id)

    profile_data = {
        "id": user_id,
        "email": email,
        "name": name or (email or "").split("@")[0] or "User",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    if avatar_url is not None:
        profile_data["avatar_url"] = avatar_url
    if phone is not None:
        profile_data["phone"] = phone
    if exam is not None:
        profile_data["exam"] = exam
    if rank is not None:
        profile_data["rank"] = rank
    if percentile is not None:
        profile_data["percentile"] = float(percentile)
    if category is not None:
        profile_data["category"] = category
    if home_state is not None:
        profile_data["home_state"] = home_state
    if branch_preferences is not None:
        profile_data["branch_preferences"] = branch_preferences
    if whatsapp_number is not None:
        profile_data["whatsapp_number"] = whatsapp_number
    if fingerprint_id is not None:
        profile_data["fingerprint_id"] = fingerprint_id
    if onboarding_complete is not None:
        profile_data["onboarding_complete"] = onboarding_complete
    if budget_range is not None:
        profile_data["budget_range"] = budget_range
    if hostel_required is not None:
        profile_data["hostel_required"] = hostel_required
    if location_preference is not None:
        profile_data["location_preference"] = location_preference
    if role is not None:
        profile_data["role"] = role

    if existing:
        query = client.table("profiles").update(profile_data).eq("id", user_id)
        response = await run_in_threadpool(query.execute)
    else:
        profile_data["created_at"] = datetime.now(timezone.utc).isoformat()
        query = client.table("profiles").insert(profile_data)
        response = await run_in_threadpool(query.execute)

    return response.data[0] if response.data else profile_data


async def patch_profile(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Partial profile update — only updates the provided fields."""
    client = get_supabase_client()
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    query = client.table("profiles").update(updates).eq("id", user_id)
    response = await run_in_threadpool(query.execute)
    return response.data[0] if response.data else updates


async def create_chat(user_id: str, title: str = "New Chat") -> Dict[str, Any]:
    client = get_supabase_client()
    chat_data = {
        "user_id": user_id,
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    query = client.table("chats").insert(chat_data)
    response = await run_in_threadpool(query.execute)
    return response.data[0] if response.data else chat_data


async def get_user_chats(user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    query = client.table("chats")\
        .select("id, title, created_at, updated_at")\
        .eq("user_id", user_id)\
        .order("updated_at", desc=True)\
        .range(offset, offset + limit - 1)
    response = await run_in_threadpool(query.execute)
    return response.data or []


async def get_chat_by_id(chat_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_client()
    query = client.table("chats")\
        .select("*")\
        .eq("id", chat_id)\
        .eq("user_id", user_id)
    response = await run_in_threadpool(query.execute)
    if response.data:
        return response.data[0]
    return None


async def update_chat_title(chat_id: str, title: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_client()
    query = client.table("chats")\
        .update({"title": title, "updated_at": datetime.now(timezone.utc).isoformat()})\
        .eq("id", chat_id)
    response = await run_in_threadpool(query.execute)
    return response.data[0] if response.data else None


async def delete_chat(chat_id: str, user_id: str) -> bool:
    client = get_supabase_client()
    query = client.table("chats").delete().eq("id", chat_id).eq("user_id", user_id)
    response = await run_in_threadpool(query.execute)
    return bool(response.data)


async def clear_all_chats(user_id: str) -> int:
    client = get_supabase_client()
    query = client.table("chats").delete().eq("user_id", user_id)
    response = await run_in_threadpool(query.execute)
    return len(response.data) if response.data else 0

async def add_message(chat_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    client = get_supabase_client()
    message_data = {
        "chat_id": chat_id,
        "role": role,
        "content": content,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    query = client.table("messages").insert(message_data)
    response = await run_in_threadpool(query.execute)
    
    update_query = client.table("chats")\
        .update({"updated_at": datetime.now(timezone.utc).isoformat()})\
        .eq("id", chat_id)
    await run_in_threadpool(update_query.execute)
    
    return response.data[0] if response.data else message_data

async def get_chat_messages(chat_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    query = client.table("messages")\
        .select("*")\
        .eq("chat_id", chat_id)\
        .order("created_at", desc=False)\
        .range(offset, offset + limit - 1)
    response = await run_in_threadpool(query.execute)
    return response.data or []

async def create_temp_chat(session_id: str, title: str = "Temporary Chat") -> Dict[str, Any]:
    client = get_supabase_client()
    chat_data = {
        "session_id": session_id,
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    query = client.table("temp_chats").insert(chat_data)
    response = await run_in_threadpool(query.execute)
    return response.data[0] if response.data else chat_data

async def get_temp_chat(session_id: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_client()
    query = client.table("temp_chats")\
        .select("*")\
        .eq("session_id", session_id)
    response = await run_in_threadpool(query.execute)
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
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    query = client.table("temp_messages").insert(message_data)
    response = await run_in_threadpool(query.execute)
    
    update_query = client.table("temp_chats")\
        .update({"updated_at": datetime.now(timezone.utc).isoformat()})\
        .eq("session_id", session_id)
    await run_in_threadpool(update_query.execute)
    
    return response.data[0] if response.data else message_data

async def get_temp_messages(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    query = client.table("temp_messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .order("created_at", desc=False)\
        .limit(limit)
    response = await run_in_threadpool(query.execute)
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
    
    delete_query = client.table("temp_chats").delete().eq("session_id", session_id)
    await run_in_threadpool(delete_query.execute)
    
    return chat_id
