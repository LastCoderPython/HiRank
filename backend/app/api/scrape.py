"""
RankRoute V2 — Scrape API Routes

Provides endpoints to trigger and monitor background web ingestion jobs.
Uses FastAPI BackgroundTasks for deferred execution.

Endpoints:
  - POST /api/scrape/run   — trigger scrape for approved URLs
  - GET  /api/scrape/status/{job_id} — check job progress
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("rankroute.api.scrape")
router = APIRouter(prefix="/api/scrape", tags=["scrape"])


# ── In-memory job store (upgrade to Redis/DB if scale requires) ───────
_jobs: Dict[str, Dict[str, Any]] = {}


# ── Request / Response Models ─────────────────────────────────────────

class ScrapeRequest(BaseModel):
    """Request body for POST /api/scrape/run."""
    urls: List[str] = Field(..., min_length=1, max_length=20)
    college_name: str = Field(..., min_length=1)
    is_official: bool = True


class ScrapeJobResponse(BaseModel):
    """Response for POST /api/scrape/run."""
    job_id: str
    status: str
    urls_queued: int
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


# ── Background ingestion task ─────────────────────────────────────────

async def _run_ingestion_job(job_id: str, urls: List[str], college_name: str, is_official: bool):
    """Background task: fetch → clean → chunk → embed → upsert."""
    from app.ingestion.scrape_runner import fetch_page, is_approved_url
    from app.ingestion.page_cleaner import clean_page
    from app.ingestion.chunker import chunk_text
    from app.ingestion.upsert_service import upsert_chunks

    job = _jobs[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.utcnow().isoformat()

    total_chunks_upserted = 0

    for url in urls:
        if not is_approved_url(url):
            job["errors"].append(f"Rejected unapproved URL: {url}")
            job["urls_failed"] += 1
            continue

        try:
            # Step 1: Fetch
            result = await fetch_page(url)
            if not result.success:
                job["errors"].append(f"Fetch failed for {url}: {result.error}")
                job["urls_failed"] += 1
                continue

            # Step 2: Clean
            cleaned = clean_page(result.content)
            if not cleaned.text or cleaned.word_count < 20:
                job["errors"].append(f"Skipped {url}: insufficient content ({cleaned.word_count} words)")
                job["urls_failed"] += 1
                continue

            # Step 3: Chunk
            chunks = chunk_text(cleaned.text)
            if not chunks:
                job["errors"].append(f"Skipped {url}: no valid chunks after processing")
                job["urls_failed"] += 1
                continue

            # Step 4 & 5: Embed + Upsert
            upsert_result = upsert_chunks(
                chunks=chunks,
                college_name=college_name,
                source_url=url,
                domain=result.domain,
                document_title=cleaned.title,
                is_official=is_official,
                page_type_override=cleaned.page_type,
                scraped_at=result.fetched_at,
            )

            total_chunks_upserted += upsert_result.get("upserted", 0)
            if upsert_result.get("errors"):
                job["errors"].extend(upsert_result["errors"])

            job["urls_completed"] += 1
            logger.info(
                "Ingested %s: %d chunks for %s",
                url, upsert_result.get("upserted", 0), college_name,
            )

        except Exception as e:
            job["errors"].append(f"Error processing {url}: {str(e)}")
            job["urls_failed"] += 1
            logger.error("Ingestion error for %s: %s", url, e)

    job["chunks_upserted"] = total_chunks_upserted
    job["status"] = "completed"
    job["completed_at"] = datetime.utcnow().isoformat()
    logger.info("Job %s completed: %d URLs, %d chunks", job_id, job["urls_completed"], total_chunks_upserted)


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/run", response_model=ScrapeJobResponse)
async def trigger_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Trigger a background scrape+ingestion job for approved URLs.

    Only official college domains and government counseling portals are allowed.
    Returns immediately with a job_id for status polling.
    """
    from app.ingestion.scrape_runner import is_approved_url

    # Pre-validate all URLs
    rejected = [url for url in request.urls if not is_approved_url(url)]
    if rejected:
        raise HTTPException(
            status_code=400,
            detail=f"Unapproved URLs: {rejected}. Only official college and counseling domains are allowed.",
        )

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "queued",
        "urls_total": len(request.urls),
        "urls_completed": 0,
        "urls_failed": 0,
        "chunks_upserted": 0,
        "errors": [],
        "started_at": None,
        "completed_at": None,
    }

    background_tasks.add_task(
        _run_ingestion_job,
        job_id=job_id,
        urls=request.urls,
        college_name=request.college_name,
        is_official=request.is_official,
    )

    return ScrapeJobResponse(
        job_id=job_id,
        status="queued",
        urls_queued=len(request.urls),
        message=f"Scrape job queued for {len(request.urls)} URL(s) under '{request.college_name}'.",
    )


@router.get("/status/{job_id}", response_model=ScrapeStatusResponse)
async def get_scrape_status(job_id: str):
    """Check the status of a scrape+ingestion job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    return ScrapeStatusResponse(
        job_id=job_id,
        status=job["status"],
        urls_total=job["urls_total"],
        urls_completed=job["urls_completed"],
        urls_failed=job["urls_failed"],
        chunks_upserted=job["chunks_upserted"],
        errors=job["errors"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
    )
