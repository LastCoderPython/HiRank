from typing import Set

from fastapi import Header, HTTPException

from app.config import settings


def _configured_api_keys() -> Set[str]:
    if not settings.agent_api_keys:
        return set()
    return {key.strip() for key in settings.agent_api_keys.split(",") if key.strip()}


async def require_agent_api_key(x_api_key: str | None = Header(default=None)):
    keys = _configured_api_keys()
    if not keys:
        raise HTTPException(status_code=500, detail="Agent API keys not configured on server")
    if not x_api_key or x_api_key not in keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
