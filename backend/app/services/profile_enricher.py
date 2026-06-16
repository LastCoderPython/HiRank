"""
Passive profile enrichment from conversation data.

After each user message, this service runs a lightweight regex +
keyword extraction pass. Any discovered attributes (exam, rank,
category, percentile) can be used to backfill NULL fields in the
user's profile — enriching data collection without any extra friction.

This is fire-and-forget: called from a Celery task, never blocks
the SSE stream.
"""

import re
from typing import Dict, Any


EXAM_PATTERNS = {
    "JEE_MAIN": r"\bjee\s*mains?\b",
    "JEE_ADV": r"\bjee\s*adv(?:anced)?\b",
    "NEET": r"\bneet\b",
    "CEE": r"\bcee\b|\bassam\s*cee\b",
}

RANK_PATTERN = r"\b(\d{1,6})\s*(?:rank|air)\b"
PERCENTILE_PATTERN = r"\b(100(?:\.0{1,2})?|\d{1,2}(?:\.\d{1,2})?)\s*(?:percentile|%ile|%|pct)\b"

CATEGORY_PATTERNS = {
    "OBC": r"\bobc(?:[-\s]ncl)?\b",
    "SC": r"\bsc\b(?!\s*ience)",
    "ST": r"\bst\b",
    "EWS": r"\bews\b",
    "General": r"\bgeneral\b|\bopen(?:\s+category)?\b",
}


class ProfileEnricher:
    """Extract structured admissions data from raw user messages."""

    def extract(self, message: str) -> Dict[str, Any]:
        """
        Returns a dict of discovered profile fields.
        Only non-None values are returned.

        Example:
            >>> enricher.extract("I got 94.5 percentile in JEE Main, OBC category")
            {'exam': 'JEE_MAIN', 'percentile': 94.5, 'category': 'OBC'}
        """
        updates: Dict[str, Any] = {}
        m = message.lower()

        # Exam detection
        for key, pattern in EXAM_PATTERNS.items():
            if re.search(pattern, m):
                updates["exam"] = key
                break

        # Rank extraction (e.g. "4521 rank", "AIR 12345", "rank 4521")
        rank_match = re.search(r"\b(?:rank|air)\s*(\d{1,6})\b|\b(\d{1,6})\s*(?:rank|air)\b", m)
        if rank_match:
            rank_str = rank_match.group(1) or rank_match.group(2)
            updates["rank"] = int(rank_str)

        # Percentile extraction (e.g. "94.5 percentile", "percentile 97.2")
        pct_match = re.search(r"\b(?:percentile|%ile|pct)\s*(100(?:\.0{1,2})?|\d{1,2}(?:\.\d{1,2})?)|\b(100(?:\.0{1,2})?|\d{1,2}(?:\.\d{1,2})?)\s*(?:percentile|%ile|%|pct)\b", m)
        if pct_match:
            pct_str = pct_match.group(1) or pct_match.group(2)
            updates["percentile"] = float(pct_str)

        # Category extraction
        for cat_key, pattern in CATEGORY_PATTERNS.items():
            if re.search(pattern, m):
                updates["category"] = cat_key
                break

        return updates


profile_enricher = ProfileEnricher()
