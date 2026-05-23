"""
Domain Registry — Single source of truth for trusted college domains.

Maps college codes to their official domains. Used by both the scraping
pipeline (scrape_runner.py) and the live search fallback (web_search.py).
Classifies any URL as "official", "educational", or "unofficial".
"""

import logging
from typing import List, Optional
from urllib.parse import urlparse
from app.config import settings

logger = logging.getLogger("rankroute.domain_registry")


# ── College → Domain Mapping ─────────────────────────────────────────
# Authoritative registry. Upgrade to Supabase + Redis when scaling
# beyond Assam colleges.
COLLEGE_DOMAINS = {
    "AEC": ["aec.ac.in", "www.aec.ac.in"],
    "JEC": ["jecassam.ac.in", "www.jecassam.ac.in"],
    "NITS": ["nits.ac.in", "www.nits.ac.in"],
    "TU": ["tezu.ernet.in", "www.tezu.ernet.in"],
    "GU": ["www.gauhati.ac.in", "gauhati.ac.in"],
    "GUIST": ["www.gauhati.ac.in", "gauhati.ac.in"],
    "DU": ["www.dibru.ac.in", "dibru.ac.in"],
    "DUIET": ["www.dibru.ac.in", "dibru.ac.in"],
    "JIST": ["jist.ac.in", "www.jist.ac.in"],
    "BBEC": ["bbec.ac.in", "www.bbec.ac.in"],
    "BVEC": ["bvec.ac.in", "www.bvec.ac.in"],
    "DEC": ["dec.ac.in", "www.dec.ac.in"],
    "GEC": ["gecassam.ac.in", "www.gecassam.ac.in"],
    "ASTU": ["astu.ac.in", "www.astu.ac.in"],
}

# The actual URLs to use for the weekly full scrape
START_URLS = [
    "https://www.aec.ac.in/",
    "https://www.jecassam.ac.in/",
    "https://www.nits.ac.in/",
    "https://www.tezu.ernet.in/",
    "https://jist.ac.in/",
    "https://www.bbec.ac.in/",
    "https://www.bvec.ac.in/",
    "https://www.dec.ac.in/",
    "https://www.gecassam.ac.in/",
    "https://www.astu.ac.in/",
    "https://dte.assam.gov.in/",
    "https://josaa.nic.in/",
    "https://www.dibru.ac.in/duiet",
    "https://gauhati.ac.in/academic/institutes/gauhati-university-institute-of-science-and-technology"
]

# Flat set for O(1) lookups (mirrors scrape_runner.APPROVED_DOMAINS)
ALL_OFFICIAL_DOMAINS = set()
for domains in COLLEGE_DOMAINS.values():
    ALL_OFFICIAL_DOMAINS.update(domains)

# Add exam portals
ALL_OFFICIAL_DOMAINS.update([
    "dte.assam.gov.in", "www.dte.assam.gov.in",
    "josaa.nic.in", "www.josaa.nic.in",
])


class DomainRegistry:
    """Zero-trust domain classification for search result filtering."""

    def __init__(self):
        self._official = ALL_OFFICIAL_DOMAINS
        self._suffixes = [
            s.strip() for s in settings.official_domain_suffixes.split(",")
        ]

    def get_domains(self, college_code: str) -> List[str]:
        """Return approved domains for a college code."""
        return COLLEGE_DOMAINS.get(college_code.upper(), [])

    def build_site_filter(self, college_code: Optional[str] = None) -> str:
        """Build a Tavily-compatible domain include list.

        If college_code is given, restrict to that college's domains.
        Otherwise, restrict to all official domains.
        """
        if college_code:
            domains = self.get_domains(college_code)
            if domains:
                return domains
        # Fallback: all official domains
        return list(self._official)

    def classify_url(self, url: str) -> str:
        """Classify a URL into trust tiers.

        Returns:
            "official"     — exact match in COLLEGE_DOMAINS
            "educational"  — ends with .ac.in / .edu.in / .gov.in (not in registry)
            "unofficial"   — everything else (reddit, quora, shiksha, etc.)
        """
        try:
            hostname = urlparse(url).hostname or ""
            hostname = hostname.lower()
        except Exception:
            return "unofficial"

        # Tier 1: exact match
        if hostname in self._official:
            return "official"

        # Tier 2: educational suffix
        for suffix in self._suffixes:
            if hostname.endswith(suffix):
                return "educational"

        # Tier 3: everything else
        return "unofficial"

    def is_trusted(self, url: str) -> bool:
        """Quick check: is this URL official or educational?"""
        return self.classify_url(url) in ("official", "educational")


domain_registry = DomainRegistry()
