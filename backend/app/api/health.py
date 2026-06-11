from fastapi import APIRouter
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health_check():
    # Lazy import to avoid circular dependency (main → health → main)
    from app.main import server_state

    if server_state != "ready":
        return {
            "status": "starting",
            "server_state": server_state,
        }
    return {
        "status": "healthy",
        "server_state": server_state,
    }
