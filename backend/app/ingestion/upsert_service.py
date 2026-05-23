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
  - freshness_bucket
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.ingestion.chunker import TextChunk
from app.ingestion.embedder import embed_chunks

logger = logging.getLogger("rankroute.ingestion.upsert")

COLLECTION_NAME = "college_web_docs"


def _compute_stable_id(source_url: str, content_hash: str, chunk_index: int) -> str:
    """Generate a stable, reproducible ID for a chunk."""
    raw = f"{source_url}:{content_hash}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _compute_freshness_bucket(scraped_at: Optional[str] = None) -> str:
    """Compute a freshness bucket based on scrape time."""
    if not scraped_at:
        return "unknown"
    try:
        scraped_dt = datetime.fromisoformat(scraped_at)
        now = datetime.now(timezone.utc)
        days_old = (now - scraped_dt).days
        if days_old <= 7:
            return "current"
        elif days_old <= 30:
            return "recent"
        elif days_old <= 180:
            return "stale"
        else:
            return "archive"
    except Exception:
        return "unknown"


def upsert_chunks(
    chunks: List[TextChunk],
    college_name: str,
    source_url: str,
    domain: str = "",
    document_title: str = "",
    is_official: bool = True,
    page_type_override: Optional[str] = None,
    scraped_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Upsert processed chunks into the college_web_docs Chroma collection.

    Returns a summary dict with counts and any errors.
    """
    from app.core.chroma_client import chroma_client

    collection = chroma_client.client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    if not chunks:
        return {"upserted": 0, "skipped": 0, "errors": []}

    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    freshness = _compute_freshness_bucket(scraped_at)

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
            "freshness_bucket": freshness,
            "chunk_index": c.chunk_index,
        })

    # Generate embeddings
    try:
        embeddings = embed_chunks(texts)
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

    return {
        "upserted": upserted,
        "skipped": len(chunks) - upserted,
        "errors": errors,
        "collection": COLLECTION_NAME,
        "total_in_collection": collection.count(),
    }
