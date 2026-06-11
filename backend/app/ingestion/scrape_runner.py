"""
RankRoute V2 — Scrape Runner

Fetches approved college pages via HTTP. Only allows whitelisted
official college domains and government counseling sources.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional

import httpx

logger = logging.getLogger("rankroute.ingestion.scraper")


from app.services.domain_registry import ALL_OFFICIAL_DOMAINS as APPROVED_DOMAINS

@dataclass
class ScrapeResult:
    """Result of scraping a single URL."""
    url: str
    success: bool
    status_code: int = 0
    content: str = ""
    content_hash: str = ""
    domain: str = ""
    fetched_at: str = ""
    error: Optional[str] = None


def is_approved_url(url: str) -> bool:
    """Check if a URL belongs to an approved domain."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        return domain in APPROVED_DOMAINS
    except Exception:
        return False


async def fetch_page(url: str, timeout: float = 15.0) -> ScrapeResult:
    """Fetch a single approved page."""
    if not is_approved_url(url):
        return ScrapeResult(
            url=url,
            success=False,
            error=f"Domain not in approved list. Only official college and counseling domains are allowed.",
        )

    try:
        from urllib.parse import urlparse
        domain = urlparse(url).hostname or ""

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "RankRoute/2.0 (Educational Counseling Bot; +https://rankroute.in)",
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as client:
            response = await client.get(url)

            content = response.text
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

            return ScrapeResult(
                url=url,
                success=response.status_code == 200,
                status_code=response.status_code,
                content=content,
                content_hash=content_hash,
                domain=domain,
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )

    except httpx.TimeoutException:
        return ScrapeResult(url=url, success=False, error="Request timed out")
    except Exception as e:
        logger.error("Scrape failed for %s: %s", url, e)
        return ScrapeResult(url=url, success=False, error=str(e))


async def fetch_pages(urls: List[str]) -> List[ScrapeResult]:
    """Fetch multiple approved pages."""
    import asyncio
    results = await asyncio.gather(
        *[fetch_page(url) for url in urls],
        return_exceptions=False,
    )
    return list(results)
