"""
RankRoute V2 — Page Cleaner

Extracts main content from scraped HTML pages using Trafilatura.
Classifies page type based on content analysis.
Falls back to regex stripping if Trafilatura returns nothing.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass

import trafilatura

logger = logging.getLogger("rankroute.ingestion.cleaner")


@dataclass
class CleanedPage:
    """Cleaned and classified page content."""
    text: str
    title: str = ""
    page_type: str = "general"
    word_count: int = 0


# ── Page type detection patterns ──────────────────────────────────────
PAGE_TYPE_PATTERNS = {
    "placement": r"placement|recruit|package|salary|ctc|campus\s*drive|hired|offer",
    "fees": r"fee\s*structure|tuition|hostel\s*fee|semester\s*fee|fee\s*detail",
    "hostel": r"hostel|accommodation|mess\s*facility|room\s*type|boarding",
    "facilities": r"facilit|infrastructure|laborator|library|computer\s*lab|workshop|sport",
    "admission_notice": r"admission\s*notice|counseling\s*schedule|seat\s*allot|round\s*\d",
    "branch_info": r"department|branch|program|curriculum|syllabus|course\s*structure",
    "notice": r"notice|circular|announcement|important\s*date",
    "about": r"about\s*(?:us|the\s*college)|history|vision|mission|established",
    "seat_matrix": r"seat\s*matrix|total\s*intake|sanctioned\s*seat",
}

# ── Boilerplate removal patterns (fallback only) ─────────────────────
BOILERPLATE_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"<style[^>]*>.*?</style>",
    r"<nav[^>]*>.*?</nav>",
    r"<footer[^>]*>.*?</footer>",
    r"<header[^>]*>.*?</header>",
    r"<!--.*?-->",
    r"<iframe[^>]*>.*?</iframe>",
    r"cookie\s*(?:policy|consent|notice)[^.]*\.",
    r"©\s*\d{4}[^.]*\.",
    r"all\s*rights\s*reserved[^.]*\.",
    r"powered\s*by[^.]*\.",
    r"terms\s*(?:of\s*use|and\s*conditions)[^.]*\.",
    r"privacy\s*policy[^.]*\.",
]


def clean_html(raw_html: str) -> str:
    """Extract main content from raw HTML using Trafilatura.

    Falls back to regex stripping if Trafilatura returns nothing
    (e.g., for very minimal pages).
    """
    # Trafilatura: purpose-built for main content extraction
    extracted = trafilatura.extract(
        raw_html,
        include_comments=False,
        include_tables=True,       # college sites often have tabular data
        no_fallback=False,          # use fallback extractors if primary fails
        favor_recall=True,          # prefer more content over precision
    )

    if extracted and len(extracted.strip()) > 50:
        return extracted.strip()

    # Fallback: basic regex cleaning for very simple pages
    return _regex_fallback_clean(raw_html)


def _regex_fallback_clean(raw_html: str) -> str:
    """Legacy regex-based cleaning as fallback for minimal pages."""
    text = raw_html

    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Decode HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&rsquo;", "'")
    text = text.replace("&lsquo;", "'")
    text = text.replace("&rdquo;", '"')
    text = text.replace("&ldquo;", '"')
    text = text.replace("&mdash;", "—")
    text = text.replace("&ndash;", "–")

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def extract_title(raw_html: str) -> str:
    """Extract the page title from HTML."""
    # Try Trafilatura metadata first
    metadata = trafilatura.extract_metadata(raw_html)
    if metadata and metadata.title:
        return metadata.title.strip()

    # Fallback to regex
    match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    if match:
        return _regex_fallback_clean(match.group(1)).strip()
    return ""


def classify_page_type(text: str) -> str:
    """Classify the page type based on content keywords."""
    text_lower = text.lower()
    scores = {}
    for page_type, pattern in PAGE_TYPE_PATTERNS.items():
        matches = len(re.findall(pattern, text_lower))
        if matches > 0:
            scores[page_type] = matches

    if scores:
        return max(scores, key=scores.get)
    return "general"


def clean_page(raw_html: str) -> CleanedPage:
    """Full pipeline: clean HTML, extract title, classify page type."""
    title = extract_title(raw_html)
    text = clean_html(raw_html)
    page_type = classify_page_type(text)
    word_count = len(text.split())

    # Skip pages with very little content
    if word_count < 20:
        text = ""

    return CleanedPage(
        text=text,
        title=title,
        page_type=page_type,
        word_count=word_count,
    )
