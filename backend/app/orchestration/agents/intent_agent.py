"""
RankRoute V2 — Intent & Parameters Agent

Extracts the structured RequestFrame from natural language queries.
Uses rules first, and falls back to a small model only when the query
is genuinely ambiguous.

Responsibilities:
  - Parse structured constraints from natural language.
  - Detect query class: prediction, descriptive, comparison, recent-update, or ambiguous.
  - Return structured JSON (IntentAgentOutput), not prose.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from app.orchestration.types import IntentAgentOutput, RequestFrame

logger = logging.getLogger("rankroute.agents.intent")


# ── College name → code mapping ──────────────────────────────────────
COLLEGE_CODES = {
    "aec": "AEC", "assam engineering college": "AEC", "assam engineering": "AEC",
    "jec": "JEC", "jorhat engineering college": "JEC", "jorhat engineering": "JEC",
    "jist": "JIST", "jorhat institute": "JIST",
    "bbec": "BBEC", "bineswar brahma": "BBEC",
    "bvec": "BVEC", "barak valley": "BVEC",
    "dec": "DEC", "dhemaji": "DEC", "dhemaji engineering": "DEC",
    "gec": "GEC", "golaghat": "GEC", "golaghat engineering": "GEC",
    "nits": "NITS", "nit silchar": "NITS", "nit-silchar": "NITS",
    "tezu": "TU", "tezpur university": "TU", "tezpur": "TU",
    "duiet": "DUIET", "dibrugarh university": "DU", "dibrugarh": "DU",
    "gust": "GUST", "gauhati university": "GU", "gauhati": "GU",
}

# ── Keywords that indicate descriptive / web-context queries ─────────
WEB_CONTEXT_KEYWORDS = [
    "fee", "fees", "fee structure", "placement", "package", "salary",
    "hostel", "campus", "facility", "facilities", "library", "sports",
    "about", "details", "info", "information", "admission process",
    "how to apply", "documents", "scholarship", "notice", "update",
    "infrastructure", "lab", "workshop", "canteen", "mess",
]

# ── Intent patterns ──────────────────────────────────────────────────
INTENT_PATTERNS = {
    r"which\s*college|college\s*(?:can|will|could)\s*i\s*get|chance|predict": "college_prediction",
    r"cutoff|cut[\s-]?off|closing\s*rank|opening\s*rank": "cutoff_inquiry",
    r"compare|difference|vs|better|between": "comparison",
    r"placement|package|salary|recruit|company": "placement_inquiry",
    r"fee|fees|cost|tuition|expense": "fee_inquiry",
    r"hostel|accommodation|room|mess": "hostel_inquiry",
    r"facility|facilities|infrastructure|lab|library|sport": "facility_inquiry",
    r"notice|update|latest|recent|new|announcement": "recent_update",
    r"branch|course|program|stream": "branch_inquiry",
    r"seat\s*matrix|total\s*seats|intake": "seat_inquiry",
}

# ── Rank extraction patterns ─────────────────────────────────────────
RANK_PATTERNS = [
    r"rank\s*(?:is|=|:)?\s*(\d+)",
    r"(\d+)\s*rank",
    r"got\s*(\d+)\s*(?:in|rank)",
    r"my\s*rank\s*(?:is|=|:)?\s*(\d+)",
    r"scored\s*(\d+)",
]

# ── Category patterns ────────────────────────────────────────────────
CATEGORY_PATTERNS = {
    r"\b(general|gen|gm)\b": "General",
    r"\b(obc|other backward)\b": "OBC",
    r"\bsc\b|\bscheduled caste\b": "SC",
    r"\bst\b|\bscheduled tribe\b": "ST",
    r"\b(sth)\b": "STH",
    r"\b(stp)\b": "STP",
    r"\b(ews|economically weaker)\b": "EWS",
}

# ── Exam patterns ────────────────────────────────────────────────────
EXAM_PATTERNS = {
    r"\bjee\s*mains?\b|\bjee\s*main\b|\bjee\b(?!\s*advanced)": "JEE",
    r"\bjee\s*advanced?\b": "JEE Advanced",
    r"\bcee\b|assam\s*cee|assam\s*combined": "CEE",
}

# ── Branch patterns ──────────────────────────────────────────────────
BRANCH_KEYWORDS = {
    "computer science": "Computer Science", "cs": "Computer Science", "cse": "Computer Science",
    "electronics": "Electronics", "ece": "Electronics and Communication",
    "electrical": "Electrical", "mechanical": "Mechanical", "civil": "Civil",
    "information technology": "Information Technology", "it": "Information Technology",
    "chemical": "Chemical", "biotechnology": "Biotechnology",
    "instrumentation": "Instrumentation", "petroleum": "Petroleum",
    "food engineering": "Food Engineering", "power electronics": "Power Electronics",
    "industrial": "Industrial & Production",
}

# ── Greeting patterns ────────────────────────────────────────────────
GREETINGS = ["hi", "hello", "hey", "good morning", "good evening", "good afternoon", "hola", "howdy", "namaste"]


class IntentAgent:
    """
    Extracts structured query parameters using rules-first approach.

    Uses regex and keyword matching for most queries. Will fall back
    to a small LLM model only for genuinely ambiguous queries
    (not yet implemented — rules handle the majority of cases).
    """

    async def run(self, query: str) -> IntentAgentOutput:
        """Parse a raw query into structured IntentAgentOutput."""
        query_lower = query.lower().strip()

        # ── Greeting detection ─────────────────────────────────────
        if self._is_greeting(query_lower):
            return IntentAgentOutput(intent="greeting", confidence=1.0)

        # ── Extract structured fields ──────────────────────────────
        intent = self._extract_intent(query_lower)
        exam = self._extract_exam(query_lower)
        rank = self._extract_rank(query_lower, exam)
        category = self._extract_category(query_lower)
        branch = self._extract_branch(query_lower)
        college_targets = self._extract_college_targets(query_lower)
        needs_web = self._needs_web_context(query_lower, intent)

        # ── Confidence estimation ──────────────────────────────────
        confidence = 1.0
        if intent == "general_inquiry" and not rank and not college_targets:
            confidence = 0.5  # ambiguous
        elif rank and exam:
            confidence = 0.95  # very clear prediction query

        return IntentAgentOutput(
            intent=intent,
            exam=exam,
            rank=rank,
            category=category or "General",
            branch_preference=branch,
            college_targets=college_targets,
            needs_web_context=needs_web,
            confidence=confidence,
        )

    def to_request_frame(self, output: IntentAgentOutput, raw_query: str) -> RequestFrame:
        """Convert IntentAgentOutput to a RequestFrame for the orchestrator."""
        return RequestFrame(
            intent=output.intent,
            exam=output.exam,
            rank=output.rank,
            category=output.category,
            branch_preference=output.branch_preference,
            college_targets=output.college_targets,
            needs_web_context=output.needs_web_context,
            confidence=output.confidence,
            raw_query=raw_query,
        )

    # ── Private extraction methods ────────────────────────────────────

    def _is_greeting(self, query_lower: str) -> bool:
        words = query_lower.split()
        if len(words) >= 5:
            return False
        return any(query_lower.startswith(g) for g in GREETINGS)

    def _extract_intent(self, query_lower: str) -> str:
        for pattern, intent in INTENT_PATTERNS.items():
            if re.search(pattern, query_lower):
                return intent
        # Default inference
        if any(w in query_lower for w in ["rank", "percentile", "score"]):
            return "college_prediction"
        return "general_inquiry"

    def _extract_exam(self, query_lower: str) -> Optional[str]:
        for pattern, exam in EXAM_PATTERNS.items():
            if re.search(pattern, query_lower):
                return exam
        return None

    def _extract_rank(self, query_lower: str, exam: Optional[str] = None) -> Optional[int]:
        for pattern in RANK_PATTERNS:
            match = re.search(pattern, query_lower)
            if match:
                return int(match.group(1))

        # Try to find standalone numbers that look like ranks
        numbers = re.findall(r'\b(\d{2,6})\b', query_lower)
        if numbers:
            num = int(numbers[0])
            if 50 <= num <= 200000:
                if "rank" in query_lower or "score" in query_lower:
                    return num
        return None

    def _extract_category(self, query_lower: str) -> Optional[str]:
        for pattern, category in CATEGORY_PATTERNS.items():
            if re.search(pattern, query_lower):
                return category
        return None

    def _extract_branch(self, query_lower: str) -> Optional[str]:
        for keyword, branch in BRANCH_KEYWORDS.items():
            if keyword in query_lower:
                return branch
        return None

    def _extract_college_targets(self, query_lower: str) -> List[str]:
        targets = []
        for keyword, code in COLLEGE_CODES.items():
            if keyword in query_lower and code not in targets:
                targets.append(code)
        return targets

    def _needs_web_context(self, query_lower: str, intent: str) -> bool:
        """Detect if the query requires descriptive web content."""
        if intent in ("fee_inquiry", "placement_inquiry", "hostel_inquiry",
                       "facility_inquiry", "college_info", "recent_update"):
            return True
        return any(kw in query_lower for kw in WEB_CONTEXT_KEYWORDS)


intent_agent = IntentAgent()
