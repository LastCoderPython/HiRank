"""
RankRoute V2 — Scrape API Routes

Provides endpoints to trigger and monitor background web ingestion jobs.
Uses Celery for durable task execution (jobs survive restarts).

Endpoints:
  - POST /api/scrape/run       — trigger scrape for approved URLs
  - POST /api/scrape/discover  — discover + ingest subpages from homepages
  - GET  /api/scrape/status/{job_id} — check job progress
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from app.middleware.api_key_auth import require_agent_api_key
from pydantic import BaseModel, Field

logger = logging.getLogger("rankroute.api.scrape")
router = APIRouter(prefix="/api/scrape", tags=["scrape"])


# ── Request / Response Models ─────────────────────────────────────────

class ScrapeRequest(BaseModel):
    model_config = {"extra": "forbid"}
    urls: List[str] = Field(..., min_length=1, max_length=20)
    college_name: str = Field(..., min_length=1)
    is_official: bool = True


class ScrapeJobResponse(BaseModel):
    """Response for POST /api/scrape/run."""
    job_id: str
    status: str
    urls_queued: int
    message: str


class SubpageDiscoveryRequest(BaseModel):
    model_config = {"extra": "forbid"}
    homepage_urls: List[str] = Field(
        ..., min_length=1, max_length=50,
        description="Homepage URLs to discover subpages from",
    )
    college_name: str = Field(..., min_length=1)
    max_subpages_per_homepage: int = Field(default=20, ge=1, le=100)


class SubpageDiscoveryResponse(BaseModel):
    """Response for POST /api/scrape/discover."""
    job_id: str
    status: str
    homepages: int
    message: str


class ScrapeStatusResponse(BaseModel):
    """Response for GET /api/scrape/status/{job_id}."""
    job_id: str
    status: str
    urls_total: int = 0
    urls_completed: int = 0
    urls_failed: int = 0
    chunks_upserted: int = 0
    errors: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# ── Celery state → response mapping ──────────────────────────────────

_CELERY_STATE_MAP = {
    "PENDING": "queued",
    "STARTED": "running",
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "RETRY": "retrying",
    "REVOKED": "cancelled",
}


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/run", response_model=ScrapeJobResponse)
async def trigger_scrape(
    request: ScrapeRequest,
    _auth=Depends(require_agent_api_key),
):
    """Trigger a background scrape+ingestion job for approved URLs.

    Only official college domains and government counseling portals are allowed.
    Returns immediately with a job_id for status polling.
    Job state is persisted in Redis (survives restarts).
    """
    from app.ingestion.scrape_runner import is_approved_url
    from app.tasks.ingestion import run_ingestion_job

    # Pre-validate all URLs
    rejected = [url for url in request.urls if not is_approved_url(url)]
    if rejected:
        raise HTTPException(
            status_code=400,
            detail=f"Unapproved URLs: {rejected}. Only official college and counseling domains are allowed.",
        )

    # Dispatch to Celery worker (runs in separate process)
    task = run_ingestion_job.delay(
        urls=request.urls,
        college_name=request.college_name,
        is_official=request.is_official,
    )

    return ScrapeJobResponse(
        job_id=task.id,
        status="queued",
        urls_queued=len(request.urls),
        message=f"Scrape job queued for {len(request.urls)} URL(s) under '{request.college_name}'.",
    )


@router.post("/discover", response_model=SubpageDiscoveryResponse)
async def trigger_subpage_discovery(
    request: SubpageDiscoveryRequest,
    _auth=Depends(require_agent_api_key),
):
    """Discover subpages from approved college homepages and ingest them.

    For each homepage URL:
      1. Fetch the homepage HTML
      2. Parse all <a> links
      3. Filter for same-domain, relevant subpage links (fee, placement,
         hostel, admission, etc.)
      4. Ingest all discovered subpages + original homepages into ChromaDB

    Returns immediately with a job_id for status polling.
    """
    from app.ingestion.scrape_runner import is_approved_url
    from app.tasks.ingestion import discover_and_ingest_job

    rejected = [
        url for url in request.homepage_urls if not is_approved_url(url)
    ]
    if rejected:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unapproved homepage URLs: {rejected}. "
                "Only official college and counseling domains are allowed."
            ),
        )

    task = discover_and_ingest_job.delay(
        homepage_urls=request.homepage_urls,
        college_name=request.college_name,
        max_subpages_per_homepage=request.max_subpages_per_homepage,
    )

    return SubpageDiscoveryResponse(
        job_id=task.id,
        status="queued",
        homepages=len(request.homepage_urls),
        message=(
            f"Subpage discovery queued for {len(request.homepage_urls)} "
            f"homepage(s) under '{request.college_name}'."
        ),
    )


@router.get("/status/{job_id}", response_model=ScrapeStatusResponse)
async def get_scrape_status(
    job_id: str,
    _auth=Depends(require_agent_api_key),
):
    """Check the status of a scrape+ingestion job (state persisted in Redis)."""
    from celery.result import AsyncResult
    from app.worker import celery_app

    result = AsyncResult(job_id, app=celery_app)

    if result.state == "PENDING":
        # Could be genuinely pending OR an unknown task ID
        return ScrapeStatusResponse(
            job_id=job_id,
            status="queued",
        )

    status = _CELERY_STATE_MAP.get(result.state, result.state.lower())

    # Extract result data if task completed successfully
    if result.state == "SUCCESS" and isinstance(result.result, dict):
        data = result.result
        return ScrapeStatusResponse(
            job_id=job_id,
            status=status,
            urls_total=data.get("urls_total", 0),
            urls_completed=data.get("urls_completed", 0),
            urls_failed=data.get("urls_failed", 0),
            chunks_upserted=data.get("chunks_upserted", 0),
            errors=data.get("errors", []),
        )

    # Failed task
    if result.state == "FAILURE":
        return ScrapeStatusResponse(
            job_id=job_id,
            status="failed",
            errors=[str(result.result)] if result.result else ["Unknown error"],
        )

    return ScrapeStatusResponse(
        job_id=job_id,
        status=status,
    )
