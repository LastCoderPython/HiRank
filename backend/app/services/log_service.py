import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from uuid import uuid4

from app.db.supabase import get_supabase_client

logger = logging.getLogger("rankroute.services.log")


class LogEntry:
    def __init__(self, row: Dict[str, Any]):
        self.id: str = row["id"]
        self.event_type: str = row["event_type"]
        self.severity: str = row["severity"]
        self.actor_id: Optional[str] = row.get("actor_id")
        self.actor_role: str = row.get("actor_role", "system")
        self.summary: str = row["summary"]
        self.details: Optional[Dict[str, Any]] = row.get("details")
        self.source: str = row.get("source", "")
        self.created_at: str = row["created_at"]


class LogService:
    def insert(
        self,
        event_type: str,
        severity: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
        source: str = "",
        actor_id: Optional[str] = None,
        actor_role: str = "system",
    ) -> bool:
        try:
            client = get_supabase_client()
            client.table("admin_logs").insert({
                "id": str(uuid4()),
                "event_type": event_type,
                "severity": severity,
                "actor_id": actor_id,
                "actor_role": actor_role,
                "summary": summary,
                "details": json.dumps(details) if details else None,
                "source": source,
            }).execute()
            return True
        except Exception as e:
            logger.error("Failed to insert admin log: %s", e)
            return False

    def query(
        self,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        source: Optional[str] = None,
        actor_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        try:
            client = get_supabase_client()
            q = client.table("admin_logs").select("*", count="exact")

            if event_type:
                q = q.eq("event_type", event_type)
            if severity:
                q = q.eq("severity", severity)
            if source:
                q = q.eq("source", source)
            if actor_id:
                q = q.eq("actor_id", actor_id)
            if date_from:
                q = q.gte("created_at", date_from)
            if date_to:
                q = q.lte("created_at", date_to)

            q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
            result = q.execute()

            entries = [LogEntry(r) for r in (result.data or [])]
            total = result.count if hasattr(result, "count") else len(entries)

            return {"entries": entries, "total": total, "limit": limit, "offset": offset}
        except Exception as e:
            logger.error("Failed to query admin logs: %s", e)
            return {"entries": [], "total": 0, "limit": limit, "offset": offset, "error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        try:
            client = get_supabase_client()
            now = datetime.now(timezone.utc)

            # Total count
            total_resp = client.table("admin_logs").select("*", count="exact", head=True).execute()
            total = getattr(total_resp, "count", 0)

            # Counts by severity
            sevs = {}
            for s in ("info", "warning", "error", "critical"):
                r = client.table("admin_logs").select("*", count="exact", head=True).eq("severity", s).execute()
                sevs[s] = getattr(r, "count", 0)

            # Last 24h count
            yesterday = (now - timedelta(hours=24)).isoformat()
            r = client.table("admin_logs").select("*", count="exact", head=True).gte("created_at", yesterday).execute()
            last_24h = getattr(r, "count", 0)

            return {"total": total, "by_severity": sevs, "last_24h": last_24h}
        except Exception as e:
            logger.error("Failed to get admin log stats: %s", e)
            return {"total": 0, "by_severity": {}, "last_24h": 0, "error": str(e)}

    def purge(self, before: datetime) -> int:
        try:
            client = get_supabase_client()
            result = client.table("admin_logs").delete().lt("created_at", before.isoformat()).execute()
            count = len(result.data) if result.data else 0
            logger.info("Purged %d admin log entries older than %s", count, before.isoformat())
            return count
        except Exception as e:
            logger.error("Failed to purge admin logs: %s", e)
            return 0


log_service = LogService()
