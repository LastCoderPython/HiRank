"""
RankRoute — Alert Service (Admin Portal)

Replaced the old SMTP-based email alerts with in-app admin_logs
records viewable in the admin panel. All threshold warnings,
critical alerts, and daily digests are now stored in the database
and accessible via the admin log viewer.
"""

import logging
from datetime import datetime, timezone

from app.services.log_service import log_service

logger = logging.getLogger("rankroute.services.alert")


class AlertService:
    """Log admin alerts to the database instead of sending email."""

    def send(self, level: str, usage: int, quota: int) -> bool:
        pct = round((usage / quota) * 100, 1) if quota > 0 else 0
        remaining = max(0, quota - usage)
        now = datetime.now(timezone.utc)
        month_name = now.strftime("%B %Y")

        if level == "warning":
            summary = f"Tavily usage warning: {usage}/{quota} ({pct}%) used this month"
            severity = "warning"
            event_type = "usage_threshold"
        elif level == "critical":
            summary = f"Tavily quota critical: {usage}/{quota} ({pct}%) — action required"
            severity = "critical"
            event_type = "usage_threshold"
        else:
            summary = f"Daily digest: {usage}/{quota} Tavily searches used ({month_name})"
            severity = "info"
            event_type = "digest"

        details = {
            "usage": usage,
            "quota": quota,
            "pct": pct,
            "remaining": remaining,
            "month": month_name,
            "level": level,
        }

        return log_service.insert(
            event_type=event_type,
            severity=severity,
            summary=summary,
            details=details,
            source="alert_service",
            actor_role="system",
        )


alert_service = AlertService()
