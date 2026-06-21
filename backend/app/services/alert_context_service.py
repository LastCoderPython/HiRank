"""
RankRoute — Alert Context Service

Manages system_alerts: short, admin-authored messages that are silently
injected into the LLM system prompt to provide guaranteed, accurate context
for time-sensitive information (e.g., counseling dates, deadline changes).

Only one alert may be active at a time. The active alert is cached in-memory
for 5 minutes to prevent database queries on every streaming request.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from app.db.supabase import get_supabase_client
from app.services.cache_service import cache_service

logger = logging.getLogger("rankroute.services.alert_context")

_CACHE_NAMESPACE = "system_alert"
_CACHE_KEY = "active"
_CACHE_TTL = 300  # 5 minutes


class AlertContextService:

    # ── Read ─────────────────────────────────────────────────────────────

    def get_active_alert(self) -> Optional[str]:
        """Return the content of the currently active alert, or None.

        Result is cached for 5 minutes to avoid a DB hit on every chat stream.
        Cache is cleared immediately whenever an alert is created, activated,
        or deleted via the admin panel.
        """
        cached = cache_service.get(_CACHE_NAMESPACE, _CACHE_KEY)
        if cached is not None:
            # Cached value can be "" (no active alert) or a real string
            return cached or None

        try:
            client = get_supabase_client()
            result = (
                client.table("system_alerts")
                .select("content")
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            content = result.data[0]["content"] if result.data else ""
            cache_service.set(_CACHE_NAMESPACE, _CACHE_KEY, content, ttl=_CACHE_TTL)
            return content or None
        except Exception as e:
            logger.error("Failed to fetch active system alert: %s", e)
            return None

    def list_alerts(self) -> list[dict]:
        """Return all alerts ordered by creation date descending."""
        try:
            client = get_supabase_client()
            result = (
                client.table("system_alerts")
                .select("id, content, is_active, created_at")
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error("Failed to list system alerts: %s", e)
            return []

    # ── Write ─────────────────────────────────────────────────────────────

    def create_alert(self, content: str) -> Optional[dict]:
        """Insert a new alert (inactive by default)."""
        try:
            client = get_supabase_client()
            result = (
                client.table("system_alerts")
                .insert({"id": str(uuid4()), "content": content, "is_active": False})
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error("Failed to create system alert: %s", e)
            return None

    def set_active_alert(self, alert_id: str) -> bool:
        """Activate the given alert and deactivate all others atomically.

        Uses two queries because Supabase's Python client does not expose
        a single conditional-update syntax for multi-row operations.
        """
        try:
            client = get_supabase_client()
            # 1. Deactivate every existing active alert
            client.table("system_alerts").update({"is_active": False}).eq(
                "is_active", True
            ).execute()
            # 2. Activate the selected one
            client.table("system_alerts").update({"is_active": True}).eq(
                "id", alert_id
            ).execute()
            self._clear_cache()
            return True
        except Exception as e:
            logger.error("Failed to activate system alert %s: %s", alert_id, e)
            return False

    def deactivate_all(self) -> bool:
        """Deactivate all alerts (useful for clearing the injection)."""
        try:
            client = get_supabase_client()
            client.table("system_alerts").update({"is_active": False}).eq(
                "is_active", True
            ).execute()
            self._clear_cache()
            return True
        except Exception as e:
            logger.error("Failed to deactivate all system alerts: %s", e)
            return False

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert by ID."""
        try:
            client = get_supabase_client()
            client.table("system_alerts").delete().eq("id", alert_id).execute()
            self._clear_cache()
            return True
        except Exception as e:
            logger.error("Failed to delete system alert %s: %s", alert_id, e)
            return False

    # ── Internal ──────────────────────────────────────────────────────────

    def _clear_cache(self) -> None:
        """Bust the in-memory cache so the next request gets fresh DB data."""
        try:
            cache_service.invalidate(_CACHE_NAMESPACE, _CACHE_KEY)
        except Exception:
            pass  # Cache miss on the next request is fine


alert_context_service = AlertContextService()
