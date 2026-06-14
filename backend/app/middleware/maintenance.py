"""
Maintenance Mode Middleware

Checks a Redis key to see if maintenance mode is active.
If active, blocks all non-admin requests with a 503 Service Unavailable.
"""

import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("rankroute.middleware.maintenance")

MAINTENANCE_KEY = "rankroute:maintenance:active"

def _get_redis_client():
    """Lazily obtain a Redis client from the app's existing connection."""
    try:
        import redis
        from app.config import settings
        return redis.Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return None

class MaintenanceMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._redis: Optional[object] = None
        self._redis_checked: bool = False

    def _ensure_redis(self):
        if self._redis_checked:
            return
        self._redis_checked = True
        try:
            client = _get_redis_client()
            if client:
                client.ping()
                self._redis = client
                logger.info("MaintenanceMiddleware: connected to Redis")
        except Exception as e:
            logger.warning("MaintenanceMiddleware: Redis unavailable (%s), will retry on next request", e)
            self._redis = None
            self._redis_checked = False

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Always allow these paths
        if path.startswith("/api/v1/admin") or path in ("/api/v1/health", "/", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        self._ensure_redis()

        if self._redis:
            try:
                from starlette.concurrency import run_in_threadpool
                is_maintenance = await run_in_threadpool(self._redis.get, MAINTENANCE_KEY)
                if is_maintenance and str(is_maintenance).lower() == "true":
                    logger.info("Maintenance mode active, rejecting request to %s", path)
                    resp = JSONResponse(
                        status_code=503,
                        content={
                            "error": "Service Unavailable", 
                            "detail": "RankRoute is currently undergoing scheduled maintenance. Please try again shortly."
                        },
                    )
                    resp.headers["Retry-After"] = "300"
                    
                    origin = request.headers.get("origin")
                    if origin:
                        resp.headers["Access-Control-Allow-Origin"] = origin
                        resp.headers["Access-Control-Allow-Credentials"] = "true"
                    return resp
            except Exception as e:
                logger.warning("Maintenance check failed (%s), allowing request", e)

        return await call_next(request)
