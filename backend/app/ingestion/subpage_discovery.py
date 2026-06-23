"""
RankRoute V2 — Subpage Discovery (P0)

Discovers relevant college subpages (fee, placement, hostel, admission, etc.)
from known homepage URLs using httpx and HTML link parsing.

This is the P0 fix for the 20%+ miss rate on fee/placement/hostel queries.
The weekly cron only scrapes 14 hardcoded homepage URLs — subpages are never
ingested, causing dense ChromaDB misses on structured queries.

Architecture:
  1. Fetch each known homepage via httpx
  2. Parse <a> tags to extract same-domain links
  3. Filter for page-type-relevant paths
  4. Aggregate results for downstream ingestion
"""

from __future__ import annotations

import logging
from html.parser import HTMLParser
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger("rankroute.ingestion.subpage_discovery")

# Path keywords indicating relevance to student admission queries.
# Each keyword triggers ingestion of that subpage.
RELEVANT_PATH_KEYWORDS = [
    "fee", "fees", "tuition", "scholarship",
    "placement", "recruit", "package", "salary", "ctc",
    "hostel", "accommodation", "mess", "boarding",
    "admission", "counseling", "seat", "eligibility", "apply",
    "facility", "facilities", "laboratory", "lab", "library", "infrastructure",
    "department", "branch", "program", "course", "syllabus", "curriculum",
    "notice", "circular", "announcement", "notification",
    "about", "overview", "introduction",
    "result", "academic", "exam", "examination",
    "nba", "naac", "accreditation", "ranking",
    "transport", "bus", "conveyance",
    "sport", "cultural", "extracurricular",
    "student", "cell", "club", "society",
    "iqac", "rti", "tender", "career", "recruitment",
]

EXCLUDE_PATH_KEYWORDS = [
    "login", "signin", "signup", "register", "password",
    "logout", "signout",
    "admin", "dashboard", "panel",
    "css", "js", "javascript", "image", "img", "photo", "gallery",
    "mailto:", "tel:", "javascript:",
    "facebook", "twitter", "instagram", "youtube", "linkedin",
    "assets", "uploads", "wp-content", "wp-", "files", "static",
    "icons", "fonts", "downloads", "pdf", "docx", "cdn-cgi",
    "share", "social", "tag", "category", "author", "archive",
]

MAX_SUBPAGES_PER_HOMEPAGE = 20


class LinkParser(HTMLParser):
    """Minimal HTML parser extracting all href attributes from <a> tags."""

    def __init__(self):
        super().__init__()
        self.links: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        if tag != "a":
            return
        for attr_name, attr_value in attrs:
            if attr_name == "href" and attr_value:
                self.links.append(attr_value.strip())


def _normalize_url(href: str, base_url: str) -> Optional[str]:
    """Resolve a potentially relative URL against a base URL.

    Returns None for anchors, javascript, mailto, and other non-HTTP schemes.
    """
    if href.startswith("#") or href.startswith("javascript:") or \
       href.startswith("mailto:") or href.startswith("tel:"):
        return None

    full_url = urljoin(base_url, href)

    if "#" in full_url:
        full_url = full_url[:full_url.index("#")]

    parsed = urlparse(full_url)
    if parsed.scheme not in ("http", "https"):
        return None

    return full_url


def _is_same_domain(url: str, base_url: str) -> bool:
    """Check if url is on the same domain as base_url."""
    try:
        url_host = urlparse(url).hostname or ""
        base_host = urlparse(base_url).hostname or ""
        return url_host == base_host or url_host.endswith("." + base_host)
    except Exception:
        return False


def _is_relevant_subpage(url: str, homepage_url: str) -> bool:
    """Check if a URL path is a relevant content page worth ingesting."""
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
    except Exception:
        return False

    if path in ("", "/", "/index.html", "/index.php", "/index.htm"):
        return False

    for keyword in EXCLUDE_PATH_KEYWORDS:
        if keyword in path:
            return False

    for keyword in RELEVANT_PATH_KEYWORDS:
        if keyword in path:
            return True

    return False


async def _fetch_page_async(
    url: str,
    client: httpx.AsyncClient,
) -> Optional[str]:
    """Fetch a page and return its HTML content using an existing client."""
    try:
        response = await client.get(url)
        if response.status_code == 200:
            return response.text
        logger.debug("HTTP %d for %s", response.status_code, url)
        return None
    except httpx.TimeoutException:
        logger.debug("Timeout fetching %s", url)
        return None
    except Exception as e:
        logger.debug("Failed to fetch %s: %s", url, e)
        return None


def _parse_links(html: str, base_url: str) -> List[str]:
    """Extract and normalize all links from HTML."""
    parser = LinkParser()
    parser.feed(html)

    normalized: Set[str] = set()
    for href in parser.links:
        url = _normalize_url(href, base_url)
        if url:
            normalized.add(url)

    return list(normalized)


async def discover_subpages(
    start_urls: List[str],
    max_per_homepage: int = MAX_SUBPAGES_PER_HOMEPAGE,
) -> Dict[str, List[str]]:
    """Discover relevant subpages from a list of homepage URLs.

    For each homepage URL:
      1. Fetch the homepage HTML
      2. Parse all <a> links
      3. Filter for same-domain, relevant subpage links
      4. Deduplicate and limit

    Returns:
        Dict mapping each homepage URL to its list of discovered subpage URLs.
    """
    headers = {
        "User-Agent": "Aariv/2.0 (Educational Counseling Bot; +https://aariv.in)",
        "Accept": "text/html,application/xhtml+xml",
    }

    result: Dict[str, List[str]] = {}

    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers=headers,
    ) as client:
        for homepage_url in start_urls:
            logger.info("Discovering subpages from: %s", homepage_url)

            html = await _fetch_page_async(homepage_url, client)
            if not html:
                logger.warning("Could not fetch homepage: %s", homepage_url)
                result[homepage_url] = []
                continue

            all_links = _parse_links(html, homepage_url)
            logger.debug(
                "Found %d total links on %s", len(all_links), homepage_url,
            )

            subpages: List[str] = []
            seen: Set[str] = set()

            for link in all_links:
                if link in seen:
                    continue
                seen.add(link)

                if not _is_same_domain(link, homepage_url):
                    continue
                if not _is_relevant_subpage(link, homepage_url):
                    continue

                subpages.append(link)
                if len(subpages) >= max_per_homepage:
                    break

            result[homepage_url] = subpages
            logger.info(
                "Discovered %d relevant subpages from %s",
                len(subpages), homepage_url,
            )

    return result


def collect_subpage_urls(
    start_urls: List[str],
    max_per_homepage: int = MAX_SUBPAGES_PER_HOMEPAGE,
) -> Dict[str, List[str]]:
    """Synchronous wrapper for discover_subpages.

    Creates a new event loop for use in Celery tasks.
    """
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            discover_subpages(start_urls, max_per_homepage),
        )
    finally:
        loop.close()
