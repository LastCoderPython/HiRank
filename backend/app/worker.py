"""
RankRoute — Celery Worker Application

Defines the Celery app, task autodiscovery, and configuration.
Both the API (for .delay() calls) and the worker process import this.
"""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "rankroute",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timeouts
    task_time_limit=600,          # hard kill after 10 min
    task_soft_time_limit=540,     # raise SoftTimeLimitExceeded at 9 min

    # Reliability
    task_acks_late=True,          # ack AFTER task completes (crash-safe)
    worker_prefetch_multiplier=1, # one task at a time per worker

    # Task routing
    task_routes={
        "app.tasks.ingestion.*": {"queue": "ingestion"},
    },

    # Autodiscover
    imports=["app.tasks.ingestion"],
)

# ── Scheduled tasks (Celery Beat) ─────────────────────────────────────
from celery.schedules import crontab
from app.services.domain_registry import START_URLS

celery_app.conf.beat_schedule = {
    # Re-scrape all approved colleges every Monday at 3 AM
    "weekly-full-scrape": {
        "task": "app.tasks.ingestion.run_ingestion_job",
        "schedule": crontab(hour=3, minute=0, day_of_week=1),
        "args": [
            START_URLS,
            "ALL_COLLEGES",
            True,
        ],
    },
}
