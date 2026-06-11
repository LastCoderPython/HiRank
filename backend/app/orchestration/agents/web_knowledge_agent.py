"""
RankRoute V2 — Web Knowledge Agent

Retrieves processed official college content from the `college_web_docs`
Chroma collection using metadata filters before semantic search.

Responsible for descriptive and freshness-sensitive questions:
  - hostel, facilities, placements, fees
  - recent notices, admission updates
  - college-specific web summaries

Design (from V2 plan):
  - Build metadata filters like college_name, page_type, is_official
  - Retrieve a small number of relevant chunks
  - Compress them into factual summary points
  - Return sources and freshness indicators
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.orchestration.types import (
    RequestFrame,
    WebKnowledgeChunk,
    WebKnowledgeOutput,
)
from app.retrieval.metadata_filters import build_college_filter, intent_to_page_types

logger = logging.getLogger("rankroute.agents.web_knowledge")


class WebKnowledgeAgent:
    """
    Specialist agent for descriptive college knowledge retrieval.

    Uses the `college_web_docs` Chroma collection with metadata
    filters before semantic search. Returns structured chunks
    with source attribution and freshness indicators.
    """

    COLLECTION_NAME = "college_web_docs"

    FRESHNESS_MULTIPLIER = {
        "current": 1.0,
        "recent": 0.9,
        "stale": 0.7,
        "archive": 0.5,
        "unknown": 0.6,
    }

    def __init__(self):
        self._collection = None
        self._initialized = False

    def _ensure_collection(self):
        """Lazily initialize the Chroma collection."""
        if not self._initialized:
            try:
                from app.core.chroma_client import chroma_client
                self._collection = chroma_client.client.get_or_create_collection(
                    name=self.COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
                self._initialized = True
                logger.info(
                    "WebKnowledgeAgent: collection '%s' has %d documents",
                    self.COLLECTION_NAME,
                    self._collection.count(),
                )
            except Exception as e:
                logger.error("Failed to init college_web_docs collection: %s", e)
                self._collection = None

    @staticmethod
    def _compute_freshness_bucket(scraped_at: Optional[str] = None) -> str:
        """Compute a freshness bucket based on scrape time (dynamic at query time)."""
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

    async def run(self, frame: RequestFrame) -> WebKnowledgeOutput:
        """Execute descriptive retrieval for a given RequestFrame."""
        self._ensure_collection()

        # 1) If the database is completely empty, fail fast (Tier 2)
        if self._collection is None or self._collection.count() == 0:
            page_types = intent_to_page_types(frame.intent)
            logger.info(json.dumps({
                "event": "chroma_empty",
                "intent": frame.intent,
                "college_targets": frame.college_targets,
                "page_types": page_types,
                "query_preview": frame.raw_query[:100],
            }))
            return await self._fallback_to_live_search(frame)

        # Build metadata filters
        page_types = intent_to_page_types(frame.intent)
        college_targets = frame.college_targets if frame.college_targets else None

        where_filter = build_college_filter(
            college_names=college_targets,
            page_types=page_types,
            is_official=True,
        )

        # Query Chroma with metadata filter + semantic search
        try:
            from app.core.embeddings import embedding_service
            query_embedding = embedding_service.embed_query(frame.raw_query)

            query_kwargs: Dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": 5,
            }
            if where_filter:
                query_kwargs["where"] = where_filter

            results = self._collection.query(**query_kwargs)

            chunks = self._format_results(results)
            
            if not chunks:
                logger.info(json.dumps({
                    "event": "chroma_miss",
                    "intent": frame.intent,
                    "college_targets": frame.college_targets,
                    "page_types": page_types,
                    "query_preview": frame.raw_query[:100],
                }))
                return await self._fallback_to_live_search(frame)

            chunks.sort(key=lambda c: c.relevance_score, reverse=True)
            summary_points = self._extract_summary_points(chunks)

            freshness_note = None
            if frame.intent == "recent_update":
                freshness_note = self._check_freshness(chunks)

            return WebKnowledgeOutput(
                chunks=chunks,
                summary_points=summary_points,
                sources_used=len(chunks),
                freshness_note=freshness_note,
            )

        except Exception as e:
            logger.error("WebKnowledgeAgent query failed: %s", e)
            return await self._fallback_to_local_data(frame)

    def _format_results(self, results: Dict) -> List[WebKnowledgeChunk]:
        """Convert Chroma query results to WebKnowledgeChunk objects with freshness-adjusted scores."""
        chunks = []
        if not results or not results.get("documents") or not results["documents"][0]:
            return chunks

        documents = results["documents"][0]
        metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(documents)
        distances = results["distances"][0] if results.get("distances") else [0.5] * len(documents)

        for doc, meta, dist in zip(documents, metadatas, distances):
            scraped_at = meta.get("scraped_at")
            freshness = self._compute_freshness_bucket(scraped_at)
            relevance = max(0, min(1.0, 1.0 - dist))
            multiplier = self.FRESHNESS_MULTIPLIER.get(freshness, 0.6)
            adjusted_score = round(relevance * multiplier, 4)

            chunks.append(WebKnowledgeChunk(
                text=doc,
                college_name=meta.get("college_name", ""),
                page_type=meta.get("page_type", ""),
                source_url=meta.get("source_url"),
                is_official=meta.get("is_official", True),
                freshness_bucket=freshness,
                scraped_at=scraped_at,
                relevance_score=adjusted_score,
            ))

        return chunks

    def _extract_summary_points(self, chunks: List[WebKnowledgeChunk]) -> List[str]:
        """Extract key factual points from retrieved chunks."""
        points = []
        for chunk in chunks[:5]:
            # Take the first meaningful sentence from each chunk
            text = chunk.text.strip()
            if text:
                sentences = text.split(". ")
                first_sentence = sentences[0].strip()
                if len(first_sentence) > 20:
                    college_prefix = f"[{chunk.college_name}] " if chunk.college_name else ""
                    points.append(f"{college_prefix}{first_sentence}.")
        return points

    def _check_freshness(self, chunks: List[WebKnowledgeChunk]) -> Optional[str]:
        """Check if retrieved chunks are fresh enough for recent-update queries."""
        if not chunks:
            return "No recent documents found in the knowledge base."

        fresh_chunks = [c for c in chunks if c.freshness_bucket in ("current", "recent")]
        if fresh_chunks:
            return f"Found {len(fresh_chunks)} recent document(s)."
        return "Retrieved documents may not reflect the latest updates. Please verify with official sources."

    async def _fallback_to_live_search(self, frame: RequestFrame) -> WebKnowledgeOutput:
        """Tier 2: Fallback to Live Web Search (Tavily) when Chroma is empty."""
        try:
            from app.services.web_search import web_search_fallback
            
            # Get the primary college target if it exists
            target_code = None
            if frame.college_targets and len(frame.college_targets) > 0:
                target_code = frame.college_targets[0]
                
            logger.info(f"Triggering WebSearchFallback for query: '{frame.raw_query}', target: {target_code}")
            
            # Pass user_id and session_id for credit enforcement
            fallback_result = await web_search_fallback.search(
                query=frame.raw_query,
                college_code=target_code,
                user_id=getattr(frame, 'user_id', None),
                session_id=getattr(frame, 'session_id', None),
            )

            # If Tavily was skipped due to credit exhaustion, fall through
            # to local data with an explicit hedging note for the LLM
            if fallback_result and fallback_result.skipped_reason == "credit_exhausted":
                logger.info("Tavily skipped (credit exhausted), falling to local data with hedging")
                local_result = await self._fallback_to_local_data(frame)
                local_result.freshness_note = (
                    "Note: Live web search was unavailable due to monthly usage limits. "
                    "If your answer relies on recent updates (notices, fee changes, "
                    "counseling dates), explicitly tell the user that your answer is "
                    "based on older local data and they should verify directly on "
                    "the college's official website."
                )
                return local_result
            
            if fallback_result and fallback_result.context:
                # Wrap the live search result into the standard WebKnowledgeOutput format
                now_iso = datetime.now(timezone.utc).isoformat()
                live_chunk = WebKnowledgeChunk(
                    text=fallback_result.context,
                    college_name=target_code or "Unknown",
                    page_type="live_search",
                    is_official=not fallback_result.has_unofficial,
                    freshness_bucket="current",
                    scraped_at=now_iso,
                    relevance_score=0.9
                )
                
                return WebKnowledgeOutput(
                    chunks=[live_chunk],
                    summary_points=[f"[{target_code or 'Live Search'}] Sourced directly from the web."],
                    sources_used=len(fallback_result.sources),
                    freshness_note="Data retrieved via Live Web Search."
                )
            else:
                logger.info("Live Web Search returned no results. Triggering Local Data Tier 3.")
                return await self._fallback_to_local_data(frame)
                
        except Exception as e:
            logger.error(f"Live Web Search fallback failed: {e}")
            return await self._fallback_to_local_data(frame)

    async def _fallback_to_local_data(self, frame: RequestFrame) -> WebKnowledgeOutput:
        """Fall back to the CollegeInfoService when Chroma has no web docs."""
        try:
            from app.services.college_info_service import college_info_service

            summary_points = []
            chunks = []

            for college_code in (frame.college_targets or []):
                info = college_info_service.get_college_info(college_code)
                if info:
                    summary = college_info_service.format_college_summary(
                        info.get("name", college_code)
                    )
                    if summary and not summary.startswith("Information not found"):
                        chunks.append(WebKnowledgeChunk(
                            text=summary,
                            college_name=info.get("name", college_code),
                            page_type="local_data",
                            is_official=True,
                            freshness_bucket="current",
                            relevance_score=0.7,
                        ))
                        summary_points.append(f"[{info.get('name', college_code)}] Local data available.")

                # Intent-specific data
                if frame.intent == "fee_inquiry":
                    fees = college_info_service.get_fee_structure(college_code)
                    if fees:
                        fee_text = "; ".join(
                            f"{f.get('program', 'B.Tech')}: ₹{f.get('total_first_year', 'N/A')} first year"
                            for f in fees[:3]
                        )
                        chunks.append(WebKnowledgeChunk(
                            text=fee_text,
                            college_name=college_code,
                            page_type="fees",
                            is_official=True,
                            freshness_bucket="current",
                            relevance_score=0.8,
                        ))

                elif frame.intent == "placement_inquiry":
                    placements = college_info_service.get_placement_stats(college_code)
                    if placements:
                        placement_text = "; ".join(
                            f"{p.get('branch', 'Unknown')}: Avg {p.get('avg_package_lpa', 'N/A')} LPA, "
                            f"Highest {p.get('highest_package_lpa', 'N/A')} LPA, "
                            f"{p.get('placement_percentage', 'N/A')}% placed"
                            for p in placements[:5]
                        )
                        chunks.append(WebKnowledgeChunk(
                            text=placement_text,
                            college_name=college_code,
                            page_type="placement",
                            is_official=True,
                            freshness_bucket="current",
                            relevance_score=0.8,
                        ))

                elif frame.intent == "hostel_inquiry":
                    facilities = college_info_service.get_facilities(college_code)
                    if facilities:
                        hostel_text = (
                            f"Campus: {facilities.get('campus_area', 'N/A')} acres | "
                            f"Boys Hostel: {facilities.get('hostel_boys', 'N/A')} | "
                            f"Girls Hostel: {facilities.get('hostel_girls', 'N/A')} | "
                            f"Capacity: {facilities.get('hostel_capacity', 'N/A')}"
                        )
                        chunks.append(WebKnowledgeChunk(
                            text=hostel_text,
                            college_name=college_code,
                            page_type="hostel",
                            is_official=True,
                            freshness_bucket="current",
                            relevance_score=0.75,
                        ))

                elif frame.intent == "facility_inquiry":
                    facilities = college_info_service.get_facilities(college_code)
                    if facilities:
                        fac_parts = []
                        if facilities.get("library_books"):
                            fac_parts.append(f"Library: {facilities['library_books']} books")
                        if facilities.get("computer_labs"):
                            fac_parts.append(f"Computer Labs: {facilities['computer_labs']}")
                        if facilities.get("wifi") == "Yes":
                            fac_parts.append("Wi-Fi Campus")
                        if facilities.get("gym") == "Yes":
                            fac_parts.append("Gymnasium")
                        if facilities.get("sports"):
                            fac_parts.append(f"Sports: {facilities['sports']}")
                        chunks.append(WebKnowledgeChunk(
                            text=" | ".join(fac_parts) if fac_parts else "Facilities data not available",
                            college_name=college_code,
                            page_type="facilities",
                            is_official=True,
                            freshness_bucket="current",
                            relevance_score=0.75,
                        ))

            return WebKnowledgeOutput(
                chunks=chunks,
                summary_points=summary_points,
                sources_used=len(chunks),
                freshness_note="Data from local CSV files — may not reflect latest updates." if chunks else None,
            )

        except Exception as e:
            logger.error("Fallback to local data failed: %s", e)
            return WebKnowledgeOutput(sources_used=0)


web_knowledge_agent = WebKnowledgeAgent()
