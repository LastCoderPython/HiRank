"""
RankRoute V2 — Budget Policy

Enforces limits on model calls, context size, and retrieval breadth
per request. Codifies cost controls as code rather than convention.

Tier defaults:
  Tier 0 (simple): max 1 parser call + 1 synthesis call
  Tier 1 (moderate): max 2 specialist calls + 1 synthesis call
  Tier 2 (complex): max 3 specialist branches + 1 synthesis call
  Retrieval cap: max 5 chunks per source before summarization
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.orchestration.routing_policy import RouteCategory


@dataclass(frozen=True)
class BudgetLimits:
    """Immutable budget constraints for a single request."""
    max_specialist_calls: int
    max_synthesis_calls: int
    max_retrieval_chunks: int
    max_context_tokens: int  # approximate hard limit for prompt assembly


# Pre-defined tier budgets
_TIER_BUDGETS = {
    "prediction_simple":            BudgetLimits(max_specialist_calls=1, max_synthesis_calls=1, max_retrieval_chunks=5, max_context_tokens=2048),
    "descriptive_simple":           BudgetLimits(max_specialist_calls=1, max_synthesis_calls=1, max_retrieval_chunks=5, max_context_tokens=2048),
    "mixed_comparison":             BudgetLimits(max_specialist_calls=3, max_synthesis_calls=1, max_retrieval_chunks=5, max_context_tokens=3072),
    "recent_update":                BudgetLimits(max_specialist_calls=2, max_synthesis_calls=1, max_retrieval_chunks=5, max_context_tokens=2048),
    "ambiguous_needs_clarification": BudgetLimits(max_specialist_calls=1, max_synthesis_calls=1, max_retrieval_chunks=0, max_context_tokens=1024),
    "greeting":                     BudgetLimits(max_specialist_calls=0, max_synthesis_calls=0, max_retrieval_chunks=0, max_context_tokens=256),
    "off_topic":                    BudgetLimits(max_specialist_calls=0, max_synthesis_calls=0, max_retrieval_chunks=0, max_context_tokens=256),
}


class BudgetPolicy:
    """Assigns and enforces request-level budgets."""

    def get_budget(self, route: "RouteCategory") -> BudgetLimits:
        """Return the budget limits for a given route category."""
        return _TIER_BUDGETS.get(route.value, _TIER_BUDGETS["ambiguous_needs_clarification"])

    def is_within_budget(
        self,
        route: "RouteCategory",
        specialist_calls_made: int,
        synthesis_calls_made: int,
        chunks_retrieved: int,
    ) -> bool:
        """Check whether current usage is within the allotted budget."""
        budget = self.get_budget(route)
        return (
            specialist_calls_made <= budget.max_specialist_calls
            and synthesis_calls_made <= budget.max_synthesis_calls
            and chunks_retrieved <= budget.max_retrieval_chunks
        )


budget_policy = BudgetPolicy()
