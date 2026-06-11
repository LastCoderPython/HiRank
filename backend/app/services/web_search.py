"""
Web Search Fallback — Self-Healing Zero-Trust RAG.

When ChromaDB has no answer, this module:
1. Calls Tavily with domain-restricted queries
2. Filters results through a Zero-Trust Interceptor
3. Optionally grounds unofficial sources (consensus, date decay, contradiction)
4. Triggers self-healing: queues new official URLs into Celery for ingestion
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse

from langsmith import traceable
from app.config import settings
from app.services.domain_registry import domain_registry

logger = logging.getLogger("rankroute.web_search")


@dataclass
class SearchSource:
    """A single search result with trust metadata."""
    url: str
    title: str
    content: str
    source_type: str        # "official", "educational", "unofficial"
    trust_score: float      # 0.0 - 1.0


@dataclass
class FallbackResult:
    """Output of the fallback search pipeline."""
    context: str                              # Clean text for LLM consumption
    sources: List[SearchSource] = field(default_factory=list)
    was_fallback: bool = True
    has_unofficial: bool = False
    skipped_reason: Optional[str] = None      # 'credit_exhausted' if Tavily was skipped


class WebSearchFallback:
    """Tavily-powered live search with Zero-Trust filtering."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy-init Tavily client (avoids import errors if not installed)."""
        if self._client is None:
            if not settings.tavily_api_key:
                logger.warning("TAVILY_API_KEY not set — fallback disabled")
                return None
            from tavily import TavilyClient
            self._client = TavilyClient(api_key=settings.tavily_api_key)
        return self._client

    @traceable(run_type="tool", name="Tavily Live Search Fallback")
    async def search(
        self,
        query: str,
        college_code: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> FallbackResult:
        """Execute a domain-restricted live web search.

        Args:
            query: The student's original question.
            college_code: If known, restrict search to this college's domains.
            user_id: Authenticated user ID (for credit enforcement).
            session_id: Anonymous session ID (for credit enforcement).

        Returns:
            FallbackResult with context, sources, and metadata.
        """
        # ── Kill switch: skip entirely when fallback is disabled ───────
        if not settings.fallback_enabled:
            return FallbackResult(context="", was_fallback=True)

        # ── Credit Gate: Check usage limits before calling Tavily ─────
        try:
            from app.services.usage_service import usage_service

            if user_id:
                credit_check = usage_service.check_and_increment_auth_tavily(user_id)
            elif session_id:
                credit_check = usage_service.check_and_increment_anon_tavily(session_id)
            else:
                credit_check = None

            if credit_check and not credit_check.allowed:
                logger.info(
                    "Tavily skipped (credit exhausted): user=%s, session=%s",
                    user_id or "N/A", (session_id or "N/A")[:12],
                )
                return FallbackResult(
                    context="", was_fallback=True,
                    skipped_reason="credit_exhausted",
                )
        except Exception as e:
            logger.warning("Usage check failed (proceeding with search): %s", e)

        client = self._get_client()
        if client is None:
            return FallbackResult(context="", was_fallback=True)

        # ── Step 1: Call Tavily with domain filter ────────────────────
        include_domains = domain_registry.build_site_filter(college_code)

        try:
            response = client.search(
                query=query,
                max_results=settings.tavily_max_results,
                include_domains=include_domains,
                search_depth="advanced",
                include_raw_content=False,
            )
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return FallbackResult(context="", was_fallback=True)

        raw_results = response.get("results", [])
        if not raw_results:
            # ── Retry without domain filter (broader search) ──────────
            logger.info("No results with domain filter, retrying broader search")
            try:
                response = client.search(
                    query=query,
                    max_results=settings.tavily_max_results,
                    search_depth="basic",
                    include_raw_content=False,
                )
                raw_results = response.get("results", [])
            except Exception as e:
                logger.error(f"Tavily broad search failed: {e}")
                return FallbackResult(context="", was_fallback=True)

        # ── Step 2: Zero-Trust Interceptor ────────────────────────────
        official, educational, unofficial = self._classify_results(raw_results)

        # ── Step 3: Ground unofficial sources ─────────────────────────
        grounded_unofficial = []
        if unofficial and not official and not educational:
            # Only use unofficial if we have NO official/educational data
            grounded_unofficial = self._ground_unofficial(unofficial)

        # ── Step 4: Merge and build context ───────────────────────────
        trusted_sources = official + educational
        all_sources = trusted_sources + grounded_unofficial

        if not all_sources:
            return FallbackResult(context="", was_fallback=True)

        context = self._build_context(query, all_sources)

        # ── Step 5: Self-heal (queue new official URLs for ingestion) ─
        new_urls = [
            s.url for s in official
            if not self._is_already_ingested(s.url)
        ]
        if new_urls:
            self._trigger_self_heal(new_urls)

        return FallbackResult(
            context=context,
            sources=all_sources,
            was_fallback=True,
            has_unofficial=len(grounded_unofficial) > 0,
        )

    def _classify_results(
        self, raw_results: List[Dict]
    ) -> Tuple[List[SearchSource], List[SearchSource], List[SearchSource]]:
        """Split Tavily results into trust tiers."""
        official, educational, unofficial = [], [], []

        for r in raw_results:
            url = r.get("url", "")
            source_type = domain_registry.classify_url(url)

            source = SearchSource(
                url=url,
                title=r.get("title", ""),
                content=r.get("content", ""),
                source_type=source_type,
                trust_score=self._compute_trust(source_type),
            )

            if source_type == "official":
                official.append(source)
            elif source_type == "educational":
                educational.append(source)
            else:
                unofficial.append(source)

        logger.info(
            f"Classified: {len(official)} official, "
            f"{len(educational)} educational, {len(unofficial)} unofficial"
        )
        return official, educational, unofficial

    def _compute_trust(self, source_type: str) -> float:
        """Assign trust score by tier."""
        return {"official": 1.0, "educational": 0.8, "unofficial": 0.3}.get(
            source_type, 0.0
        )

    def _ground_unofficial(
        self, sources: List[SearchSource]
    ) -> List[SearchSource]:
        """Apply grounding pipeline to unofficial sources.

        Filters:
        1. Consensus: need 2+ sources with overlapping content
        2. Date decay: discard posts > 18 months old (heuristic)
        3. Short content filter: discard tiny snippets
        """
        if len(sources) < 2:
            # Rule of consensus: need at least 2 sources
            logger.info("Unofficial sources rejected: fewer than 2 (no consensus)")
            return []

        grounded = []
        for s in sources:
            # Filter out very short, low-quality snippets
            if len(s.content.strip()) < 50:
                continue

            # Check for date staleness (heuristic: look for year mentions)
            if self._is_stale_content(s.content):
                logger.debug(f"Discarding stale unofficial source: {s.url}")
                continue

            s.source_type = "grounded_unofficial"
            s.trust_score = 0.4
            grounded.append(s)

        if len(grounded) < 2:
            logger.info("Unofficial sources rejected after grounding filters")
            return []

        logger.info(f"Grounded {len(grounded)} unofficial sources")
        return grounded

    def _is_stale_content(self, content: str) -> bool:
        """Heuristic: reject content referencing years older than 2 years."""
        import re
        current_year = datetime.now(timezone.utc).year
        years_found = re.findall(r'\b(20\d{2})\b', content)
        if years_found:
            latest_year = max(int(y) for y in years_found)
            if current_year - latest_year > 2:
                return True
        return False

    def _build_context(
        self, query: str, sources: List[SearchSource]
    ) -> str:
        """Build LLM-ready context from search results."""
        lines = [
            "=== LIVE WEB SEARCH RESULTS ===",
            f"Query: {query}",
            "The following information was retrieved from live web search",
            "because the local database did not have this data.",
            "",
        ]

        for i, s in enumerate(sources, 1):
            trust_label = {
                "official": "✅ OFFICIAL",
                "educational": "🎓 EDUCATIONAL",
                "grounded_unofficial": "⚠️ COMMUNITY (verified by consensus)",
            }.get(s.source_type, "❓ UNKNOWN")

            lines.append(f"--- Source {i} [{trust_label}] ---")
            lines.append(f"URL: {s.url}")
            lines.append(f"Title: {s.title}")
            lines.append(s.content)
            lines.append("")

        lines.append("=== INSTRUCTIONS ===")
        lines.append(
            "Use the above data to answer the user's question. "
            "Cite the source URL when quoting specific facts. "
            "If any source is marked COMMUNITY, explicitly tell the user "
            "that this information is from student discussions, not official."
        )

        return "\n".join(lines)

    def _is_already_ingested(self, url: str) -> bool:
        """Check if URL was already scraped recently (Redis-backed).

        Uses the ingested URL set populated by upsert_service after
        each successful upsert. TTL is 7 days — URLs are naturally
        re-ingested by the weekly cron scrape.
        """
        from app.ingestion.upsert_service import is_url_recently_ingested
        return is_url_recently_ingested(url)

    def _trigger_self_heal(self, urls: List[str]) -> None:
        """Queue newly discovered official URLs for background ingestion."""
        try:
            from app.tasks.ingestion import self_heal_ingest
            for url in urls:
                self_heal_ingest.delay(url)
                logger.info(f"Self-heal queued: {url}")
        except Exception as e:
            # Non-fatal: if Celery is down, we still answer the student
            logger.warning(f"Self-heal queue failed (non-fatal): {e}")


web_search_fallback = WebSearchFallback()
