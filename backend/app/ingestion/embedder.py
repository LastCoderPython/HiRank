"""
RankRoute V2 — Embedder

Generates embeddings for text chunks using the existing EmbeddingService.
This module wraps the HuggingFace embedding model for batch processing
during ingestion.
"""

from __future__ import annotations

import logging
from typing import List

from app.core.embeddings import embedding_service

logger = logging.getLogger("rankroute.ingestion.embedder")


def embed_chunks(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Embed a list of text chunks in batches.

    Uses the existing HuggingFace embedding model configured in settings.
    """
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        embeddings = embedding_service.embed_documents(batch)
        all_embeddings.extend(embeddings)
        logger.info("Embedded batch %d-%d / %d", i, min(i + batch_size, len(texts)), len(texts))

    return all_embeddings
