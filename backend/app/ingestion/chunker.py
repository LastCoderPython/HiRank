"""
RankRoute V2 — Section-Aware Chunker

Splits cleaned page text into semantic chunks that preserve heading
context. Prefers section-aware splitting over fixed-size blind chunking.
"""

from __future__ import annotations

import re
import hashlib
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger("rankroute.ingestion.chunker")


@dataclass
class TextChunk:
    """A single semantic chunk with heading context."""
    text: str
    heading: str = ""
    chunk_index: int = 0
    content_hash: str = ""
    char_count: int = 0


def chunk_text(
    text: str,
    max_chunk_chars: int = 800,
    min_chunk_chars: int = 100,
    overlap_chars: int = 50,
) -> List[TextChunk]:
    """Split text into section-aware semantic chunks.

    Strategy:
      1. Split on paragraph/section boundaries first.
      2. If a section is too long, split on sentence boundaries.
      3. Preserve heading context in each chunk.
      4. Deduplicate near-identical chunks.
    """
    if not text or len(text.strip()) < min_chunk_chars:
        return []

    # Split on double-newlines or heading-like patterns
    sections = re.split(r"\n{2,}|(?=\b[A-Z][A-Z\s]{5,}:)", text)
    sections = [s.strip() for s in sections if s.strip()]

    chunks: List[TextChunk] = []
    current_heading = ""
    chunk_index = 0

    for section in sections:
        # Detect heading-like patterns
        heading_match = re.match(r"^([A-Z][A-Z\s&]{3,}):?\s*(.*)", section)
        if heading_match and len(heading_match.group(1)) < 60:
            current_heading = heading_match.group(1).strip()
            remaining = heading_match.group(2).strip()
            if remaining:
                section = remaining
            else:
                continue

        if len(section) <= max_chunk_chars:
            # Section fits in one chunk
            chunk = TextChunk(
                text=section,
                heading=current_heading,
                chunk_index=chunk_index,
                content_hash=hashlib.sha256(section.encode()).hexdigest()[:12],
                char_count=len(section),
            )
            chunks.append(chunk)
            chunk_index += 1
        else:
            # Section too long — split on sentences
            sentences = re.split(r"(?<=[.!?])\s+", section)
            current_chunk = ""

            for sentence in sentences:
                if len(current_chunk) + len(sentence) + 1 <= max_chunk_chars:
                    current_chunk = f"{current_chunk} {sentence}".strip() if current_chunk else sentence
                else:
                    if current_chunk and len(current_chunk) >= min_chunk_chars:
                        chunk = TextChunk(
                            text=current_chunk,
                            heading=current_heading,
                            chunk_index=chunk_index,
                            content_hash=hashlib.sha256(current_chunk.encode()).hexdigest()[:12],
                            char_count=len(current_chunk),
                        )
                        chunks.append(chunk)
                        chunk_index += 1

                    # Start new chunk with overlap
                    if overlap_chars > 0 and current_chunk:
                        overlap = current_chunk[-overlap_chars:]
                        current_chunk = f"{overlap} {sentence}".strip()
                    else:
                        current_chunk = sentence

            # Flush remaining
            if current_chunk and len(current_chunk) >= min_chunk_chars:
                chunk = TextChunk(
                    text=current_chunk,
                    heading=current_heading,
                    chunk_index=chunk_index,
                    content_hash=hashlib.sha256(current_chunk.encode()).hexdigest()[:12],
                    char_count=len(current_chunk),
                )
                chunks.append(chunk)
                chunk_index += 1

    # Deduplicate near-identical chunks
    chunks = _deduplicate(chunks)

    return chunks


def _deduplicate(chunks: List[TextChunk]) -> List[TextChunk]:
    """Remove chunks with identical content hashes."""
    seen_hashes = set()
    unique = []
    for chunk in chunks:
        if chunk.content_hash not in seen_hashes:
            seen_hashes.add(chunk.content_hash)
            unique.append(chunk)
    return unique
