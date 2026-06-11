"""
Analytics API — admin-only endpoints for usage insights.

GET  /api/admin/analytics/overview    → Summary stats
GET  /api/admin/analytics/daily       → Daily chat volume (last N days)
GET  /api/admin/analytics/predictions → Prediction distribution data
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Query
from starlette.concurrency import run_in_threadpool
from app.api.admin import require_admin
from app.db.supabase import get_supabase_client

logger = logging.getLogger("rankroute.api.analytics")
router = APIRouter(prefix="/api/admin/analytics", tags=["analytics"])


@router.get("/overview")
async def get_analytics_overview(admin: Dict[str, Any] = Depends(require_admin)):
    client = get_supabase_client()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    # Total chats ever
    q1 = client.table("chats").select("*", count="exact", head=True)
    total_chats = await run_in_threadpool(q1.execute)
    total_chats_count = getattr(total_chats, "count", 0)

    # Chats today
    q2 = client.table("chats").select("*", count="exact", head=True).gte("created_at", today_start)
    chats_today = await run_in_threadpool(q2.execute)
    chats_today_count = getattr(chats_today, "count", 0)

    # Total messages
    q3 = client.table("messages").select("*", count="exact", head=True)
    total_msgs = await run_in_threadpool(q3.execute)
    total_msgs_count = getattr(total_msgs, "count", 0)

    # Unique users
    q4 = client.table("profiles").select("*", count="exact", head=True)
    total_users = await run_in_threadpool(q4.execute)
    total_users_count = getattr(total_users, "count", 0)

    # Total predictions (logged events)
    q5 = client.table("admin_logs").select("*", count="exact", head=True).eq("event_type", "prediction")
    total_predictions = await run_in_threadpool(q5.execute)
    total_pred_count = getattr(total_predictions, "count", 0)

    return {
        "total_chats": total_chats_count,
        "chats_today": chats_today_count,
        "total_messages": total_msgs_count,
        "total_users": total_users_count,
        "total_predictions": total_pred_count,
    }


@router.get("/daily")
async def get_daily_analytics(days: int = Query(30, ge=1, le=90), admin: Dict[str, Any] = Depends(require_admin)):
    client = get_supabase_client()
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days - 1)

    # Fetch chats created in the date range
    query = client.table("chats").select("created_at").gte("created_at", start.isoformat())
    resp = await run_in_threadpool(query.execute)
    rows = resp.data or []

    daily_counts: Dict[str, int] = {}
    for r in rows:
        day = r["created_at"][:10]
        daily_counts[day] = daily_counts.get(day, 0) + 1

    # Fill in zeros for missing days
    result = []
    for i in range(days):
        day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        result.append({"date": day, "chats": daily_counts.get(day, 0)})

    return {"daily": result, "total_days": days}


@router.get("/predictions")
async def get_prediction_analytics(admin: Dict[str, Any] = Depends(require_admin)):
    # Band distribution from cutoff predictions
    # This is derived from admin_logs prediction events
    client = get_supabase_client()
    query = client.table("admin_logs").select("details").eq("event_type", "prediction").limit(500)
    resp = await run_in_threadpool(query.execute)
    rows = resp.data or []

    band_counts = {"safe": 0, "target": 0, "ambitious": 0}
    for r in rows:
        details = r.get("details", {})
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                details = {}
        bands = details.get("bands") if isinstance(details, dict) else None
        if isinstance(bands, dict):
            for b in ("safe", "target", "ambitious"):
                band_counts[b] = band_counts.get(b, 0) + bands.get(b, 0)

    return {
        "band_distribution": band_counts,
        "total_prediction_events": len(rows),
    }

