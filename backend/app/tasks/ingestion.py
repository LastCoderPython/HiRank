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
    """
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _async_ingestion(self.request.id, urls, college_name, is_official)
        )
        return result
    finally:
        loop.close()


async def _async_ingestion(task_id, urls, college_name, is_official):
    """The actual async ingestion logic, extracted from scrape.py."""
    from app.ingestion.scrape_runner import fetch_page, is_approved_url
    from app.ingestion.page_cleaner import clean_page
    from app.ingestion.chunker import chunk_text
    from app.ingestion.upsert_service import upsert_chunks

    results = {
        "task_id": task_id,
        "urls_total": len(urls),
        "urls_completed": 0,
        "urls_failed": 0,
        "chunks_upserted": 0,
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

            # Step 3: Chunk
            chunks = chunk_text(cleaned.text)
            if not chunks:
                results["errors"].append(f"Skipped {url}: no valid chunks")
                results["urls_failed"] += 1
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
    Uses the exact same pipeline: fetch → clean → chunk → embed → upsert.
    """
    import asyncio
    from urllib.parse import urlparse

    # Derive a college name from the domain
    hostname = urlparse(url).hostname or ""
    college_name = hostname.replace("www.", "").split(".")[0].upper()

    logger.info(f"Self-heal ingesting: {url} (college: {college_name})")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _async_ingestion(
                task_id=self.request.id,
                urls=[url],
                college_name=college_name,
                is_official=True,
            )
        )
        logger.info(f"Self-heal complete for {url}: {result}")
        return result
    finally:
        loop.close()
