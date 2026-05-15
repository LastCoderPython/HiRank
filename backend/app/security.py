import time
import asyncio
from collections import defaultdict, deque
from typing import Deque, Dict, Set

from fastapi import Header, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings


def _configured_api_keys() -> Set[str]:
    if not settings.agent_api_keys:
        return set()
    return {key.strip() for key in settings.agent_api_keys.split(",") if key.strip()}


async def require_agent_api_key(x_api_key: str | None = Header(default=None)):
    keys = _configured_api_keys()
    if not keys:
        return
    if not x_api_key or x_api_key not in keys:
        raise HTTPException(status_code=401, detail="Invalid API key")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int, interval_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.interval_seconds = interval_seconds
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/agents"):
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        now = time.time()

        async with self._lock:
            window = self._requests[client_host]
            while window and now - window[0] > self.interval_seconds:
                window.popleft()

            if len(window) >= self.max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Rate limit exceeded", "detail": "Try again shortly"},
                )

            window.append(now)

        return await call_next(request)
