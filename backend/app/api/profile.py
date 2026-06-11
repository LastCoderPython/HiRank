"""
User Profile API — GET and PATCH endpoints.

GET  /api/profile      → Returns full profile including onboarding fields
PATCH /api/profile     → Partial update (only provided fields are changed)

Used by:
- AuthProvider (fetchSession) to check onboarding_complete
- OnboardingModal to save exam/rank/category after email OTP verification
- SettingsModal to progressively collect state/branch/whatsapp
"""

from fastapi import APIRouter, HTTPException, Cookie
from pydantic import BaseModel
from typing import Optional, List
from app.api.auth import verify_jwt
import logging

logger = logging.getLogger("rankroute.api.profile")
router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: Optional[str] = None
    exam: Optional[str] = None
    rank: Optional[int] = None
    percentile: Optional[float] = None
    category: Optional[str] = None
    home_state: Optional[str] = None
    branch_preferences: Optional[List[str]] = None
    whatsapp_number: Optional[str] = None
    fingerprint_id: Optional[str] = None
    onboarding_complete: Optional[bool] = None
    budget_range: Optional[str] = None
    hostel_required: Optional[bool] = None
    location_preference: Optional[str] = None


def _get_user_id(sb_access_token: Optional[str]) -> str:
    """Extract user ID from the access token cookie."""
    if not sb_access_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = verify_jwt(sb_access_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


@router.get("")
async def get_profile(sb_access_token: Optional[str] = Cookie(None)):
    """Returns the full user profile including all onboarding fields."""
    user_id = _get_user_id(sb_access_token)
    from app.db.supabase import get_user_by_id
    profile = await get_user_by_id(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


ALLOWED_PROFILE_FIELDS = frozenset({
    "name", "exam", "rank", "percentile", "category",
    "home_state", "branch_preferences", "whatsapp_number",
    "fingerprint_id", "onboarding_complete",
    "budget_range", "hostel_required", "location_preference",
})


@router.patch("")
async def update_profile(
    body: ProfileUpdateRequest,
    sb_access_token: Optional[str] = Cookie(None),
):
    """Partial profile update — only provided (non-None) fields are changed."""
    user_id = _get_user_id(sb_access_token)
    from app.db.supabase import patch_profile
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    unexpected = set(updates) - ALLOWED_PROFILE_FIELDS
    if unexpected:
        raise HTTPException(status_code=422, detail=f"Unexpected fields: {', '.join(sorted(unexpected))}")
    updated = await patch_profile(user_id, updates)
    logger.info("Profile updated for user %s: %s", user_id, list(updates.keys()))
    return updated
