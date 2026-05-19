"""
RankRoute V2 — Fallback Policy

Defines what happens when the system is uncertain:
  - Ask a clarifying question if essential parameters are missing.
  - Downgrade to structured-only output if web evidence is weak.
  - Say data is insufficient rather than hallucinating.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class FallbackAction(str, Enum):
    ASK_CLARIFICATION = "ask_clarification"
    DOWNGRADE_TO_STRUCTURED = "downgrade_to_structured"
    ADMIT_INSUFFICIENT_DATA = "admit_insufficient_data"
    NONE = "none"


@dataclass
class FallbackDecision:
    action: FallbackAction
    clarification_question: Optional[str] = None
    reason: Optional[str] = None


# Templates for common clarifying questions
_CLARIFICATION_TEMPLATES = {
    "rank": "Could you share your rank so I can predict your college options?",
    "exam": "Which exam did you appear for — CEE or JEE Mains?",
    "category": "What is your reservation category (General, OBC, SC, ST, EWS)?",
    "college": "Which college(s) are you interested in?",
}


class FallbackPolicy:
    """Decides the fallback action when evidence is weak or missing."""

    def decide(
        self,
        missing_fields: Optional[List[str]] = None,
        web_evidence_weak: bool = False,
        intent: Optional[str] = None,
    ) -> FallbackDecision:
        # Priority 1: essential fields missing → ask clarification
        if missing_fields:
            questions = [
                _CLARIFICATION_TEMPLATES.get(f, f"Could you clarify your {f}?")
                for f in missing_fields
            ]
            return FallbackDecision(
                action=FallbackAction.ASK_CLARIFICATION,
                clarification_question=" ".join(questions),
            )

        # Priority 2: web evidence weak → downgrade to structured only
        if web_evidence_weak:
            return FallbackDecision(
                action=FallbackAction.DOWNGRADE_TO_STRUCTURED,
                reason="Descriptive web evidence was weak or conflicting; "
                       "falling back to structured cutoff data only.",
            )

        # Priority 3: general uncertainty
        if intent and intent in ("general_inquiry",):
            return FallbackDecision(
                action=FallbackAction.ADMIT_INSUFFICIENT_DATA,
                reason="Not enough data to provide a confident answer.",
            )

        return FallbackDecision(action=FallbackAction.NONE)


fallback_policy = FallbackPolicy()
