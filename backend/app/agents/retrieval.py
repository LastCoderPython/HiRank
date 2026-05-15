from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.core.chroma_client import chroma_client


@dataclass
class RetrievalCandidate:
    source_id: str
    text: str
    metadata: Dict
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    final_score: float = 0.0


def _tokenize(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", text.lower()) if len(t) > 2}


class HybridRetriever:
    def __init__(self, semantic_weight: float = 0.65, keyword_weight: float = 0.35):
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight

    async def retrieve(self, query: str, collection_name: str, top_k: int = 8) -> List[RetrievalCandidate]:
        semantic_results = await asyncio.to_thread(
            chroma_client.search_similar,
            query,
            collection_name,
            max(top_k * 2, 12),
            None,
        )

        query_tokens = _tokenize(query)
        candidates: List[RetrievalCandidate] = []
        for row in semantic_results:
            text = row.get("document", "")
            source_id = row.get("id", "unknown")
            metadata = row.get("metadata", {})

            semantic = max(0.0, min(1.0, float(row.get("match_percentage", 0.0)) / 100.0))
            doc_tokens = _tokenize(text)
            overlap = len(query_tokens & doc_tokens)
            keyword = overlap / max(1, len(query_tokens))

            year = int(metadata.get("year", 0) or 0)
            freshness_bonus = 0.03 if year >= 2023 else 0.0

            final = (self.semantic_weight * semantic) + (self.keyword_weight * keyword) + freshness_bonus
            candidates.append(
                RetrievalCandidate(
                    source_id=source_id,
                    text=text,
                    metadata=metadata,
                    semantic_score=semantic,
                    keyword_score=keyword,
                    final_score=final,
                )
            )

        reranked = sorted(candidates, key=lambda item: item.final_score, reverse=True)
        return reranked[:top_k]

    @staticmethod
    def compress_chunks(candidates: List[RetrievalCandidate], max_chars: int = 420) -> List[RetrievalCandidate]:
        compressed: List[RetrievalCandidate] = []
        for item in candidates:
            text = item.text.strip()
            if len(text) > max_chars:
                text = text[:max_chars].rsplit(" ", 1)[0] + "..."
            compressed.append(
                RetrievalCandidate(
                    source_id=item.source_id,
                    text=text,
                    metadata=item.metadata,
                    semantic_score=item.semantic_score,
                    keyword_score=item.keyword_score,
                    final_score=item.final_score,
                )
            )
        return compressed

    @staticmethod
    def build_citations(candidates: List[RetrievalCandidate]) -> List[Dict[str, Optional[str]]]:
        citations = []
        for index, item in enumerate(candidates, start=1):
            citations.append(
                {
                    "citation_id": f"C{index}",
                    "source_id": item.source_id,
                    "title": item.metadata.get("college_name") or item.metadata.get("institute") or "Education Source",
                    "url": item.metadata.get("source_url"),
                    "excerpt": item.text,
                    "score": round(item.final_score, 4),
                }
            )
        return citations


hybrid_retriever = HybridRetriever()
