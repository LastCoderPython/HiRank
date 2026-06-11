"""
Distributed Rate Limiter Middleware (Redis-backed)

Uses a Redis sorted-set sliding window so rate limits are enforced
globally across all Gunicorn workers and (if scaled) all container
instances.  Falls back to a local in-memory deque if Redis is
unavailable, preserving per-worker limiting as a degraded mode.
"""

import time
import asyncio
import logging
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("rankroute.middleware.rate_limit")

# Per-endpoint rate limit overrides: (max_requests, interval_seconds)
_ENDPOINT_LIMITS: Dict[str, Tuple[int, int]] = {
    "/api/chat": (10, 60),
    "/api/auth/email/send-otp": (5, 60),
    "/api/auth/email/verify": (10, 60),
    "/api/health": (30, 60),
}


def _get_redis_client():
    """Lazily obtain a Redis client from the app's existing connection."""
    try:
        import redis
        from app.config import settings
        return redis.Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int, interval_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.interval_seconds = interval_seconds

        # Redis client (lazy init)
        self._redis: Optional[object] = None
        self._redis_checked: bool = False

        # Fallback: local in-memory sliding window (per-worker only)
        self._local_requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._local_lock = asyncio.Lock()

    def _ensure_redis(self):
        """Try once to connect to Redis; fall back to local on failure."""
        if self._redis_checked:
            return
        self._redis_checked = True
        try:
            client = _get_redis_client()
            if client:
                client.ping()
                self._redis = client
                logger.info("Rate limiter: using Redis-backed sliding window")
        except Exception as e:
            logger.warning("Rate limiter: Redis unavailable (%s), falling back to local memory", e)
            self._redis = None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in ("/", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        limit, window_sec = _ENDPOINT_LIMITS.get(path, (self.max_requests, self.interval_seconds))

        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_host = forwarded.split(",")[0].strip()
        else:
            client_host = request.client.host if request.client else "unknown"

        self._ensure_redis()

        if self._redis:
            is_allowed = await self._check_redis(client_host, path, limit, window_sec)
        else:
            is_allowed = await self._check_local(client_host, limit, window_sec)

        if not is_allowed:
            resp = JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "detail": "Try again shortly"},
            )
            origin = request.headers.get("origin")
            if origin:
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Allow-Credentials"] = "true"
            return resp

        return await call_next(request)

    async def _check_redis(self, client_host: str, path: str, limit: int, window_sec: int) -> bool:
        """
        Redis sliding-window rate limiter using sorted sets.

        Key: rl:{client_host}:{path}
        Score & Member: current timestamp (float)
        """
        from starlette.concurrency import run_in_threadpool

        key = f"rl:{client_host}:{path}"
        now = time.time()
        window_start = now - window_sec

        try:
            def _redis_pipeline():
                pipe = self._redis.pipeline(transaction=True)
                pipe.zremrangebyscore(key, 0, window_start)   # prune expired
                pipe.zadd(key, {str(now): now})                # add current
                pipe.zcard(key)                                # count
                pipe.expire(key, window_sec + 1)               # TTL safety
                return pipe.execute()

            results = await run_in_threadpool(_redis_pipeline)
            current_count = results[2]
            return current_count <= limit
        except Exception as e:
            logger.warning("Redis rate-limit check failed (%s), allowing request", e)
            return True  # fail-open on Redis error

    async def _check_local(self, client_host: str, limit: int, window_sec: int) -> bool:
        """Fallback: per-worker in-memory sliding window."""
        now = time.time()
        async with self._local_lock:
            window = self._local_requests[client_host]
            while window and now - window[0] > window_sec:
                window.popleft()
            if len(window) >= limit:
                return False
            window.append(now)
        return True
