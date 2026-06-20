"""
RankRoute V2 — Upsert Service

Inserts or updates processed web content chunks into the college_web_docs
Chroma collection with stable IDs based on URL + content hash.

Metadata per chunk:
  - college_name
  - page_type
  - source_url
  - scraped_at
  - content_hash
  - is_official
  - domain
  - document_title
  # (freshness computed dynamically at query time — not stored)
  - scrape_version (ISO timestamp of the scrape batch)

Staleness Management:
  - delete_all_for_url():    Wipes all chunks for a URL (used by weekly cron).
  - purge_stale_for_url():   Removes chunks with old scrape_version (used by
                             self-heal during live sessions — zero-downtime).
  - is_url_recently_ingested(): Checks Redis to prevent redundant re-ingestion.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.ingestion.chunker import TextChunk
from app.core.embeddings import embedding_service

logger = logging.getLogger("rankroute.ingestion.upsert")

COLLECTION_NAME = "college_web_docs"


def _compute_stable_id(source_url: str, content_hash: str, chunk_index: int) -> str:
    """Generate a stable, reproducible ID for a chunk."""
    raw = f"{source_url}:{content_hash}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def upsert_chunks(
    chunks: List[TextChunk],
    college_name: str,
    source_url: str,
    domain: str = "",
    document_title: str = "",
    is_official: bool = True,
    page_type_override: Optional[str] = None,
    scraped_at: Optional[str] = None,
    scrape_version: Optional[str] = None,
    validation_status: str = "passed",
) -> Dict[str, Any]:
    """Upsert processed chunks into the college_web_docs Chroma collection.

    Args:
        validation_status: One of "passed", "downgraded", "validator_error".
            Stored in chunk metadata for query-time filtering.

    Returns a summary dict with counts and any errors.
    """
    from app.core.chroma_client import chroma_client

    collection = chroma_client.get_collection(COLLECTION_NAME)

    if not chunks:
        return {"upserted": 0, "skipped": 0, "errors": []}

    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    scrape_version = scrape_version or scraped_at

    # Prepare data for upsert
    texts = [c.text for c in chunks]
    ids = [_compute_stable_id(source_url, c.content_hash, c.chunk_index) for c in chunks]
    metadatas = []
    for c in chunks:
        metadatas.append({
            "college_name": college_name,
            "page_type": page_type_override or c.heading.lower() or "general",
            "source_url": source_url,
            "scraped_at": scraped_at,
            "content_hash": c.content_hash,
            "is_official": is_official,
            "domain": domain,
            "document_title": document_title,
            "chunk_index": c.chunk_index,
            "scrape_version": scrape_version,
            "validation_status": validation_status,
        })

    # Generate embeddings
    try:
        logger.info("Embedding %d chunks...", len(texts))
        embeddings = embedding_service.embed_documents_in_batches(texts, batch_size=32)
    except Exception as e:
        logger.error("Embedding failed: %s", e)
        return {"upserted": 0, "skipped": len(chunks), "errors": [str(e)]}

    # Upsert in batches
    batch_size = 50
    upserted = 0
    errors = []

    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i: i + batch_size]
        batch_docs = texts[i: i + batch_size]
        batch_metas = metadatas[i: i + batch_size]
        batch_embeds = embeddings[i: i + batch_size]

        try:
            collection.upsert(
                ids=batch_ids,
                documents=batch_docs,
                embeddings=batch_embeds,
                metadatas=batch_metas,
            )
            upserted += len(batch_ids)
            logger.info("Upserted %d/%d chunks for %s", upserted, len(ids), college_name)
        except Exception as e:
            errors.append(str(e))
            logger.error("Upsert batch failed: %s", e)

    # Register this URL as ingested in Redis (for dedup in self-heal)
    if upserted > 0:
        _register_ingested_url(source_url)

    return {
        "upserted": upserted,
        "skipped": len(chunks) - upserted,
        "errors": errors,
        "collection": COLLECTION_NAME,
        "total_in_collection": collection.count(),
    }


# ── Staleness Management ──────────────────────────────────────────────

def delete_all_for_url(source_url: str) -> int:
    """Delete ALL chunks for a source URL unconditionally.

    Used by the weekly cron scrape (3 AM, zero traffic).
    Simple and correct — the brief empty window is acceptable.
    """
    from app.core.chroma_client import chroma_client

    collection = chroma_client.get_collection(COLLECTION_NAME)

    try:
        # Get count before delete for logging
        existing = collection.get(where={"source_url": source_url}, include=[])
        count = len(existing["ids"]) if existing and existing.get("ids") else 0

        if count > 0:
            collection.delete(where={"source_url": source_url})
            logger.info("Purged %d old chunks for URL: %s", count, source_url)
        return count
    except Exception as e:
        logger.warning("Failed to purge old chunks for %s: %s", source_url, e)
        return 0


def purge_stale_for_url(source_url: str, current_version: str) -> int:
    """Delete chunks for a URL that have an older scrape_version.

    Used by self_heal_ingest during live sessions — ensures old data
    is only removed AFTER new data is confirmed written (zero downtime).
    """
    from app.core.chroma_client import chroma_client

    collection = chroma_client.get_collection(COLLECTION_NAME)

    try:
        # Find all chunks for this URL
        existing = collection.get(
            where={"source_url": source_url},
            include=["metadatas"],
        )

        if not existing or not existing.get("ids"):
            return 0

        # Collect IDs whose scrape_version != current_version
        stale_ids = []
        for chunk_id, meta in zip(existing["ids"], existing["metadatas"]):
            chunk_version = meta.get("scrape_version", "")
            if chunk_version and chunk_version != current_version:
                stale_ids.append(chunk_id)

        if stale_ids:
            collection.delete(ids=stale_ids)
            logger.info(
                "Purged %d stale chunks (version != %s) for URL: %s",
                len(stale_ids), current_version[:19], source_url,
            )
        return len(stale_ids)
    except Exception as e:
        logger.warning("Failed to purge stale chunks for %s: %s", source_url, e)
        return 0


def is_url_recently_ingested(url: str) -> bool:
    """Check if a URL was ingested recently (within the last 7 days).

    Uses a Redis SET to track ingested URLs. Returns False if Redis
    is unavailable (fail-open: re-ingest is safe, just wasteful).
    """
    try:
        import redis as redis_lib
        from app.config import settings
        r = redis_lib.from_url(settings.redis_url, decode_responses=True)
        return r.sismember("rankroute:ingested_urls", url)
    except Exception as e:
        logger.debug("Redis check failed (fail-open): %s", e)
        return False


def _register_ingested_url(source_url: str) -> None:
    """Record a URL as recently ingested in Redis (TTL = 7 days).

    Prevents the self-heal loop from re-ingesting the same URL
    on every Tavily hit. The weekly cron naturally refreshes all
    URLs regardless of this cache.
    """
    try:
        import redis as redis_lib
        from app.config import settings
        r = redis_lib.from_url(settings.redis_url, decode_responses=True)
        r.sadd("rankroute:ingested_urls", source_url)
        # Expire the whole set after 7 days. The weekly cron will
        # re-populate it naturally on the next scrape cycle.
        r.expire("rankroute:ingested_urls", 7 * 24 * 3600)
        logger.debug("Registered ingested URL: %s", source_url)
    except Exception as e:
        logger.debug("Redis registration failed (non-fatal): %s", e)
