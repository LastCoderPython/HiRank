"""
RankRoute — Celery Ingestion Tasks

Full pipeline: fetch → clean → chunk → embed → upsert
Runs in dedicated Celery worker process, NOT in the API process.
Includes retry logic for transient HTTP failures.
"""
import logging
from celery import shared_task
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("rankroute.tasks.ingestion")


@shared_task(
    bind=True,
    name="app.tasks.ingestion.run_ingestion_job",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    queue="ingestion",
)
def run_ingestion_job(self, urls: list, college_name: str, is_official: bool = True):
    """
    Full ingestion pipeline for a list of URLs.
    Runs in the Celery worker process, NOT in the API process.
    Uses delete-before-upsert (safe at 3 AM, zero traffic).
    """
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _async_ingestion(
                self.request.id, urls, college_name, is_official,
                purge_before_upsert=True,
            )
        )
        return result
    finally:
        loop.close()


async def _async_ingestion(
    task_id, urls, college_name, is_official,
    purge_before_upsert: bool = False,
    scrape_version: str = None,
):
    """The actual async ingestion logic, extracted from scrape.py.

    Args:
        purge_before_upsert: If True, deletes all old chunks for each URL
            before upserting (used by weekly cron — safe at 3 AM).
        scrape_version: If set, tags all new chunks with this version
            (used by self-heal for post-upsert stale purging).
    """
    from app.ingestion.scrape_runner import fetch_page, is_approved_url
    from app.ingestion.page_cleaner import clean_page
    from app.ingestion.chunker import chunk_text
    from app.ingestion.upsert_service import upsert_chunks, delete_all_for_url
    from app.ingestion.content_validator import validate_page
    import json

    results = {
        "task_id": task_id,
        "urls_total": len(urls),
        "urls_completed": 0,
        "urls_failed": 0,
        "chunks_upserted": 0,
        "chunks_purged": 0,
        "errors": [],
    }

    for url in urls:
        if not is_approved_url(url):
            results["errors"].append(f"Rejected unapproved URL: {url}")
            results["urls_failed"] += 1
            continue

        try:
            # Step 1: Fetch (with retry for transient failures)
            result = await _fetch_with_retry(url)
            if not result.success:
                results["errors"].append(f"Fetch failed for {url}: {result.error}")
                results["urls_failed"] += 1
                continue

            # Step 2: Clean
            cleaned = clean_page(result.content)
            if not cleaned.text or cleaned.word_count < 20:
                results["errors"].append(f"Skipped {url}: insufficient content")
                results["urls_failed"] += 1
                continue

            # Step 3: Validate content before embedding (Phase 18)
            validation_status = "passed"
            page_type_override = cleaned.page_type
            try:
                validation = validate_page(cleaned, result.content, url)
                if not validation.is_valid:
                    results["errors"].append(f"Skipped {url}: {validation.reason}")
                    results["urls_failed"] += 1
                    logger.info(json.dumps({
                        "event": "validation_rejected",
                        "url": url,
                        "reason": validation.reason,
                        "rejected_by": validation.rejected_by,
                        "page_type": cleaned.page_type,
                        "word_count": cleaned.word_count,
                    }))
                    continue
                if validation.downgrade_to:
                    page_type_override = validation.downgrade_to
                    validation_status = "downgraded"
                    logger.info(json.dumps({
                        "event": "validation_downgraded",
                        "url": url,
                        "from": cleaned.page_type,
                        "to": validation.downgrade_to,
                    }))
            except Exception as ve:
                logger.error("Validator crashed for %s: %s", url, ve, exc_info=True)
                validation_status = "validator_error"

            # Step 4: Chunk
            chunks = chunk_text(cleaned.text)
            if not chunks:
                results["errors"].append(f"Skipped {url}: no valid chunks")
                results["urls_failed"] += 1
                continue

            # Step 5: Purge old data (weekly cron path only)
            if purge_before_upsert:
                purged = delete_all_for_url(url)
                results["chunks_purged"] += purged

            # Step 6 & 7: Embed + Upsert
            upsert_result = upsert_chunks(
                chunks=chunks,
                college_name=college_name,
                source_url=url,
                domain=result.domain,
                document_title=cleaned.title,
                is_official=is_official,
                page_type_override=page_type_override,
                scraped_at=result.fetched_at,
                scrape_version=scrape_version,
                validation_status=validation_status,
            )

            results["chunks_upserted"] += upsert_result.get("upserted", 0)
            if upsert_result.get("errors"):
                results["errors"].extend(upsert_result["errors"])

            results["urls_completed"] += 1
            logger.info("Ingested %s: %d chunks", url, upsert_result.get("upserted", 0))

        except Exception as e:
            results["errors"].append(f"Error processing {url}: {str(e)}")
            results["urls_failed"] += 1
            logger.error("Ingestion error for %s: %s", url, e)

    return results


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
async def _fetch_with_retry(url):
    """Fetch with exponential backoff retry for transient HTTP failures."""
    from app.ingestion.scrape_runner import fetch_page
    result = await fetch_page(url)
    if not result.success and result.status_code in (429, 500, 502, 503, 504):
        raise Exception(f"Transient error {result.status_code} for {url}")
    return result


# ── Self-Healing Task ─────────────────────────────────────────────────
@shared_task(
    bind=True,
    name="app.tasks.ingestion.self_heal_ingest",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
    queue="ingestion",
)
def self_heal_ingest(self, url: str):
    """Auto-ingest a single newly discovered official URL into ChromaDB.

    Triggered by web_search.py when the Tavily fallback finds a new
    official page that isn't in our database yet.

    Uses version-tagging: writes new chunks first, then purges old
    chunks with a different scrape_version. This guarantees zero
    downtime — old data serves reads until new data is confirmed.
    """
    import asyncio
    from datetime import datetime, timezone
    from urllib.parse import urlparse
    from app.ingestion.upsert_service import purge_stale_for_url

    # Derive a college name from the domain
    hostname = urlparse(url).hostname or ""
    college_name = hostname.replace("www.", "").split(".")[0].upper()

    # Generate a unique version tag for this scrape batch
    scrape_version = datetime.now(timezone.utc).isoformat()

    logger.info(f"Self-heal ingesting: {url} (college: {college_name}, version: {scrape_version[:19]})")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Step 1: Write new chunks (old chunks still serve reads)
        result = loop.run_until_complete(
            _async_ingestion(
                task_id=self.request.id,
                urls=[url],
                college_name=college_name,
                is_official=True,
                purge_before_upsert=False,
                scrape_version=scrape_version,
            )
        )

        # Step 2: Only after new chunks are confirmed, purge old versions
        if result.get("urls_completed", 0) > 0:
            purged = purge_stale_for_url(url, scrape_version)
            result["chunks_purged"] = purged
            logger.info(f"Self-heal complete for {url}: {result}")
        else:
            logger.warning(f"Self-heal produced no chunks for {url}, skipping purge")

        return result
    finally:
        loop.close()


# ── Subpage Discovery Task (P0) ───────────────────────────────────────
@shared_task(
    bind=True,
    name="app.tasks.ingestion.discover_and_ingest_job",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    queue="ingestion",
)
def discover_and_ingest_job(
    self,
    homepage_urls: list,
    college_name: str,
    is_official: bool = True,
    max_subpages_per_homepage: int = 20,
):
    """Discover subpages from homepages, then ingest everything.

    Step 1: Discover relevant subpage URLs from each homepage.
    Step 2: Merge homepages + discovered subpages into one ingestion run.
    Step 3: Ingest all URLs (homepages included) into ChromaDB.

    This is the P0 fix for the 20%+ miss rate on fee/placement/hostel
    queries. The weekly cron only scrapes 14 hardcoded URLs — subpages
    are never ingested, causing dense ChromaDB misses.
    """
    from app.ingestion.subpage_discovery import collect_subpage_urls

    discovered = collect_subpage_urls(
        homepage_urls,
        max_per_homepage=max_subpages_per_homepage,
    )

    all_urls = list(homepage_urls)
    total_discovered = 0
    for homepage, subpages in discovered.items():
        all_urls.extend(subpages)
        total_discovered += len(subpages)
        logger.info(
            "Discovered %d subpages from %s",
            len(subpages), homepage,
        )

    logger.info(
        "Starting ingestion: %d homepages + %d discovered subpages = %d URLs",
        len(homepage_urls), total_discovered, len(all_urls),
    )

    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _async_ingestion(
                self.request.id, all_urls, college_name, is_official,
                purge_before_upsert=True,
            )
        )
        result["homepages"] = len(homepage_urls)
        result["subpages_discovered"] = total_discovered
        return result
    finally:
        loop.close()


# ── Admin Alert Task ──────────────────────────────────────────────────
@shared_task(
    name="app.tasks.ingestion.send_admin_alert",
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def send_admin_alert(level: str, usage: int, quota: int):
    """Send admin alert email for Tavily quota thresholds or daily digest.

    Dispatched by usage_service when global Tavily counter crosses
    50% or 90% thresholds, or by Celery Beat for the daily digest.

    Runs in Celery worker — never blocks the student's chat response.
    """
    from app.services.alert_service import alert_service
    success = alert_service.send(level, usage, quota)
    if success:
        logger.info("Admin alert sent: level=%s, usage=%d/%d", level, usage, quota)
    else:
        logger.warning("Admin alert failed or not configured: level=%s", level)
    return {"level": level, "usage": usage, "quota": quota, "sent": success}
