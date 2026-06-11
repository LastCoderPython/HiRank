import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


logger = logging.getLogger("rankroute.observability")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = request_id
        response.headers["x-response-time-ms"] = f"{elapsed_ms:.2f}"

        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        # Log slow requests (>10s) and server errors to admin_logs
        if elapsed_ms > 10000 or response.status_code >= 500:
            try:
                from app.services.log_service import log_service
                log_service.insert(
                    event_type="system_event",
                    severity="warning" if response.status_code < 500 else "error",
                    summary=f"Slow request ({elapsed_ms:.0f}ms) or error {response.status_code}: {request.method} {request.url.path}",
                    details={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": round(elapsed_ms, 2),
                    },
                    source="observability.middleware",
                )
            except Exception:
                pass

        return response
