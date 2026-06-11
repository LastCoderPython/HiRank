"""
Background profile enrichment task.

Dispatched after each authenticated user's message in the SSE stream.
Extracts structured data (exam, rank, category, percentile) from the
raw message text and backfills NULL fields in the user's profile.

Never overwrites explicit onboarding data — only fills in gaps.
"""

import asyncio
import logging
from app.worker import celery_app

logger = logging.getLogger("rankroute.tasks.enrichment")


@celery_app.task(queue="enrichment", max_retries=1, ignore_result=True)
def enrich_profile_from_message(user_id: str, message: str):
    """Non-blocking: extract structured data from user message and update profile.

    Only updates fields that are currently NULL in the database.
    This ensures explicit onboarding data is never overwritten by inferred data.
    """
    from app.services.profile_enricher import profile_enricher
    from app.db.supabase import get_user_by_id, patch_profile

    updates = profile_enricher.extract(message)
    if not updates:
        return

    try:
        existing = asyncio.run(get_user_by_id(user_id))
        if not existing:
            return

        # Only fill in NULL fields — never overwrite explicit onboarding data
        filtered = {k: v for k, v in updates.items() if not existing.get(k)}
        if filtered:
            asyncio.run(patch_profile(user_id, filtered))
            logger.info(
                "Enriched profile for %s: %s",
                user_id, list(filtered.keys()),
            )
    except Exception as e:
        logger.error("Profile enrichment failed for %s: %s", user_id, e)
